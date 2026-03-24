from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketState

from app.api.chat import _build_turn_end_payload, _run_graph_loop, _send_capability_reply
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

    async def astream_events(self, inputs, config=None, version="v2"):
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


class FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.messages = []
        self.app = SimpleNamespace(state=SimpleNamespace(vector_store=SimpleNamespace()))

    async def send_json(self, payload):
        self.messages.append(payload)


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
            "node_prompts": {},
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
    assert websocket.messages[1]["node"] == "supervisor_agent"
    assert "我现在主要可以这样和你配合" in websocket.messages[1]["data"]
    assert websocket.messages[-1]["event"] == "turn_end"


@pytest.mark.asyncio
async def test_run_graph_loop_returns_modern_turn_end_payload():
    snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/a.jpg", "desc": "hero"}],
            "note_document": build_note_document(
                document_view={"page_title": "Mate 60 页面", "blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
                block_style_map={"global_vars": {"--bg-color": "#fff"}},
            ),
            "final_html": "<html><body>ok</body></html>",
            "node_prompts": {"intent_worker": "prompt"},
        }
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_graph_loop(
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
    assert data["node_prompts"]["intent_worker"] == "prompt"
    assert data["nodePrompts"]["intent_worker"] == "prompt"
    assert data["turn_trace"]["query"] == "帮我生成一篇华为 Mate 60 笔记"
    assert "changed_blocks" in data["turn_trace"]
    assert data["artifact"]["artifact_type"] == "purchase_decision_note"
    assert data["artifact_version"]["version_id"].startswith("version_")
    assert data["artifact_version"]["parent_version_id"] in ("", None)
    assert data["revision_status"]["status"] in {"idle", "ready", "applied", "failed"}


@pytest.mark.asyncio
async def test_run_graph_loop_emits_action_required_from_pending_checkpoint_state():
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

    await _run_graph_loop(
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


@pytest.mark.asyncio
async def test_run_graph_loop_preserves_selected_element_in_graph_inputs():
    snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "note_document": {"document_meta": {"title": "局部编辑页"}, "blocks": [], "assets": []},
            "final_html": "<html></html>",
            "node_prompts": {},
        },
        checkpoint_id="ckpt_ws_local",
    )
    agent = FakeAgent(snapshot)
    websocket = FakeWebSocket()

    await _run_graph_loop(
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
    assert call["version"] == "v2"


@pytest.mark.asyncio
async def test_run_graph_loop_uses_latest_thread_snapshot_when_parent_checkpoint_is_supplied():
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
            "node_prompts": {"planner_agent": [{"role": "system", "content": "p"}]},
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

    await _run_graph_loop(
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
async def test_run_graph_loop_turn_trace_is_written_back_to_latest_snapshot():
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

    await _run_graph_loop(
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
