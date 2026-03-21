"""RAG ingestion orchestration for preload and task-triggered flows."""

from __future__ import annotations

from typing import Any

from app.services.cache_service import cache_service
from app.services.rag_knowledge import build_knowledge_record, evaluate_retrieval_quality


def build_records_from_fact_sources(
    *,
    entity_name: str,
    scenario: str,
    ingest_mode: str,
    fact_sources: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in fact_sources or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        source = str(item.get("url") or item.get("source") or "").strip()
        if not title or not source:
            continue
        records.append(
            build_knowledge_record(
                entity_name=entity_name,
                query=str(item.get("query") or entity_name),
                title=title,
                url=source,
                snippet=str(item.get("snippet") or "").strip(),
                scope=str(item.get("source_scope") or item.get("source_type") or "general"),
                scenario=scenario,
                ingest_mode=ingest_mode,
            )
        )
    return records


async def ingest_retrieved_knowledge(
    *,
    entity_name: str,
    scenario: str,
    ingest_mode: str,
    knowledge: dict[str, Any],
) -> dict[str, Any]:
    records = build_records_from_fact_sources(
        entity_name=entity_name,
        scenario=scenario,
        ingest_mode=ingest_mode,
        fact_sources=knowledge.get("fact_sources") or [],
    )
    kb_snapshot = await cache_service.upsert_knowledge_records(entity_name, records, ingest_mode=ingest_mode)
    retrieval_eval = evaluate_retrieval_quality(
        retrieval_hits=knowledge.get("retrieval_hits") or [],
        fact_sources=knowledge.get("fact_sources") or [],
        knowledge_records=records,
    )
    return {
        "records": records,
        "kb_snapshot": kb_snapshot,
        "retrieval_eval": retrieval_eval,
    }
