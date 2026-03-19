from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.workspace import router as workspace_router


class FakeSnapshot:
    def __init__(self, values=None):
        self.values = values or {}


class FakeAgent:
    def __init__(self, values=None):
        self.snapshot = FakeSnapshot(values or {})
        self.updated = []

    async def aget_state(self, config):
        return self.snapshot

    async def aupdate_state(self, config, values):
        self.updated.append({"config": config, "values": values})
        return None


def _build_app(agent=None):
    app = FastAPI()
    app.include_router(workspace_router)
    app.state.agent = agent or FakeAgent()
    app.state.vector_store = SimpleNamespace()
    return app


def test_workspace_asset_search_endpoint_returns_structured_results(monkeypatch):
    async def fake_search(_query, num=5):
        return [f"https://img.example/{idx}.jpg" for idx in range(num)]

    monkeypatch.setattr("app.api.workspace.search_google_images", fake_search)
    app = _build_app()

    with TestClient(app) as client:
        response = client.get("/workspace/thread-1/assets/search", params={"query": "Mate 60 实拍图", "limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["results"]) == 3
    assert payload["results"][0]["source_type"] == "search"


def test_workspace_cover_endpoint_updates_cover_block_and_imports_asset():
    agent = FakeAgent(
        {
            "image_assets": [],
            "data_dsl": {
                "blocks": [{"id": "title_1", "component_type": "TitleBlock", "props": {}}],
                "title_1": {"type": "TitleBlock", "title": "旧标题"},
            },
        }
    )
    app = _build_app(agent)

    with TestClient(app) as client:
        response = client.post(
            "/workspace/thread-1/assets/cover",
            json={
                "url": "https://img.example/cover.jpg",
                "desc": "Mate 60 封面",
                "source_type": "search",
                "query": "Mate 60 实拍图",
            },
        )

    assert response.status_code == 200
    patch = agent.updated[0]["values"]
    assert patch["image_assets"][0]["url"] == "https://img.example/cover.jpg"
    assert patch["data_dsl"]["blocks"][0]["component_type"] == "CoverSwiper"
    assert patch["data_dsl"]["blocks"][1]["component_type"] == "TitleBlock"
    assert patch["data_dsl"]["title_1"]["title"] == "旧标题"
    cover_block = patch["data_dsl"]["blocks"][0]
    assert patch["data_dsl"][cover_block["id"]]["image_urls"] == ["https://img.example/cover.jpg"]


def test_workspace_fact_confirmation_updates_retrieved_knowledge():
    agent = FakeAgent(
        {
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "fact_conflicts": [
                    {
                        "field": "battery_capacity",
                        "values": [
                            {"value": "4500", "sources": ["媒体测评"]},
                            {"value": "5000", "sources": ["华为官网"]},
                        ],
                    }
                ],
                "fact_confidence": "low",
                "core_attributes": {},
                "text_facts": "资料存在冲突。",
            }
        }
    )
    app = _build_app(agent)

    with TestClient(app) as client:
        response = client.post(
            "/workspace/thread-1/facts/confirm",
            json={
                "field": "battery_capacity",
                "value": "5000",
                "sources": ["华为官网"],
            },
        )

    assert response.status_code == 200
    patch = agent.updated[0]["values"]["retrieved_knowledge"]
    assert patch["confirmed_facts"]["battery_capacity"]["value"] == "5000mAh"
    assert patch["core_attributes"]["battery_capacity"] == "5000mAh"
    assert patch["fact_review_status"] == "confirmed"
    assert patch["fact_conflicts"] == []
