from datetime import datetime
from types import SimpleNamespace

from app.schemas.responses import BlockGalleryOverviewResponse, EvaluationOverviewResponse, TrendListResponse, WorkspaceDataResponse
from langchain_core.messages import HumanMessage
import pytest

from app.api.workspace import _build_benchmark_overview, _build_evaluation_overview, _build_inspector_summary, _extract_session_title, _format_checkpoint_timestamp, _pick_row_value, dedupe_assets, format_messages, rollback_thread_to_checkpoint
from app.schemas.requests import ThreadRollbackRequest
from app.services.block_gallery import get_block_gallery_component, get_block_gallery_overview, get_block_gallery_scenario


def test_format_checkpoint_timestamp_accepts_datetime():
    value = datetime(2026, 3, 19, 18, 0, 0)
    assert _format_checkpoint_timestamp(value) == "2026-03-19T18:00:00"


def test_format_checkpoint_timestamp_accepts_string():
    value = "2026-03-19T18:00:00+08:00"
    assert _format_checkpoint_timestamp(value) == value


def test_workspace_data_response_accepts_structured_messages_and_prompts():
    response = WorkspaceDataResponse(
        is_new=False,
        messages={
            "main": [
                {"role": "user", "content": "帮我生成一篇 Mate 60 笔记"},
                {"role": "assistant", "content": "已完成页面更新"},
            ]
        },
        active_panel="main",
        selected_element_id=None,
        image_assets=[{"url": "https://img.example/1.jpg", "desc": "封面图", "source_type": "search"}],
        node_prompts={"intent_agent": [{"role": "system", "content": "prompt"}]},
        note_document={"document_meta": {"title": "Mate 60 页面"}, "blocks": [], "assets": []},
        turn_trace={"note_editor": {"action": "update_block"}},
        agent_backends={"note_editor": "structured_function_calling"},
        inspector_summary={"status": "active"},
        oss_url=None,
        source_code="<html></html>",
        checkpoints=[{"checkpoint_id": "ckpt_1", "intent": "create", "node": "document_renderer", "timestamp": "2026-03-23T01:00:00"}],
    )

    assert response.messages["main"][0]["role"] == "user"
    assert response.node_prompts["intent_agent"][0]["role"] == "system"
    assert response.image_assets[0]["source_type"] == "search"
    assert response.agent_backends["note_editor"] == "structured_function_calling"
    assert response.checkpoints[0].node == "document_renderer"


def test_format_messages_flattens_multimodal_human_message():
    formatted = format_messages([
        HumanMessage(content=[
            {"type": "text", "text": "帮我生成一篇 Mate 60 笔记"},
            {"type": "image_url", "image_url": {"url": "https://img.example/1.jpg"}},
        ])
    ])

    assert formatted[0]["role"] == "user"
    assert formatted[0]["content"] == "帮我生成一篇 Mate 60 笔记"
    assert formatted[0]["imageUrls"] == ["https://img.example/1.jpg"]


def test_format_messages_assigns_checkpoint_to_user_turns():
    formatted = format_messages(
        [
            HumanMessage(content="第一轮"),
            HumanMessage(content="第二轮"),
        ],
        turn_anchor_map={0: "ckpt_1", 1: "ckpt_2"},
    )

    assert formatted[0]["checkpointId"] == "ckpt_1"
    assert formatted[1]["checkpointId"] == "ckpt_2"
    assert formatted[0]["messageKind"] == "user_prompt"


def test_dedupe_assets_merges_same_url_entries():
    deduped = dedupe_assets([
        {"url": "https://img.example/1.jpg", "desc": "A", "source_type": "search"},
        {"url": "https://img.example/1.jpg", "query": "Mate 60"},
    ])

    assert len(deduped) == 1
    assert deduped[0]["desc"] == "A"
    assert deduped[0]["query"] == "Mate 60"


