import logging
import asyncio
import time
from typing import List, Optional
from zhipuai import ZhipuAI
from app.core.config import settings

logger = logging.getLogger(__name__)
DEFAULT_NUM = 10
DEFAULT_ENGINE = "search_pro"
_CIRCUIT_UNAVAILABLE_UNTIL = 0.0
_CIRCUIT_REASON = ""


def _should_trip_search_circuit(exc: Exception) -> bool:
    text = str(exc or "")
    return any(token in text for token in ("1113", "429", "余额不足", "无可用资源包"))


def _search_circuit_open() -> bool:
    return _CIRCUIT_UNAVAILABLE_UNTIL > time.monotonic()


def _trip_search_circuit(reason: str, ttl_seconds: int = 600) -> None:
    global _CIRCUIT_UNAVAILABLE_UNTIL, _CIRCUIT_REASON
    _CIRCUIT_UNAVAILABLE_UNTIL = time.monotonic() + ttl_seconds
    _CIRCUIT_REASON = reason


def _search_circuit_reason() -> str:
    remaining = int(max(0, _CIRCUIT_UNAVAILABLE_UNTIL - time.monotonic()))
    if not _CIRCUIT_REASON:
        return "search circuit open"
    return f"{_CIRCUIT_REASON} (cooldown {remaining}s)"

def _get_zhipu_client(api_key: Optional[str] = None):
    # 强制路由：始终优先从 settings.ZHI_PU_API_KEY 读取
    key = (api_key or getattr(settings, "ZHI_PU_API_KEY", "")).strip()
    return ZhipuAI(api_key=key) if key else None

async def search_network_async(query: str, api_key: Optional[str] = None, num: int = DEFAULT_NUM, search_engine: str = DEFAULT_ENGINE) -> str:
    """[感知矩阵] 智谱官方原生联网搜索工具"""
    if not query.strip(): return "[网络检索] 查询词为空。"
    if _search_circuit_open():
        return f"[网络检索] 智谱搜索暂时不可用：{_search_circuit_reason()}"
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
        if _should_trip_search_circuit(e):
            _trip_search_circuit(str(e))
        logger.error("Zhipu Web Search error: %s", e)
        return f"[网络检索] 智谱请求异常: {e}"

async def search_network_structured_async(query: str, api_key: Optional[str] = None, num: int = DEFAULT_NUM, search_engine: str = DEFAULT_ENGINE) -> List[dict]:
    """[感知矩阵] 返回结构化搜索结果，用于 RAG 或背景蒸馏"""
    if not query.strip(): return []
    if _search_circuit_open():
        logger.warning("Zhipu Web Search skipped by circuit: %s", _search_circuit_reason())
        return []
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
        if _should_trip_search_circuit(e):
            _trip_search_circuit(str(e))
        logger.warning("Zhipu Web Search structured error: %s", e)
        return []
