from __future__ import annotations

import json
from typing import Any


TRUTH_REQUEST_PATTERNS: tuple[str, ...] = (
    "游玩日记",
    "旅行日记",
    "真实打卡",
    "真实行程",
    "我的原话",
    "原话",
    "几点几分",
    "几点到",
    "几分到",
    "当天经历",
    "今天的行程",
    "亲身经历",
    "第一人称日志",
    "打卡日志",
    "现场记录",
)


def query_requests_truth_mode(query: str | None) -> bool:
    text = str(query or "").strip()
    if not text:
        return False
    return any(token in text for token in TRUTH_REQUEST_PATTERNS)


def normalize_user_provided_facts(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        normalized = dict(payload)
    else:
        normalized = {"raw_text": str(payload or "").strip()}
    raw_text = str(normalized.get("raw_text") or "").strip()
    if not raw_text:
        derived_parts = []
        for key, value in normalized.items():
            if key == "raw_text":
                continue
            if isinstance(value, list):
                values = [str(item or "").strip() for item in value if str(item or "").strip()]
                if values:
                    derived_parts.append(f"{key}: {' / '.join(values)}")
                continue
            normalized_value = str(value or "").strip()
            if normalized_value:
                derived_parts.append(f"{key}: {normalized_value}")
        raw_text = "\n".join(derived_parts).strip()
    normalized["raw_text"] = raw_text
    return normalized


def has_user_provided_facts(payload: Any) -> bool:
    normalized = normalize_user_provided_facts(payload)
    return bool(normalized.get("raw_text"))


def build_tool_safety_result(
    *,
    tool_name: str,
    reason: str,
    next_action: str,
    required_fields: list[str] | None = None,
    safe_payload: dict[str, Any] | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "tool_safety_result": {
            "status": "insufficient_truth",
            "tool_name": str(tool_name or ""),
            "reason": str(reason or "tool_unavailable"),
            "next_action": str(next_action or "ask_user_for_facts"),
            "required_fields": [str(item) for item in (required_fields or []) if str(item).strip()],
            "detail": str(detail or "").strip() or None,
            "safe_payload": safe_payload or {},
        }
    }


def dumps_tool_safety_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)
