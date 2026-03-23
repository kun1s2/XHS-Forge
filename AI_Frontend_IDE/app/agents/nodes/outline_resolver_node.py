from __future__ import annotations

from typing import Any

from app.agents.graph import outline_resolver as run_outline_resolver, outline_synthesizer
from app.agents.state import UIProjectState


async def outline_resolver(state: UIProjectState) -> dict[str, Any]:
    """
    现代化大纲入口：直接走确定性 resolver。
    """
    return await run_outline_resolver(state)


async def outline_resolver_preview(state: UIProjectState) -> dict[str, Any]:
    """
    输出轻量 page outline 预览，便于测试和诊断直接检查 block skeleton。
    """
    result = await run_outline_resolver(state)
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


def continue_outline_resolution(state: UIProjectState) -> str:
    """
    解析器路由占位符。
    """
    return "outline_resolver"


__all__ = ["outline_resolver", "outline_resolver_preview", "outline_synthesizer", "continue_outline_resolution"]
