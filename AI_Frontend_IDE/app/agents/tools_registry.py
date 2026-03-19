# app/agents/tools_registry.py
from app.tools.amap import place_search_async, amap_weather_query
from app.tools.network_search import search_network_structured_async
from app.tools.image_recognition import describe_image_async
from app.tools.serpapi_search import search_google_images
from app.tools.block_search import search_block_manual # ✨ 导入积木检索工具
from app.tools.canvas_tools import append_block, insert_block, remove_block, update_block_brief, finish_layout # ✨ 导入画布手术刀
from langchain_core.tools import tool

# 🛠️ 【X-Forge 全球工具池】：所有原子能力在此注册为标准 @tool

@tool
async def amap_search(keywords: str, city: str = None) -> str:
    """高德地图 POI 搜索。输入关键词和城市名，返回周边的地点详细信息。"""
    return await place_search_async(keywords, city)

@tool
async def weather_api(city: str) -> str:
    """高德天气查询。输入城市名，返回该城市的实时天气情况（温度、风向、湿度等）。"""
    return await amap_weather_query(city)

@tool
async def network_search(query: str) -> str:
    """全网实时搜索。输入查询词，返回互联网上最新的新闻、评论和百科资料。"""
    results = await search_network_structured_async(query)
    return "\n".join([f"- {r['title']}: {r['snippet']}" for r in results]) if results else "未找到搜索结果。"

@tool
async def image_vibe(image_url: str) -> str:
    """视觉调性分析。输入图片 URL，分析图片的构图、主色调、氛围和所含内容。"""
    return await describe_image_async(image_url)

@tool
async def google_images(query: str) -> str:
    """Google 高清大图搜索。专门用于寻找真实产品素材，返回图片直链列表。"""
    links = await search_google_images(query, num=5)
    return "\n".join(links) if links else "未找到相关图片。"

# ---------------------------------------------------------

# 归拢到工具池字典
TOOL_POOL = {
    "amap_search": amap_search,
    "weather_api": weather_api,
    "network_search": network_search,
    "image_vibe": image_vibe,
    "google_images": google_images,
    "search_block_manual": search_block_manual,
    "append_block": append_block,
    "insert_block": insert_block,
    "remove_block": remove_block,
    "update_block_brief": update_block_brief,
    "finish_layout": finish_layout
}

# 默认工具集划分
RESEARCH_TOOLS = [network_search, google_images]
OUTLINE_TOOLS = [search_block_manual, append_block, insert_block, remove_block, update_block_brief, finish_layout]