def test_extract_session_title_prefers_first_human_message():
    title = _extract_session_title(
        {
            "main_messages": [
                HumanMessage(content="帮我生成一篇关于华为 Mate 60 的对比种草笔记"),
            ]
        },
        "thread_12345678",
    )

    assert title.startswith("帮我生成一篇关于华为 Mate 60")


def test_extract_session_title_falls_back_to_thread_id_without_note_document_title():
    title = _extract_session_title(
        {
            "document_view": {
                "page_title": "华为 Mate 60 高能种草页"
            }
        },
        "thread_12345678",
    )

    assert title == "项目 thread_1"

def test_extract_session_title_ignores_legacy_page_title_when_note_document_exists():
    title = _extract_session_title(
        {
            "note_document": {
                "document_meta": {
                    "title": "新版 NoteDocument 标题"
                }
            },
            "document_view": {
                "page_title": "旧页面标题"
            }
        },
        "thread_12345678",
    )

    assert title == "新版 NoteDocument 标题"


def test_pick_row_value_supports_dict_row():
    row = {"thread_id": "thread_abc"}
    assert _pick_row_value(row, "thread_id", 0) == "thread_abc"


def test_workspace_data_response_accepts_turn_trace():
    response = WorkspaceDataResponse(
        is_new=False,
        messages={"main": []},
        active_panel="main",
        selected_element_id=None,
        turn_trace={"warnings": ["noop"]},
        oss_url=None,
        checkpoints=[],
    )

    assert response.turn_trace["warnings"] == ["noop"]


def test_workspace_data_response_no_longer_requires_legacy_page_or_style_fields():
    response = WorkspaceDataResponse(
        is_new=True,
        messages={"main": []},
        active_panel="main",
        selected_element_id=None,
        note_document={"document_meta": {"title": "新页面"}, "blocks": [], "assets": []},
        oss_url=None,
        checkpoints=[],
    )

    dumped = response.model_dump()
    assert "document_view" not in dumped
    assert "block_style_map" not in dumped


class _FakeSnapshot:
    def __init__(self, values, checkpoint_id="ckpt_latest"):
        self.values = values
        self.config = {"configurable": {"checkpoint_id": checkpoint_id}}


class _FakeRollbackAgent:
    def __init__(self, target_values, latest_values):
        self.target_snapshot = _FakeSnapshot(target_values, checkpoint_id="ckpt_target")
        self.latest_snapshot = _FakeSnapshot(latest_values, checkpoint_id="ckpt_latest")
        self.updated = []

    async def aget_state(self, config):
        configurable = (config or {}).get("configurable") or {}
        if configurable.get("checkpoint_id") == "ckpt_target":
            return self.target_snapshot
        return self.latest_snapshot

    async def aupdate_state(self, config, values, as_node=None):
        self.updated.append({"config": config, "values": values, "as_node": as_node})
        latest_values = dict(values)
        latest_values.setdefault("note_document", {"document_meta": {"title": "回滚后页面"}, "blocks": [], "assets": []})
        self.latest_snapshot = _FakeSnapshot(latest_values, checkpoint_id="ckpt_after_rollback")


@pytest.mark.asyncio
async def test_thread_rollback_endpoint_restores_checkpoint_state():
    target_values = {
        "main_messages": [HumanMessage(content="旧问题")],
        "note_document": {"document_meta": {"title": "旧页面"}, "blocks": [], "assets": []},
    }
    latest_values = {
        "main_messages": [HumanMessage(content="新问题")],
        "note_document": {"document_meta": {"title": "新页面"}, "blocks": [], "assets": []},
    }
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(agent=_FakeRollbackAgent(target_values, latest_values))))

    response = await rollback_thread_to_checkpoint(
        "thread_123",
        ThreadRollbackRequest(checkpoint_id="ckpt_target", panel="main"),
        request,
    )

    assert response.status == "success"
    assert request.app.state.agent.updated[0]["values"]["note_document"]["document_meta"]["title"] == "旧页面"


