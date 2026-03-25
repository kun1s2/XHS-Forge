from types import SimpleNamespace

import pytest
from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from starlette.websockets import WebSocketState

from app.agents.runtime import apply_supervisor_checkpoint_decision
from app.agents.runtime import supervisor_runtime as supervisor_runtime_module
from app.api.chat import _build_turn_end_payload, _run_supervisor_turn, _send_capability_reply
from app.schemas.requests import ChatWSPayload
from app.core.note_document import build_note_document


class FakeSnapshot:
    def __init__(self, values, checkpoint_id="ckpt_ws_1"):
        self.next = []
        self.values = values
        self.config = {"configurable": {"checkpoint_id": checkpoint_id}}


class FakeAgent:
    def __init__(self, snapshot, latest_snapshot=None):
        self.snapshot = snapshot
        self.latest_snapshot = latest_snapshot or snapshot
        self.calls = []
        self.updated = []

    async def astream_events(self, inputs, config=None, version="runtime"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        if False:
            yield {}

    async def aget_state(self, config):
        configurable = (config or {}).get("configurable") or {}
        if configurable.get("checkpoint_id"):
            return self.snapshot
        return self.latest_snapshot

    async def aupdate_state(self, config, values):
        self.updated.append({"config": config, "values": values})
        if isinstance(values, dict):
            latest_values = dict(self.latest_snapshot.values)
            latest_values.update(values)
            self.latest_snapshot = FakeSnapshot(
                latest_values,
                checkpoint_id=self.latest_snapshot.config["configurable"]["checkpoint_id"],
            )
        return None


class ScriptedFlowAgent(FakeAgent):
    async def astream_events(self, inputs, config=None, version="runtime"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        values = dict(self.latest_snapshot.values)
        messages = list(inputs.get("messages") or [])
        prompt = ""
        if messages:
            content = getattr(messages[-1], "content", "")
            prompt = content if isinstance(content, str) else str(content)

        if "更直接" in prompt:
            next_values = dict(values)
            next_values.update(
                {
                    "current_phase": "composition",
                    "final_html": "<html><body>edited</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": [
                            {"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60 值不值得买"}},
                            {
                                "id": "story_1",
                                "type": "StoryText",
                                "props": {
                                    "paragraphs": [
                                        "如果你预算就在 4500 元上下，又特别看重拍照和续航，华为 Mate 60 依然值得优先看。",
                                        "真正要纠结的不是它强不强，而是你能不能接受价格门槛和同价位竞品带来的取舍。",
                                    ]
                                },
                            },
                        ],
                        "assets": [],
                    },
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "resume_directive": None,
                    "pending_checkpoint": None,
                }
            )
            self.latest_snapshot = FakeSnapshot(
                next_values,
                checkpoint_id=self.latest_snapshot.config["configurable"]["checkpoint_id"],
            )
        if False:
            yield {}


class RetrievalOnlyCreateAgent(FakeAgent):
    async def astream_events(self, inputs, config=None, version="runtime"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        values = dict(self.latest_snapshot.values)
        values.update(
            {
                "intent_decision": {"task_type": "create", "operation_type": "generate"},
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "retrieval_summary": {"strategy": "structured_knowledge_first"},
                },
                "planner_output": {
                    "block_intents": [
                        {"intent_type": "heading"},
                        {"intent_type": "decision_summary"},
                    ]
                },
                "resume_directive": {
                    "preferred_worker": "composition_worker",
                    "resume_query": "继续把购买决策档案落成可见页面，不要停在分析阶段。",
                    "decision": "auto_materialize",
                },
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [{"field": "price"}],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "pending_checkpoint": None,
            }
        )
        self.latest_snapshot = FakeSnapshot(
            values,
            checkpoint_id=self.latest_snapshot.config["configurable"]["checkpoint_id"],
        )
        if False:
            yield {}


class RetrievalOnlyAssetEditAgent(FakeAgent):
    async def astream_events(self, inputs, config=None, version="runtime"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        values = dict(self.latest_snapshot.values)
        values.update(
            {
                "intent_decision": {
                    "task_type": "edit",
                    "operation_type": "asset_edit",
                    "needs_assets": True,
                    "needs_research": True,
                },
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "retrieval_summary": {"strategy": "image_search_first"},
                },
                "image_assets": [
                    {"asset_id": "img_1", "url": "https://img.example/mate60-1.jpg", "desc": "Mate 60 真机图 1"},
                    {"asset_id": "img_2", "url": "https://img.example/mate60-2.jpg", "desc": "Mate 60 真机图 2"},
                ],
                "resume_directive": None,
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "pending_checkpoint": None,
            }
        )
        self.latest_snapshot = FakeSnapshot(
            values,
            checkpoint_id=self.latest_snapshot.config["configurable"]["checkpoint_id"],
        )
        if False:
            yield {}


class FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.messages = []
        self.app = SimpleNamespace(state=SimpleNamespace(vector_store=SimpleNamespace()))

    async def send_json(self, payload):
        self.messages.append(payload)


def test_sanitize_persistent_conversation_messages_drops_tool_messages():
    from app.api.chat import _sanitize_persistent_conversation_messages

    human = HumanMessage(content="我想补图")
    ai_with_tool = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "retrieval_worker", "args": {}}])
    tool = ToolMessage(content="检索结果", tool_call_id="call_1")
    safe_ai = AIMessage(content="我先帮你整理候选图。")

    sanitized = _sanitize_persistent_conversation_messages([human, ai_with_tool, tool, safe_ai])

    assert sanitized == [human, safe_ai]


@pytest.mark.asyncio
async def test_send_capability_reply_streams_direct_chat_response_without_rendering():
    snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "note_document": build_note_document(
                document_view={"page_title": "当前页面", "blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
                block_style_map={},
            ),
            "final_html": "<html></html>",
            "worker_prompts": {},
        },
        checkpoint_id="ckpt_direct_chat",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()
    payload = ChatWSPayload(content="你有什么功能?", panel="main")

    await _send_capability_reply(
        agent=agent,
        thread_id="thread-capability",
        payload=payload,
        websocket=websocket,
        user_query_str="你有什么功能?",
    )

    assert websocket.messages[0]["event"] == "thought"
    assert websocket.messages[1]["event"] == "token"
    assert websocket.messages[1]["worker"] == "supervisor_agent"
    assert "我现在主要可以这样和你配合" in websocket.messages[1]["data"]
    assert websocket.messages[-1]["event"] == "turn_end"


@pytest.mark.asyncio
async def test_run_supervisor_turn_returns_modern_turn_end_payload():
    snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/mate60-hero.jpg", "desc": "华为 Mate 60 hero"}],
            "note_document": build_note_document(
                document_view={"page_title": "Mate 60 页面", "blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
                block_style_map={"global_vars": {"--bg-color": "#fff"}},
            ),
            "final_html": "<html><body>ok</body></html>",
            "worker_prompts": {"intent_worker": "prompt"},
        }
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {"active_panel": "main", "selected_element_id": "无 (全局修改)"},
        {"configurable": {"thread_id": "thread-ws-1"}},
        websocket,
        turn_context={
            "user_query": "帮我生成一篇华为 Mate 60 笔记",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )

    message = websocket.messages[-1]
    assert message["event"] == "turn_end"
    data = message["data"]
    assert data["checkpoint_id"] == "ckpt_ws_1"
    assert data["checkpointId"] == "ckpt_ws_1"
    assert "page_data" not in data
    assert "pageData" not in data
    assert "style_data" not in data
    assert "styleData" not in data
    assert data["note_document"]["document_meta"]["title"] == "Mate 60 页面"
    assert data["source_code"] == "<html><body>ok</body></html>"
    assert data["htmlPreview"] == "<html><body>ok</body></html>"
    assert data["worker_prompts"]["intent_worker"] == "prompt"
    assert data["workerPrompts"]["intent_worker"] == "prompt"
    assert data["turn_trace"]["query"] == "帮我生成一篇华为 Mate 60 笔记"
    assert "changed_blocks" in data["turn_trace"]
    assert data["artifact"]["artifact_type"] == "purchase_decision_note"
    assert data["artifact_version"]["version_id"].startswith("version_")
    assert data["artifact_version"]["parent_version_id"] in ("", None)
    assert data["revision_status"]["status"] in {"idle", "ready", "applied", "failed"}


