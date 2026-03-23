import asyncio
from types import SimpleNamespace

from app.api.workspace import (
    AssetPreferenceRequest,
    AssetMutationRequest,
    FactConfirmationRequest,
    confirm_workspace_fact,
    import_workspace_asset,
    remove_workspace_asset,
    search_workspace_images,
    set_workspace_cover_asset,
    update_workspace_asset_preferences,
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
    assert [block["type"] for block in patch["note_document"]["blocks"]] == ["TitleBlock"]
    assert patch["note_document"]["blocks"][0]["props"]["title"] == "旧标题"
    assert patch["note_document"]["ui_state"]["cover_asset_url"] == "https://img.example/cover.jpg"
    assert patch["note_document"]["assets"][0]["role"] == "cover"
    assert patch["note_document"]["assets"][0]["used_by_blocks"] == []
    trace_patch = agent.updated[-1]["values"]["turn_trace"]["workspace_action"]
    assert trace_patch["action"] == "workspace_set_cover"
    assert trace_patch["target_block_id"] == "global"
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


def test_workspace_remove_asset_clears_cover_preference_and_block_references():
    agent = FakeAgent({
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search", "role": "cover"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图", "source_type": "search", "role": "supporting"},
        ],
        "note_document": build_note_document(
            document_view={
                "page_title": "示例",
                "blocks": [
                    {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
                    {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                ],
                "cover_1": {"type": "CoverSwiper", "image_urls": ["https://img.example/cover.jpg"]},
                "title_1": {"type": "TitleBlock", "title": "示例标题"},
            },
            block_style_map={},
            image_assets=[
                {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search", "role": "cover"},
                {"url": "https://img.example/detail.jpg", "desc": "细节图", "source_type": "search", "role": "supporting"},
            ],
        ),
    })
    agent.snapshot.values["note_document"]["ui_state"]["cover_asset_url"] = "https://img.example/cover.jpg"
    request = _build_request(agent)

    response = asyncio.run(remove_workspace_asset("thread-1", "https://img.example/cover.jpg", request))

    assert response.message == "素材已删除"
    patch = agent.updated[0]["values"]
    assert patch["image_assets"][0]["__replace__"] is True
    assert [asset["url"] for asset in patch["image_assets"][1:]] == ["https://img.example/detail.jpg"]
    assert patch["note_document"]["ui_state"]["cover_asset_url"] is None
    assert [asset["url"] for asset in patch["note_document"]["assets"]] == ["https://img.example/detail.jpg"]
    cover_block = patch["note_document"]["blocks"][0]
    assert cover_block["type"] == "CoverSwiper"
    assert cover_block["props"]["image_urls"] == []
    assert cover_block["asset_refs"] == []
    assert agent.updated[-1]["values"]["turn_trace"]["workspace_action"]["action"] == "workspace_remove_asset"


def test_workspace_asset_preferences_can_mark_inline_locked_and_excluded():
    agent = FakeAgent({
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search", "role": "cover", "selection_state": "available", "locked": False},
            {"url": "https://img.example/body.jpg", "desc": "正文图", "source_type": "search", "role": "supporting", "selection_state": "available", "locked": False},
        ],
        "note_document": build_note_document(
            document_view={"page_title": "示例", "blocks": []},
            block_style_map={},
            image_assets=[
                {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search", "role": "cover", "selection_state": "available", "locked": False},
                {"url": "https://img.example/body.jpg", "desc": "正文图", "source_type": "search", "role": "supporting", "selection_state": "available", "locked": False},
            ],
        ),
    })
    agent.snapshot.values["note_document"]["ui_state"]["cover_asset_url"] = "https://img.example/cover.jpg"
    request = _build_request(agent)

    response = asyncio.run(
        update_workspace_asset_preferences(
            "thread-1",
            AssetPreferenceRequest(
                url="https://img.example/cover.jpg",
                role="inline",
                locked=True,
                selection_state="available",
            ),
            request,
        )
    )

    assert response.message == "素材偏好已更新"
    patch = agent.updated[0]["values"]
    body_asset = next(item for item in patch["image_assets"][1:] if item["url"] == "https://img.example/cover.jpg")
    assert body_asset["role"] == "inline"
    assert body_asset["locked"] is True
    assert patch["note_document"]["ui_state"]["cover_asset_url"] is None

    response = asyncio.run(
        update_workspace_asset_preferences(
            "thread-1",
            AssetPreferenceRequest(
                url="https://img.example/body.jpg",
                selection_state="excluded",
            ),
            request,
        )
    )

    assert response.message == "素材偏好已更新"
    patch = agent.updated[2]["values"]
    excluded_asset = next(item for item in patch["image_assets"][1:] if item["url"] == "https://img.example/body.jpg")
    assert excluded_asset["selection_state"] == "excluded"
    assert excluded_asset["locked"] is False
    assert agent.updated[-1]["values"]["turn_trace"]["workspace_action"]["action"] == "workspace_update_asset_preferences"
