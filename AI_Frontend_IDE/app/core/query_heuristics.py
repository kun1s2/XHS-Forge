"""Shared deterministic query heuristics for routing and lightweight edits.

These helpers keep high-signal keyword rules in one place so agent nodes do not
grow ad-hoc token lists for the same decisions. They are intentionally small,
explicit, and used only for fast-path routing or low-risk deterministic assists.
"""

from collections.abc import Iterable


EXISTING_CANVAS_EDIT_ACTION_TOKENS = (
    "保留",
    "改",
    "修改",
    "重写",
    "优化",
    "调整",
    "简短",
    "简洁",
    "精简",
    "丰富",
    "删除",
    "删掉",
    "替换",
    "换成",
    "移动",
    "挪",
    "加强",
    "弱化",
    "润色",
    "改成",
    "改一下",
)

EXISTING_CANVAS_TARGET_TOKENS = (
    "标题",
    "正文",
    "文本",
    "段落",
    "封面",
    "主题",
    "风格",
)

PARAGRAPH_REFERENCE_TOKENS = (
    "第一段",
    "第二段",
    "第三段",
    "这一段",
)

STYLE_ROUTE_TOKENS = (
    "主题",
    "风格",
    "配色",
    "灰蓝",
    "克制",
    "视觉",
    "样式",
)

STRUCTURE_ROUTE_TOKENS = (
    "结构",
    "顺序",
    "位置",
    "前面",
    "后面",
    "移动",
    "删除",
    "新增",
    "加一个",
    "补一个",
)

IMAGE_REQUEST_TOKENS = (
    "搜图",
    "找图",
    "实拍图",
    "实拍",
    "配图",
    "图片",
    "首图",
    "封面",
)

BEFORE_POSITION_TOKENS = (
    "前面",
    "前边",
    "之前",
    "上面",
    "前插",
)

SHARPER_TONE_TOKENS = (
    "毒舌",
    "犀利",
    "更狠",
    "尖锐",
    "刻薄",
)


def contains_any_token(text: str | None, tokens: Iterable[str]) -> bool:
    raw_text = text or ""
    return any(token in raw_text for token in tokens)


def looks_like_existing_canvas_edit(user_text: str | None) -> bool:
    return (
        contains_any_token(user_text, EXISTING_CANVAS_EDIT_ACTION_TOKENS)
        or contains_any_token(user_text, EXISTING_CANVAS_TARGET_TOKENS)
        or contains_any_token(user_text, PARAGRAPH_REFERENCE_TOKENS)
    )


def infer_existing_canvas_edit_route(user_text: str | None) -> str:
    if contains_any_token(user_text, STYLE_ROUTE_TOKENS):
        return "style_node"
    if contains_any_token(user_text, STRUCTURE_ROUTE_TOKENS):
        return "structure_node"
    return "content_node"


def mentions_paragraph_reference(user_text: str | None) -> bool:
    return contains_any_token(user_text, PARAGRAPH_REFERENCE_TOKENS)


def wants_image_search(user_text: str | None) -> bool:
    return contains_any_token(user_text, IMAGE_REQUEST_TOKENS)


def wants_before_position(user_text: str | None) -> bool:
    return contains_any_token(user_text, BEFORE_POSITION_TOKENS)


def wants_sharper_tone(user_text: str | None) -> bool:
    return contains_any_token(user_text, SHARPER_TONE_TOKENS)