@pytest.mark.asyncio
async def test_run_supervisor_turn_emits_action_required_from_pending_checkpoint_state():
    snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "note_document": {"document_meta": {"title": "Mate 60 页面"}, "blocks": [], "assets": []},
            "pending_checkpoint": {
                "checkpoint_type": "knowledge_review_checkpoint",
                "checkpoint_id": "knowledge-review::seeding",
                "title": "需要确认候选知识",
                "summary": "请先确认这轮候选知识怎么采用",
                "options": [{"label": "采用推荐项", "value": "approve_recommended", "recommended": True}],
                "resume_token": "thread:ckpt:resume",
            },
        },
        checkpoint_id="ckpt_action_required",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {"messages": [], "main_messages": []},
        {"configurable": {"thread_id": "thread-ws-action"}},
        websocket,
        turn_context={
            "user_query": "继续",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )

    assert websocket.messages[-1]["event"] == "action_required"
    payload = websocket.messages[-1]["data"]
    assert payload["checkpoint_type"] == "knowledge_review_checkpoint"
    assert payload["resume_token"] == "thread:ckpt:resume"


def test_turn_end_payload_uses_note_document_only_fields():
    payload = _build_turn_end_payload(
        "ckpt_alias_trimmed",
        oss_url="https://example.com/render.html",
        image_assets=[],
        source_code="<html></html>",
        note_document={"document_meta": {"title": "Mate 60 页面"}, "blocks": [], "assets": []},
        artifact={"artifact_id": "artifact_demo", "artifact_type": "purchase_decision_note"},
        artifact_version={"version_id": "version_demo"},
        revision_status={"status": "ready"},
    )

    assert "page_data" not in payload
    assert "pageData" not in payload
    assert "style_data" not in payload
    assert "styleData" not in payload
    assert "noteData" not in payload
    assert payload["artifact"]["artifact_id"] == "artifact_demo"
    assert payload["artifactVersion"]["version_id"] == "version_demo"
    assert payload["revisionStatus"]["status"] == "ready"


def test_apply_supervisor_checkpoint_decision_clears_pending_checkpoint():
    patch = apply_supervisor_checkpoint_decision(
        {
            "pending_checkpoint": {
                "checkpoint_type": "structure_checkpoint",
                "checkpoint_id": "structure::seeding",
            },
            "planner_output": {"block_intents": []},
            "planner_policy": {"layout_policy": {}},
            "active_archetype": "seeding",
            "main_messages": [],
            "selected_element_id": "",
            "active_panel": "main",
            "intent_decision": {"task_type": "create"},
        },
        {
            "action_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding",
            "decision": "seeding_compare",
        },
    )

    assert patch["pending_checkpoint"] is None
    assert patch["resume_directive"]["preferred_worker"] == "retrieval_worker"
    assert "不要再次请求结构确认" in patch["resume_directive"]["resume_query"]


@pytest.mark.asyncio
async def test_run_supervisor_turn_preserves_selected_element_in_runtime_inputs():
    snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "note_document": {"document_meta": {"title": "局部编辑页"}, "blocks": [], "assets": []},
            "final_html": "<html></html>",
            "worker_prompts": {},
        },
        checkpoint_id="ckpt_ws_local",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {
            "active_panel": "main",
            "selected_element_id": "poll_1",
            "creator_persona": "毒舌测评博主",
        },
        {"configurable": {"thread_id": "thread-ws-2"}},
        websocket,
        turn_context={
            "user_query": "把这个投票改得更毒舌一点",
            "selected_element_id": "poll_1",
            "panel": "main",
            "before_values": {},
        },
    )

    assert len(agent.calls) == 1
    call = agent.calls[0]
    assert call["inputs"]["selected_element_id"] == "poll_1"
    assert call["inputs"]["active_panel"] == "main"
    assert call["inputs"]["creator_persona"] == "毒舌测评博主"
    assert call["version"] == "runtime"