def test_evaluation_overview_response_accepts_structured_payload():
    response = EvaluationOverviewResponse(
        data={
            "overall_score": 88.5,
            "overall_status": "healthy",
            "categories": [{"name": "路由评估", "score": 90.0, "status": "strong"}],
            "recommendations": ["当前路由链稳定。"],
        }
    )

    assert response.data["overall_status"] == "healthy"
    assert response.data["categories"][0]["name"] == "路由评估"


def test_trend_list_response_accepts_structured_trend_items():
    response = TrendListResponse(
        trends=[
            {
                "keyword": "华为 Mate 60",
                "score": 12.0,
                "scenario_hint": "seeding",
                "entity_type": "product_topic",
                "source": "system_preload",
                "freshness": "fresh",
                "cache_freshness": "fresh",
                "record_count": 3,
                "recommended_prompt": "帮我生成一篇关于「华为 Mate 60」的对比种草笔记，信息要靠谱，结论要鲜明，不要默认补和主题无关的风景配图。",
            }
        ]
    )

    assert response.trends[0].keyword == "华为 Mate 60"
    assert response.trends[0].scenario_hint == "seeding"
    assert response.trends[0].recommended_prompt


def test_block_gallery_overview_response_accepts_structured_payload():
    payload = get_block_gallery_overview()
    response = BlockGalleryOverviewResponse(data=payload)

    assert response.data["components"]
    assert response.data["scenarios"]
    assert response.data["components"][0]["fixture"]["note_document"]["blocks"]


def test_block_gallery_component_and_scenario_fixtures_are_accessible():
    component = get_block_gallery_component("VersusCard")
    scenario = get_block_gallery_scenario("seeding_compare")

    assert component is not None
    assert component["fixture"]["note_document"]["blocks"][0]["type"] == "VersusCard"
    assert scenario is not None
    assert len(scenario["fixture"]["note_document"]["blocks"]) >= 3



def test_build_inspector_summary_highlights_attention_signals():
    summary = _build_inspector_summary({
        "note_document": {
            "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
            "theme": {"preset": "seeding_hot"},
            "blocks": [{"id": "poll_1", "type": "PollBlock"}],
            "assets": [{"url": "https://img.example/1.jpg", "role": "cover", "used_by_blocks": ["poll_1"]}],
            "fact_bindings": [{"block_id": "poll_1", "bindings": [{"field": "summary"}]}],
        },
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_conflicts": [{"field": "battery_capacity", "values": []}],
            "confirmed_facts": {"battery_capacity": {"value": "5000mAh"}},
            "fact_sources": [{"title": "官方页"}],
            "fact_confidence": "medium",
        },
        "turn_trace": {
            "warnings": ["style_changed_without_content"],
            "changed_blocks": [{"id": "poll_1", "type": "PollBlock", "changed_fields": ["style"]}],
            "note_editor": {"action": "update_block", "target_block_id": "poll_1", "structured": True},
        },
        "intent_route": "note_editor",
        "active_panel": "main",
        "agent_backends": {"note_editor": "create_agent"},
        "selected_element_id": "poll_1",
    })

    assert summary["status"] == "attention"
    assert summary["focus"]["entity_name"] == "华为 Mate 60"
    assert summary["document"]["block_count"] == 1
    assert summary["execution"]["warning_count"] == 1
    assert summary["facts"]["conflict_count"] == 1
    assert summary["suggestions"]


def test_build_inspector_summary_prefers_workspace_action_when_note_editor_absent():
    summary = _build_inspector_summary({
        "note_document": {
            "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
            "blocks": [{"id": "story_1", "type": "StoryText"}],
            "assets": [],
            "fact_bindings": [],
        },
        "turn_trace": {
            "warnings": [],
            "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
            "workspace_action": {"action": "workspace_rollback_component", "target_block_id": "story_1", "structured": True},
        },
        "selected_element_id": "story_1",
    })

    assert summary["execution"]["last_action"] == "workspace_rollback_component"
    assert summary["execution"]["target_block_id"] == "story_1"
    assert summary["execution"]["changed_block_count"] == 1


