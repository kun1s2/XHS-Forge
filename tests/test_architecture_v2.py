import pytest
from unittest.mock import AsyncMock, patch
from app.agents.nodes.intent_node import _normalize_gateway_result, intent_agent
from app.agents.nodes.planner_node import planner_node
from app.agents.graph import map_components, outline_resolver, route_intent
from app.core.component_manifest import (
    build_component_contract_map,
    component_manifest_version,
    filter_payload_for_component,
    get_asset_support,
    get_component_aliases,
    get_component_label,
    get_component_semantic_role,
    get_quick_actions,
    get_supported_scenarios,
    get_theme_slots,
    list_components_for_semantic_role,
    normalize_component_type,
    resolve_component_for_block_intent,
)
from app.core.note_document import (
    build_note_document,
    build_note_document_from_state,
    note_document_to_document_view,
    update_note_document_cover_preference,
)
from app.core.request_semantics import payload_requests_create
from app.core.schema import IntentGatewayOutput, NoteDocument


def test_component_manifest_contracts_and_normalization():
    assert component_manifest_version() == "v2"
    contracts = build_component_contract_map(stable_only=True)
    assert contracts["PollBlock"] == ["question", "option_a", "option_b"]
    assert normalize_component_type("参数卡") == "ProductSpecCard"
    assert get_component_label("PollBlock") == "投票卡"
    assert get_component_semantic_role("VersusCard") == "comparison"
    assert get_asset_support("CoverSwiper") == "required"
    assert "图片轮播" in get_component_aliases("CoverSwiper")
    assert "travel" in get_supported_scenarios("LocationBlock")
    assert "interactive" in get_theme_slots("PollBlock")
    assert "结论更鲜明" in get_quick_actions("VersusCard")
    travel_location = list_components_for_semantic_role("location_info", scenario_names=["travel"])
    assert travel_location and travel_location[0]["type"] == "LocationBlock"
    payload = filter_payload_for_component("PollBlock", {"question": "买吗", "option_a": "买", "option_b": "不买", "scores": [1, 2]})
    assert payload == {"type": "PollBlock", "question": "买吗", "option_a": "买", "option_b": "不买"}


def test_note_document_round_trip_from_legacy_payloads():
    note_document = build_note_document(
        document_view={
            "page_title": "Mate 60 页面",
            "page_theme": {"--primary-vibe": "#ff2442"},
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "cover_1": {"type": "CoverSwiper", "image_urls": ["https://img.example/1.jpg"]},
            "story_1": {
                "type": "StoryText",
                "paragraphs": ["第一段", "第二段"],
                "paragraph_meta": [{"kind": "verified", "sources": ["华为官网"], "hint": "已确认", "fields": ["battery_capacity"]}],
            },
        },
        block_style_map={
            "global_vars": {"--bg-color": "#fff"},
            "story_1": {"css_classes": "rounded-xl", "inline_styles": {"color": "#111"}},
        },
        image_assets=[{"url": "https://img.example/1.jpg", "desc": "封面图", "source_type": "search"}],
        selected_element_id="story_1",
        active_panel="main",
        scenarios=["seeding", "travel"],
        active_archetype="seeding",
        retrieved_knowledge={"confirmed_facts": {"battery_capacity": {"value": "5000mAh"}}},
        planner_output={"block_intents": [{"intent_type": "heading"}]},
    )

    assert note_document["document_meta"]["title"] == "Mate 60 页面"
    assert note_document["assets"][0]["used_by_blocks"] == ["cover_1"]
    assert note_document["blocks"][1]["fact_bindings"][0]["sources"] == ["华为官网"]
    assert note_document["blocks"][1]["fact_bindings"][0]["fact_fields"] == ["battery_capacity"]
    assert note_document["blocks"][1]["fact_bindings"][0]["fact_field_labels"] == ["电池容量"]
    assert note_document["blocks"][1]["editable_targets"] == ["paragraphs", "paragraphs[0]", "paragraphs[1]", "paragraphs[2]"]
    assert note_document["blocks"][1]["semantic_role"] == "narrative_text"
    assert note_document["ui_state"]["patch_tracks"] == {}

    document_view, block_style_map, image_assets = note_document_to_document_view(note_document)
    assert document_view["page_title"] == "Mate 60 页面"
    assert document_view["story_1"]["paragraphs"][1] == "第二段"
    assert block_style_map["story_1"]["css_classes"] == "rounded-xl"
    assert image_assets[0]["url"] == "https://img.example/1.jpg"


