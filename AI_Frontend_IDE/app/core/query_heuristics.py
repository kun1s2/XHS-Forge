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

CAPABILITY_QUERY_TOKENS = (
    "你有什么功能",
    "你有哪些功能",
    "你有什么能力",
    "你有哪些能力",
    "你能做什么",
    "你可以做什么",
    "你会什么",
    "怎么用",
    "如何使用",
    "怎么和你配合",
    "你支持什么",
    "能帮我做什么",
    "可以帮我什么",
    "介绍一下你的功能",
    "介绍一下你的能力",
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

ATTENTION_HOOK_TOKENS = (
    "吸引眼球",
    "吸引用户眼球",
    "吸睛",
    "更吸睛",
    "更抓人",
    "更吸引用户",
    "更吸引用户眼球",
    "更有冲击力",
    "更有张力",
    "更有记忆点",
    "更抓眼球",
)


def contains_any_token(text: str | None, tokens: Iterable[str]) -> bool:
    raw_text = text or ""
    return any(token in raw_text for token in tokens)


def looks_like_existing_canvas_edit(user_text: str | None) -> bool:
    return (
        contains_any_token(user_text, EXISTING_CANVAS_EDIT_ACTION_TOKENS)
        or contains_any_token(user_text, EXISTING_CANVAS_TARGET_TOKENS)
        or contains_any_token(user_text, PARAGRAPH_REFERENCE_TOKENS)
        or wants_image_search(user_text)
    )


def infer_existing_canvas_edit_route(user_text: str | None) -> str:
    if wants_image_search(user_text):
        return "retrieval_worker"
    return "composition_worker"


def mentions_paragraph_reference(user_text: str | None) -> bool:
    return contains_any_token(user_text, PARAGRAPH_REFERENCE_TOKENS)


def wants_image_search(user_text: str | None) -> bool:
    return contains_any_token(user_text, IMAGE_REQUEST_TOKENS)


def wants_before_position(user_text: str | None) -> bool:
    return contains_any_token(user_text, BEFORE_POSITION_TOKENS)


def wants_sharper_tone(user_text: str | None) -> bool:
    return contains_any_token(user_text, SHARPER_TONE_TOKENS)


def wants_attention_hook(user_text: str | None) -> bool:
    return contains_any_token(user_text, ATTENTION_HOOK_TOKENS)


def looks_like_capability_query(user_text: str | None) -> bool:
    raw_text = str(user_text or "").strip()
    if not raw_text:
        return False
    return contains_any_token(raw_text, CAPABILITY_QUERY_TOKENS)