def test_build_inspector_summary_includes_component_builder_overview():
    summary = _build_inspector_summary({
        "note_document": {
            "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
            "blocks": [{"id": "poll_1", "type": "PollBlock"}],
            "assets": [],
            "fact_bindings": [],
        },
        "turn_trace": {
            "component_builder": {
                "poll_1": {
                    "component_type": "PollBlock",
                    "fallback_used": True,
                    "contract_filter_count": 2,
                    "precheck_warning_count": 1,
                    "fact_summary_count": 3,
                    "asset_count": 1,
                    "prompt_mode": "compact_contract_first",
                    "contract_first": True,
                }
            }
        },
    })

    assert summary["builder"]["component_count"] == 1
    assert summary["builder"]["fallback_count"] == 1
    assert summary["builder"]["contract_filter_count"] == 2
    assert summary["builder"]["precheck_warning_count"] == 1
    assert summary["builder"]["fact_summary_count"] == 3
    assert summary["builder"]["asset_count"] == 1
    assert summary["builder"]["prompt_modes"] == ["compact_contract_first"]
    assert summary["builder"]["contract_first"] is True
    assert summary["builder"]["component_types"] == ["PollBlock"]
    assert any("builder fallback" in tip for tip in summary["suggestions"])
    assert any("过滤掉了一些越权字段" in tip for tip in summary["suggestions"])
    assert any("必填字段缺失" in tip for tip in summary["suggestions"])
    assert any("压缩后的事实摘要" in tip for tip in summary["suggestions"])


def test_build_inspector_summary_includes_retrieval_overview():
    summary = _build_inspector_summary({
        "note_document": {
            "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
            "blocks": [{"id": "spec_1", "type": "ProductSpecCard"}],
            "assets": [],
            "fact_bindings": [],
        },
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "fact_sources": [
                {"title": "华为官网 Mate 60", "url": "https://example.com/official", "snippet": "价格 6999", "source_scope": "official"},
                {"title": "用户评价合集", "url": "https://example.com/review", "snippet": "影像强", "source_scope": "review"},
            ],
            "retrieval_hits": [
                {"scope": "official", "query": "Mate 60 核心参数 价格 官方", "count": 1, "titles": ["华为官网 Mate 60"]},
                {"scope": "review", "query": "Mate 60 用户评价 真实体验", "count": 1, "titles": ["用户评价合集"]},
            ],
            "retrieval_summary": {
                "strategy": "live_search_with_citations",
                "policy_name": "cache_then_live_grounded",
                "policy_path": "cache_first_then_live_search",
                "ingest_mode": "task_triggered_ingest",
            "cache_hit": False,
            "cache_freshness": "miss",
            "cache_key": "mate 60",
            "cache_age_seconds": 0,
            "cache_ttl_seconds": 21600,
            "cache_remaining_ttl_seconds": 0,
            "live_search_used": True,
            "query": "Mate 60",
                "query_variants": ["Mate 60 核心参数 价格 官方", "Mate 60 用户评价 真实体验"],
                "citation_count": 2,
                "image_count": 1,
                "grounding_status": "grounded",
                "freshness": "live",
                "record_count": 2,
                "fresh_record_count": 2,
                "stale_record_count": 0,
                "hit_scopes": ["official", "review"],
                "rerank_applied": True,
            },
            "retrieval_eval": {
                "citation_coverage": 1.0,
                "grounding_score": 1.0,
                "source_quality": "high",
                "recommendation": "可直接作为 grounded evidence 展示",
            },
        },
    })

    assert summary["retrieval"]["strategy"] == "live_search_with_citations"
    assert summary["retrieval"]["policy_name"] == "cache_then_live_grounded"
    assert summary["retrieval"]["policy_path"] == "cache_first_then_live_search"
    assert summary["retrieval"]["ingest_mode"] == "task_triggered_ingest"
    assert summary["retrieval"]["citation_count"] == 2
    assert summary["retrieval"]["cache_freshness"] == "miss"
    assert summary["retrieval"]["cache_key"] == "mate 60"
    assert summary["retrieval"]["cache_ttl_seconds"] == 21600
    assert summary["retrieval"]["hit_count"] == 2
    assert summary["retrieval"]["grounding_status"] == "grounded"
    assert summary["retrieval"]["freshness"] == "live"
    assert summary["retrieval"]["record_count"] == 2
    assert summary["retrieval"]["fresh_record_count"] == 2
    assert summary["retrieval"]["stale_record_count"] == 0
    assert summary["retrieval"]["rerank_applied"] is True
    assert summary["retrieval"]["citation_coverage"] == 1.0
    assert summary["retrieval"]["grounding_score"] == 1.0
    assert summary["retrieval"]["source_quality"] == "high"
    assert summary["retrieval"]["recommendation"] == "可直接作为 grounded evidence 展示"


