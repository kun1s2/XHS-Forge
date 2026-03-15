import logging
import asyncio
from typing import List, Optional
from zhipuai import ZhipuAI
from app.core.config import settings

logger = logging.getLogger(__name__)
DEFAULT_NUM = 10
DEFAULT_ENGINE = "search_pro"

def _get_zhipu_client(api_key: Optional[str] = None):
    # 强制路由：始终优先从 settings.ZHI_PU_API_KEY 读取
    key = (api_key or getattr(settings, "ZHI_PU_API_KEY", "")).strip()
    return ZhipuAI(api_key=key) if key else None

async def search_network_async(query: str, api_key: Optional[str] = None, num: int = DEFAULT_NUM, search_engine: str = DEFAULT_ENGINE) -> str:
    """[感知矩阵] 智谱官方原生联网搜索工具"""
    if not query.strip(): return "[网络检索] 查询词为空。"
    client = _get_zhipu_client(api_key)
    if not client: return "[网络检索] 未配置 ZHI_PU_API_KEY。"

    def _do_search():
        # 调用智谱最新官方原生 Web Search 接口
        return client.web_search.web_search(
            search_engine=search_engine,
            search_query=query,
            count=num,
            search_recency_filter="noLimit",
            content_size="high"
        )

    try:
        response = await asyncio.to_thread(_do_search)
        results = getattr(response, "search_result", [])
        if not results: return f"[网络检索] 未找到与「{query}」相关的结果。"

        lines = []
        for i, item in enumerate(results[:num], 1):
            title = item.get("title", "") if isinstance(item, dict) else getattr(item, "title", "")
            link = item.get("link", "") if isinstance(item, dict) else getattr(item, "link", "")
            content = item.get("content", "") if isinstance(item, dict) else getattr(item, "content", "")
            lines.append(f"[{i}] {title}\n链接: {link}\n{content[:400]}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error("Zhipu Web Search error: %s", e)
        return f"[网络检索] 智谱请求异常: {e}"

async def search_network_structured_async(query: str, api_key: Optional[str] = None, num: int = DEFAULT_NUM, search_engine: str = DEFAULT_ENGINE) -> List[dict]:
    """[感知矩阵] 返回结构化搜索结果，用于 RAG 或背景蒸馏"""
    if not query.strip(): return []
    client = _get_zhipu_client(api_key)
    if not client: return []

    def _do_search():
        return client.web_search.web_search(
            search_engine=search_engine, search_query=query, count=num, content_size="high"
        )
    try:
        response = await asyncio.to_thread(_do_search)
        results = getattr(response, "search_result", [])
        out = []
        for item in results[:num]:
            out.append({
                "title": item.get("title", "") if isinstance(item, dict) else getattr(item, "title", ""),
                "link": item.get("link", "") if isinstance(item, dict) else getattr(item, "link", ""),
                "snippet": (item.get("content", "") if isinstance(item, dict) else getattr(item, "content", ""))[:400]
            })
        return out
    except Exception as e:
        logger.warning("Zhipu Web Search structured error: %s", e)
        return []
