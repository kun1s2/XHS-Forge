"""Knowledge record helpers for preload/task-ingest RAG flows.

The RAG layer in XHS-Forge stores reusable evidence, not final generated notes.
This module keeps the storage model explicit so retrieval, freshness, evaluation,
and UI diagnostics can all speak the same language.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
import hashlib


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def trust_level_for_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if not host:
        return "low"
    official_hints = (
        ".gov.cn",
        ".gov",
        ".edu",
        ".edu.cn",
        "official",
        "huawei.com",
        "apple.com",
        "sony.com",
        "amap.com",
    )
    if any(hint in host for hint in official_hints):
        return "high"
    if any(hint in host for hint in ("zhihu.com", "bilibili.com", "xiaohongshu.com", "weibo.com")):
        return "medium"
    return "medium"


def ttl_for_doc_type(doc_type: str) -> int:
    if doc_type == "trend":
        return 6 * 3600
    if doc_type == "fact":
        return 30 * 24 * 3600
    if doc_type == "opinion_summary":
        return 7 * 24 * 3600
    if doc_type == "pattern":
        return 90 * 24 * 3600
    return 24 * 3600


def infer_doc_type(scope: str, query: str = "") -> str:
    scope_text = str(scope or "").lower()
    query_text = str(query or "").lower()
    if scope_text in {"official", "spec", "location"}:
        return "fact"
    if "争议" in query_text or "评价" in query_text or scope_text in {"review", "opinion"}:
        return "opinion_summary"
    if "热点" in query_text or "趋势" in query_text:
        return "trend"
    return "fact"


def build_knowledge_record(
    *,
    entity_name: str,
    query: str,
    title: str,
    url: str,
    snippet: str,
    scope: str,
    scenario: str,
    ingest_mode: str,
    doc_type: str | None = None,
    content: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    resolved_doc_type = doc_type or infer_doc_type(scope, query)
    issued_at = _parse_iso(updated_at) or _utc_now()
    ttl_seconds = ttl_for_doc_type(resolved_doc_type)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    digest = hashlib.sha1(f"{entity_name}|{url}|{title}|{scope}".encode("utf-8")).hexdigest()[:16]
    return {
        "record_id": f"rag_{digest}",
        "doc_type": resolved_doc_type,
        "entity_name": entity_name,
        "scenario": scenario or "general",
        "category": scope or "general",
        "source": url,
        "source_scope": scope or "general",
        "source_title": title,
        "query": query,
        "title": title,
        "snippet": snippet,
        "content": content or snippet or title,
        "trust_level": trust_level_for_url(url),
        "ingest_mode": ingest_mode,
        "updated_at": _iso(issued_at),
        "expires_at": _iso(expires_at),
        "ttl_seconds": ttl_seconds,
    }


def dedupe_knowledge_records(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        title = str(item.get("title") or item.get("source_title") or "").strip()
        if not source or not title:
            continue
        key = (source, title)
        existing = deduped.get(key)
        if not existing:
            deduped[key] = deepcopy(item)
            continue
        merged = deepcopy(existing)
        for field in ("snippet", "content", "query", "scenario", "category", "source_scope", "doc_type"):
            if not merged.get(field) and item.get(field):
                merged[field] = item[field]
        trust_order = {"high": 3, "medium": 2, "low": 1}
        if trust_order.get(str(item.get("trust_level") or "low"), 1) > trust_order.get(str(merged.get("trust_level") or "low"), 1):
            merged["trust_level"] = item.get("trust_level")
        expires_existing = _parse_iso(str(merged.get("expires_at") or ""))
        expires_item = _parse_iso(str(item.get("expires_at") or ""))
        if expires_existing and expires_item and expires_item > expires_existing:
            merged["expires_at"] = item.get("expires_at")
            merged["ttl_seconds"] = item.get("ttl_seconds")
        deduped[key] = merged
    return list(deduped.values())


def split_records_by_freshness(records: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fresh: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    now = _utc_now()
    for record in records or []:
        if not isinstance(record, dict):
            continue
        expires_at = _parse_iso(str(record.get("expires_at") or ""))
        if expires_at and expires_at < now:
            stale.append(record)
        else:
            fresh.append(record)
    return fresh, stale


def summarize_record_freshness(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    fresh, stale = split_records_by_freshness(records)
    freshness = "fresh" if fresh else ("stale" if stale else "unknown")
    return {
        "record_count": len(fresh) + len(stale),
        "fresh_record_count": len(fresh),
        "stale_record_count": len(stale),
        "freshness": freshness,
    }


def evaluate_retrieval_quality(
    *,
    retrieval_hits: list[dict[str, Any]] | None,
    fact_sources: list[dict[str, Any]] | None,
    knowledge_records: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    hits = [item for item in (retrieval_hits or []) if isinstance(item, dict)]
    sources = [item for item in (fact_sources or []) if isinstance(item, dict)]
    records = [item for item in (knowledge_records or []) if isinstance(item, dict)]
    freshness = summarize_record_freshness(records)
    scopes = {str(item.get("scope") or "") for item in hits if item.get("count")}
    citation_coverage = round(min(1.0, len(sources) / max(1, len(hits))), 2) if hits else 0.0
    grounding_score = round(min(1.0, (len(sources) * 0.4) + (len(scopes) * 0.2)), 2)
    source_quality = "high" if any(str(item.get("trust_level") or "") == "high" for item in records) else ("medium" if records else "low")
    if sources and freshness["stale_record_count"] == 0:
        recommendation = "可直接作为 grounded evidence 展示"
    elif sources and freshness["stale_record_count"] > 0:
        recommendation = "存在过期知识，展示时应保守并提示时效"
    elif hits:
        recommendation = "有命中但引用不足，建议补 citation 或保守表达"
    else:
        recommendation = "本轮未命中稳定知识，建议回退到普通生成"
    return {
        "hit_count": len(hits),
        "scope_count": len(scopes),
        "citation_count": len(sources),
        "citation_coverage": citation_coverage,
        "grounding_score": grounding_score,
        "freshness": freshness["freshness"],
        "fresh_record_count": freshness["fresh_record_count"],
        "stale_record_count": freshness["stale_record_count"],
        "source_quality": source_quality,
        "recommendation": recommendation,
    }
