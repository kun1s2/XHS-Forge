from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.api import chat as chat_api
from app.api.chat import router as chat_router
from app.api.workspace import router as workspace_router
from app.core.note_document import build_note_document
from app.agents.state import merge_state_patch


@dataclass
class FakeStateSnapshot:
    values: dict[str, Any]
    checkpoint_id: str
    source: str = "document_renderer"

    @property
    def next(self) -> list[str]:
        return []

    @property
    def config(self) -> dict[str, Any]:
        return {"configurable": {"checkpoint_id": self.checkpoint_id}}

    @property
    def metadata(self) -> dict[str, Any]:
        return {"source": self.source}

    @property
    def created_at(self) -> datetime:
        return datetime.now()


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query: str):
        return None

    async def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows_provider):
        self._rows_provider = rows_provider

    def cursor(self):
        return _FakeCursor(self._rows_provider())


class _FakeCheckpointer:
    def __init__(self, rows_provider):
        self.conn = _FakeConn(rows_provider)


class FakeE2EAgent:
    def __init__(self):
        self._latest: dict[str, FakeStateSnapshot] = {}
        self._history: dict[str, list[FakeStateSnapshot]] = {}
        self.checkpointer = _FakeCheckpointer(self._latest_rows)

    def _latest_rows(self) -> list[dict[str, str]]:
        return [
            {"thread_id": thread_id, "last_cid": snapshot.checkpoint_id}
            for thread_id, snapshot in sorted(self._latest.items(), key=lambda item: item[1].checkpoint_id, reverse=True)
        ]

    async def astream_events(self, inputs, config=None, version="v2"):
        thread_id = ((config or {}).get("configurable") or {}).get("thread_id") or "thread-e2e"
        self._simulate_turn(thread_id, inputs or {})
        if False:
            yield {}

    async def aget_state(self, config):
        configurable = (config or {}).get("configurable") or {}
        thread_id = configurable.get("thread_id") or "thread-e2e"
        checkpoint_id = configurable.get("checkpoint_id")
        if checkpoint_id:
            for snapshot in self._history.get(thread_id, []):
                if snapshot.checkpoint_id == checkpoint_id:
                    return snapshot
        return self._latest.get(thread_id, FakeStateSnapshot({}, "ckpt-empty"))

    async def aupdate_state(self, config, values, as_node=None):
        configurable = (config or {}).get("configurable") or {}
        thread_id = configurable.get("thread_id") or "thread-e2e"
        latest = self._latest.get(thread_id, FakeStateSnapshot({}, f"{thread_id}-ckpt-0"))
        merged_values = merge_state_patch(dict(latest.values), dict(values or {}))
        next_snapshot = FakeStateSnapshot(
            merged_values,
            checkpoint_id=latest.checkpoint_id,
            source=as_node or "document_renderer",
        )
        self._latest[thread_id] = next_snapshot
        self._history.setdefault(thread_id, []).insert(0, next_snapshot)
        return None

    async def aget_state_history(self, config):
        thread_id = ((config or {}).get("configurable") or {}).get("thread_id") or "thread-e2e"
        for snapshot in self._history.get(thread_id, []):
            yield snapshot

    def _next_checkpoint_id(self, thread_id: str) -> str:
        count = len(self._history.get(thread_id, [])) + 1
        return f"{thread_id}-ckpt-{count}"

    def _simulate_turn(self, thread_id: str, inputs: dict[str, Any]):
        latest_values = deepcopy((self._latest.get(thread_id) or FakeStateSnapshot({}, f"{thread_id}-ckpt-0")).values)
        panel = inputs.get("active_panel") or "main"
        selected = inputs.get("selected_element_id") or "无 (全局修改)"
        creator = inputs.get("creator_persona") or "硬核数码博主"
        main_messages = list(latest_values.get("main_messages") or [])
        latest_message = ((inputs.get("main_messages") or [None])[-1]) if inputs.get("main_messages") else None
        query = getattr(latest_message, "content", "") if latest_message is not None else ""
        query = str(query or "")
        if latest_message is not None:
            main_messages.append(latest_message)

        if selected not in ["无 (全局修改)", "none", None]:
            note_document = latest_values.get("note_document") or self._build_seeding_note_document(with_hero=False)
            blocks = list(note_document.get("blocks") or [])
            for block in blocks:
                if str(block.get("id") or "") == str(selected):
                    props = dict(block.get("props") or {})
                    if str(block.get("type") or "") == "PollBlock":
                        props["question"] = "如果只能选一个，你更看重影像还是续航？"
                        props["option_a"] = "影像一定要强"
                        props["option_b"] = "续航绝对优先"
                    block["props"] = props
            note_document["blocks"] = blocks
            turn_trace = {
                "query": query,
                "selected_element_id": selected,
                "panel": panel,
                "timeline": [{"event": "node_start", "node": "note_editor"}, {"event": "node_end", "node": "note_editor"}],
                "route": {"intent_route": "note_editor", "active_archetype": "seeding"},
                "planner": {},
                "note_editor": {
                    "action": "local_edit",
                    "target_block_id": selected,
                    "structured": True,
                    "fallback_used": False,
                },
                "before_summary": {"title": "华为 Mate 60 对比种草", "block_count": len(blocks), "block_order": []},
                "after_summary": {"title": "华为 Mate 60 对比种草", "block_count": len(blocks), "block_order": []},
                "changed_blocks": [{"id": selected, "type": "PollBlock", "changed_fields": ["props"]}],
                "warnings": [],
            }
            values = {
                **latest_values,
                "main_messages": main_messages,
                "active_panel": panel,
                "selected_element_id": selected,
                "creator_persona": creator,
                "active_archetype": "seeding",
                "scenarios": ["seeding", "general"],
                "intent_route": "note_editor",
                "note_document": note_document,
                "turn_trace": turn_trace,
                "final_html": "<html><body>poll edited</body></html>",
                "agent_backends": {
                    "intent_agent": "structured_function_calling",
                    "note_editor": "create_agent",
                    "theme_compiler": "deterministic_compiler",
                    "document_renderer": "deterministic_renderer",
                },
            }
        elif "阿那亚" in query or "攻略" in query:
            note_document = self._build_travel_note_document()
            values = self._build_generated_values(
                latest_values=latest_values,
                main_messages=main_messages,
                panel=panel,
                selected=selected,
                creator=creator,
                query=query,
                active_archetype="travel",
                scenarios=["travel", "general"],
                note_document=note_document,
                planner_block_intents=["hero_media", "heading", "narrative_text", "location_info"],
                final_html="<html><body>travel page</body></html>",
                citation_count=2,
            )
        elif "日常" in query or "生活" in query:
            note_document = self._build_daily_note_document()
            values = self._build_generated_values(
                latest_values=latest_values,
                main_messages=main_messages,
                panel=panel,
                selected=selected,
                creator=creator,
                query=query,
                active_archetype="daily_share",
                scenarios=["daily_share", "general"],
                note_document=note_document,
                planner_block_intents=["heading", "narrative_text", "ambience_snapshot", "interactive_opinion"],
                final_html="<html><body>daily page</body></html>",
                citation_count=1,
            )
        else:
            note_document = self._build_seeding_note_document(with_hero=False)
            values = self._build_generated_values(
                latest_values=latest_values,
                main_messages=main_messages,
                panel=panel,
                selected=selected,
                creator=creator,
                query=query,
                active_archetype="seeding",
                scenarios=["seeding", "general"],
                note_document=note_document,
                planner_block_intents=["heading", "narrative_text", "evidence_summary", "comparison", "interactive_opinion"],
                final_html="<html><body>seeding page</body></html>",
                citation_count=3,
            )

        checkpoint_id = self._next_checkpoint_id(thread_id)
        snapshot = FakeStateSnapshot(values, checkpoint_id=checkpoint_id)
        self._latest[thread_id] = snapshot
        self._history.setdefault(thread_id, []).insert(0, snapshot)

    def _build_generated_values(
        self,
        *,
        latest_values: dict[str, Any],
        main_messages: list[Any],
        panel: str,
        selected: str,
        creator: str,
        query: str,
        active_archetype: str,
        scenarios: list[str],
        note_document: dict[str, Any],
        planner_block_intents: list[str],
        final_html: str,
        citation_count: int,
    ) -> dict[str, Any]:
        block_types = [str(block.get("type") or "") for block in (note_document.get("blocks") or [])]
        changed_blocks = [
            {"id": str(block.get("id") or ""), "type": str(block.get("type") or ""), "changed_fields": ["added"]}
            for block in (note_document.get("blocks") or [])
        ]
        retrieval_summary = {
            "strategy": "semantic_hybrid",
            "policy_name": "hybrid_grounded",
            "policy_path": "query -> kb -> rerank -> grounded",
            "ingest_mode": "task_triggered_ingest",
            "cache_hit": False,
            "cache_freshness": "miss",
            "live_search_used": True,
            "query": query,
            "entity_name": "华为 Mate 60" if active_archetype == "seeding" else "阿那亚" if active_archetype == "travel" else "日常分享",
            "citation_count": citation_count,
            "image_count": len(note_document.get("assets") or []),
            "grounding_status": "grounded",
            "freshness": "fresh",
            "record_count": citation_count,
            "fresh_record_count": citation_count,
            "stale_record_count": 0,
            "rerank_applied": True,
            "query_variants": [query, f"{query} 参数"],
            "hit_scopes": ["official", "review"],
        }
        retrieval_eval = {
            "citation_coverage": 0.9,
            "grounding_score": 0.88,
            "source_quality": "high",
            "recommendation": "当前 grounding 质量稳定，可直接展示。",
        }
        planner_output = {
            "block_intents": [{"intent_type": item, "preferred_component": ""} for item in planner_block_intents],
            "theme_policy": {"preset": "xhs-clean", "interaction_bias": "high"},
        }
        turn_trace = {
            "query": query,
            "selected_element_id": selected,
            "panel": panel,
            "timeline": [
                {"event": "node_start", "node": "intent_agent"},
                {"event": "node_end", "node": "intent_agent"},
                {"event": "node_start", "node": "planner"},
                {"event": "node_end", "node": "planner"},
                {"event": "node_start", "node": "document_renderer"},
                {"event": "node_end", "node": "document_renderer"},
            ],
            "route": {"intent_route": "research_agent", "active_archetype": active_archetype},
            "planner": {"block_intents": planner_block_intents, "theme_preset": "xhs-clean"},
            "note_editor": {},
            "before_summary": {"title": "XHS-Forge Note", "block_count": 0, "block_order": []},
            "after_summary": {
                "title": (note_document.get("document_meta") or {}).get("title") or "页面",
                "block_count": len(note_document.get("blocks") or []),
                "block_order": [{"id": str(block.get("id") or ""), "type": str(block.get("type") or "")} for block in (note_document.get("blocks") or [])],
            },
            "changed_blocks": changed_blocks,
            "warnings": [],
            "component_builder": {
                str(block.get("id") or ""): {
                    "component_type": str(block.get("type") or ""),
                    "prompt_mode": "compact_contract_first",
                    "fact_summary_count": 4,
                    "asset_count": len(note_document.get("assets") or []),
                    "fallback_used": False,
                    "contract_filter_count": 0,
                    "precheck_warning_count": 0,
                }
                for block in (note_document.get("blocks") or [])
            },
            "theme_compiler": {"theme_name": "xhs-clean", "block_count": len(note_document.get("blocks") or []), "source": "planner_policy"},
        }
        return {
            **latest_values,
            "main_messages": main_messages,
            "active_panel": panel,
            "selected_element_id": selected,
            "creator_persona": creator,
            "active_archetype": active_archetype,
            "scenarios": scenarios,
            "intent_route": "research_agent",
            "note_document": note_document,
            "planner_output": planner_output,
            "planner_policy": {"theme_policy": {"preset": "xhs-clean", "interaction_bias": "high"}},
            "turn_trace": turn_trace,
            "retrieved_knowledge": {
                "entity_name": retrieval_summary["entity_name"],
                "fact_sources": [{"title": "source", "url": "https://example.com"}] * citation_count,
                "retrieval_summary": retrieval_summary,
                "retrieval_eval": retrieval_eval,
            },
            "image_assets": list(note_document.get("assets") or []),
            "final_html": final_html,
            "final_oss_url": "data:text/html;base64,PGh0bWw+PC9odG1sPg==",
            "agent_backends": {
                "intent_agent": "structured_function_calling",
                "planner": "deterministic_policy_builder",
                "outline_resolver": "deterministic_resolver",
                "component_builder": "contract_first_worker",
                "theme_compiler": "deterministic_compiler",
                "document_renderer": "deterministic_renderer",
            },
        }

    def _build_seeding_note_document(self, *, with_hero: bool) -> dict[str, Any]:
        blocks = [
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "radar_1", "component_type": "RadarChartBlock", "content_brief": "雷达图"},
            {"id": "versus_1", "component_type": "VersusCard", "content_brief": "对比"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ]
        if with_hero:
            blocks.insert(0, {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"})
        document_view = {
            "page_title": "华为 Mate 60 对比种草",
            "blocks": blocks,
            "title_1": {"type": "TitleBlock", "title": "华为 Mate 60 对比种草"},
            "story_1": {"type": "StoryText", "paragraphs": ["这一代更适合重视续航和稳定体验的人。"]},
            "radar_1": {"type": "RadarChartBlock", "dimensions": ["续航", "性能", "影像", "价格"], "scores": [9, 8, 8, 6]},
            "versus_1": {"type": "VersusCard", "title": "华为 Mate 60 vs 同档竞品", "proText": "续航更强", "conText": "价格不算低"},
            "poll_1": {"type": "PollBlock", "question": "你更在意影像还是续航？", "option_a": "影像", "option_b": "续航"},
        }
        if with_hero:
            document_view["cover_1"] = {"type": "CoverSwiper", "image_urls": ["https://img.example/cover.jpg"]}
        return build_note_document(
            document_view=document_view,
            block_style_map={"global_vars": {"--theme-name": "xhs-clean"}},
            image_assets=[{"url": "https://img.example/cover.jpg", "role": "cover"}] if with_hero else [],
            scenarios=["seeding", "general"],
            active_archetype="seeding",
            planner_output={"block_intents": [{"intent_type": "heading"}]},
        )

    def _build_travel_note_document(self) -> dict[str, Any]:
        return build_note_document(
            document_view={
                "page_title": "阿那亚一日游攻略",
                "blocks": [
                    {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
                    {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                    {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                    {"id": "loc_1", "component_type": "LocationBlock", "content_brief": "地点"},
                ],
                "cover_1": {"type": "CoverSwiper", "image_urls": ["https://img.example/anaya.jpg"]},
                "title_1": {"type": "TitleBlock", "title": "阿那亚一日游攻略"},
                "story_1": {"type": "StoryText", "paragraphs": ["适合周末短逃离，节奏要轻，路线要清楚。"]},
                "loc_1": {"type": "LocationBlock", "name": "阿那亚礼堂", "address": "河北秦皇岛"},
            },
            block_style_map={"global_vars": {"--theme-name": "travel_clean"}},
            image_assets=[{"url": "https://img.example/anaya.jpg", "role": "cover"}],
            scenarios=["travel", "general"],
            active_archetype="travel",
            planner_output={"block_intents": [{"intent_type": "hero_media"}]},
        )

    def _build_daily_note_document(self) -> dict[str, Any]:
        return build_note_document(
            document_view={
                "page_title": "今天的生活小记",
                "blocks": [
                    {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                    {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                    {"id": "weather_1", "component_type": "WeatherPolaroid", "content_brief": "氛围"},
                    {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
                ],
                "title_1": {"type": "TitleBlock", "title": "今天的生活小记"},
                "story_1": {"type": "StoryText", "paragraphs": ["把一天里最轻松的一段情绪留下来。"]},
                "weather_1": {"type": "WeatherPolaroid", "desc": "今天适合慢下来。", "weather": "多云", "temperature": "22°C", "time": "傍晚"},
                "poll_1": {"type": "PollBlock", "question": "你今天更想休息还是出门？", "option_a": "休息", "option_b": "出门"},
            },
            block_style_map={"global_vars": {"--theme-name": "daily_soft"}},
            scenarios=["daily_share", "general"],
            active_archetype="daily_share",
            planner_output={"block_intents": [{"intent_type": "narrative_text"}]},
        )


@pytest.fixture
def e2e_client(monkeypatch):
    async def _no_cache(*args, **kwargs):
        return None

    async def _no_veto(*args, **kwargs):
        return False

    async def _noop_background(*args, **kwargs):
        return None

    monkeypatch.setattr(chat_api, "get_trend_cache", _no_cache)
    monkeypatch.setattr(chat_api, "process_new_trend_background", _noop_background)
    monkeypatch.setattr(chat_api.RiskControlCache, "check_veto", staticmethod(_no_veto))

    app = FastAPI()
    agent = FakeE2EAgent()
    app.state.agent = agent
    app.state.vector_store = SimpleNamespace()
    app.include_router(workspace_router)
    app.include_router(chat_router, prefix="/ws")

    with TestClient(app) as client:
        yield client, agent


def _send_ws_message(client: TestClient, thread_id: str, content: str, *, selected_element_id: str = "无 (全局修改)"):
    with client.websocket_connect(f"/ws/chat/{thread_id}") as websocket:
        websocket.send_json(
            {
                "content": content,
                "panel": "main",
                "selected_element_id": selected_element_id,
                "creator_persona": "硬核数码博主",
            }
        )
        while True:
            payload = websocket.receive_json()
            if payload.get("event") == "turn_end":
                return payload["data"]


def _send_ws_message_with_assets(
    client: TestClient,
    thread_id: str,
    content: str,
    *,
    current_assets: list[dict[str, Any]],
    selected_element_id: str = "无 (全局修改)",
):
    with client.websocket_connect(f"/ws/chat/{thread_id}") as websocket:
        websocket.send_json(
            {
                "content": content,
                "panel": "main",
                "selected_element_id": selected_element_id,
                "creator_persona": "硬核数码博主",
                "current_assets": current_assets,
            }
        )
        while True:
            payload = websocket.receive_json()
            if payload.get("event") == "turn_end":
                return payload["data"]


def test_e2e_seeding_create_flow_generates_multi_block_note_without_weather_polaroid(e2e_client):
    client, _agent = e2e_client
    turn_end = _send_ws_message(client, "thread-e2e-seeding", "帮我生成一篇关于华为 Mate 60 的对比种草笔记")

    note_document = turn_end["note_document"]
    block_types = [str(block.get("type") or "") for block in (note_document.get("blocks") or [])]
    assert len(block_types) >= 5
    assert "TitleBlock" in block_types
    assert "VersusCard" in block_types
    assert "PollBlock" in block_types
    assert "WeatherPolaroid" not in block_types

    workspace = client.get("/workspace/thread-e2e-seeding")
    assert workspace.status_code == 200
    payload = workspace.json()
    assert payload["note_document"]["document_meta"]["title"] == "华为 Mate 60 对比种草"
    assert payload["inspector_summary"]["retrieval"]["grounding_status"] == "grounded"


def test_e2e_travel_create_flow_surfaces_cover_and_location_block(e2e_client):
    client, _agent = e2e_client
    turn_end = _send_ws_message(client, "thread-e2e-travel", "帮我做一篇阿那亚一日游攻略，信息要靠谱一点")

    block_types = [str(block.get("type") or "") for block in (turn_end["note_document"].get("blocks") or [])]
    assert "CoverSwiper" in block_types
    assert "LocationBlock" in block_types

    inspect = client.get("/workspace/thread-e2e-travel/inspect")
    assert inspect.status_code == 200
    data = inspect.json()["data"]
    assert data["inspector_summary"]["focus"]["scenarios"][0] == "travel"


def test_e2e_local_edit_flow_updates_target_block_and_trace(e2e_client):
    client, _agent = e2e_client
    _send_ws_message(client, "thread-e2e-edit", "帮我生成一篇关于华为 Mate 60 的对比种草笔记")
    turn_end = _send_ws_message(client, "thread-e2e-edit", "把这个投票改得更毒舌一点", selected_element_id="poll_1")

    changed_blocks = turn_end["turn_trace"]["changed_blocks"]
    assert any(item["id"] == "poll_1" for item in changed_blocks)

    workspace = client.get("/workspace/thread-e2e-edit")
    note_document = workspace.json()["note_document"]
    poll_block = next(block for block in (note_document.get("blocks") or []) if block.get("id") == "poll_1")
    assert poll_block["props"]["question"] == "如果只能选一个，你更看重影像还是续航？"


def test_e2e_benchmark_and_evaluation_overview_aggregate_recent_sessions(e2e_client):
    client, _agent = e2e_client
    _send_ws_message(client, "thread-e2e-bench-seeding", "帮我生成一篇关于华为 Mate 60 的对比种草笔记")
    _send_ws_message(client, "thread-e2e-bench-travel", "帮我做一篇阿那亚一日游攻略，信息要靠谱一点")
    _send_ws_message(client, "thread-e2e-bench-daily", "帮我写一篇日常分享，语气轻一点")

    benchmark = client.get("/workspace/benchmark/overview")
    assert benchmark.status_code == 200
    benchmark_data = benchmark.json()["data"]
    scenario_names = [item["scenario"] for item in benchmark_data["distributions"]["scenarios"]]
    assert "seeding" in scenario_names
    assert "travel" in scenario_names
    assert benchmark_data["rag"]["grounded_session_rate"] > 0

    evaluation = client.get("/workspace/evaluation/overview")
    assert evaluation.status_code == 200
    evaluation_data = evaluation.json()["data"]
    category_names = [item["name"] for item in evaluation_data["categories"]]
    assert "路由评估" in category_names
    assert "RAG 评估" in category_names


def test_e2e_trend_cache_fast_path_is_disabled_when_runtime_assets_exist(e2e_client, monkeypatch):
    client, _agent = e2e_client

    cached_note_document = build_note_document(
        document_view={
            "page_title": "缓存页",
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
            ],
            "cover_1": {"type": "CoverSwiper", "image_urls": []},
        },
        block_style_map={"global_vars": {"--theme-name": "xhs-clean"}},
        image_assets=[],
        scenarios=["seeding"],
        active_archetype="seeding",
        planner_output={"block_intents": [{"intent_type": "hero_media"}]},
    )

    async def _cached(*args, **kwargs):
        return cached_note_document

    monkeypatch.setattr(chat_api, "get_trend_cache", _cached)

    turn_end = _send_ws_message_with_assets(
        client,
        "thread-e2e-trend-assets",
        "帮我生成一篇关于华为 Mate 60 的对比种草笔记",
        current_assets=[{"url": "https://img.example/mate-cover.jpg", "role": "cover"}],
    )

    block_types = [str(block.get("type") or "") for block in (turn_end["note_document"].get("blocks") or [])]
    assert len(block_types) >= 5
    assert "VersusCard" in block_types
    assert turn_end["note_document"]["document_meta"]["title"] != "缓存页"
