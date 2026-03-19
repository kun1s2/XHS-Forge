from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import router as chat_router


class FakeSnapshot:
    def __init__(self, values, checkpoint_id="ckpt_ws_1"):
        self.next = []
        self.values = values
        self.config = {"configurable": {"checkpoint_id": checkpoint_id}}


class FakeAgent:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    async def astream_events(self, inputs, config=None, version="v2"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        if False:
            yield {}

    async def aget_state(self, config):
        return self.snapshot

    async def aupdate_state(self, config, values):
        return None


def _build_test_app(agent):
    app = FastAPI()
    app.include_router(chat_router, prefix="/ws")
    app.state.agent = agent
    app.state.vector_store = SimpleNamespace()
    return app


def test_websocket_turn_end_returns_compatible_payload(monkeypatch):
    async def fake_check_veto(_query):
        return False

    async def fake_get_cache(_query, _selected):
        return None

    async def fake_process_trend(_query, websocket=None):
        return None

    monkeypatch.setattr("app.api.chat.RiskControlCache.check_veto", fake_check_veto)
    monkeypatch.setattr("app.api.chat.get_trend_cache", fake_get_cache)
    monkeypatch.setattr("app.api.chat.process_new_trend_background", fake_process_trend)

    snapshot = FakeSnapshot(
        {
            "image_assets": [{"url": "https://img.example/a.jpg", "desc": "hero"}],
            "data_dsl": {"page_title": "Mate 60 页面", "blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
            "style_dsl": {"global_vars": {"--bg-color": "#fff"}},
            "final_html": "<html><body>ok</body></html>",
            "node_prompts": {"intent_agent": "prompt"},
        }
    )
    agent = FakeAgent(snapshot)
    app = _build_test_app(agent)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat/thread-ws-1") as websocket:
            websocket.send_json(
                {
                    "content": "帮我生成一篇华为 Mate 60 笔记",
                    "panel": "main",
                    "selected_element_id": "无 (全局修改)",
                    "creator_persona": "硬核数码博主",
                }
            )
            message = websocket.receive_json()

    assert message["event"] == "turn_end"
    data = message["data"]
    assert data["checkpoint_id"] == "ckpt_ws_1"
    assert data["checkpointId"] == "ckpt_ws_1"
    assert data["page_data"]["page_title"] == "Mate 60 页面"
    assert data["pageData"]["page_title"] == "Mate 60 页面"
    assert data["noteData"]["page_title"] == "Mate 60 页面"
    assert data["style_data"]["global_vars"]["--bg-color"] == "#fff"
    assert data["styleData"]["global_vars"]["--bg-color"] == "#fff"
    assert data["source_code"] == "<html><body>ok</body></html>"
    assert data["htmlPreview"] == "<html><body>ok</body></html>"
    assert data["node_prompts"]["intent_agent"] == "prompt"
    assert data["nodePrompts"]["intent_agent"] == "prompt"


def test_websocket_selected_element_id_flows_into_graph_inputs(monkeypatch):
    async def fake_check_veto(_query):
        return False

    async def fake_get_cache(_query, _selected):
        return None

    async def fake_process_trend(_query, websocket=None):
        return None

    monkeypatch.setattr("app.api.chat.RiskControlCache.check_veto", fake_check_veto)
    monkeypatch.setattr("app.api.chat.get_trend_cache", fake_get_cache)
    monkeypatch.setattr("app.api.chat.process_new_trend_background", fake_process_trend)

    snapshot = FakeSnapshot(
        {
            "image_assets": [],
            "data_dsl": {"page_title": "局部编辑页", "blocks": []},
            "style_dsl": {},
            "final_html": "<html></html>",
            "node_prompts": {},
        },
        checkpoint_id="ckpt_ws_local",
    )
    agent = FakeAgent(snapshot)
    app = _build_test_app(agent)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat/thread-ws-2") as websocket:
            websocket.send_json(
                {
                    "content": "把这个投票改得更毒舌一点",
                    "panel": "main",
                    "selected_element_id": "poll_1",
                    "creator_persona": "毒舌测评博主",
                }
            )
            message = websocket.receive_json()

    assert message["event"] == "turn_end"
    assert len(agent.calls) == 1
    call = agent.calls[0]
    assert call["inputs"]["selected_element_id"] == "poll_1"
    assert call["inputs"]["active_panel"] == "main"
    assert call["inputs"]["creator_persona"] == "毒舌测评博主"
    assert call["version"] == "v2"
