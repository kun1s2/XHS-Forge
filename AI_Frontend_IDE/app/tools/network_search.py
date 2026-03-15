# app/tools/network_search.py — 联网检索统一入口，已替换为以智谱为核心
"""
已将 SerpAPI 替换为智谱联网。
通过 .env 的 NETWORK_SEARCH_BACKEND 切换，默认为 zhipu。
智谱需 ZHI_PU_API_KEY。
"""

import logging
from typing import List, Optional
from app.tools.zhipu_network_search import (
    search_network_async as zhipu_search,
    search_network_structured_async as zhipu_structured
)

logger = logging.getLogger(__name__)

async def search_network_async(
    query: str,
    api_key: Optional[str] = None,
    num: int = 5,
    source_hint: str = "",
) -> str:
    """
    联网检索统一入口。目前默认使用智谱。
    返回格式化摘要文本。
    """
    from app.core.config import settings
    backend = (getattr(settings, "NETWORK_SEARCH_BACKEND", None) or "zhipu").strip().lower()
    
    if backend == "serpapi":
        # 如果用户非要用 serpapi，保留一层警告或尝试调用（如果代码还没删干净）
        logger.warning("SerpAPI 已被标记为废弃，建议切换到 zhipu。")
        # 这里为了“对接原本功能”，如果未来还需要 SerpAPI，可以在此加回实现
        
    return await zhipu_search(query=query, api_key=api_key, num=num)


async def search_network_structured_async(
    query: str,
    api_key: Optional[str] = None,
    num: int = 5,
    source_hint: str = "",
) -> List[dict]:
    """
    联网检索结构化入口。返回与 search_enricher 等兼容的 list[dict]。
    """
    from app.core.config import settings
    backend = (getattr(settings, "NETWORK_SEARCH_BACKEND", None) or "zhipu").strip().lower()
    
    return await zhipu_structured(query=query, api_key=api_key, num=num)


def get_network_search_tool():
    """
    返回联网检索的 LangChain 兼容 tool（async）。
    """
    from langchain_core.tools import tool

    @tool
    async def search_network(query: str, source_hint: str = "", num: int = 5) -> str:
        """联网检索：使用智谱执行网络搜索。query 为查询词，num 为返回条数。"""
        return await search_network_async(
            query=query,
            num=num,
            source_hint=source_hint or "",
        )

    search_network.name = "search_network"
    return search_network