def test_note_document_schema_accepts_richer_block_metadata():
    note_document = build_note_document(
        document_view={
            "page_title": "协议页面",
            "blocks": [
                {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数证据"},
            ],
            "spec_1": {
                "type": "ProductSpecCard",
                "core_features": ["已确认 5000mAh"],
                "feature_meta": [{"kind": "verified", "sources": ["华为官网"], "hint": "已确认", "fields": ["battery_capacity"]}],
            },
        },
        image_assets=[{"url": "https://img.example/spec.jpg", "desc": "参数图", "source_type": "search"}],
    )

    document = NoteDocument(**note_document)

    assert document.blocks[0].label
    assert document.blocks[0].semantic_role == "evidence_summary"
    assert "core_features" in document.blocks[0].editable_targets
    assert document.blocks[0].asset_support == "none"
    assert document.blocks[0].fact_binding_support is True
    assert document.blocks[0].fact_bindings[0]["fact_fields"] == ["battery_capacity"]
    assert document.blocks[0].fact_bindings[0]["fact_field_labels"] == ["电池容量"]


def test_note_document_cover_preference_does_not_materialize_cover_block():
    note_document = build_note_document(
        document_view={
            "page_title": "封面偏好页面",
            "blocks": [{"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}],
            "title_1": {"type": "TitleBlock", "title": "Mate 60"},
        },
        image_assets=[
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图", "source_type": "search"},
        ],
    )
    preferred = update_note_document_cover_preference(note_document, "https://img.example/cover.jpg")

    assert [block["type"] for block in preferred["blocks"]] == ["TitleBlock"]
    assert preferred["ui_state"]["cover_asset_url"] == "https://img.example/cover.jpg"
    assert preferred["assets"][0]["role"] == "cover"
    assert preferred["assets"][0]["used_by_blocks"] == []

    rebuilt = build_note_document_from_state({
        "note_document": preferred,
        "image_assets": [
            {"url": "https://img.example/cover.jpg", "desc": "封面图", "source_type": "search"},
            {"url": "https://img.example/detail.jpg", "desc": "细节图", "source_type": "search"},
        ],
    })

    assert [block["type"] for block in rebuilt["blocks"]] == ["TitleBlock"]
    assert rebuilt["ui_state"]["cover_asset_url"] == "https://img.example/cover.jpg"
    assert next(asset for asset in rebuilt["assets"] if asset["url"] == "https://img.example/cover.jpg")["role"] == "cover"


def test_note_document_applies_retrieval_grounding_to_blocks_without_manual_meta():
    note_document = build_note_document(
        document_view={
            "page_title": "Mate 60 grounded 页面",
            "blocks": [
                {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数证据"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文总结"},
            ],
            "spec_1": {"type": "ProductSpecCard", "core_features": ["5000mAh", "6999 元"]},
            "story_1": {"type": "StoryText", "paragraphs": ["这台机器的影像表现很强。"]},
        },
        retrieved_knowledge={
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh"},
                "price": {"value": "6999元"},
            },
            "fact_sources": [
                {"title": "华为官网 Mate 60", "url": "https://consumer.huawei.com/cn/phones/mate-60/", "source_scope": "official"},
                {"title": "用户评价合集", "url": "https://www.bilibili.com/video/BV1xx", "source_scope": "review"},
            ],
        },
    )

    spec_block = next(block for block in note_document["blocks"] if block["id"] == "spec_1")
    story_block = next(block for block in note_document["blocks"] if block["id"] == "story_1")

    assert spec_block["fact_bindings"][0]["kind"] == "retrieval_grounded"
    assert spec_block["fact_bindings"][0]["sources"] == ["华为官网 Mate 60"]
    assert spec_block["fact_bindings"][0]["source_items"] == [
        {
            "label": "华为官网 Mate 60",
            "url": "https://consumer.huawei.com/cn/phones/mate-60/",
            "source_scope": "official",
        }
    ]
    assert "battery_capacity" in spec_block["fact_bindings"][0]["fact_fields"]
    assert story_block["fact_bindings"][0]["kind"] == "retrieval_grounded"
    assert story_block["fact_bindings"][0]["sources"] == ["用户评价合集"]
    assert story_block["fact_bindings"][0]["source_items"] == [
        {
            "label": "用户评价合集",
            "url": "https://www.bilibili.com/video/BV1xx",
            "source_scope": "review",
        }
    ]
    assert any(binding["block_id"] == "spec_1" for binding in note_document["fact_bindings"])


def test_intent_gateway_result_normalization_fills_seeding_when_missing_scores():
    normalized = _normalize_gateway_result(
        IntentGatewayOutput(
            thought_process="分析",
            reason="进入内容主链",
            task_type="create",
            edit_scope="none",
            needs_research=True,
            needs_assets="search",
            scenario_scores={},
            risk_flags=[],
        )
    )

    assert normalized["task_type"] == "create"
    assert normalized["needs_research"] is True
    assert normalized["needs_assets"] == "search"
    assert normalized["scenario_scores"] == {"seeding": 1.0}


@pytest.mark.asyncio
async def test_planner_node_outputs_policy_and_block_intents():
    result = await planner_node(
        {
            "intent_decision": {
                "scenario_scores": {"travel": 0.6, "seeding": 0.4},
            },
            "active_archetype": "travel",
            "scenarios": ["travel", "seeding"],
            "has_controversy": True,
            "image_assets": [{"url": "https://img.example/1.jpg"}],
            "retrieved_knowledge": {
                "battle_report": {"title": "A vs B"},
                "core_attributes": {"battery": "5000mAh"},
            },
            "main_messages": [type("Msg", (), {"content": "做一篇大阪旅行相机种草笔记"})()],
            "document_view": {},
        }
    )

    planner_output = result["planner_output"]
    assert result["agent_backends"]["planner"] == "deterministic_policy_builder"
    assert result["active_archetype"] == "travel"
    assert planner_output["theme_policy"]["preset"]
    intent_types = [item["intent_type"] for item in planner_output["block_intents"]]
    assert "hero_media" in intent_types
    assert "location_info" in intent_types
    assert "comparison" in intent_types
    assert resolve_component_for_block_intent("fact_list", scenario_scores={"seeding": 1.0}) == "ProductSpecCard"
    assert resolve_component_for_block_intent("location_info", scenario_scores={"travel": 1.0}) == "LocationBlock"
    assert "planner_agent" in result["node_prompts"]
    assert result["node_prompts"]["planner_agent"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_planner_node_skips_hero_media_for_seeding_without_images_or_cover_request():
    result = await planner_node(
        {
            "intent_decision": {
                "scenario_scores": {"seeding": 1.0},
            },
            "active_archetype": "seeding",
            "scenarios": ["seeding"],
            "has_controversy": True,
            "image_assets": [],
            "retrieved_knowledge": {
                "battle_report": {"title": "A vs B"},
                "core_attributes": {"battery": "5000mAh"},
            },
            "main_messages": [type("Msg", (), {"content": "帮我生成一篇关于华为 Mate 60 的对比种草笔记"})()],
            "document_view": {},
        }
    )

    intent_types = [item["intent_type"] for item in result["planner_output"]["block_intents"]]
    preferred_components = [item["preferred_component"] for item in result["planner_output"]["block_intents"]]
    assert "hero_media" not in intent_types
    assert "WeatherPolaroid" not in preferred_components


@pytest.mark.asyncio
async def test_planner_node_still_outputs_block_intents_for_create_requests_on_existing_canvas():
    result = await planner_node(
        {
            "intent_decision": {
                "task_type": "create",
                "scenario_scores": {"seeding": 1.0},
            },
            "active_archetype": "seeding",
            "scenarios": ["seeding"],
            "has_controversy": True,
            "image_assets": [],
            "retrieved_knowledge": {
                "battle_report": {"title": "Mate 60 vs iPhone"},
                "core_attributes": {"battery": "5000mAh"},
            },
            "main_messages": [type("Msg", (), {"content": "帮我生成一篇关于华为 Mate 60 的对比种草笔记"})()],
            "note_document": {
                "document_meta": {"title": "旧页面"},
                "theme": {"page_theme": {}, "global_vars": {}},
                "blocks": [
                    {
                        "id": "cover_old",
                        "type": "CoverSwiper",
                        "label": "图片轮播",
                        "semantic_role": "hero_media",
                        "content_brief": "旧封面",
                        "props": {"type": "CoverSwiper", "image_urls": []},
                        "style": {},
                        "asset_refs": [],
                        "fact_bindings": [],
                        "editable_targets": ["image_urls"],
                        "asset_support": "required",
                        "fact_binding_support": False,
                        "order": 0,
                    }
                ],
                "assets": [],
                "fact_bindings": [],
                "provenance": {},
                "ui_state": {},
                "planner": {},
            },
        }
    )

    intent_types = [item["intent_type"] for item in result["planner_output"]["block_intents"]]
    assert "heading" in intent_types
    assert "narrative_text" in intent_types
    assert "comparison" in intent_types


@pytest.mark.asyncio
async def test_planner_node_rebuilds_for_main_panel_create_like_query_even_without_intent_result():
    result = await planner_node(
        {
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
            "active_archetype": "seeding",
            "scenarios": ["seeding"],
            "has_controversy": True,
            "image_assets": [],
            "retrieved_knowledge": {
                "battle_report": {"title": "Mate 60 vs iPhone"},
                "core_attributes": {"battery": "5000mAh"},
            },
            "main_messages": [type("Msg", (), {"content": "帮我生成一篇关于华为 Mate 60 的对比种草笔记"})()],
            "note_document": {
                "document_meta": {"title": "旧页面"},
                "theme": {"page_theme": {}, "global_vars": {}},
                "blocks": [
                    {
                        "id": "cover_old",
                        "type": "CoverSwiper",
                        "label": "图片轮播",
                        "semantic_role": "hero_media",
                        "content_brief": "旧封面",
                        "props": {"type": "CoverSwiper", "image_urls": []},
                        "style": {},
                        "asset_refs": [],
                        "fact_bindings": [],
                        "editable_targets": ["image_urls"],
                        "asset_support": "required",
                        "fact_binding_support": False,
                        "order": 0,
                    }
                ],
                "assets": [],
                "fact_bindings": [],
                "provenance": {},
                "ui_state": {},
                "planner": {},
            },
        }
    )

    intent_types = [item["intent_type"] for item in result["planner_output"]["block_intents"]]
    assert "heading" in intent_types
    assert "comparison" in intent_types


@pytest.mark.asyncio
async def test_outline_resolver_rebuilds_existing_canvas_for_create_like_query():
    result = await outline_resolver(
        {
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
            "main_messages": [type("Msg", (), {"content": "帮我生成一篇关于华为 Mate 60 的对比种草笔记"})()],
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "summary": "这是一台亮点和争议并存的高端机。",
                "key_selling_points": ["续航稳定", "大屏沉浸", "辨识度高"],
            },
            "note_document": {
                "document_meta": {"title": "旧页面"},
                "theme": {"page_theme": {}, "global_vars": {}},
                "blocks": [
                    {
                        "id": "cover_old",
                        "type": "CoverSwiper",
                        "label": "图片轮播",
                        "semantic_role": "hero_media",
                        "content_brief": "旧封面",
                        "props": {"type": "CoverSwiper", "image_urls": []},
                        "style": {},
                        "asset_refs": [],
                        "fact_bindings": [],
                        "editable_targets": ["image_urls"],
                        "asset_support": "required",
                        "fact_binding_support": False,
                        "order": 0,
                    }
                ],
                "assets": [],
                "fact_bindings": [],
                "provenance": {},
                "ui_state": {},
                "planner": {},
            },
            "planner_output": {
                "block_intents": [
                    {"intent_type": "heading", "preferred_component": "TitleBlock"},
                    {"intent_type": "narrative_text", "preferred_component": "StoryText"},
                    {"intent_type": "comparison", "preferred_component": "VersusCard"},
                    {"intent_type": "interactive_opinion", "preferred_component": "PollBlock"},
                ],
                "scenario_scores": {"seeding": 1.0},
            },
        }
    )

    block_types = [block["type"] for block in result["note_document"]["blocks"]]
    assert block_types[:2] == ["TitleBlock", "StoryText"]
    assert "VersusCard" in block_types
    assert result["turn_trace"]["outline"]["block_count"] >= 4


def test_note_document_carries_patch_tracks_from_state_shape():
    note_document = build_note_document(
        document_view={
            "page_title": "演化页面",
            "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        patch_tracks={
            "story_1": [
                {
                    "timestamp": 1710000000,
                    "prompt": "把这段改短一点",
                    "agent_thought": "压缩正文",
                }
            ]
        },
    )

    assert note_document["ui_state"]["patch_tracks"]["story_1"][0]["prompt"] == "把这段改短一点"


@pytest.mark.asyncio
async def test_intent_agent_reports_skipped_backend_when_no_messages():
    result = await intent_agent({
        "main_messages": [],
        "content_messages": [],
        "image_messages": [],
        "structure_messages": [],
        "style_messages": [],
        "messages": [],
        "active_panel": "main",
        "document_view": {},
    })

    assert result["intent_route"] == "END"
    assert result["agent_backends"]["intent_agent"] == "skipped_no_messages"


@pytest.mark.asyncio
async def test_intent_agent_llm_path_uses_gateway_v2_schema():
    mock_output = IntentGatewayOutput(
        thought_process="新建内容，需要 research 与搜图",
        reason="新建种草",
        task_type="create",
        edit_scope="none",
        needs_research=True,
        needs_assets="search",
        scenario_scores={"seeding": 1.0},
        risk_flags=[],
    )

    with patch("langchain_core.runnables.base.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_output
        result = await intent_agent({
            "active_panel": "main",
            "main_messages": [type("Msg", (), {"content": "帮我做一篇 Mate 60 种草笔记"})()],
            "document_view": {},
            "selected_element_id": None,
            "active_archetype": "seeding",
        })

    assert result["intent_route"] == "research_agent"
    assert result["intent_decision"]["task_type"] == "create"
    assert result["intent_decision"]["needs_research"] is True
    assert result["scenario_scores"] == {"seeding": 1.0}
    assert result["agent_backends"]["intent_agent"] == "structured_function_calling"


@pytest.mark.asyncio
async def test_intent_agent_uses_deterministic_fast_path_for_selected_block_edits():
    result = await intent_agent({
        "active_panel": "content",
        "content_messages": [type("Msg", (), {"content": "把这一段改得更简短一点"})()],
        "document_view": {"blocks": [{"id": "story_1", "component_type": "StoryText"}]},
        "selected_element_id": "story_1",
        "active_archetype": "travel",
    })

    assert result["intent_route"] == "patch_node"
    assert result["intent_decision"]["task_type"] == "edit"
    assert result["intent_decision"]["edit_scope"] == "selected_paragraph"
    assert result["agent_backends"]["intent_agent"] == "deterministic_fast_path"
    assert result["scenario_scores"] == {"travel": 1.0}


@pytest.mark.asyncio
async def test_intent_agent_uses_deterministic_fast_path_for_style_panel_global_edits():
    result = await intent_agent({
        "active_panel": "style",
        "style_messages": [type("Msg", (), {"content": "整体改得更克制一点"})()],
        "document_view": {"blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
        "selected_element_id": None,
        "active_archetype": "seeding",
    })

    assert result["intent_route"] == "theme_compiler"
    assert result["intent_decision"]["task_type"] == "edit"
    assert result["intent_decision"]["edit_scope"] == "global"
    assert result["agent_backends"]["intent_agent"] == "deterministic_fast_path"
    assert result["scenario_scores"] == {"seeding": 1.0}


@pytest.mark.asyncio
async def test_intent_agent_uses_deterministic_fast_path_for_main_existing_canvas_edits():
    result = await intent_agent({
        "active_panel": "main",
        "main_messages": [type("Msg", (), {"content": "文本简短一点"})()],
        "document_view": {"blocks": [{"id": "story_1", "component_type": "StoryText"}]},
        "selected_element_id": None,
        "active_archetype": "travel",
    })

    assert result["intent_route"] == "note_editor"
    assert result["intent_decision"]["task_type"] == "edit"
    assert result["intent_decision"]["edit_scope"] == "global"
    assert result["agent_backends"]["intent_agent"] == "deterministic_fast_path"


@pytest.mark.asyncio
async def test_intent_agent_routes_existing_canvas_image_requests_to_research_agent():
    result = await intent_agent({
        "active_panel": "main",
        "main_messages": [type("Msg", (), {"content": "怎么没有图片，加一些图片"})()],
        "document_view": {"blocks": [{"id": "story_1", "component_type": "StoryText"}]},
        "selected_element_id": None,
        "active_archetype": "seeding",
    })

    assert result["intent_route"] == "research_agent"
    assert result["intent_decision"]["task_type"] == "edit"
    assert result["agent_backends"]["intent_agent"] == "deterministic_fast_path"


@pytest.mark.asyncio
async def test_intent_agent_uses_capability_fast_path_for_help_queries():
    result = await intent_agent({
        "active_panel": "main",
        "main_messages": [type("Msg", (), {"content": "你有什么功能？"})()],
        "document_view": {},
        "selected_element_id": None,
        "active_archetype": "seeding",
    })

    assert result["intent_route"] == "direct_chat_node"
    assert result["intent_decision"]["task_type"] == "inspect"
    assert result["intent_decision"]["edit_scope"] == "none"
    assert result["agent_backends"]["intent_agent"] == "deterministic_capability_fast_path"


def test_payload_requests_create_returns_false_for_capability_queries():
    assert payload_requests_create(
        content="你有什么功能?",
        panel="main",
        selected_element_id="无 (全局修改)",
    ) is False


@pytest.mark.asyncio
async def test_intent_agent_existing_canvas_styleish_edit_maps_to_style_route():
    result = await intent_agent({
        "active_panel": "main",
        "main_messages": [type("Msg", (), {"content": "把整体页面改成更克制的灰蓝风格"})()],
        "document_view": {"blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
        "selected_element_id": None,
        "active_archetype": "seeding",
    })

    assert result["intent_route"] == "theme_compiler"
    assert result["intent_decision"]["task_type"] == "edit"
    assert result["agent_backends"]["intent_agent"] == "deterministic_fast_path"


def test_route_intent_prefers_note_editor_for_style_panel_fast_path():
    route = route_intent({
        "intent_decision": {
            "task_type": "edit",
            "edit_scope": "global",
            "needs_research": False,
        },
        "intent_route": "theme_compiler",
        "active_panel": "style",
        "document_view": {"blocks": [{"id": "title_1", "component_type": "TitleBlock"}]},
    })

    assert route == "note_editor"


@pytest.mark.asyncio
async def test_outline_resolver_node_uses_planner_block_intents_without_outline_tool_loop():
    result = await outline_resolver(
        {
            "planner_output": {
                "scenario_scores": {"seeding": 0.8},
                "block_intents": [
                    {"intent_type": "hero_media", "preferred_component": "CoverSwiper"},
                    {"intent_type": "heading", "preferred_component": "TitleBlock"},
                    {"intent_type": "narrative_text", "preferred_component": "StoryText"},
                    {"intent_type": "interactive_opinion", "preferred_component": "PollBlock"},
                ],
            },
            "image_assets": [{"url": "https://img.example/1.jpg"}],
            "retrieved_knowledge": {"entity_name": "华为 Mate 60", "summary": "总结", "key_selling_points": ["影像", "续航"]},
            "main_messages": [type("Msg", (), {"content": "做一篇 Mate 60 种草笔记"})()],
            "document_view": {},
            "block_style_map": {},
        }
    )

    assert result["agent_backends"]["outline_resolver"] == "deterministic_resolver"
    blocks = result["note_document"]["blocks"]
    assert [block["type"] for block in blocks][:3] == ["CoverSwiper", "TitleBlock", "StoryText"]
    assert result["turn_trace"]["outline"]["mode"] == "resolver"
    assert result["turn_trace"]["outline"]["resolution_source"] == "manifest_semantic_role"


def test_map_components_only_dispatches_builder_tasks_when_blocks_exist():
    sends = map_components(
        {
            "note_document": {
                "document_meta": {"title": "测试页面"},
                "theme": {"page_theme": {}, "global_vars": {}},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "content_brief": "标题"},
                    {"id": "text_1", "type": "StoryText", "content_brief": "正文"},
                ],
                "assets": [],
                "fact_bindings": [],
                "provenance": {},
                "ui_state": {},
                "planner": {},
            },
            "planner_policy": {},
            "retrieved_knowledge": {},
            "image_assets": [],
            "main_messages": [type("Msg", (), {"content": "帮我生成一篇华为 Mate 60 的对比种草笔记"})()],
        }
    )

    assert len(sends) == 2
    assert all(getattr(item, "node", "") == "component_builder" for item in sends)
