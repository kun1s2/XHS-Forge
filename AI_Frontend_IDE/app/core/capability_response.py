"""Deterministic capability/help replies for chat-first product guidance."""

from __future__ import annotations

from typing import Any

from app.core.note_document import build_note_document_from_state


def build_capability_reply(values: dict[str, Any] | None = None) -> str:
    safe_values = values or {}
    note_document = build_note_document_from_state(safe_values)
    has_canvas = bool((note_document.get("blocks") or []))

    lines = [
        "我现在主要可以这样和你配合：",
        "1. 从一句需求开始，先理解你的目标，再规划页面结构和内容方向。",
        "2. 需要时补搜公开信息、补图、发现缺口，并在关键分叉点和你确认。",
        "3. 生成后继续打磨，支持按块局部修改、复盘建议继续优化、回滚和从历史点分支。",
        "4. 尽量把来源、事实边界和修改范围说清楚，不是只给你一版结果就结束。",
    ]
    if has_canvas:
        lines.append("5. 你也可以直接基于当前页面继续说：只改哪一块、先补图、先补事实，或者按复盘建议继续优化。")
    else:
        lines.append("5. 你可以直接说要写什么，比如测评、旅行、探店、日常分享，我会先给计划，再带你一起把它做完整。")

    lines.extend(
        [
            "",
            "你现在可以直接试这些说法：",
            "• 写一篇关于 xx 的测评 / 游记 / 探店",
            "• 只改这块的标题 / 正文 / 结论",
            "• 先帮我补图 / 补事实",
            "• 按复盘建议继续优化",
        ]
    )
    return "\n".join(lines).strip()