def test_build_benchmark_overview_aggregates_sessions():
    overview = _build_benchmark_overview([
        {
            "thread_id": "thread_alpha",
            "title": "Mate 60 页面",
            "updated_at": "2026-03-21T10:00:00",
            "values": {
                "note_document": {
                    "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
                    "theme": {"preset": "seeding_hot"},
                    "blocks": [
                        {"id": "spec_1", "type": "ProductSpecCard"},
                        {"id": "poll_1", "type": "PollBlock"},
                    ],
                    "assets": [{"url": "https://img.example/1.jpg", "role": "cover"}],
                    "fact_bindings": [],
                },
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "fact_sources": [{"title": "官网"}],
                    "retrieval_hits": [{"scope": "official", "query": "Mate 60 官方", "count": 1}],
                    "retrieval_summary": {
                        "strategy": "cache_hit",
                        "cache_hit": True,
                        "cache_freshness": "fresh",
                        "cache_age_seconds": 120,
                        "cache_remaining_ttl_seconds": 1800,
                        "citation_count": 1,
                        "record_count": 1,
                        "fresh_record_count": 1,
                        "stale_record_count": 0,
                        "grounding_status": "grounded",
                        "rerank_applied": False,
                    },
                    "retrieval_eval": {
                        "citation_coverage": 1.0,
                        "grounding_score": 0.95,
                        "source_quality": "high",
                    },
                },
                "turn_trace": {
                    "warnings": [],
                    "changed_blocks": [{"id": "spec_1", "type": "ProductSpecCard", "changed_fields": ["props"]}],
                    "component_builder": {
                        "spec_1": {"component_type": "ProductSpecCard", "fallback_used": False}
                    },
                    "note_editor": {"action": "update_block", "target_block_id": "spec_1", "structured": True},
                },
                "agent_backends": {"note_editor": "create_agent"},
            },
        },
        {
            "thread_id": "thread_beta",
            "title": "阿那亚攻略",
            "updated_at": "2026-03-21T09:00:00",
            "values": {
                "note_document": {
                    "document_meta": {"title": "阿那亚攻略", "scenarios": ["travel"]},
                    "theme": {"preset": "travel_editorial"},
                    "blocks": [{"id": "loc_1", "type": "LocationBlock"}],
                    "assets": [],
                    "fact_bindings": [],
                },
                "retrieved_knowledge": {
                    "entity_name": "阿那亚",
                    "fact_sources": [{"title": "景区信息"}],
                    "retrieval_hits": [{"scope": "official", "query": "阿那亚 门票", "count": 1}],
                    "retrieval_summary": {
                        "strategy": "live_search_with_citations",
                        "cache_hit": False,
                        "cache_freshness": "miss",
                        "live_search_used": True,
                        "citation_count": 1,
                        "record_count": 2,
                        "fresh_record_count": 1,
                        "stale_record_count": 1,
                        "grounding_status": "grounded",
                        "rerank_applied": True,
                    },
                    "retrieval_eval": {
                        "citation_coverage": 0.8,
                        "grounding_score": 0.75,
                        "source_quality": "medium",
                    },
                },
                "turn_trace": {
                    "warnings": ["fallback_used"],
                    "changed_blocks": [{"id": "loc_1", "type": "LocationBlock", "changed_fields": ["props"]}],
                    "component_builder": {
                        "loc_1": {"component_type": "LocationBlock", "fallback_used": True}
                    },
                    "note_editor": {"action": "append_block", "target_block_id": "loc_1", "structured": True, "fallback_used": True},
                },
                "agent_backends": {"note_editor": "create_agent"},
            },
        },
    ])

    assert overview["session_count"] == 2
    assert overview["active_document_count"] == 2
    assert overview["summary"]["avg_block_count"] == 1.5
    assert overview["rag"]["session_count"] == 2
    assert overview["rag"]["grounded_session_count"] == 2
    assert overview["cache"]["cache_hit_rate"] == 0.5
    assert overview["cache"]["live_search_rate"] == 0.5
    assert overview["cache"]["rerank_rate"] == 0.5
    assert overview["execution"]["builder_fallback_total"] == 1
    assert overview["execution"]["warning_session_count"] == 1
    assert overview["distributions"]["scenarios"][0]["scenario"] in {"seeding", "travel"}
    assert overview["distributions"]["components"][0]["component_type"] in {"ProductSpecCard", "PollBlock", "LocationBlock"}
    assert len(overview["sessions"]) == 2
    assert overview["recommendations"]


