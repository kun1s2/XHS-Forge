from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocketState

from app.api.chat import _build_turn_end_payload, _run_graph_loop
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
        if isinstance(values, dict) and values.get("turn_trace"):
            latest_values = dict(self.latest_snapshot.values)
            latest_values["turn_trace"] = values["turn_trace"]
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
async def test_run_graph_loop_returns_modern_turn_end_payload():
    snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/a.jpg", "desc": "hero"}],
            "note_document": build_note_document(
                document_view={"page_title": "Mate 60 页面", "blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
                block_style_map={"global_vars": {"--bg-color": "#fff"}},
            ),
            "final_html": "<html><body>ok</body></html>",
            "node_prompts": {"intent_agent": "prompt"},
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
    assert data["node_prompts"]["intent_agent"] == "prompt"
    assert data["nodePrompts"]["intent_agent"] == "prompt"
    assert data["turn_trace"]["query"] == "帮我生成一篇华为 Mate 60 笔记"
    assert "changed_blocks" in data["turn_trace"]


def test_turn_end_payload_drops_legacy_page_aliases():
    payload = _build_turn_end_payload(
        "ckpt_alias_trimmed",
        oss_url="https://example.com/render.html",
        image_assets=[],
        source_code="<html></html>",
        note_document={"document_meta": {"title": "Mate 60 页面"}, "blocks": [], "assets": []},
    )

    assert "page_data" not in payload
    assert "pageData" not in payload
    assert "style_data" not in payload
    assert "styleData" not in payload
    assert "noteData" not in payload


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