@pytest.mark.asyncio
async def test_run_supervisor_turn_uses_latest_thread_snapshot_when_parent_snapshot_is_supplied():
    parent_snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/cover.jpg", "desc": "old hero"}],
            "final_html": "",
            "note_document": {"document_meta": {"title": "旧封面"}, "blocks": [{"id": "cover_1", "type": "CoverSwiper", "props": {}}], "assets": []},
        },
        checkpoint_id="parent_ckpt",
    )
    latest_snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/cover.jpg", "desc": "hero"}],
            "final_html": "<html><body>new</body></html>",
            "worker_prompts": {"planner_agent": [{"role": "system", "content": "p"}]},
            "note_document": {
                "document_meta": {"title": "Mate 60 页面"},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "props": {}},
                    {"id": "story_1", "type": "StoryText", "props": {}},
                ],
                "assets": [],
            },
        },
        checkpoint_id="latest_ckpt",
    )
    agent = FakeAgent(parent_snapshot, latest_snapshot=latest_snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {"active_panel": "main", "selected_element_id": "无 (全局修改)"},
        {"configurable": {"thread_id": "thread-ws-parent", "checkpoint_id": "parent_ckpt"}},
        websocket,
        turn_context={
            "user_query": "继续完善这篇笔记",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": parent_snapshot.values,
        },
    )

    turn_end = websocket.messages[-1]
    assert turn_end["event"] == "turn_end"
    assert turn_end["data"]["checkpoint_id"] == "latest_ckpt"
    assert turn_end["data"]["note_document"]["document_meta"]["title"] == "Mate 60 页面"
    assert turn_end["data"]["source_code"] == "<html><body>new</body></html>"


@pytest.mark.asyncio
async def test_run_supervisor_turn_turn_trace_is_written_back_to_latest_snapshot():
    latest_snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "final_html": "<html></html>",
            "note_document": {"document_meta": {"title": "Mate 60 页面"}, "blocks": [], "assets": []},
        },
        checkpoint_id="latest_ckpt",
    )
    agent = FakeAgent(latest_snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {"active_panel": "main", "selected_element_id": "无 (全局修改)"},
        {"configurable": {"thread_id": "thread-ws-trace"}},
        websocket,
        turn_context={
            "user_query": "帮我继续整理",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )

    assert agent.updated
    assert "turn_trace" in agent.updated[-1]["values"]
    assert "artifact" in agent.updated[-1]["values"]
    assert "artifact_version" in agent.updated[-1]["values"]


@pytest.mark.asyncio
async def test_run_supervisor_turn_resume_protocol_executes_workers_without_model(monkeypatch):
    async def _fake_retrieval(*, focus="", runtime=None):
        return Command(
            update={
                "current_phase": "retrieval",
                "resume_directive": {
                    "preferred_worker": "composition_worker",
                    "resume_query": "继续把页面落成完整档案",
                    "decision": "auto_followup",
                },
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [{"field": "price"}],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "retrieved_knowledge": {"retrieval_summary": {"strategy": "structured_first"}},
            }
        )

    async def _fake_composition(*, focus="", runtime=None):
        return Command(
            update={
                "current_phase": "composition",
                "resume_directive": None,
                "note_document": {
                    "document_meta": {"title": "Mate 60 购买决策档案"},
                    "blocks": [
                        {"id": "title_1", "type": "TitleBlock", "props": {"title": "Mate 60 值不值得买"}},
                        {
                            "id": "story_1",
                            "type": "StoryText",
                            "props": {"paragraphs": ["Mate 60 更适合看重影像风格、续航稳定和品牌体验的人。"]},
                        },
                        {
                            "id": "risk_1",
                            "type": "StoryText",
                            "props": {"paragraphs": ["如果你更在意极致性价比和激进堆料，它不是唯一答案。"]},
                            "semantic_role": "narrative_text",
                        },
                    ],
                    "assets": [],
                },
                "last_worker_result": {
                    "worker_name": "composition_worker",
                    "status": "success",
                    "changed_blocks": [
                        {"id": "title_1", "type": "TitleBlock", "changed_fields": ["added"]},
                        {"id": "story_1", "type": "StoryText", "changed_fields": ["added"]},
                        {"id": "risk_1", "type": "StoryText", "changed_fields": ["added"]},
                    ],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": True,
                },
            }
        )

    monkeypatch.setattr(supervisor_runtime_module.retrieval_worker, "coroutine", _fake_retrieval)
    monkeypatch.setattr(supervisor_runtime_module.composition_worker, "coroutine", _fake_composition)

    snapshot = FakeSnapshot(
        {
            "resume_directive": {
                "preferred_worker": "retrieval_worker",
                "resume_query": "继续推进",
                "decision": "approve",
            },
            "note_document": {"document_meta": {"title": "空白页"}, "blocks": [], "assets": []},
            "image_assets": [],
            "final_html": "",
        },
        checkpoint_id="ckpt_resume_protocol",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {"messages": [], "main_messages": []},
        {"configurable": {"thread_id": "thread-resume-protocol"}},
        websocket,
        turn_context={
            "user_query": "",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )

    assert agent.calls == []
    assert websocket.messages[-1]["event"] == "turn_end"
    assert websocket.messages[-1]["data"]["note_document"]["blocks"][0]["id"] == "title_1"
    assert websocket.messages[-1]["data"]["artifact_version"]["version_id"].startswith("version_")


@pytest.mark.asyncio
async def test_run_supervisor_turn_auto_materializes_empty_create_canvas(monkeypatch):
    async def _fake_composition(*, focus="", runtime=None):
        return Command(
            update={
                "current_phase": "composition",
                "resume_directive": None,
                "note_document": {
                    "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                    "blocks": [
                        {"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60 值不值得买"}}
                    ],
                    "assets": [],
                },
                "last_worker_result": {
                    "worker_name": "composition_worker",
                    "status": "success",
                    "changed_blocks": [{"id": "title_1", "type": "TitleBlock", "changed_fields": ["added"]}],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": True,
                },
            }
        )

    monkeypatch.setattr(supervisor_runtime_module.composition_worker, "coroutine", _fake_composition)

    snapshot = FakeSnapshot(
        {
            "note_document": {"document_meta": {"title": "空白页"}, "blocks": [], "assets": []},
            "image_assets": [],
            "final_html": "",
            "worker_prompts": {},
        },
        checkpoint_id="ckpt_auto_materialize",
    )
    agent = RetrievalOnlyCreateAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
        },
        {"configurable": {"thread_id": "thread-auto-materialize"}},
        websocket,
        turn_context={
            "user_query": "帮我判断华为 Mate 60 值不值得买，并生成购买决策档案",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "message_kind": "user_prompt",
            "before_values": {},
        },
    )

    assert websocket.messages[-1]["event"] == "turn_end"
    note_document = websocket.messages[-1]["data"]["note_document"]
    assert note_document["blocks"]
    assert note_document["blocks"][0]["id"] == "title_1"


