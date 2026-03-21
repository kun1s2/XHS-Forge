from __future__ import annotations

from typing import Any

from app.agents.graph import outline_resolver_node, outline_synthesizer
from app.agents.state import UIProjectState


async def outline_resolver(state: UIProjectState) -> dict[str, Any]:
    """
    现代化大纲入口：直接走确定性 resolver。
    兼容旧导入路径，避免仓库内历史脚本继续引用 历史大纲实现。
    """
    return await outline_resolver_node(state)


async def outline_agent(state: UIProjectState) -> dict[str, Any]:
    """
    历史兼容壳。
    旧测试或脚本若仍调用 outline_agent，会被转发到现代化 resolver。
    同时附带一个轻量 page_outline，避免旧脚本直接崩溃。
    """
    result = await outline_resolver_node(state)
    blocks = list((result.get("note_document") or {}).get("blocks") or [])
    return {
        **result,
        "page_outline": [
            {
                "id": str(block.get("id") or ""),
                "component_type": str(block.get("type") or ""),
                "content_brief": str(block.get("content_brief") or ""),
            }
            for block in blocks
        ],
    }


def should_continue_outlining(state: UIProjectState) -> str:
    """
    历史兼容函数。正式 graph 已不再使用 历史工具循环。
    保留该符号仅为了避免旧测试/脚本导入失败。
    """
    return "outline_resolver"


__all__ = ["outline_resolver", "outline_agent", "outline_synthesizer", "should_continue_outlining"]
