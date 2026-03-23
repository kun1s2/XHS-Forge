"""提示词工程基础模块。

这里统一管理模板加载、消息渲染和 Prompt Lab 快照构造，避免每个节点各自
发明一套 prompt plumbing。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt_template(template_name: str) -> str:
    """按模板名读取提示词模板文本。"""
    path = PROMPTS_ROOT / template_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_chat_prompt(
    *,
    system_template_name: str,
    human_template: str,
    template_format: str = "jinja2",
) -> ChatPromptTemplate:
    """基于 system 模板和 human 模板构造聊天提示词对象。"""
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt_template(system_template_name)),
            ("human", human_template),
        ],
        template_format=template_format,
    )


def render_prompt_messages(prompt: ChatPromptTemplate, inputs: dict[str, Any]) -> list[dict[str, str]]:
    """把 ChatPromptTemplate 渲染成便于记录和展示的消息列表。"""
    rendered_messages = prompt.format_messages(**inputs)
    return [
        {"role": str(message.type or "system"), "content": str(message.content or "")}
        for message in rendered_messages
    ]


def render_string_prompt(template_name: str, **inputs: Any) -> str:
    """把字符串模板渲染成最终 prompt 文本。"""
    template = PromptTemplate.from_template(load_prompt_template(template_name), template_format="jinja2")
    return template.format(**inputs)


def _stringify_prompt_content(value: Any) -> str:
    """把结构化对象稳定转成可读字符串，供 Prompt Lab 展示。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(exclude_none=True), ensure_ascii=False, indent=2)
    return str(value)


def build_prompt_snapshot(
    node_name: str,
    *,
    messages: list[dict[str, str]] | None = None,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    assistant_payload: Any | None = None,
) -> dict[str, list[dict[str, str]]]:
    """构造统一格式的节点 prompt 快照。"""
    if messages is None:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": _stringify_prompt_content(system_prompt)})
        if user_prompt:
            messages.append({"role": "user", "content": _stringify_prompt_content(user_prompt)})
        if assistant_payload is not None:
            messages.append({"role": "assistant", "content": _stringify_prompt_content(assistant_payload)})
    return {node_name: messages}
