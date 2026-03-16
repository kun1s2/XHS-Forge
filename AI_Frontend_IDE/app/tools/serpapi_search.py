import os
import httpx
from typing import List, Optional
from app.core.config import settings

async def search_google_images(query: str, num: int = 5) -> List[str]:
    """
    [视觉狙击手] 使用 SerpApi 猎取真实的 Google 高清图片直链。
    """
    api_key = settings.SERPAPI_API_KEY
    if not api_key:
        print("⚠️ [SerpApi] 未配置 API Key，搜图功能失效。")
        return []

    url = "https://serpapi.com/search"
    params = {
        "engine": "google_images",
        "q": query,
        "api_key": api_key,
        "num": num,
        "ijn": 0
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("images_results", [])
            # 提取原始高清直链 (original)
            image_links = [img.get("original") for img in results if img.get("original")]
            
            # 简单的真实性初筛：排除一些明显的 base64 或损坏链接
            valid_links = [link for link in image_links if link.startswith("http")]
            
            print(f"🎯 [SerpApi] 成功猎取 {len(valid_links)} 张高清大图，查询词: {query}")
            return valid_links
            
    except Exception as e:
        print(f"❌ [SerpApi] 搜图失败: {e}")
        return []
