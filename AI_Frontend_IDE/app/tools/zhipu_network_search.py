# app/tools/zhipu_network_search.py — 智谱 Web Search API 联网检索
"""
智谱官方「网络搜索」API：POST /paas/v4/web_search，返回结构化结果。
文档：https://docs.bigmodel.cn/cn/guide/tools/web-search
未配置 ZHI_PU_API_KEY 时返回说明文案。与 SerpAPI 统一为 link/title/snippet 便于上层兼容。
"""

import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

ZHIPU_WEB_SEARCH_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"
MAX_SNIPPET_LEN = 400
DEFAULT_NUM = 10
# 智谱 search_engine: search_std | search_pro | search_pro_sogou | search_pro_quark
DEFAULT_ENGINE = "search_std"


async def search_network_async(
    query: str,
    api_key: Optional[str] = None,
    num: int = DEFAULT_NUM,
    search_engine: str = DEFAULT_ENGINE,
    search_intent: bool = False,
) -> str:
    """
    使用智谱 Web Search API 执行网络检索，返回格式化摘要文本。
    api_key 为 None 时从 settings.ZHI_PU_API_KEY 读取。
    """
    if not query or not query.strip():
        return "[网络检索] 查询词为空。"
    from app.core.config import settings
    key = (api_key or "").strip() or (getattr(settings, "ZHI_PU_API_KEY", None) or "").strip()
    if not key:
        return "[网络检索] 未配置 ZHI_PU_API_KEY，无法使用智谱联网。请在 .env 中设置，或将 NETWORK_SEARCH_BACKEND 设为 serpapi。"
    q = query.strip()[:70]
    count = min(max(1, num), 50)
    payload = {
        "search_query": q,
        "search_engine": search_engine,
        "search_intent": search_intent,
        "count": count,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                ZHIPU_WEB_SEARCH_URL,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Zhipu Web Search HTTP error: %s", e)
        return f"[网络检索] 智谱请求失败: HTTP {e.response.status_code}。"
    except Exception as e:
        logger.warning("Zhipu Web Search request error: %s", e)
        return f"[网络检索] 智谱请求异常: {e!s}。"

    err = data.get("error") if isinstance(data.get("error"), dict) else None
    if err:
        code = err.get("code", "")
        msg = err.get("message", "")
        return f"[网络检索] 智谱返回错误: {code} {msg}。"

    results = data.get("search_result") or []
    if not results:
        return f"[网络检索] 未找到与「{q}」相关的网页结果。"
    lines = []
    for i, item in enumerate(results[:count], 1):
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        content = (item.get("content") or "").strip()
        if len(content) > MAX_SNIPPET_LEN:
            content = content[:MAX_SNIPPET_LEN] + "..."
        lines.append(f"[{i}] {title}\n链接: {link}\n{content}")
    return "\n\n".join(lines)


async def search_network_structured_async(
    query: str,
    api_key: Optional[str] = None,
    num: int = DEFAULT_NUM,
    search_engine: str = DEFAULT_ENGINE,
    search_intent: bool = False,
) -> List[dict]:
    """
    智谱 Web Search，返回与 SerpAPI 兼容的结构：link, title, snippet。
    未配置或失败时返回空列表。
    """
    if not query or not query.strip():
        return []
    from app.core.config import settings
    key = (api_key or "").strip() or (getattr(settings, "ZHI_PU_API_KEY", None) or "").strip()
    if not key:
        return []
    q = query.strip()[:70]
    count = min(max(1, num), 50)
    payload = {
        "search_query": q,
        "search_engine": search_engine,
        "search_intent": search_intent,
        "count": count,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                ZHIPU_WEB_SEARCH_URL,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Zhipu Web Search structured request error: %s", e)
        return []

    if data.get("error"):
        return []
    results = data.get("search_result") or []
    out = []
    for item in results[:count]:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()
        content = (item.get("content") or "").strip()
        if len(content) > MAX_SNIPPET_LEN:
            content = content[:MAX_SNIPPET_LEN] + "..."
        out.append({"link": link, "title": title, "snippet": content})
    return out
