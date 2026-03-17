# app/agents/tools_registry.py
from app.tools.amap import amap_poi_search, amap_weather_query
from app.tools.network_search import search_network_structured_async
from app.tools.image_recognition import analyze_image_vibe_async
from langchain_core.tools import tool

# 🛠️ 【X-Forge 全球工具池】：所有原子能力在此注册
TOOL_POOL = {
    "amap_search": amap_poi_search,
    "weather_api": amap_weather_query,
    "network_search": search_network_structured_async,
    "image_vibe": analyze_image_vibe_async
}

# 兼容性导出：默认全量工具集
RESEARCH_TOOLS = list(TOOL_POOL.values())
