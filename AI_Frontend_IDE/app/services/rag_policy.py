"""Formal retrieval policy helpers for XHS-Forge RAG.

This module keeps retrieval decision-making explicit:
- choose which retrieval path to prefer
- standardize query variants
- rerank citations by trust/freshness instead of using raw fetch order
"""

from __future__ import annotations

from typing import Any


def build_query_variants(*, user_query: str, entity_name: str) -> list[dict[str, str]]:
    subject = str(entity_name or user_query or "").strip() or "当前主题"
    return [
        {"scope": "official", "query": f"{subject} 核心参数 价格 官方"},
        {"scope": "review", "query": f"{subject} 用户评价 真实体验"},
    ]


def choose_retrieval_policy(
    *,
    user_query: str,
    cache_keywords: list[str] | None,
    needs_assets: str,
) -> dict[str, Any]:
    cache_hit_candidate = bool(cache_keywords)
    asset_mode = "search" if str(needs_assets or "").lower() == "search" else "none"
    return {
        "policy_name": "cache_then_live_grounded",
        "policy_path": "cache_first_then_live_search",
        "cache_hit_candidate": cache_hit_candidate,
        "enable_live_search": True,
        "enable_image_search": asset_mode == "search",
        "asset_mode": asset_mode,
        "reason": "优先复用热点知识底座，对长尾或未命中主题再做在线 grounded search。",
        "user_query": user_query,
    }


def _source_priority(source_scope: str) -> int:
    scope = str(source_scope or "").lower()
    if scope == "official":
        return 3
    if scope == "review":
        return 2
    return 1


def _trust_priority(trust_level: str) -> int:
    trust = str(trust_level or "").lower()
    if trust == "high":
        return 3
    if trust == "medium":
        return 2
    return 1


def rerank_fact_sources(
    fact_sources: list[dict[str, Any]] | None,
    knowledge_records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    records = {
        str(item.get("source") or "").strip(): item
        for item in (knowledge_records or [])
        if isinstance(item, dict) and str(item.get("source") or "").strip()
    }

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        url = str(item.get("url") or item.get("source") or "").strip()
        record = records.get(url, {})
        stale_penalty = 0 if int(record.get("ttl_seconds") or 0) > 0 else -1
        return (
            _source_priority(str(item.get("source_scope") or item.get("source_type") or "")),
            _trust_priority(str(record.get("trust_level") or item.get("trust_level") or "")),
            stale_penalty,
        )

    ranked = [item for item in (fact_sources or []) if isinstance(item, dict)]
    ranked.sort(key=score, reverse=True)
    return ranked
