"""Deterministic enrichment orchestrator with tool-calling.

The orchestration stays agentic, but runtime data now enters through the
NoteDocument bridge so execution payload adapters stay localized to the service
boundary instead of leaking through the main node flow.
"""

import json
from copy import deepcopy
from langchain_core.tools import tool
from app.core.agent_runtime import create_controlled_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.note_document import build_note_document_from_state
from app.services.location_enricher import enrich_location_blocks
from app.services.search_enricher import enrich_product_document
from app.services.image_generator import auto_generate_images


def _merge_note_documents(base: dict, patch: dict) -> dict:
    merged = deepcopy(base or {})
    patch_doc = deepcopy(patch or {})

    if patch_doc.get("document_meta"):
        merged["document_meta"] = {**(merged.get("document_meta") or {}), **patch_doc.get("document_meta", {})}
    if patch_doc.get("theme"):
        merged["theme"] = {**(merged.get("theme") or {}), **patch_doc.get("theme", {})}
    if patch_doc.get("planner"):
        merged["planner"] = patch_doc.get("planner")
    if patch_doc.get("ui_state"):
        merged["ui_state"] = {**(merged.get("ui_state") or {}), **patch_doc.get("ui_state", {})}
    if patch_doc.get("provenance"):
        merged["provenance"] = {**(merged.get("provenance") or {}), **patch_doc.get("provenance", {})}

    base_blocks = {str(block.get("id") or ""): deepcopy(block) for block in (merged.get("blocks") or []) if isinstance(block, dict)}
    ordered_ids = [str(block.get("id") or "") for block in (merged.get("blocks") or []) if isinstance(block, dict) and block.get("id")]

    def _prefer_non_empty(existing: dict, incoming: dict) -> dict:
        merged_payload = deepcopy(existing or {})
        for key, value in (incoming or {}).items():
            if value in (None, "", [], {}):
                continue
            merged_payload[key] = value
        return merged_payload

    for block in patch_doc.get("blocks") or []:
        if not isinstance(block, dict) or not block.get("id"):
            continue
        block_id = str(block.get("id"))
        existing = base_blocks.get(block_id, {})
        base_blocks[block_id] = {
            **existing,
            **block,
            "props": _prefer_non_empty(existing.get("props") or {}, block.get("props") or {}),
            "style": _prefer_non_empty(existing.get("style") or {}, block.get("style") or {}),
        }
        if block_id not in ordered_ids:
            ordered_ids.append(block_id)
    merged["blocks"] = [base_blocks[block_id] for block_id in ordered_ids if block_id in base_blocks]

    if patch_doc.get("assets"):
        merged["assets"] = deepcopy(patch_doc.get("assets") or [])
    if patch_doc.get("fact_bindings"):
        merged["fact_bindings"] = deepcopy(patch_doc.get("fact_bindings") or [])
    return merged

# 初始化底层 LLM 引擎
_tool_llm = create_llm(
    model=settings.LLM_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0.1
)

