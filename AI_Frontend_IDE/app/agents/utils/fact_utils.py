from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


FACT_FIELD_LABELS = {
    "battery_capacity": "电池容量",
    "price": "价格",
}

FACT_FIELD_UNITS = {
    "battery_capacity": "mAh",
    "price": "元",
}


def normalize_fact_value(field: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    unit = FACT_FIELD_UNITS.get(field)
    if not unit:
        return text
    if unit.lower() in text.lower():
        return text
    if text.replace(".", "", 1).isdigit():
        return f"{text}{unit}"
    return text


def normalize_confirmed_facts(raw_confirmed: Any) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_confirmed, dict):
        return normalized

    for field, payload in raw_confirmed.items():
        if isinstance(payload, dict):
            raw_value = payload.get("value")
            sources = payload.get("sources") or []
            confirmed_at = payload.get("confirmed_at")
        else:
            raw_value = payload
            sources = []
            confirmed_at = None

        value = normalize_fact_value(field, raw_value)
        if not value:
            continue

        normalized[field] = {
            "value": value,
            "field_label": FACT_FIELD_LABELS.get(field, field),
            "sources": [str(item) for item in sources if str(item).strip()],
            "confirmed_at": confirmed_at or datetime.now().isoformat(),
        }

    return normalized


def render_confirmed_facts_note(confirmed_facts: dict[str, dict[str, Any]]) -> str:
    if not confirmed_facts:
        return ""

    lines = ["【已确认事实】"]
    for field, payload in confirmed_facts.items():
        label = payload.get("field_label") or FACT_FIELD_LABELS.get(field, field)
        value = payload.get("value") or ""
        sources = payload.get("sources") or []
        source_suffix = f"（来源: {' / '.join(sources[:2])}）" if sources else ""
        lines.append(f"- {label}: {value}{source_suffix}")
    return "\n".join(lines)


def build_fact_grounding_context(knowledge: dict[str, Any]) -> str:
    safe_knowledge = knowledge if isinstance(knowledge, dict) else {}
    confirmed_facts = normalize_confirmed_facts(safe_knowledge.get("confirmed_facts"))
    conflicts = safe_knowledge.get("fact_conflicts") or []
    sources = safe_knowledge.get("fact_sources") or []
    lines: list[str] = []

    if confirmed_facts:
        lines.append("【最高优先级：已确认事实】")
        for field, payload in confirmed_facts.items():
            label = payload.get("field_label") or FACT_FIELD_LABELS.get(field, field)
            value = payload.get("value") or ""
            lines.append(f"- {label}: {value}")

    if conflicts:
        lines.append("【仍存在冲突，避免写成绝对结论】")
        for conflict in conflicts[:4]:
            field = str(conflict.get("field") or "")
            options = [str(item.get("value") or "") for item in (conflict.get("values") or []) if str(item.get("value") or "")]
            if options:
                lines.append(f"- {FACT_FIELD_LABELS.get(field, field)}: {' / '.join(options)}")

    if sources:
        lines.append("【可引用来源】")
        for source in sources[:3]:
            title = str(source.get("title") or source.get("url") or "未命名来源").strip()
            source_type = str(source.get("source_type") or "web")
            lines.append(f"- {title} ({source_type})")

    return "\n".join(lines).strip()


def summarize_confirmed_attributes(knowledge: dict[str, Any]) -> list[str]:
    confirmed_facts = normalize_confirmed_facts((knowledge or {}).get("confirmed_facts"))
    summaries: list[str] = []
    for field, payload in confirmed_facts.items():
        label = payload.get("field_label") or FACT_FIELD_LABELS.get(field, field)
        value = payload.get("value") or ""
        if value:
            summaries.append(f"{label}: {value}")
    return summaries


def get_unconfirmed_conflict_fields(knowledge: dict[str, Any]) -> list[str]:
    safe_knowledge = knowledge if isinstance(knowledge, dict) else {}
    confirmed_facts = normalize_confirmed_facts(safe_knowledge.get("confirmed_facts"))
    fields: list[str] = []
    for conflict in safe_knowledge.get("fact_conflicts", []) or []:
        field = str(conflict.get("field") or "").strip()
        if field and field not in confirmed_facts:
            fields.append(field)
    return fields


def build_conflict_safe_notes(knowledge: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for field in get_unconfirmed_conflict_fields(knowledge):
        label = FACT_FIELD_LABELS.get(field, field)
        notes.append(f"{label}: 存在多版本说法，建议以官方页或人工确认为准")
    return notes


def _strip_confirmed_note(text_facts: str) -> str:
    marker = "【已确认事实】"
    if marker not in text_facts:
        return text_facts.strip()
    return text_facts.split(marker, 1)[0].strip()


def apply_confirmed_facts_to_knowledge(knowledge: dict[str, Any]) -> dict[str, Any]:
    next_knowledge = deepcopy(knowledge or {})
    confirmed_facts = normalize_confirmed_facts(next_knowledge.get("confirmed_facts"))
    next_knowledge["confirmed_facts"] = confirmed_facts

    remaining_conflicts = []
    for conflict in next_knowledge.get("fact_conflicts", []) or []:
        if str(conflict.get("field") or "") not in confirmed_facts:
            remaining_conflicts.append(conflict)
    next_knowledge["fact_conflicts"] = remaining_conflicts

    core_attributes = dict(next_knowledge.get("core_attributes") or {})
    for field in get_unconfirmed_conflict_fields(next_knowledge):
        core_attributes.pop(field, None)
    for field, payload in confirmed_facts.items():
        core_attributes[field] = payload.get("value")
    next_knowledge["core_attributes"] = core_attributes

    text_facts = _strip_confirmed_note(str(next_knowledge.get("text_facts") or ""))
    confirmed_note = render_confirmed_facts_note(confirmed_facts)
    if confirmed_note:
        next_knowledge["text_facts"] = f"{text_facts}\n\n{confirmed_note}".strip()
    elif text_facts:
        next_knowledge["text_facts"] = text_facts

    next_knowledge["needs_fact_confirmation"] = bool(remaining_conflicts)
    if remaining_conflicts:
        next_knowledge["fact_review_status"] = "pending"
        next_knowledge["fact_confidence"] = "low"
    elif confirmed_facts:
        next_knowledge["fact_review_status"] = "confirmed"
        if str(next_knowledge.get("fact_confidence") or "medium") == "low":
            next_knowledge["fact_confidence"] = "medium"
    else:
        next_knowledge["fact_review_status"] = "clear"

    return next_knowledge


def merge_confirmed_fact_selection(
    knowledge: dict[str, Any],
    *,
    field: str,
    value: Any,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    next_knowledge = deepcopy(knowledge or {})
    confirmed_facts = normalize_confirmed_facts(next_knowledge.get("confirmed_facts"))
    confirmed_facts[field] = {
        "value": normalize_fact_value(field, value),
        "field_label": FACT_FIELD_LABELS.get(field, field),
        "sources": [str(item) for item in (sources or []) if str(item).strip()],
        "confirmed_at": datetime.now().isoformat(),
    }
    next_knowledge["confirmed_facts"] = confirmed_facts
    return apply_confirmed_facts_to_knowledge(next_knowledge)