@pytest.mark.asyncio
async def test_run_supervisor_turn_auto_materializes_asset_edit_on_existing_canvas(monkeypatch):
    async def _fake_retrieval(*, focus="", runtime=None):
        assert "图片" in focus or "真机" in focus
        return Command(
            update={
                "current_phase": "retrieval",
                "intent_decision": {
                    "task_type": "edit",
                    "operation_type": "asset_edit",
                    "needs_assets": True,
                    "needs_research": True,
                },
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "retrieval_summary": {"strategy": "image_search_first"},
                },
                "image_assets": [
                    {"asset_id": "img_1", "url": "https://img.example/mate60-1.jpg", "desc": "Mate 60 真机图 1"},
                    {"asset_id": "img_2", "url": "https://img.example/mate60-2.jpg", "desc": "Mate 60 真机图 2"},
                ],
                "resume_directive": None,
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "pending_checkpoint": None,
            }
        )

    async def _fake_composition(*, focus="", runtime=None):
        assert "图片" in focus or "素材" in focus
        return Command(
            update={
                "current_phase": "composition",
                "resume_directive": None,
                "note_document": {
                    "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                    "blocks": [
                        {"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60 值不值得买"}},
                        {
                            "id": "story_1",
                            "type": "StoryText",
                            "props": {"paragraphs": ["如果你看重拍照风格和续航稳定，Mate 60 仍然值得放进主选项。"]},
                        },
                        {
                            "id": "cover_1",
                            "type": "CoverSwiper",
                            "props": {
                                "image_urls": [
                                    "https://img.example/mate60-1.jpg",
                                    "https://img.example/mate60-2.jpg",
                                ]
                            },
                        },
                    ],
                    "assets": [
                        {"asset_id": "img_1", "url": "https://img.example/mate60-1.jpg"},
                        {"asset_id": "img_2", "url": "https://img.example/mate60-2.jpg"},
                    ],
                },
                "last_worker_result": {
                    "worker_name": "composition_worker",
                    "status": "success",
                    "changed_blocks": [{"id": "cover_1", "type": "CoverSwiper", "changed_fields": ["props"]}],
                    "assets_delta": [
                        {"asset_id": "img_1", "url": "https://img.example/mate60-1.jpg"},
                        {"asset_id": "img_2", "url": "https://img.example/mate60-2.jpg"},
                    ],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": True,
                },
            }
        )

    monkeypatch.setattr(supervisor_runtime_module.retrieval_worker, "coroutine", _fake_retrieval)
    monkeypatch.setattr(supervisor_runtime_module.composition_worker, "coroutine", _fake_composition)

    snapshot = FakeSnapshot(
        {
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60 值不值得买"}},
                    {"id": "story_1", "type": "StoryText", "props": {"paragraphs": ["先看购买结论。"]}},
                ],
                "assets": [],
            },
            "image_assets": [],
            "final_html": "",
            "worker_prompts": {},
        },
        checkpoint_id="ckpt_asset_materialize",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="这份档案图片太少了，补几张更像真机质感的图片。")],
            "main_messages": [HumanMessage(content="这份档案图片太少了，补几张更像真机质感的图片。")],
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
        },
        {"configurable": {"thread_id": "thread-asset-materialize"}},
        websocket,
        turn_context={
            "user_query": "这份档案图片太少了，补几张更像真机质感的图片。",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "message_kind": "user_prompt",
            "before_values": {},
        },
    )

    assert websocket.messages[-1]["event"] == "turn_end"
    note_document = websocket.messages[-1]["data"]["note_document"]
    assert any(block.get("id") == "cover_1" for block in note_document["blocks"])
    assert websocket.messages[-1]["data"]["artifact_version"]["version_id"].startswith("version_")


