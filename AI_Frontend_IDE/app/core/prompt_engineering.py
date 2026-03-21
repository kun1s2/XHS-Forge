from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt_template(template_name: str) -> str:
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
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_prompt_template(system_template_name)),
            ("human", human_template),
        ],
        template_format=template_format,
    )


def render_prompt_messages(prompt: ChatPromptTemplate, inputs: dict[str, Any]) -> list[dict[str, str]]:
    rendered_messages = prompt.format_messages(**inputs)
    return [
        {"role": str(message.type or "system"), "content": str(message.content or "")}
        for message in rendered_messages
    ]


def render_string_prompt(template_name: str, **inputs: Any) -> str:
    template = PromptTemplate.from_template(load_prompt_template(template_name), template_format="jinja2")
    return template.format(**inputs)


def _stringify_prompt_content(value: Any) -> str:
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
    if messages is None:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": _stringify_prompt_content(system_prompt)})
        if user_prompt:
            messages.append({"role": "user", "content": _stringify_prompt_content(user_prompt)})
        if assistant_payload is not None:
            messages.append({"role": "assistant", "content": _stringify_prompt_content(assistant_payload)})
    return {node_name: messages}
