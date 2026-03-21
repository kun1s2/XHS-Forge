import asyncio
from types import SimpleNamespace

from app.api.workspace import (
    AssetMutationRequest,
    FactConfirmationRequest,
    confirm_workspace_fact,
    import_workspace_asset,
    search_workspace_images,
    set_workspace_cover_asset,
)
from app.core.note_document import build_note_document


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


def _build_request(agent=None):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(agent=agent or FakeAgent(), vector_store=SimpleNamespace())))


def test_workspace_asset_search_endpoint_returns_structured_results(monkeypatch):
    async def fake_search(_query, num=5):
        return [f"https://img.example/{idx}.jpg" for idx in range(num)]

    monkeypatch.setattr("app.api.workspace.search_google_images", fake_search)
    payload = asyncio.run(search_workspace_images("thread-1", "Mate 60 实拍图", 3))
    assert payload.status == "success"
    assert len(payload.results) == 3
    assert payload.results[0].source_type == "search"


def test_workspace_cover_endpoint_updates_cover_block_and_imports_asset():
    agent = FakeAgent(
        {
            "image_assets": [],
            "note_document": build_note_document(
                document_view={
                    "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": ""}],
                    "title_1": {"type": "TitleBlock", "title": "旧标题"},
                },
                block_style_map={},
            ),
        }
    )
    request = _build_request(agent)
    response = asyncio.run(
        set_workspace_cover_asset(
            "thread-1",
            AssetMutationRequest(
                url="https://img.example/cover.jpg",
                desc="Mate 60 封面",
                source_type="search",
                query="Mate 60 实拍图",
            ),
            request,
        )
    )

    assert response.message == "已设为封面图"
    patch = agent.updated[0]["values"]
    assert patch["image_assets"][0]["url"] == "https://img.example/cover.jpg"
    assert patch["note_document"]["blocks"][0]["type"] == "CoverSwiper"
    assert patch["note_document"]["blocks"][1]["type"] == "TitleBlock"
    assert patch["note_document"]["blocks"][1]["props"]["title"] == "旧标题"
    cover_block = patch["note_document"]["blocks"][0]
    assert cover_block["props"]["image_urls"] == ["https://img.example/cover.jpg"]
    trace_patch = agent.updated[-1]["values"]["turn_trace"]["workspace_action"]
    assert trace_patch["action"] == "workspace_set_cover"
    assert trace_patch["target_block_id"] == cover_block["id"]
    assert isinstance(agent.updated[-1]["values"]["turn_trace"]["changed_blocks"], list)


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
    request = _build_request(agent)
    response = asyncio.run(
        confirm_workspace_fact(
            "thread-1",
            FactConfirmationRequest(field="battery_capacity", value="5000", sources=["华为官网"]),
            request,
        )
    )

    assert response.message == "已确认 电池容量: 5000"
    patch = agent.updated[0]["values"]
    knowledge_patch = patch["retrieved_knowledge"]
    assert knowledge_patch["confirmed_facts"]["battery_capacity"]["value"] == "5000mAh"
    assert knowledge_patch["core_attributes"]["battery_capacity"] == "5000mAh"
    assert knowledge_patch["fact_review_status"] == "confirmed"
    assert knowledge_patch["fact_conflicts"] == []
    assert patch["note_document"]["provenance"]["confirmed_facts"]["battery_capacity"]["value"] == "5000mAh"


def test_workspace_import_asset_also_updates_note_document():
    agent = FakeAgent({
        "image_assets": [],
        "note_document": build_note_document(
            document_view={"page_title": "示例", "blocks": []},
            block_style_map={},
        ),
    })
    request = _build_request(agent)
    response = asyncio.run(
        import_workspace_asset(
            "thread-1",
            AssetMutationRequest(
                url="https://img.example/lib.jpg",
                desc="图库图",
                source_type="search",
                query="Mate 60",
            ),
            request,
        )
    )

    assert response.message == "素材已加入资产池"
    patch = agent.updated[0]["values"]
    assert patch["image_assets"][0]["url"] == "https://img.example/lib.jpg"
    assert patch["note_document"]["assets"][0]["url"] == "https://img.example/lib.jpg"
    assert patch["note_document"]["document_meta"]["title"] == "示例"
    assert agent.updated[-1]["values"]["turn_trace"]["workspace_action"]["action"] == "workspace_import_asset"