@pytest.mark.asyncio
async def test_long_flow_checkpoint_resume_then_revision_edit(monkeypatch):
    async def _fake_retrieval(*, focus="", runtime=None):
        return Command(
            update={
                "current_phase": "retrieval",
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "summary": "华为 Mate 60 更适合先从购买结论、关键参数和真实代价三个角度来判断。",
                    "retrieval_summary": {"strategy": "structured_knowledge_first", "entity_name": "华为 Mate 60"},
                    "fact_slots": {
                        "price": {"summary": "当前价格大致落在 4500 元上下的讨论区间。"},
                        "battery": {"summary": "续航表现稳定，适合重度日用。"},
                    },
                },
                "resume_directive": {
                    "preferred_worker": "composition_worker",
                    "resume_query": "继续把已确认结构落成购买决策档案，不要再次请求结构确认。",
                    "decision": "seeding_compare",
                },
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [{"field": "price"}, {"field": "battery"}],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "pending_checkpoint": None,
            }
        )

    async def _fake_composition(*, focus="", runtime=None):
        focus_text = str(focus or "")
        is_revision = any(token in focus_text for token in ("更直接", "购买建议", "结论还不够直接", "优先修改区块"))
        story_paragraphs = (
            [
                "优先看你在不在乎华为这套影像风格和系统取向，如果在乎，Mate 60 依然值得优先考虑。",
                "如果你更在意纯参数堆料和更激进的性价比，那就别把它当成唯一答案。",
            ]
            if is_revision
            else [
                "如果你看重拍照风格和续航，Mate 60 这页已经能先给出明确结论。",
                "接下来更关键的是把价格边界和竞品取舍说透。",
            ]
        )
        changed_fields = ["props"] if is_revision else ["added"]
        return Command(
            update={
                "current_phase": "composition",
                "resume_directive": None,
                "final_html": "<html><body>created</body></html>",
                "note_document": {
                    "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                    "blocks": [
                        {"id": "title_1", "type": "TitleBlock", "props": {"title": "华为 Mate 60 值不值得买"}},
                        {
                            "id": "story_1",
                            "type": "StoryText",
                            "props": {"paragraphs": story_paragraphs},
                        },
                        {
                            "id": "risk_1",
                            "type": "StoryText",
                            "props": {"paragraphs": ["如果你更在意极致参数堆料，这页结论需要配合预算和偏好一起看。"]},
                        },
                    ],
                    "assets": [],
                },
                "critique_feedback": {
                    "action_recipes": [
                        {
                            "label": "把结论说得更直接",
                            "prompt": "把结论改得更直接一点，像给朋友的购买建议。",
                            "scope": "summary",
                            "why_now": "当前结论还不够直接。",
                            "expected_effect": "用户一眼就能看懂值不值得买。",
                        }
                    ]
                },
                "needs_revision": True,
                "last_worker_result": {
                    "worker_name": "composition_worker",
                    "status": "success",
                    "changed_blocks": [
                        {"id": "title_1", "type": "TitleBlock", "changed_fields": ["added"]},
                        {"id": "story_1", "type": "StoryText", "changed_fields": changed_fields},
                        {"id": "risk_1", "type": "StoryText", "changed_fields": ["added"]},
                    ],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": True,
                },
                "pending_checkpoint": None,
            }
        )

    monkeypatch.setattr(supervisor_runtime_module.retrieval_worker, "coroutine", _fake_retrieval)
    monkeypatch.setattr(supervisor_runtime_module.composition_worker, "coroutine", _fake_composition)

    initial_values = {
        "active_archetype": "seeding",
        "planner_output": {"block_intents": []},
        "planner_policy": {"layout_policy": {}},
        "intent_decision": {"task_type": "create", "operation_type": "generate"},
        "pending_checkpoint": {
            "checkpoint_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding_compare",
            "title": "这页先按哪种方向搭骨架？",
            "summary": "请先确认这页的主方向。",
            "options": [{"label": "更像对比测评", "value": "seeding_compare", "recommended": True}],
            "resume_token": "thread:structure:resume",
        },
        "note_document": {"document_meta": {"title": "空白页"}, "blocks": [], "assets": []},
        "image_assets": [],
        "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
    }
    agent = ScriptedFlowAgent(FakeSnapshot(initial_values, checkpoint_id="ckpt_long_flow"))
    websocket = FakeWebSocket()
    config = {"configurable": {"thread_id": "thread-long-flow"}}

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
        },
        config,
        websocket,
        turn_context={
            "user_query": "帮我判断华为 Mate 60 值不值得买，并生成购买决策档案",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )

    assert websocket.messages[-1]["event"] == "action_required"
    checkpoint_patch = apply_supervisor_checkpoint_decision(
        agent.latest_snapshot.values,
        {
            "action_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding_compare",
            "decision": "seeding_compare",
        },
    )
    await agent.aupdate_state(config, checkpoint_patch)

    await _run_supervisor_turn(
        agent,
        {"messages": [], "main_messages": []},
        config,
        websocket,
        turn_context={
            "user_query": "",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "message_kind": "checkpoint_decision",
            "before_values": initial_values,
        },
    )

    after_structure = websocket.messages[-1]
    if after_structure["event"] == "action_required":
        assert after_structure["data"]["checkpoint_type"] == "knowledge_review_checkpoint"

        checkpoint_patch = apply_supervisor_checkpoint_decision(
            agent.latest_snapshot.values,
            {
                "action_type": "knowledge_review_checkpoint",
                "checkpoint_id": after_structure["data"]["checkpoint_id"],
                "decision": "approve_recommended",
            },
        )
        await agent.aupdate_state(config, checkpoint_patch)

        await _run_supervisor_turn(
            agent,
            {"messages": [], "main_messages": []},
            config,
            websocket,
            turn_context={
                "user_query": "",
                "selected_element_id": "无 (全局修改)",
                "panel": "main",
                "message_kind": "checkpoint_decision",
                "before_values": agent.latest_snapshot.values,
            },
        )
        created_turn = websocket.messages[-1]
    else:
        created_turn = after_structure

    assert created_turn["event"] == "turn_end"
    created_data = created_turn["data"]
    assert created_data["note_document"]["document_meta"]["title"] == "华为 Mate 60 购买决策档案"
    assert created_data["artifact_version"]["version_id"].startswith("version_")
    first_version_id = created_data["artifact_version"]["version_id"]
    assert created_data["revision_status"]["status"] in {"ready", "applied"}

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="把结论改得更直接一点")],
            "main_messages": [HumanMessage(content="把结论改得更直接一点")],
            "active_panel": "main",
            "selected_element_id": "story_1",
        },
        config,
        websocket,
        turn_context={
            "user_query": "把结论改得更直接一点",
            "selected_element_id": "story_1",
            "panel": "main",
            "message_kind": "revision_action",
            "before_values": agent.latest_snapshot.values,
        },
    )

    revised_turn = websocket.messages[-1]
    assert revised_turn["event"] == "turn_end"
    revised_data = revised_turn["data"]
    assert revised_data["artifact_version"]["parent_version_id"] == first_version_id
    assert revised_data["artifact_version"]["revision_reason"]
    story_block = next(
        block for block in revised_data["note_document"]["blocks"] if block.get("id") == "story_1"
    )
    paragraphs = story_block.get("props", {}).get("paragraphs") or []
    assert any("优先看" in str(item) for item in paragraphs)
