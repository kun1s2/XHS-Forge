# app/agents/tools_registry.py
from app.tools.amap import place_search_async, amap_weather_query
from app.tools.network_search import search_network_structured_async
from app.tools.image_recognition import describe_image_async
from app.tools.serpapi_search import search_google_images
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
    "google_images": google_images
}

# 兼容性导出：用于特定节点的强绑定工具
google_image_search_tool = google_images

# 默认全量工具集
RESEARCH_TOOLS = list(TOOL_POOL.values())
