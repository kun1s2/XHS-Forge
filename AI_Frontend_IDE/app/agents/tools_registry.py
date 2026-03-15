from langchain_core.tools import tool
from app.services.rag_service import retrieve_brand_knowledge
from app.tools.image_recognition import describe_image
from app.tools.network_search import search_network_async
import asyncio

@tool
async def retrieve_private_knowledge(query: str) -> str:
    """当用户指令涉及品牌、特定产品或需要内部机密时，调用此工具检索私域知识库 (PGVector)。"""
    knowledge = await retrieve_brand_knowledge(query)
    return knowledge if knowledge else "未找到相关私域知识。"

@tool
async def search_public_internet(query: str) -> str:
    """当询问最新热点、本地知识库缺失的当日新闻或新发布商品时，必须调用此工具。"""
    result = await search_network_async(query)
    return result if result else "全网检索未找到有效信息。"

@tool
async def analyze_uploaded_images(image_urls: list[str]) -> str:
    """当用户上传了图片（提供了URL），调用此工具利用视觉模型分析图片内容，并提取主色调 (Primary Hex) 和点缀色 (Accent Hex)。"""
    results = []
    for url in image_urls:
        prompt = "描述图片内容并提取主色调和点缀色，格式如：主要内容是...，主色：#xxxxxx，点缀色：#xxxxxx"
        res = await asyncio.to_thread(describe_image, url, prompt)
        results.append(f"图片 {url} 分析结果：{res}")
    return "\n".join(results)

# 注册给大脑的所有工具
RESEARCH_TOOLS = [retrieve_private_knowledge, search_public_internet, analyze_uploaded_images]
