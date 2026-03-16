import json
from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
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
        return json.dumps({"data_dsl": enriched_dsl, "new_assets": new_assets}, ensure_ascii=False)
    except Exception as e:
        return f"Error: {e}"

# 初始化工具调用的 LLM
_tool_llm = create_llm(
    model=settings.LLM_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0.1
)

# 使用 langgraph.prebuilt 快速构建一个 ReAct Agent（包含 LLM 节点和 Tool 节点的主循环）
tools = [enrich_product_tool, enrich_location_tool, generate_images_tool]
enrichment_react_agent = create_react_agent(_tool_llm, tools)

async def enrichment_node_v2(state: UIProjectState) -> dict:
    """
    【最新技术栈：Tool Calling 代理引擎】
    抛弃原先呆板的串行调用，让大模型自主决定需要调用哪些增强工具。
    """
    data_dsl = state.get("data_dsl", {})
    active_archetype = state.get("active_archetype", "general")
    
    if not data_dsl:
        return {}

    prompt = f"""你是一个前端数据增强架构师。
当前页面的原型类别是: {active_archetype}
当前的页面数据 (data_dsl) 如下:
{json.dumps(data_dsl, ensure_ascii=False)}

请分析以上数据，并使用提供的工具对其进行增强。
- 如果有商品卡片 (ProductCard) 或参数卡片 (ProductSpecCard)，请调用 enrich_product_tool。
- 如果有位置打卡 (LocationBlock) 且缺少坐标，请调用 enrich_location_tool。
- 如果有组件缺少图片 (image_urls 为空)，请调用 generate_images_tool。

你可以并行或串行调用工具。所有需要的增强完成后，请回复“增强完毕”。"""

    # 运行内部的 ReAct Agent 图
    print(f"🧠 [Tool Calling 引擎] 启动增强管家，赋予其 3 项增强武器...")
    result = await enrichment_react_agent.ainvoke({"messages": [("user", prompt)]})
    
    # 提取经过工具反复修改后的最终结果
    # 因为我们的工具是无状态的字符串传递，Agent 可能会在回复中输出最终的 JSON，或者我们需要从工具调用的返回值里去提取。
    # 为了保证生产稳定性（防止大模型弄坏 JSON），在实际业务中我们通常让工具直接修改外部状态。
    # 这里为了演示“大脑 -> 工具 -> 大脑”的纯正范式：
    pass