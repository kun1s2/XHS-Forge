import json
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState, merge_dsl
from app.core.config import settings
from app.services.location_enricher import enrich_page_dsl
from app.services.search_enricher import enrich_product_data
from app.services.image_generator import auto_generate_images

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
    data_dsl = state.get("data_dsl", {})
    active_archetype = state.get("active_archetype", "general")
    image_assets = state.get("image_assets", [])
    
    if not data_dsl:
        return {}

    # === 🛡️ 核心优化 1：使用闭包定义工具，彻底切断大模型传参导致的幻觉 ===
    @tool
    async def enrich_product_tool() -> str:
        """当存在商品卡片、参数列表时，调用此工具进行参数核实和事实增强。无参数。"""
        try:
            enriched = await enrich_product_data(data_dsl, active_archetype)
            return json.dumps({"source": "product", "data_dsl": enriched}, ensure_ascii=False)
        except Exception as e:
            return f"Error: product_tool 失败 - {str(e)}"

    @tool
    async def enrich_location_tool() -> str:
        """当页面存在位置打卡组件时，调用此工具补全经纬度。无参数。"""
        try:
            enriched = await enrich_page_dsl(data_dsl)
            return json.dumps({"source": "location", "data_dsl": enriched}, ensure_ascii=False)
        except Exception as e:
            return f"Error: location_tool 失败 - {str(e)}"

    @tool
    async def generate_images_tool() -> str:
        """当组件缺少图片（URL为空）时，调用此工具进行搜图/生图并提取配色。无参数。"""
        try:
            enriched_dsl, new_assets = await auto_generate_images(data_dsl, active_archetype)
            return json.dumps({
                "source": "images", 
                "data_dsl": enriched_dsl, 
                "new_assets": new_assets
            }, ensure_ascii=False)
        except Exception as e:
            return f"Error: generate_images_tool 失败 - {str(e)}"

    # 动态组装 Agent，工具在内部即可直接访问外层的 data_dsl
    tools = [enrich_product_tool, enrich_location_tool, generate_images_tool]
    enrichment_react_agent = create_react_agent(_tool_llm, tools)

    # === 🛡️ 核心优化 2：极简摘要 Prompt，节约 Token ===
    # 只提取组件 ID 和类型给大模型，不给具体内容，防止它迷失在海量数据中
    component_outline = {k: v.get("component_type", "Unknown") for k, v in data_dsl.items() if isinstance(v, dict)}
    
    prompt = f"""你是一个高级数据增强管家。当前原型: {active_archetype}
当前页面的组件大纲如下:
{json.dumps(component_outline, ensure_ascii=False)}

请分析以上组件树，按需调用工具：
- 有商品/参数类组件 -> 调用 enrich_product_tool
- 有位置地图类组件 -> 调用 enrich_location_tool
- 需要视觉配图 -> 调用 generate_images_tool

【最高指令】：
1. 工具会自动读取后台数据，你无需传递任何参数。
2. 调用完必要的工具后，请直接回复“增强完毕”。绝对不要在回复中输出任何 JSON 数据！"""

    print(f"🧠 [Tool Calling 引擎] 启动增强管家，分析大纲: {component_outline}")
    result = await enrichment_react_agent.ainvoke({"messages": [("user", prompt)]})
    
    # === 🛡️ 核心优化 3：唯一事实来源解析 (Single Source of Truth) ===
    final_data_dsl = data_dsl
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
                if "data_dsl" in tool_res:
                    final_data_dsl = merge_dsl(final_data_dsl, tool_res["data_dsl"])
                if "new_assets" in tool_res:
                    final_new_assets.extend(tool_res["new_assets"])
                    
            except json.JSONDecodeError:
                print(f"⚠️ [解析警告] 工具返回非标准 JSON: {msg.content[:100]}...")
            except Exception as e:
                print(f"⚠️ [未知错误] 合并过程发生错误: {e}")

    print(f"✅ [Tool Calling 引擎] 数据增强与合并安全闭环。")
    
    return {
        "data_dsl": final_data_dsl,
        "image_assets": final_new_assets
    }