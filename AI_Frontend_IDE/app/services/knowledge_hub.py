"""Knowledge ingestion, review, and persistence helpers.

This module turns uploaded documents and retrieved evidence into a layered
knowledge model that the chat workflow can review before generation.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from langchain_core.documents import Document
from langgraph.store.postgres import AsyncPostgresStore

from app.agents.state import UIProjectState
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.config import settings
from app.services.rag_knowledge import trust_level_for_url
from app.services.retrieval_profiles import infer_retrieval_profile

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = ROOT / "runtime" / "knowledge_uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

KNOWLEDGE_SCOPE_SESSION = "session"
KNOWLEDGE_SCOPE_PERSISTENT = "persistent"
KNOWLEDGE_SCOPE_CANDIDATE = "candidate_session"

REVIEW_PENDING = "pending_review"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
REVIEW_DEFERRED = "deferred"
REVIEW_CONFIRMED = "confirmed"
REVIEW_CONFLICTED = "conflicted"
REVIEW_DISABLED = "disabled"
REVIEW_STALE = "stale"

SUPPORTED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".json", ".csv", ".xlsx"}
MAX_UPLOAD_SIZE_BYTES = 8 * 1024 * 1024

SEEDING_FIELD_LABELS = {
    "price": "价格与版本",
    "chipset": "CPU / SoC",
    "battery": "电池与续航",
    "charging": "充电",
    "display": "屏幕",
    "camera": "影像",
    "storage": "存储版本",
}

TRAVEL_FIELD_LABELS = {
    "location": "地点",
    "route": "路线建议",
    "hours": "开放时间",
    "transport": "交通",
    "ticket": "门票",
}

FIELD_ORDER = [
    "chipset",
    "battery",
    "charging",
    "display",
    "camera",
    "price",
    "storage",
    "location",
    "route",
    "hours",
    "transport",
    "ticket",
]

DEFAULT_STALE_WINDOWS = {
    "price": 7,
    "ticket": 7,
    "hours": 7,
    "transport": 14,
    "route": 14,
    "chipset": 90,
    "battery": 90,
    "charging": 90,
    "display": 90,
    "camera": 90,
    "storage": 90,
    "topic": 30,
}

STORE_NAMESPACE_ROOT = ("knowledge_hub", "persistent")
STORE_DOCS_NAMESPACE = (*STORE_NAMESPACE_ROOT, "documents")
STORE_RECORDS_NAMESPACE = (*STORE_NAMESPACE_ROOT, "records")
STORE_CONFLICT_NAMESPACE = (*STORE_NAMESPACE_ROOT, "conflicts")
STORE_INDEX_FIELDS = [
    "title",
    "entity_hint",
    "normalized_entity",
    "field_or_topic",
    "summary",
    "value",
    "source_title",
    "scene_hint",
    "kb_scope",
    "knowledge_scope",
    "review_status",
]

FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "price": (
        r"(?:价格|售价|发售价|起售价|定价)[:：]?\s*(?:¥|￥)?\s*([0-9]{2,6}(?:\.[0-9]+)?)",
        r"(?:¥|￥)\s*([0-9]{2,6}(?:\.[0-9]+)?)",
    ),
    "chipset": (
        r"((?:骁龙|麒麟|天玑|Snapdragon|Dimensity|A\d+)[^，。\n]{0,28})",
    ),
    "battery": (
        r"((?:电池(?:容量)?|续航)[^。\n]{0,24}(?:[0-9]{3,5}\s*mAh|[0-9]{1,2}\s*小时)[^。\n]{0,16})",
    ),
    "charging": (
        r"((?:快充|充电(?:功率)?|有线快充|无线快充)[^。\n]{0,24}(?:[0-9]{2,3}\s*W)[^。\n]{0,16})",
    ),
    "display": (
        r"((?:屏幕|显示|亮度|分辨率)[^。\n]{0,36})",
    ),
    "camera": (
        r"((?:影像|相机|主摄|长焦|超广角)[^。\n]{0,36})",
    ),
    "storage": (
        r"((?:存储|内存|版本)[^。\n]{0,36}(?:GB|TB)[^。\n]{0,24})",
    ),
    "location": (
        r"((?:地址|位于|地点|位置)[^。\n]{0,48})",
    ),
    "route": (
        r"((?:路线|顺序|先.+再.+|游览顺序|建议路线)[^。\n]{0,48})",
    ),
    "hours": (
        r"((?:开放时间|营业时间|开园时间|闭园时间)[^。\n]{0,48})",
    ),
    "transport": (
        r"((?:交通|地铁|公交|打车|自驾)[^。\n]{0,48})",
    ),
    "ticket": (
        r"((?:门票|票价|预约)[^。\n]{0,48})",
    ),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    value = dt or _now()
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slug(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", str(text or "").strip().lower()).strip("-")
    return normalized or uuid.uuid4().hex[:8]


def _coerce_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", name or "knowledge")
    return base[:120] or "knowledge"


def _source_type_for_upload(scope: str) -> str:
    return "user_kb_curated" if scope == KNOWLEDGE_SCOPE_PERSISTENT else "user_kb"


def _trust_level_for_source(source_type: str, locator: str | None = None) -> str:
    if source_type in {"user_provided", "user_kb_curated"}:
        return "high"
    if source_type == "user_kb":
        return "medium"
    if source_type == "web_search":
        return trust_level_for_url(locator or "")
    return "medium"


def _field_label(field: str) -> str:
    return SEEDING_FIELD_LABELS.get(field) or TRAVEL_FIELD_LABELS.get(field) or field.replace("_", " ")


def _field_stale_days(field: str) -> int:
    if field.startswith("topic::"):
        return DEFAULT_STALE_WINDOWS["topic"]
    return DEFAULT_STALE_WINDOWS.get(field, 30)


def _support_level_for_source(source_type: str) -> str:
    mapping = {
        "user_provided": "user_confirmed",
        "user_kb_curated": "user_kb_curated",
        "user_kb": "user_kb_curated",
        "official": "official",
        "structured_search": "structured_search",
        "review_ugc": "review_ugc",
        "web_search": "structured_search",
        "model_inference": "model_inference",
    }
    return mapping.get(source_type, "structured_search")


def _chunk_page_ref(index: int, section_title: str | None = None) -> str:
    if section_title:
        return section_title
    return f"chunk-{index + 1}"


def _extract_json_text(raw: bytes) -> str:
    try:
        payload = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return raw.decode("utf-8", errors="ignore")
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_csv_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return text
    if len(rows) == 1:
        return " | ".join(rows[0])
    headers = rows[0]
    lines: list[str] = []
    for row in rows[1:]:
        cells = []
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            if value:
                cells.append(f"{header}: {value}")
        if cells:
            lines.append("；".join(cells))
    return "\n".join(lines) if lines else text


def _extract_docx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    text_nodes = [node.text or "" for node in root.iter() if node.tag.endswith("}t")]
    return "\n".join(filter(None, text_nodes))


def _extract_xlsx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(node.itertext()).strip()
                for node in shared_root.iter()
                if node.tag.endswith("}si")
            ]

        lines: list[str] = []
        for sheet_name in [item for item in archive.namelist() if item.startswith("xl/worksheets/sheet") and item.endswith(".xml")]:
            sheet_root = ET.fromstring(archive.read(sheet_name))
            for row in [item for item in sheet_root.iter() if item.tag.endswith("}row")]:
                cells: list[str] = []
                for cell in [item for item in row if item.tag.endswith("}c")]:
                    value_node = next((child for child in cell if child.tag.endswith("}v")), None)
                    if value_node is None or value_node.text is None:
                        continue
                    value = value_node.text
                    if cell.attrib.get("t") == "s":
                        try:
                            value = shared_strings[int(value)]
                        except Exception:
                            pass
                    ref = cell.attrib.get("r") or ""
                    cells.append(f"{ref}: {value}")
                if cells:
                    lines.append("；".join(cells))
    return "\n".join(lines)


def _extract_pdf_text(raw: bytes) -> str:
    text = raw.decode("latin-1", errors="ignore")
    matches = re.findall(r"\(([^()]*)\)", text)
    cleaned = [item.strip() for item in matches if len(item.strip()) >= 3]
    if cleaned:
        return "\n".join(cleaned)
    return text


def _strip_html(text: str) -> str:
    no_scripts = re.sub(r"<(script|style)[^>]*>.*?</\\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_scripts)
    return re.sub(r"\s+", " ", no_tags).strip()


def _extract_url_text(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "XHS-Forge KnowledgeBot/1.0"})
    with urlopen(request, timeout=12) as response:
        body = response.read()
        content_type = str(response.headers.get("Content-Type") or "").lower()
    title = url
    text = body.decode("utf-8", errors="ignore")
    if "text/html" in content_type:
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() or title
        text = _strip_html(text)
    return title, text


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text or "") if part.strip()]
    if paragraphs:
        return paragraphs
    sentences = [part.strip() for part in re.split(r"(?<=[。！？.!?])\s+", text or "") if part.strip()]
    return sentences


def _chunk_text(text: str, *, section_title: str | None = None, max_chars: int = 900, overlap: int = 120) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return chunks
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current}\n{paragraph}".strip()
            continue
        if current:
            chunks.append({"section_title": section_title or "", "text": current})
        current = paragraph[-overlap:] + "\n" + paragraph if overlap and len(paragraph) > max_chars else paragraph
        if len(current) > max_chars:
            for start in range(0, len(current), max_chars - overlap):
                slice_text = current[start : start + max_chars].strip()
                if slice_text:
                    chunks.append({"section_title": section_title or "", "text": slice_text})
            current = ""
    if current:
        chunks.append({"section_title": section_title or "", "text": current})
    return chunks


def _choose_entity_type(entity_name: str, scene_hint: str) -> str:
    text = str(entity_name or "").lower()
    if any(token in text for token in ("mate", "iphone", "小米", "华为", "手机", "电视", "ultra", "pro", "max")):
        return "product/model"
    if any(token in text for token in ("公司", "brand", "品牌")):
        return "brand/company"
    return "product/model" if scene_hint == "seeding" else "topic"


def _estimate_review_recommendation(source_type: str, field_or_topic: str) -> bool:
    if source_type in {"user_provided", "user_kb_curated", "official"}:
        return True
    if field_or_topic in {"price", "chipset", "battery", "charging", "display", "camera"}:
        return True
    return False


def _extract_field_records(
    *,
    chunk_text: str,
    document_id: str,
    chunk_id: str,
    kb_scope: str,
    source_type: str,
    normalized_entity: str,
    entity_type: str,
    scene_hint: str,
    page_or_section: str,
    source_label: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    support_level = _support_level_for_source(source_type)
    trust_level = _trust_level_for_source(source_type, source_label)
    now_iso = _iso()
    text = chunk_text.strip()

    for field, patterns in FIELD_PATTERNS.items():
        if scene_hint == "seeding" and field in {"location", "route", "hours", "transport", "ticket"}:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = _coerce_text(match.group(1) if match.groups() else match.group(0))
            if not value:
                continue
            locator = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "page_or_section": page_or_section,
                "source_excerpt": text[:220],
            }
            knowledge_id = f"know_{uuid.uuid4().hex[:12]}"
            records.append(
                {
                    "knowledge_id": knowledge_id,
                    "record_id": knowledge_id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "entity_type": entity_type,
                    "normalized_entity": normalized_entity,
                    "field_or_topic": field,
                    "field_label": _field_label(field),
                    "value": value,
                    "summary": value,
                    "source_type": source_type,
                    "source_scope": source_type,
                    "support_level": support_level,
                    "trust_level": trust_level,
                    "knowledge_scope": kb_scope,
                    "review_status": REVIEW_PENDING if kb_scope == KNOWLEDGE_SCOPE_CANDIDATE else REVIEW_APPROVED,
                    "recommended": _estimate_review_recommendation(source_type, field),
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "stale_after_days": _field_stale_days(field),
                    "evidence_locator": locator,
                    "source_title": source_label,
                    "snippet": text[:220],
                    "used_by_blocks": [],
                }
            )
            break

    if records:
        return records

    sentence = _split_paragraphs(text)[0] if _split_paragraphs(text) else text[:220]
    topic_slug = _slug(sentence[:32])
    locator = {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "page_or_section": page_or_section,
        "source_excerpt": text[:220],
    }
    knowledge_id = f"know_{uuid.uuid4().hex[:12]}"
    field_or_topic = f"topic::{topic_slug}"
    return [
        {
            "knowledge_id": knowledge_id,
            "record_id": knowledge_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "entity_type": entity_type,
            "normalized_entity": normalized_entity,
            "field_or_topic": field_or_topic,
            "field_label": "补充主题",
            "value": sentence[:180],
            "summary": sentence[:180],
            "source_type": source_type,
            "source_scope": source_type,
            "support_level": support_level,
            "trust_level": trust_level,
            "knowledge_scope": kb_scope,
            "review_status": REVIEW_PENDING if kb_scope == KNOWLEDGE_SCOPE_CANDIDATE else REVIEW_APPROVED,
            "recommended": False,
            "created_at": now_iso,
            "updated_at": now_iso,
            "stale_after_days": _field_stale_days(field_or_topic),
            "evidence_locator": locator,
            "source_title": source_label,
            "snippet": text[:220],
            "used_by_blocks": [],
        }
    ]


def extract_candidate_records_from_text(
    *,
    title: str,
    text: str,
    entity_hint: str,
    scene_hint: str,
    source_type: str = "web_search",
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    normalized_entity = normalize_entity_name(entity_hint or title)
    entity_type = _choose_entity_type(normalized_entity, scene_hint)
    records: list[dict[str, Any]] = []
    for index, chunk_payload in enumerate(_chunk_text(text, section_title=title)):
        chunk_text = _coerce_text(chunk_payload.get("text"))
        if not chunk_text:
            continue
        chunk_id = f"{document_id}_chunk_{index + 1}"
        page_or_section = _chunk_page_ref(index, str(chunk_payload.get("section_title") or "").strip() or None)
        extracted = _extract_field_records(
            chunk_text=chunk_text,
            document_id=document_id,
            chunk_id=chunk_id,
            kb_scope=KNOWLEDGE_SCOPE_CANDIDATE,
            source_type=source_type,
            normalized_entity=normalized_entity,
            entity_type=entity_type,
            scene_hint=scene_hint,
            page_or_section=page_or_section,
            source_label=title,
        )
        if source_url:
            for item in extracted:
                locator = item.get("evidence_locator")
                if isinstance(locator, dict):
                    locator["source_url"] = source_url
        records.extend(extracted)
    return records


def _record_group_key(record: dict[str, Any]) -> str:
    return f"{record.get('normalized_entity') or ''}::{record.get('field_or_topic') or ''}"


def _record_priority(record: dict[str, Any]) -> tuple[int, int, str]:
    support_order = {
        "user_confirmed": 6,
        "user_kb_curated": 5,
        "official": 4,
        "structured_search": 3,
        "review_ugc": 2,
        "model_inference": 1,
    }
    trust_order = {"high": 3, "medium": 2, "low": 1}
    return (
        support_order.get(str(record.get("support_level") or ""), 0),
        trust_order.get(str(record.get("trust_level") or ""), 0),
        str(record.get("updated_at") or ""),
    )


def group_records(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        key = _record_group_key(item)
        bucket = grouped.setdefault(
            key,
            {
                "group_id": key,
                "normalized_entity": item.get("normalized_entity"),
                "entity_type": item.get("entity_type"),
                "field_or_topic": item.get("field_or_topic"),
                "field_label": item.get("field_label") or _field_label(str(item.get("field_or_topic") or "")),
                "records": [],
                "recommended_record_id": None,
                "review_status": item.get("review_status") or REVIEW_PENDING,
            },
        )
        bucket["records"].append(item)
    result: list[dict[str, Any]] = []
    for bucket in grouped.values():
        bucket["records"] = sorted(
            bucket["records"],
            key=_record_priority,
            reverse=True,
        )
        if bucket["records"]:
            bucket["recommended_record_id"] = bucket["records"][0].get("record_id")
        result.append(bucket)
    return sorted(
        result,
        key=lambda item: (
            FIELD_ORDER.index(str(item.get("field_or_topic"))) if str(item.get("field_or_topic")) in FIELD_ORDER else len(FIELD_ORDER),
            str(item.get("normalized_entity") or ""),
        ),
    )


def build_structured_slots_from_records(records: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    for group in group_records(records):
        field = str(group.get("field_or_topic") or "")
        if field.startswith("topic::"):
            continue
        best = next((item for item in group.get("records") or [] if str(item.get("review_status") or "") in {REVIEW_APPROVED, REVIEW_CONFIRMED}), None)
        if not best:
            best = (group.get("records") or [None])[0]
        if not isinstance(best, dict):
            continue
        slots[field] = {
            "scope": best.get("source_type") or best.get("source_scope") or "session_kb",
            "summary": best.get("summary") or best.get("value") or "",
            "title": best.get("source_title") or best.get("normalized_entity") or "",
            "url": (((best.get("evidence_locator") or {}) if isinstance(best.get("evidence_locator"), dict) else {}).get("source_url")) or "",
            "knowledge_id": best.get("record_id"),
        }
    return slots


def build_confirmed_facts_from_records(records: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    confirmed: dict[str, dict[str, Any]] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("review_status") or "")
        if status not in {REVIEW_APPROVED, REVIEW_CONFIRMED}:
            continue
        field = str(item.get("field_or_topic") or "")
        if field.startswith("topic::"):
            continue
        confirmed[field] = {
            "value": str(item.get("value") or item.get("summary") or ""),
            "field_label": str(item.get("field_label") or _field_label(field)),
            "sources": [str(item.get("source_title") or "")],
            "source_type": str(item.get("source_type") or ""),
            "support_level": str(item.get("support_level") or ""),
            "knowledge_id": str(item.get("record_id") or ""),
        }
    return confirmed


def build_knowledge_records_from_structured(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    for item in records or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("review_status") or "")
        if status not in {REVIEW_APPROVED, REVIEW_CONFIRMED}:
            continue
        derived.append(
            {
                "record_id": item.get("record_id"),
                "doc_type": "knowledge_fact",
                "entity_name": item.get("normalized_entity"),
                "category": item.get("field_or_topic"),
                "source": (((item.get("evidence_locator") or {}) if isinstance(item.get("evidence_locator"), dict) else {}).get("source_url")) or "",
                "source_scope": item.get("source_type") or "session_kb",
                "source_title": item.get("source_title") or item.get("normalized_entity"),
                "query": item.get("normalized_entity"),
                "title": f"{item.get('normalized_entity') or ''} · {item.get('field_label') or item.get('field_or_topic') or ''}".strip(),
                "snippet": item.get("summary") or item.get("value") or "",
                "trust_level": item.get("trust_level") or "medium",
                "ingest_mode": "knowledge_hub_structured",
                "updated_at": item.get("updated_at") or _iso(),
                "expires_at": _iso(_now() + timedelta(days=_field_stale_days(str(item.get("field_or_topic") or "")))),
                "ttl_seconds": _field_stale_days(str(item.get("field_or_topic") or "")) * 24 * 3600,
            }
        )
    return derived


def _record_is_active(record: dict[str, Any]) -> bool:
    status = str(record.get("review_status") or "")
    return status not in {REVIEW_REJECTED, REVIEW_DISABLED, REVIEW_STALE}


def filter_records(
    records: list[dict[str, Any]] | None,
    *,
    entity_name: str | None = None,
    required_fields: list[str] | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    normalized_entity = normalize_entity_name(entity_name or "")
    allowed_fields = {str(item) for item in (required_fields or []) if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for item in records or []:
        if not isinstance(item, dict):
            continue
        if normalized_entity:
            current_entity = normalize_entity_name(str(item.get("normalized_entity") or ""))
            if current_entity and current_entity != normalized_entity:
                continue
        field = str(item.get("field_or_topic") or "")
        if allowed_fields and field not in allowed_fields and not field.startswith("topic::"):
            continue
        if active_only and not _record_is_active(item):
            continue
        filtered.append(deepcopy(item))
    return filtered


def build_knowledge_plan(state: UIProjectState) -> dict[str, Any]:
    query = ""
    main_messages = state.get("main_messages") or []
    if main_messages:
        latest = getattr(main_messages[-1], "content", "")
        query = latest if isinstance(latest, str) else str(latest)
    active_archetype = str(state.get("active_archetype") or "seeding")
    existing_knowledge = state.get("retrieved_knowledge") or {}
    entity_name = normalize_entity_name((existing_knowledge or {}).get("entity_name") or query)
    profile = infer_retrieval_profile(
        user_query=query,
        entity_name=entity_name or query,
        active_archetype=active_archetype,
    )
    required_fields = list(profile.get("critical_slot_keys") or [])
    high_risk_fields = []
    high_risk_fields.extend(["price", "chipset", "battery"])
    preferred_sources = ["user_provided_facts", "session_kb", "persistent_kb", "knowledge_snapshot/cache", "web_search"]
    return {
        "goal_summary": f"围绕「{entity_name or query or '当前主题'}」先补齐最影响成稿质量的事实，再决定如何表达。",
        "required_fields": required_fields,
        "preferred_sources": preferred_sources,
        "high_risk_fields": high_risk_fields,
        "missing_user_inputs": [],
        "review_required": True,
        "knowledge_budget": min(5, max(3, len(required_fields) or 3)),
        "retrieval_profile": profile.get("profile_name") or "digital_grounded",
        "field_labels": profile.get("slot_labels") or {},
        "entity_name": entity_name or query,
    }


def records_from_user_provided_facts(
    user_facts: dict[str, Any] | None,
    *,
    entity_name: str,
    active_archetype: str,
) -> list[dict[str, Any]]:
    normalized_entity = normalize_entity_name(entity_name)
    entity_type = _choose_entity_type(normalized_entity, active_archetype)
    now_iso = _iso()
    records: list[dict[str, Any]] = []
    for key, value in (user_facts or {}).items():
        if key in {"source", "requested_by"}:
            continue
        if isinstance(value, list):
            normalized_value = " / ".join([_coerce_text(item) for item in value if _coerce_text(item)])
        else:
            normalized_value = _coerce_text(value)
        if not normalized_value:
            continue
        field = str(key).replace("_custom", "")
        if field == "raw_text":
            field = "topic::user_context"
        knowledge_id = f"know_{uuid.uuid4().hex[:12]}"
        records.append(
            {
                "knowledge_id": knowledge_id,
                "record_id": knowledge_id,
                "entity_type": entity_type,
                "normalized_entity": normalized_entity,
                "field_or_topic": field,
                "field_label": _field_label(field),
                "value": normalized_value,
                "summary": normalized_value,
                "source_type": "user_provided",
                "source_scope": "user_provided_facts",
                "support_level": "user_confirmed",
                "trust_level": "high",
                "knowledge_scope": KNOWLEDGE_SCOPE_SESSION,
                "review_status": REVIEW_CONFIRMED,
                "recommended": True,
                "created_at": now_iso,
                "updated_at": now_iso,
                "stale_after_days": _field_stale_days(field),
                "evidence_locator": {
                    "source_excerpt": normalized_value[:220],
                    "source_url": "",
                    "source_label": "用户直接补充",
                },
                "source_title": "用户直接补充",
                "snippet": normalized_value[:220],
                "used_by_blocks": [],
            }
        )
    return records


def query_session_records(knowledge: dict[str, Any] | None, *, entity_name: str, required_fields: list[str] | None = None) -> list[dict[str, Any]]:
    session_payload = ((knowledge or {}).get("session_kb") or {}) if isinstance(knowledge, dict) else {}
    items = [
        deepcopy(item)
        for item in (session_payload.get("records") or [])
        if isinstance(item, dict) and str(item.get("review_status") or "") in {REVIEW_APPROVED, REVIEW_CONFIRMED}
    ]
    return filter_records(items, entity_name=entity_name, required_fields=required_fields, active_only=True)


def query_candidate_records(
    knowledge: dict[str, Any] | None,
    *,
    entity_name: str,
    required_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    candidate_payload = ((knowledge or {}).get("candidate_session_kb") or {}) if isinstance(knowledge, dict) else {}
    items = [
        deepcopy(item)
        for item in (candidate_payload.get("records") or [])
        if isinstance(item, dict) and str(item.get("review_status") or "") == REVIEW_PENDING
    ]
    return filter_records(items, entity_name=entity_name, required_fields=required_fields, active_only=True)


def query_persistent_records(
    snapshot: dict[str, Any] | None,
    *,
    entity_name: str,
    required_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    items = [
        deepcopy(item)
        for item in ((snapshot or {}).get("records") or [])
        if isinstance(item, dict) and str(item.get("review_status") or REVIEW_CONFIRMED) in {REVIEW_APPROVED, REVIEW_CONFIRMED}
    ]
    return filter_records(items, entity_name=entity_name, required_fields=required_fields, active_only=True)


@dataclass
class ParsedKnowledgeSource:
    document_id: str
    title: str
    file_name: str
    source_type: str
    kb_scope: str
    raw_path: str
    text: str
    chunks: list[dict[str, Any]]
    records: list[dict[str, Any]]
    entity_hint: str
    scene_hint: str


class KnowledgeHubService:
    def __init__(self) -> None:
        self._persistent_docs: dict[str, dict[str, Any]] = {}
        self._persistent_records: dict[str, list[dict[str, Any]]] = {}
        self._persistent_conflicts: dict[str, list[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._store: AsyncPostgresStore | None = None

    def bind_store(self, store: AsyncPostgresStore | None) -> None:
        self._store = store

    @asynccontextmanager
    async def _resolve_store(self):
        if self._store is not None:
            yield self._store
            return
        async with AsyncPostgresStore.from_conn_string(settings.POSTGRES_URL) as store:
            await store.setup()
            yield store

    async def _store_put(
        self,
        namespace: tuple[str, ...],
        key: str,
        value: dict[str, Any],
    ) -> None:
        async with self._resolve_store() as store:
            await store.aput(namespace, key, value, index=STORE_INDEX_FIELDS)

    async def _store_delete(self, namespace: tuple[str, ...], key: str) -> None:
        async with self._resolve_store() as store:
            await store.adelete(namespace, key)

    async def _store_get(self, namespace: tuple[str, ...], key: str) -> dict[str, Any] | None:
        async with self._resolve_store() as store:
            item = await store.aget(namespace, key)
        value = getattr(item, "value", None)
        return deepcopy(value) if isinstance(value, dict) else None

    async def _store_search(
        self,
        namespace_prefix: tuple[str, ...],
        *,
        filter: dict[str, Any] | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        async with self._resolve_store() as store:
            items = await store.asearch(namespace_prefix, filter=filter or None, limit=limit)
        values: list[dict[str, Any]] = []
        for item in items:
            value = getattr(item, "value", None)
            if isinstance(value, dict):
                values.append(deepcopy(value))
        return values

    async def _save_raw_file(self, *, content: bytes, file_name: str, kb_scope: str) -> str:
        subdir = UPLOAD_ROOT / ("persistent" if kb_scope == KNOWLEDGE_SCOPE_PERSISTENT else "session")
        subdir.mkdir(parents=True, exist_ok=True)
        target = subdir / f"{uuid.uuid4().hex[:8]}_{_safe_filename(file_name)}"
        target.write_bytes(content)
        return str(target)

    async def parse_upload(
        self,
        *,
        file_name: str,
        content: bytes,
        kb_scope: str,
        source_type: str,
        entity_hint: str,
        scene_hint: str,
        thread_id: str | None = None,
    ) -> ParsedKnowledgeSource:
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
            raise ValueError(f"暂不支持 {suffix or '该类型'} 文件")
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError("文件过大，请控制在 8MB 内")

        raw_path = await self._save_raw_file(content=content, file_name=file_name, kb_scope=kb_scope)
        if suffix in {".txt", ".md"}:
            text = content.decode("utf-8", errors="ignore")
        elif suffix == ".json":
            text = _extract_json_text(content)
        elif suffix == ".csv":
            text = _extract_csv_text(content)
        elif suffix == ".docx":
            text = _extract_docx_text(content)
        elif suffix == ".xlsx":
            text = _extract_xlsx_text(content)
        elif suffix == ".pdf":
            text = _extract_pdf_text(content)
        else:
            text = content.decode("utf-8", errors="ignore")

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        normalized_entity = normalize_entity_name(entity_hint or Path(file_name).stem)
        entity_type = _choose_entity_type(normalized_entity, scene_hint)
        chunk_dicts = _chunk_text(text, section_title=Path(file_name).stem)
        records: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        for index, chunk_payload in enumerate(chunk_dicts):
            chunk_text = _coerce_text(chunk_payload.get("text"))
            if not chunk_text:
                continue
            chunk_id = f"{document_id}_chunk_{index + 1}"
            page_or_section = _chunk_page_ref(index, str(chunk_payload.get("section_title") or "").strip() or None)
            chunks.append(
                {
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "page_content": chunk_text,
                    "metadata": {
                        "document_id": document_id,
                        "chunk_id": chunk_id,
                        "source_type": source_type,
                        "kb_scope": kb_scope,
                        "thread_id": thread_id or "",
                        "entity_hint": normalized_entity,
                        "scene_hint": scene_hint,
                        "page_or_section": page_or_section,
                        "source_path": raw_path,
                        "file_name": file_name,
                    },
                }
            )
            records.extend(
                _extract_field_records(
                    chunk_text=chunk_text,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    # 上传资料先进入候选知识，走同一条审查主链；
                    # 长期作用域只影响原始资料落盘和后续升格目标，不跳过审查。
                    kb_scope=KNOWLEDGE_SCOPE_CANDIDATE,
                    source_type=source_type,
                    normalized_entity=normalized_entity,
                    entity_type=entity_type,
                    scene_hint=scene_hint,
                    page_or_section=page_or_section,
                    source_label=file_name,
                )
            )

        return ParsedKnowledgeSource(
            document_id=document_id,
            title=Path(file_name).stem,
            file_name=file_name,
            source_type=source_type,
            kb_scope=kb_scope,
            raw_path=raw_path,
            text=text,
            chunks=chunks,
            records=records,
            entity_hint=normalized_entity,
            scene_hint=scene_hint,
        )

    async def parse_text_input(
        self,
        *,
        title: str,
        text: str,
        kb_scope: str,
        source_type: str,
        entity_hint: str,
        scene_hint: str,
        thread_id: str | None = None,
    ) -> ParsedKnowledgeSource:
        content = text.encode("utf-8")
        return await self.parse_upload(
            file_name=f"{_safe_filename(title or 'knowledge')}.txt",
            content=content,
            kb_scope=kb_scope,
            source_type=source_type,
            entity_hint=entity_hint,
            scene_hint=scene_hint,
            thread_id=thread_id,
        )

    async def parse_url_input(
        self,
        *,
        url: str,
        kb_scope: str,
        entity_hint: str,
        scene_hint: str,
        thread_id: str | None = None,
    ) -> ParsedKnowledgeSource:
        try:
            title, text = await asyncio.to_thread(_extract_url_text, url)
        except URLError as exc:
            raise ValueError(f"抓取资料失败：{exc.reason}") from exc
        except Exception as exc:
            raise ValueError(f"抓取资料失败：{exc}") from exc
        parsed = await self.parse_text_input(
            title=title or urlparse(url).netloc or "web-knowledge",
            text=text,
            kb_scope=kb_scope,
            source_type=_source_type_for_upload(kb_scope),
            entity_hint=entity_hint,
            scene_hint=scene_hint,
            thread_id=thread_id,
        )
        for chunk in parsed.chunks:
            chunk["metadata"]["source_url"] = url
        for record in parsed.records:
            locator = record.get("evidence_locator")
            if isinstance(locator, dict):
                locator["source_url"] = url
            record["source_title"] = title or url
        return parsed

    async def index_chunks(self, chunks: list[dict[str, Any]], vector_store: Any | None) -> int:
        if not vector_store or not chunks:
            return 0
        docs = [
            Document(page_content=str(item.get("page_content") or ""), metadata=dict(item.get("metadata") or {}))
            for item in chunks
            if str(item.get("page_content") or "").strip()
        ]
        if not docs:
            return 0
        try:
            await vector_store.aadd_documents(docs)
            return len(docs)
        except Exception:
            return 0

    async def upsert_persistent_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        promoted = 0
        conflicts = 0
        async with self._lock:
            for record in records:
                entity = normalize_entity_name(str(record.get("normalized_entity") or ""))
                if not entity:
                    continue
                field_or_topic = str(record.get("field_or_topic") or "")
                persistent_record = deepcopy(record)
                persistent_record["knowledge_scope"] = KNOWLEDGE_SCOPE_PERSISTENT
                persistent_record["review_status"] = REVIEW_CONFIRMED
                persistent_record["updated_at"] = _iso()
                persistent_record["stale_after_days"] = int(
                    persistent_record.get("stale_after_days") or _field_stale_days(field_or_topic)
                )
                try:
                    existing = await self._store_search(
                        STORE_RECORDS_NAMESPACE,
                        filter={
                            "normalized_entity": entity,
                            "field_or_topic": field_or_topic,
                        },
                        limit=50,
                    )
                except Exception:
                    existing = deepcopy(self._persistent_records.get(entity, []))

                exact_match = next(
                    (
                        item
                        for item in existing
                        if str(item.get("field_or_topic") or "") == field_or_topic
                        and str(item.get("value") or "") == str(persistent_record.get("value") or "")
                    ),
                    None,
                )
                if exact_match:
                    exact_match["updated_at"] = _iso()
                    self._persistent_records.setdefault(entity, [])
                    deduped = {
                        str(item.get("record_id") or f"{entity}:{field_or_topic}"): item
                        for item in [*self._persistent_records.get(entity, []), exact_match]
                    }
                    self._persistent_records[entity] = list(deduped.values())
                    try:
                        await self._store_put(
                            STORE_RECORDS_NAMESPACE,
                            str(exact_match.get("record_id") or exact_match.get("knowledge_id") or uuid.uuid4().hex),
                            exact_match,
                        )
                    except Exception:
                        pass
                    continue

                conflict_match = next(
                    (
                        item
                        for item in existing
                        if str(item.get("field_or_topic") or "") == field_or_topic
                        and str(item.get("value") or "") != str(persistent_record.get("value") or "")
                    ),
                    None,
                )
                if conflict_match:
                    conflicts += 1
                    group_id = f"conflict::{entity}::{field_or_topic}"
                    conflict_entry = {
                        "group_id": group_id,
                        "reason": "value_conflict",
                        "recommended_record_id": conflict_match.get("record_id"),
                        "old_record": deepcopy(conflict_match),
                        "new_record": deepcopy(persistent_record),
                        "normalized_entity": entity,
                        "field_or_topic": field_or_topic,
                        "updated_at": _iso(),
                    }
                    bucket = self._persistent_conflicts.setdefault(group_id, [])
                    bucket.append(conflict_entry)
                    try:
                        conflict_key = str(
                            persistent_record.get("record_id")
                            or persistent_record.get("knowledge_id")
                            or uuid.uuid4().hex
                        )
                        await self._store_put(STORE_CONFLICT_NAMESPACE, conflict_key, conflict_entry)
                    except Exception:
                        pass
                    continue

                self._persistent_records.setdefault(entity, []).append(persistent_record)
                promoted += 1
                try:
                    await self._store_put(
                        STORE_RECORDS_NAMESPACE,
                        str(persistent_record.get("record_id") or persistent_record.get("knowledge_id") or uuid.uuid4().hex),
                        persistent_record,
                    )
                except Exception:
                    pass
            return {
                "promoted_count": promoted,
                "conflict_count": conflicts,
            }

    async def register_persistent_document(self, parsed: ParsedKnowledgeSource) -> None:
        document_payload = {
            "document_id": parsed.document_id,
            "title": parsed.title,
            "file_name": parsed.file_name,
            "entity_hint": parsed.entity_hint,
            "scene_hint": parsed.scene_hint,
            "source_type": parsed.source_type,
            "kb_scope": parsed.kb_scope,
            "raw_path": parsed.raw_path,
            "chunk_count": len(parsed.chunks),
            "created_at": _iso(),
            "normalized_entity": normalize_entity_name(parsed.entity_hint or parsed.title),
        }
        async with self._lock:
            self._persistent_docs[parsed.document_id] = document_payload
            try:
                await self._store_put(STORE_DOCS_NAMESPACE, parsed.document_id, document_payload)
            except Exception:
                pass

    async def list_persistent_snapshot(self, *, entity_name: str | None = None) -> dict[str, Any]:
        normalized = normalize_entity_name(entity_name or "") if entity_name else ""
        try:
            if normalized:
                records = await self._store_search(
                    STORE_RECORDS_NAMESPACE,
                    filter={"normalized_entity": normalized},
                    limit=200,
                )
                conflicts = await self._store_search(
                    STORE_CONFLICT_NAMESPACE,
                    filter={"normalized_entity": normalized},
                    limit=100,
                )
                documents = await self._store_search(
                    STORE_DOCS_NAMESPACE,
                    filter={"normalized_entity": normalized},
                    limit=100,
                )
            else:
                records = await self._store_search(STORE_RECORDS_NAMESPACE, limit=500)
                conflicts = await self._store_search(STORE_CONFLICT_NAMESPACE, limit=200)
                documents = await self._store_search(STORE_DOCS_NAMESPACE, limit=200)
        except Exception:
            async with self._lock:
                if normalized:
                    records = deepcopy(self._persistent_records.get(normalized, []))
                    conflicts = [
                        item
                        for key, values in self._persistent_conflicts.items()
                        if normalized in key
                        for item in deepcopy(values)
                    ]
                    documents = [
                        deepcopy(item)
                        for item in self._persistent_docs.values()
                        if normalize_entity_name(str(item.get("entity_hint") or "")) == normalized
                    ]
                else:
                    records = [deepcopy(item) for values in self._persistent_records.values() for item in values]
                    conflicts = [item for values in self._persistent_conflicts.values() for item in deepcopy(values)]
                    documents = [deepcopy(item) for item in self._persistent_docs.values()]
        return {
            "records": records,
            "groups": group_records(records),
            "review_queue": conflicts,
            "documents": documents,
            "record_count": len(records),
        }

    def build_demo_pack_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "pack_id": "digital_mate60",
                "title": "数码测评 Demo 包",
                "scenario": "seeding",
                "documents": [
                    {
                        "title": "Mate 60 参数表",
                        "entity_hint": "华为 Mate 60",
                        "text": "产品：华为 Mate 60\n价格：5999\n处理器：麒麟芯片\n电池容量：4750mAh\n充电功率：66W\n屏幕：LTPO OLED 高刷屏\n影像：主摄升级，长焦表现稳定\n存储版本：12GB+512GB",
                    },
                    {
                        "title": "Mate 60 体验摘要",
                        "entity_hint": "华为 Mate 60",
                        "text": "影像风格更稳，续航表现扎实，价格门槛偏高但质感在线。对比时要重点写影像、续航和价格。",
                    },
                ],
            },
            {
                "pack_id": "digital_xiaomi14",
                "title": "数码对比 Demo 包",
                "scenario": "seeding",
                "documents": [
                    {
                        "title": "小米 14 参数表",
                        "entity_hint": "小米 14",
                        "text": "产品：小米 14\n价格：3999 起\n处理器：第三代骁龙 8\n电池容量：4610mAh\n充电功率：90W 有线\n屏幕：高亮高刷直屏\n影像：徕卡影像风格，主摄表现稳定\n存储版本：8GB+256GB 起",
                    },
                    {
                        "title": "小米 14 对比摘要",
                        "entity_hint": "小米 14",
                        "text": "性能释放积极，充电速度更激进，价格门槛更低。对比华为 Mate 60 时要重点看性能价格比、充电和系统偏好。",
                    },
                ],
            },
        ]

    def build_demo_eval_sets(self) -> list[dict[str, Any]]:
        return [
            {
                "pack_id": "digital_mate60",
                "title": "数码测评 Golden Eval Set",
                "scenario": "seeding",
                "questions": [
                    {
                        "id": "mate60_worth_buying",
                        "question": "华为 Mate 60 值不值得买？",
                        "expected_facts": {
                            "price": "5999",
                            "battery": "4750mAh",
                            "charging": "66W",
                        },
                        "expected_answer_points": [
                            "提到价格门槛",
                            "提到影像与续航",
                            "结论偏购买判断而非纯参数罗列",
                        ],
                        "forbidden_hallucinations": [
                            "编造具体跑分",
                            "编造不存在的官方优惠",
                        ],
                    },
                ],
            },
            {
                "pack_id": "digital_xiaomi14",
                "title": "数码对比 Golden Eval Set",
                "scenario": "seeding",
                "questions": [
                    {
                        "id": "xiaomi14_compare",
                        "question": "把小米 14 和华为 Mate 60 放在一起做购买判断",
                        "expected_facts": {
                            "price": "3999 起",
                            "battery": "4610mAh",
                            "charging": "90W",
                        },
                        "expected_answer_points": [
                            "提到价格门槛更低",
                            "提到性能价格比或充电速度",
                            "结论偏购买判断而非纯参数罗列",
                        ],
                        "forbidden_hallucinations": [
                            "编造不存在的官方优惠",
                            "编造未提供的对比跑分",
                        ],
                    },
                ],
            },
        ]


knowledge_hub_service = KnowledgeHubService()


def merge_candidate_records_into_retrieved(
    retrieved_knowledge: dict[str, Any] | None,
    *,
    knowledge_plan: dict[str, Any] | None = None,
    candidate_records: list[dict[str, Any]] | None = None,
    session_records: list[dict[str, Any]] | None = None,
    persistent_snapshot: dict[str, Any] | None = None,
    appended_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    def _dedupe_by_identity(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for item in records:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("knowledge_scope") or ""),
                str(item.get("normalized_entity") or ""),
                str(item.get("field_or_topic") or ""),
                str(item.get("value") or item.get("summary") or ""),
            )
            deduped[key] = item
        return list(deduped.values())

    knowledge = deepcopy(retrieved_knowledge or {})
    if knowledge_plan:
        knowledge["knowledge_plan"] = deepcopy(knowledge_plan)
    candidate_payload = deepcopy(knowledge.get("candidate_session_kb") or {})
    existing_candidate_records = [item for item in (candidate_payload.get("records") or []) if isinstance(item, dict)]
    merged_candidate = _dedupe_by_identity(existing_candidate_records + [deepcopy(item) for item in (candidate_records or []) if isinstance(item, dict)])
    candidate_payload["records"] = merged_candidate
    candidate_payload["groups"] = group_records(merged_candidate)
    candidate_payload["record_count"] = len(merged_candidate)
    candidate_payload["pending_count"] = len([item for item in merged_candidate if str(item.get("review_status") or "") == REVIEW_PENDING])
    if appended_documents:
        candidate_payload["documents"] = [*list(candidate_payload.get("documents") or []), *deepcopy(appended_documents)]
    knowledge["candidate_session_kb"] = candidate_payload

    session_payload = deepcopy(knowledge.get("session_kb") or {})
    existing_session_records = [item for item in (session_payload.get("records") or []) if isinstance(item, dict)]
    merged_session = _dedupe_by_identity(existing_session_records + [deepcopy(item) for item in (session_records or []) if isinstance(item, dict)])
    session_payload["records"] = merged_session
    session_payload["groups"] = group_records(merged_session)
    session_payload["record_count"] = len(merged_session)
    session_payload["knowledge_version"] = f"kv_{uuid.uuid4().hex[:8]}"
    if appended_documents and session_records:
        session_payload["documents"] = [*list(session_payload.get("documents") or []), *deepcopy(appended_documents)]
    knowledge["session_kb"] = session_payload

    if persistent_snapshot:
        knowledge["persistent_kb"] = deepcopy(persistent_snapshot)

    structured_records = [*merged_session]
    knowledge["structured_knowledge_records"] = structured_records
    knowledge["fact_slots"] = {
        **(knowledge.get("fact_slots") or {}),
        **build_structured_slots_from_records(structured_records),
    }
    knowledge["confirmed_facts"] = {
        **(knowledge.get("confirmed_facts") or {}),
        **build_confirmed_facts_from_records(structured_records),
    }
    structured_records_for_display = build_knowledge_records_from_structured(structured_records)
    existing_records = [item for item in (knowledge.get("knowledge_records") or []) if isinstance(item, dict)]
    dedupe_keyed = {(str(item.get("record_id") or ""), str(item.get("title") or "")): item for item in [*existing_records, *structured_records_for_display]}
    knowledge["knowledge_records"] = list(dedupe_keyed.values())
    return knowledge


def apply_knowledge_review_decision(
    retrieved_knowledge: dict[str, Any] | None,
    *,
    decision: str,
    record_ids: list[str] | None = None,
) -> dict[str, Any]:
    knowledge = deepcopy(retrieved_knowledge or {})
    candidate_payload = deepcopy(knowledge.get("candidate_session_kb") or {})
    session_payload = deepcopy(knowledge.get("session_kb") or {})
    candidate_records = [deepcopy(item) for item in (candidate_payload.get("records") or []) if isinstance(item, dict)]
    session_records = [deepcopy(item) for item in (session_payload.get("records") or []) if isinstance(item, dict)]

    wanted = {str(item) for item in (record_ids or []) if str(item).strip()}
    approved_batch: list[dict[str, Any]] = []

    if decision == "approve_recommended":
        grouped = group_records(candidate_records)
        wanted = {
            str(group.get("recommended_record_id") or "")
            for group in grouped
            if str(group.get("recommended_record_id") or "").strip()
        }
    elif decision in {"approve_selected", "reject_selected", "defer_selected"} and not wanted:
        return knowledge

    next_candidate_records: list[dict[str, Any]] = []
    for item in candidate_records:
        record_id = str(item.get("record_id") or "")
        if decision == "defer_all":
            item["review_status"] = REVIEW_DEFERRED
            next_candidate_records.append(item)
            continue
        if decision in {"approve_recommended", "approve_selected"} and record_id in wanted:
            approved = deepcopy(item)
            approved["review_status"] = REVIEW_APPROVED
            approved["knowledge_scope"] = KNOWLEDGE_SCOPE_SESSION
            approved_batch.append(approved)
            next_candidate_records.append({**item, "review_status": REVIEW_APPROVED})
            continue
        if decision == "reject_selected" and record_id in wanted:
            next_candidate_records.append({**item, "review_status": REVIEW_REJECTED})
            continue
        if decision == "defer_selected" and record_id in wanted:
            next_candidate_records.append({**item, "review_status": REVIEW_DEFERRED})
            continue
        next_candidate_records.append(item)

    deduped_session: dict[tuple[str, str, str], dict[str, Any]] = {
        (
            str(item.get("normalized_entity") or ""),
            str(item.get("field_or_topic") or ""),
            str(item.get("value") or ""),
        ): item
        for item in session_records
    }
    for item in approved_batch:
        deduped_session[
            (
                str(item.get("normalized_entity") or ""),
                str(item.get("field_or_topic") or ""),
                str(item.get("value") or ""),
            )
        ] = item

    candidate_payload["records"] = next_candidate_records
    candidate_payload["groups"] = group_records(next_candidate_records)
    candidate_payload["record_count"] = len(next_candidate_records)
    candidate_payload["pending_count"] = len(
        [item for item in next_candidate_records if str(item.get("review_status") or "") == REVIEW_PENDING]
    )
    session_payload["records"] = list(deduped_session.values())
    session_payload["groups"] = group_records(session_payload["records"])
    session_payload["record_count"] = len(session_payload["records"])
    session_payload["knowledge_version"] = f"kv_{uuid.uuid4().hex[:8]}"
    knowledge["candidate_session_kb"] = candidate_payload
    knowledge["session_kb"] = session_payload
    knowledge["structured_knowledge_records"] = deepcopy(session_payload["records"])
    knowledge["fact_slots"] = {
        **(knowledge.get("fact_slots") or {}),
        **build_structured_slots_from_records(session_payload["records"]),
    }
    knowledge["confirmed_facts"] = {
        **(knowledge.get("confirmed_facts") or {}),
        **build_confirmed_facts_from_records(session_payload["records"]),
    }
    structured_records_for_display = build_knowledge_records_from_structured(session_payload["records"])
    existing_records = [item for item in (knowledge.get("knowledge_records") or []) if isinstance(item, dict)]
    dedupe_keyed = {(str(item.get("record_id") or ""), str(item.get("title") or "")): item for item in [*existing_records, *structured_records_for_display]}
    knowledge["knowledge_records"] = list(dedupe_keyed.values())
    return knowledge


def select_records_from_candidate(
    retrieved_knowledge: dict[str, Any] | None,
    *,
    record_ids: list[str] | None = None,
    normalized_entity: str | None = None,
    field_or_topic: str | None = None,
) -> list[dict[str, Any]]:
    candidate_payload = ((retrieved_knowledge or {}).get("candidate_session_kb") or {}) if isinstance(retrieved_knowledge, dict) else {}
    records = [deepcopy(item) for item in (candidate_payload.get("records") or []) if isinstance(item, dict)]
    selected: list[dict[str, Any]] = []
    wanted_ids = {str(item) for item in (record_ids or []) if str(item).strip()}
    normalized = normalize_entity_name(normalized_entity or "")
    for item in records:
        if wanted_ids and str(item.get("record_id") or "") not in wanted_ids:
            continue
        if normalized and normalize_entity_name(str(item.get("normalized_entity") or "")) != normalized:
            continue
        if field_or_topic and str(item.get("field_or_topic") or "") != str(field_or_topic):
            continue
        selected.append(item)
    return selected


def select_records_from_session(
    retrieved_knowledge: dict[str, Any] | None,
    *,
    record_ids: list[str] | None = None,
    normalized_entity: str | None = None,
    field_or_topic: str | None = None,
) -> list[dict[str, Any]]:
    session_payload = ((retrieved_knowledge or {}).get("session_kb") or {}) if isinstance(retrieved_knowledge, dict) else {}
    records = [deepcopy(item) for item in (session_payload.get("records") or []) if isinstance(item, dict)]
    selected: list[dict[str, Any]] = []
    wanted_ids = {str(item) for item in (record_ids or []) if str(item).strip()}
    normalized = normalize_entity_name(normalized_entity or "")
    for item in records:
        if wanted_ids and str(item.get("record_id") or "") not in wanted_ids:
            continue
        if normalized and normalize_entity_name(str(item.get("normalized_entity") or "")) != normalized:
            continue
        if field_or_topic and str(item.get("field_or_topic") or "") != str(field_or_topic):
            continue
        selected.append(item)
    return selected