def test_build_benchmark_overview_handles_empty_snapshot_list():
    overview = _build_benchmark_overview([])

    assert overview["session_count"] == 0
    assert overview["sessions"] == []
    assert overview["recommendations"]


def test_build_evaluation_overview_aggregates_six_dimensions():
    overview = _build_evaluation_overview([
        {
            "thread_id": "thread_eval",
            "title": "Mate 60 页面",
            "updated_at": "2026-03-22T10:00:00",
            "values": {
                "intent_route": "note_editor",
                "agent_backends": {"intent_agent": "deterministic_fast_path"},
                "planner_output": {
                    "block_intents": [
                        {"intent": "hero_media"},
                        {"intent": "evidence_summary"},
                    ]
                },
                "planner_policy": {
                    "theme_policy": {"preset": "seed_hot"},
                    "layout_policy": {"preferred_block_intents": ["hero_media", "evidence_summary"]},
                    "fact_policy": {"grounding": "strict"},
                    "asset_policy": {"mode": "cover_first"},
                },
                "note_document": {
                    "document_meta": {"title": "Mate 60 页面", "scenarios": ["seeding"]},
                    "blocks": [
                        {"id": "cover_1", "type": "CoverSwiper"},
                        {"id": "spec_1", "type": "ProductSpecCard"},
                    ],
                    "assets": [],
                    "fact_bindings": [],
                },
                "turn_trace": {
                    "warnings": [],
                    "changed_blocks": [{"id": "spec_1", "changed_fields": ["props"]}],
                    "note_editor": {
                        "action": "update_block",
                        "target_block_id": "spec_1",
                        "structured": True,
                    },
                },
                "retrieved_knowledge": {
                    "retrieval_summary": {
                        "cache_hit": True,
                        "cache_freshness": "fresh",
                        "cache_ttl_seconds": 7200,
                        "cache_remaining_ttl_seconds": 3600,
                        "live_search_used": False,
                        "grounding_status": "grounded",
                        "citation_count": 2,
                    },
                    "retrieval_eval": {
                        "citation_coverage": 0.9,
                        "grounding_score": 0.88,
                    },
                    "fact_sources": [{"title": "官方页"}],
                },
            },
        }
    ])

    assert overview["overall_score"] > 0
    assert overview["overall_status"] in {"strong", "healthy", "attention", "weak"}
    assert len(overview["categories"]) == 6
    category_names = {item["name"] for item in overview["categories"]}
    assert category_names == {"路由评估", "规划评估", "执行评估", "RAG 评估", "缓存评估", "系统级评估"}
    assert overview["suite"]["case_count"] >= 6
    assert overview["sessions"][0]["intent_route"] == "note_editor"
    assert overview["recommendations"]
