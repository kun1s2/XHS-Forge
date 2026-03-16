import json
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState, merge_dsl
from app.core.config import settings
from app.services.location_enricher import enrich_page_dsl
from app.services.search_enricher import enrich_product_data
from app.services.image_generator import auto_generate_images

# ✨ 现代化：将之前硬编码的增强逻辑封装为标准 Tool
@tool
async def enrich_product_tool(data_dsl_str: str, archetype: str) -> str:
    """当需要对商品参数、价格进行联网核实和事实增强时调用此工具。传入 JSON 字符串格式的 data_dsl。"""
    try:
        data_dsl = json.loads(data_dsl_str)
        enriched = await enrich_product_data(data_dsl, archetype)
        return json.dumps(enriched, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"

@tool
async def enrich_location_tool(data_dsl_str: str) -> str:
    """当页面中包含 LocationBlock 组件，且需要补全经纬度坐标时调用此工具。"""
    try:
        data_dsl = json.loads(data_dsl_str)
        enriched = await enrich_page_dsl(data_dsl)
        return json.dumps(enriched, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"

@tool
async def generate_images_tool(data_dsl_str: str, archetype: str) -> str:
    """当页面中的 CoverSwiper 或 ProductCard 等组件缺少真实图片时，调用此工具生成图片并提取视觉配色。"""
    try:
        data_dsl = json.loads(data_dsl_str)
        enriched_dsl, new_assets = await auto_generate_images(data_dsl, archetype)
        # 注意：这里我们返回一个特殊的结构，以便后续解析
        return json.dumps({"data_dsl": enriched_dsl, "new_assets": new_assets}, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"

# 初始化工具调用的 LLM (已对齐 ChatOpenAI)
_tool_llm = create_llm(
    model=settings.LLM_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0.1
)

# 使用 langgraph.prebuilt 快速构建一个 ReAct Agent
tools = [enrich_product_tool, enrich_location_tool, generate_images_tool]
enrichment_react_agent = create_react_agent(_tool_llm, tools)

async def enrichment_node_v2(state: UIProjectState) -> dict:
    """
    【最新技术栈：Tool Calling 代理引擎】
    让大模型自主决定增强时机，实现“状态感知”的智能补全。
    """
    data_dsl = state.get("data_dsl", {})
    active_archetype = state.get("active_archetype", "general")
    image_assets = state.get("image_assets", [])
    
    if not data_dsl:
        return {}

    prompt = f"""你是一个前端数据增强架构师。
当前页面的原型类别是: {active_archetype}
当前的页面数据 (data_dsl) 如下:
{json.dumps(data_dsl, ensure_ascii=False)}

请分析以上数据，并使用提供的工具对其进行增强。
- 如果有商品卡片或参数卡片，请调用 enrich_product_tool。
- 如果有位置打卡且缺少坐标，请调用 enrich_location_tool。
- 如果有组件缺少图片（URL为空），请调用 generate_images_tool。

你可以并行或串行调用工具。所有需要的增强完成后，请直接输出最终增强后的 JSON 数据，不要带有 Markdown 代码块。"""

    print(f"🧠 [Tool Calling 引擎] 启动增强管家，正在执行自主增强...")
    
    # 运行内部 Agent
    result = await enrichment_react_agent.ainvoke({"messages": [("user", prompt)]})
    
    # === ✨ 核心闭环逻辑：从工具调用历史中收刮最终状态 ===
    # 使用 merge_dsl 确保不会丢失原始数据
    final_data_dsl = data_dsl
    final_new_assets = []
    
    # 遍历消息历史，寻找工具执行的结果
    for msg in result["messages"]:
        # 尝试从回复的文本中寻找 JSON (针对模型最后直接输出的情况)
        if hasattr(msg, "content") and msg.content:
            try:
                import re
                # 寻找最外层的 JSON 结构
                json_match = re.search(r'\{.*\}', msg.content, re.DOTALL)
                if json_match:
                    potental_json = json.loads(json_match.group())
                    if "page_order" in potental_json or "components" in str(potental_json): 
                        final_data_dsl = merge_dsl(final_data_dsl, potental_json)
            except:
                pass
        
        # 从工具返回的消息中直接提取数据并合并
        if msg.type == "tool":
            try:
                tool_res = json.loads(msg.content)
                if isinstance(tool_res, dict):
                    # 关键修复：只有当 tool_res 本身包含 page_order 或 components 时，才将其视为 DSL 直接合并
                    # 且为了防止模型将 {"data_dsl": {...}} 误传为顶级结构，我们优先提取 data_dsl
                    if "data_dsl" in tool_res:
                        final_data_dsl = merge_dsl(final_data_dsl, tool_res["data_dsl"])
                        
                        if "new_assets" in tool_res:
                            final_new_assets.extend(tool_res["new_assets"])
                        continue

                    if "page_order" in tool_res or "components" in tool_res:
                        final_data_dsl = merge_dsl(final_data_dsl, tool_res)
                        
                    if "new_assets" in tool_res:
                        final_new_assets.extend(tool_res["new_assets"])
            except:
                pass

    print(f"✅ [Tool Calling 引擎] 增强完毕，已同步至全局状态。")
    
    return {
        "data_dsl": final_data_dsl,
        "image_assets": final_new_assets
    }