async def enrichment_node_v2(state: UIProjectState) -> dict:
    """
    【架构升级：闭包 Tool Calling 引擎】
    消除 Token 爆炸风险，保证数据深度合并的绝对安全。
    """
    note_document = build_note_document_from_state(state)
    active_archetype = state.get("active_archetype", "general")
    image_assets = state.get("image_assets", []) or list(note_document.get("assets") or [])
    
    if not note_document.get("blocks"):
        return {}

    # === 🛡️ 核心优化 1：使用闭包定义工具，彻底切断大模型传参导致的幻觉 ===
    @tool
    async def enrich_product_tool() -> str:
        """当存在商品卡片、参数列表时，调用此工具进行参数核实和事实增强。无参数。"""
        try:
            enriched = await enrich_product_document(note_document, active_archetype)
            return json.dumps({"source": "product", "note_document": enriched}, ensure_ascii=False)
        except Exception as e:
            return f"Error: product_tool 失败 - {str(e)}"

    @tool
    async def enrich_location_tool() -> str:
        """当页面存在位置打卡组件时，调用此工具补全经纬度。无参数。"""
        try:
            enriched = await enrich_location_blocks(note_document)
            return json.dumps({"source": "location", "note_document": enriched}, ensure_ascii=False)
        except Exception as e:
            return f"Error: location_tool 失败 - {str(e)}"

    @tool
    async def generate_images_tool() -> str:
        """当组件缺少图片（URL为空）时，调用此工具进行搜图/生图并提取配色。无参数。"""
        try:
            enriched_note_document, new_assets = await auto_generate_images(note_document, active_archetype)
            return json.dumps({
                "source": "images", 
                "note_document": enriched_note_document, 
                "new_assets": new_assets
            }, ensure_ascii=False)
        except Exception as e:
            return f"Error: generate_images_tool 失败 - {str(e)}"

    tools = [enrich_product_tool, enrich_location_tool, generate_images_tool]
    system_prompt = """你是一个高级数据增强管家。
你的职责是分析当前页面组件大纲，并按需调用工具完成商品事实增强、地理增强或配图增强。

【工具策略】
- 有商品/参数类组件 -> 调用 enrich_product_tool
- 有位置地图类组件 -> 调用 enrich_location_tool
- 需要视觉配图 -> 调用 generate_images_tool

【最高指令】
1. 工具会自动读取后台数据，你无需传递任何参数。
2. 只调用必要工具，避免重复增强。
3. 调用完必要工具后，请直接回复“增强完毕”。绝对不要在回复中输出任何 JSON 数据！"""
    enrichment_react_agent = create_controlled_agent(
        model=_tool_llm,
        tools=tools,
        name="enrichment_agent",
        prompt=system_prompt,
    )

    # === 🛡️ 核心优化 2：极简摘要 Prompt，节约 Token ===
    # 只提取组件 ID 和类型给大模型，不给具体内容，防止它迷失在海量数据中
    component_outline = {
        str(block.get("id") or ""): str(block.get("type") or "Unknown")
        for block in (note_document.get("blocks") or [])
        if isinstance(block, dict)
    }
    
    user_prompt = f"""当前原型: {active_archetype}
当前页面的组件大纲如下:
{json.dumps(component_outline, ensure_ascii=False)}

请分析以上组件树，并按需调用工具完成增强。"""

    print(f"🧠 [Tool Calling 引擎] 启动增强管家，分析大纲: {component_outline}")
    result = await enrichment_react_agent.ainvoke({"messages": [("user", user_prompt)]})
    
    # === 🛡️ 核心优化 3：唯一事实来源解析 (Single Source of Truth) ===
    final_note_document = deepcopy(note_document)
    final_new_assets = image_assets.copy() # 保护原有资产不丢失
    
    for msg in result["messages"]:
        if msg.type == "tool":
            # 捕获报错，打破静默吞噬
            if msg.content.startswith("Error:"):
                print(f"❌ [工具执行异常] {msg.content}")
                continue
                
            try:
                tool_res = json.loads(msg.content)
                print(f"🎯 [工具执行成功] 来源: {tool_res.get('source')}")
                
                # 精准提取并合并
                if "note_document" in tool_res:
                    final_note_document = _merge_note_documents(final_note_document, tool_res["note_document"])
                if "new_assets" in tool_res:
                    final_new_assets.extend(tool_res["new_assets"])
                    
            except json.JSONDecodeError:
                print(f"⚠️ [解析警告] 工具返回非标准 JSON: {msg.content[:100]}...")
            except Exception as e:
                print(f"⚠️ [未知错误] 合并过程发生错误: {e}")

    print(f"✅ [Tool Calling 引擎] 数据增强与合并安全闭环。")
    
    return {
        "note_document": final_note_document,
        "image_assets": final_new_assets,
        "agent_backends": {"enrichment_agent": enrichment_react_agent.backend},
    }
