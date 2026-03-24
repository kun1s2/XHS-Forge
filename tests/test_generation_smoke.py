import pytest
from unittest.mock import AsyncMock, patch

from app.agents.nodes.component_builder import apply_component_contract_layer, apply_component_contract_with_trace, build_component_fallback, enforce_component_contract
from app.core.note_document import build_note_document_from_state
from app.agents.state import merge_state_patch
from app.agents.nodes.distill_node import distill_node
from app.agents.nodes.distill_node import _extract_conflicts, _extract_structured_sources, _infer_fact_confidence
from app.agents.utils.fact_utils import apply_confirmed_facts_to_knowledge, merge_confirmed_fact_selection
from app.agents.nodes.theme_compiler_node import theme_compiler
from app.agents.nodes.document_renderer_node import document_renderer
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.graph import outline_synthesizer
from app.services.cache_service import CacheService
from app.services.search_enricher import enrich_product_document
from app.services.retrieval_profiles import build_followup_query_variants, compute_missing_slot_keys


def test_normalize_entity_name():
    assert normalize_entity_name("帮我针对华为 Mate 60 做一个深度种草笔记") == "华为 Mate 60"
    assert normalize_entity_name("帮我针对「索尼 A7M4」做一篇测评") == "索尼 A7M4"
    assert normalize_entity_name("我想写小米17 Ultra") == "小米17 Ultra"




def test_apply_component_contract_layer_filters_payload_to_manifest_contract():
    fallback = {
        "type": "PollBlock",
        "question": "你更看重影像还是性能？",
        "option_a": "影像",
        "option_b": "性能",
    }
    payload = {
        "type": "PollBlock",
        "question": "重新站队？",
        "option_a": "影像",
        "option_b": "性能",
        "scores": [99, 1],
        "random_field": "should_drop",
    }

    merged = apply_component_contract_layer("PollBlock", payload, fallback)
    assert merged == {
        "type": "PollBlock",
        "question": "重新站队？",
        "option_a": "影像",
        "option_b": "性能",
    }


def test_apply_component_contract_with_trace_reports_filtered_fields_and_precheck_warnings():
    merged, trace = apply_component_contract_with_trace(
        "PollBlock",
        {
            "type": "PollBlock",
            "question": "重新站队？",
            "random_field": "should_drop",
        },
        {
            "type": "PollBlock",
            "question": "默认问题",
            "option_a": "影像",
            "option_b": "性能",
            "scores": [1, 2],
        },
    )

    assert merged["question"] == "重新站队？"
    assert merged["option_a"] == "影像"
    assert merged["option_b"] == "性能"
    assert trace["contract_filter_count"] == 2
    assert trace["dropped_payload_fields"] == ["random_field"]
    assert "missing_required_before_merge:option_a" in trace["precheck_warnings"]
    assert "missing_required_before_merge:option_b" in trace["precheck_warnings"]


def test_enforce_component_contract_for_poll():
    fallback = {
        "type": "PollBlock",
        "question": "你更看重影像还是性能？",
        "option_a": "影像",
        "option_b": "性能",
    }
    merged = enforce_component_contract("PollBlock", {"title": "普通文案"}, fallback)
    assert merged["question"] == fallback["question"]
    assert merged["option_a"] == fallback["option_a"]
    assert merged["option_b"] == fallback["option_b"]


def test_apply_component_contract_layer_strips_placeholder_cover_images():
    merged = apply_component_contract_layer(
        "CoverSwiper",
        {
            "type": "CoverSwiper",
            "image_urls": [
                "https://example.com/image1.jpg",
                "https://picsum.photos/800/1200",
                "https://img.example/mate-1.jpg",
            ],
        },
        {
            "type": "CoverSwiper",
            "image_urls": ["https://img.example/mate-1.jpg", "https://img.example/mate-2.jpg"],
        },
    )

    assert merged["image_urls"] == ["https://img.example/mate-1.jpg"]


def test_build_note_document_from_state_strips_placeholder_cover_images_from_existing_blocks():
    note_document = build_note_document_from_state({
        "note_document": {
            "document_meta": {"title": "测试页面"},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "cover_1",
                    "type": "CoverSwiper",
                    "props": {
                        "type": "CoverSwiper",
                        "image_urls": [
                            "https://example.com/image1.jpg",
                            "https://picsum.photos/800/1200",
                            "https://img.example/mate-1.jpg",
                        ],
                    },
                    "asset_refs": [
                        "https://example.com/image1.jpg",
                        "https://img.example/mate-1.jpg",
                    ],
                }
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
            "planner": {},
        }
    })

    block = note_document["blocks"][0]
    assert block["props"]["image_urls"] == ["https://img.example/mate-1.jpg"]
    assert block["asset_refs"] == ["https://img.example/mate-1.jpg"]


def test_build_note_document_from_state_downgrades_timeline_to_recommended_without_user_facts():
    note_document = build_note_document_from_state({
        "active_archetype": "travel",
        "note_document": {
            "document_meta": {"title": "测试页面", "active_archetype": "travel"},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "timeline_1",
                    "type": "TimelineBlock",
                    "props": {
                        "type": "TimelineBlock",
                        "events": [
                            {"timestamp": "2024-06-16T09:00:00", "title": "到达", "description": "海边散步"},
                        ],
                    },
                    "fact_bindings": [],
                }
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
            "planner": {},
        },
    })

    block = note_document["blocks"][0]
    assert block["props"]["mode"] == "recommended"
    assert block["props"]["events"][0]["timestamp"] == "上午"


def test_build_note_document_from_state_removes_unconfirmed_weather_snapshot_fields():
    note_document = build_note_document_from_state({
        "active_archetype": "travel",
        "note_document": {
            "document_meta": {"title": "测试页面", "active_archetype": "travel"},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "weather_1",
                    "type": "WeatherPolaroid",
                    "props": {
                        "type": "WeatherPolaroid",
                        "weather": "晴",
                        "temperature": "24C",
                        "time": "今日",
                        "desc": "海边风很舒服。",
                    },
                    "fact_bindings": [],
                }
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
            "planner": {},
        },
    })

    block = note_document["blocks"][0]
    assert block["props"]["mode"] == "ambience"
    assert "weather" not in block["props"]
    assert "temperature" not in block["props"]
    assert "time" not in block["props"]


def test_build_component_fallback_uses_travel_facts_mode_for_product_spec_card():
    payload = build_component_fallback(
        "ProductSpecCard",
        "spec_1",
        "旅行价格与套餐",
        "写一篇阿那亚一日游",
        {"entity_name": "阿那亚", "core_attributes": {"价格": "599元起"}},
        [],
        active_archetype="travel",
    )

    assert payload["mode"] == "travel_facts"


@pytest.mark.asyncio
async def test_cache_service_sanitizes_trend_result_placeholder_cover_images():
    cache = CacheService(use_redis=False)
    await cache.set_trend_result(
        "华为 Mate 60",
        "none",
        {
            "document_meta": {"title": "测试页面"},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "cover_1",
                    "type": "CoverSwiper",
                    "props": {
                        "type": "CoverSwiper",
                        "image_urls": [
                            "https://example.com/image1.jpg",
                            "https://img.example/mate-1.jpg",
                        ],
                    },
                }
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
            "planner": {},
        },
    )

    cached = await cache.get_trend_result("华为 Mate 60", "none")
    assert cached is not None
    assert cached["blocks"][0]["props"]["image_urls"] == ["https://img.example/mate-1.jpg"]


@pytest.mark.asyncio
async def test_search_enricher_falls_back_to_structured_results_when_llm_json_is_sparse():
    note_document = {
        "document_meta": {"title": "华为 Mate 60"},
        "blocks": [
            {
                "id": "spec_1",
                "type": "ProductSpecCard",
                "props": {"title": "华为 Mate 60"},
            }
        ],
    }

    mock_results = [
        {
            "title": "华为 Mate 60 官方价格与参数",
            "link": "https://consumer.huawei.com/mate60",
            "snippet": "官方售价 ￥5999 起，支持卫星通信与北斗消息，影像风格鲜明。",
        },
        {
            "title": "华为 Mate 60 使用体验",
            "link": "https://example.review/mate60",
            "snippet": "续航稳定，系统流畅，影像调性有辨识度。",
        },
    ]

    class _SparseResponse:
        content = '{"refined_name":"华为 Mate 60","price":"未提及","features":[]}'

    with patch("app.services.search_enricher.search_network_structured_async", new=AsyncMock(return_value=mock_results)):
        with patch("app.services.search_enricher.get_cleaner_llm") as mock_get_llm:
            mock_get_llm.return_value = AsyncMock()
            mock_get_llm.return_value.ainvoke = AsyncMock(return_value=_SparseResponse())
            enriched = await enrich_product_document(note_document, archetype="seeding")

    props = enriched["blocks"][0]["props"]
    assert props["price"] == "￥5999"
    assert props["core_features"]
    assert props["sources"][0]["url"] == "https://consumer.huawei.com/mate60"


def test_retrieval_profiles_compute_missing_slot_keys_and_followup_queries():
    retrieval_profile = {
        "slot_labels": {
            "chipset": "CPU / SoC",
            "battery": "电池与续航",
            "price": "价格与版本",
        },
        "followup_limit": 2,
        "followup_queries": {
            "chipset": ["华为 Mate 60 处理器 芯片 SoC 官方 参数"],
            "battery": ["华为 Mate 60 电池容量 续航 官方 实测"],
            "price": ["华为 Mate 60 售价 版本 官方 发售价"],
        },
    }
    fact_slots = {
        "price": {"summary": "5999 起"},
    }

    missing_slot_keys = compute_missing_slot_keys(
        slot_labels=retrieval_profile["slot_labels"],
        fact_slots=fact_slots,
    )
    assert missing_slot_keys == ["chipset", "battery"]

    followups = build_followup_query_variants(
        user_query="华为 Mate 60 测评",
        entity_name="华为 Mate 60",
        retrieval_profile=retrieval_profile,
        missing_slot_keys=missing_slot_keys,
    )
    assert [item["scope"] for item in followups] == ["chipset", "battery"]
    assert all("华为 Mate 60" in item["query"] for item in followups)


@pytest.mark.asyncio
async def test_generation_smoke_pipeline():
    # Smoke test should stay deterministic and local; it is not responsible for
    # verifying the remote distill model.
    knowledge = {
        "entity_name": "华为 Mate 60",
        "text_facts": "麒麟芯片回归，影像和卫星通信是亮点，价格门槛较高。",
        "summary": "麒麟芯片回归，影像和卫星通信是亮点，价格门槛较高。",
        "key_selling_points": ["麒麟芯片回归", "影像能力稳定", "支持卫星通信"],
        "is_fact_ready": True,
    }

    title_data = build_component_fallback(
        comp_type="TitleBlock",
        comp_id="title_1",
        content_brief="华为 Mate 60 深度种草",
        user_query="帮我做华为 Mate 60 深度种草",
        retrieved_knowledge=knowledge,
        image_assets=[],
    )
    story_data = build_component_fallback(
        comp_type="StoryText",
        comp_id="text_1",
        content_brief="亮点总结",
        user_query="帮我做华为 Mate 60 深度种草",
        retrieved_knowledge=knowledge,
        image_assets=[],
    )
    radar_data = build_component_fallback(
        comp_type="RadarChartBlock",
        comp_id="radar_1",
        content_brief="雷达图",
        user_query="帮我做华为 Mate 60 深度种草",
        retrieved_knowledge=knowledge,
        image_assets=[],
    )
    poll_data = build_component_fallback(
        comp_type="PollBlock",
        comp_id="poll_1",
        content_brief="投票",
        user_query="帮我做华为 Mate 60 深度种草",
        retrieved_knowledge=knowledge,
        image_assets=[],
    )

    state = {
        "planner_policy": {"theme_policy": {"preset": "seeding_hot", "interaction_bias": "high"}},
        "block_style_map": {},
        "document_view": {
            "page_title": "华为 Mate 60 深度种草",
            "blocks": [
                {"id": "title_1", "component_type": "TitleBlock", "content_brief": "华为 Mate 60 深度种草"},
                {"id": "text_1", "component_type": "StoryText", "content_brief": "亮点总结"},
                {"id": "radar_1", "component_type": "RadarChartBlock", "content_brief": "雷达图"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "title_1": title_data,
            "text_1": story_data,
            "radar_1": radar_data,
            "poll_1": poll_data,
        },
    }

    styled = await theme_compiler(state)
    state["note_document"] = styled["note_document"]
    rendered = await document_renderer(state)
    html = rendered["final_html"]

    assert knowledge["entity_name"] == "华为 Mate 60"
    assert knowledge["is_fact_ready"] is True
    assert "华为 Mate 60 深度种草" in html
    assert "五维表现雷达" in html
    assert "最打动你的是哪一点" in html


@pytest.mark.asyncio
async def test_outline_synthesizer_injects_title_and_story_guards():
    result = await outline_synthesizer({
        "intent_decision": {"task_type": "edit"},
        "main_messages": [type("Msg", (), {"content": "帮我针对华为 Mate 60 做一个深度种草笔记"})()],
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
                    "id": "cover_1",
                    "type": "CoverSwiper",
                    "label": "图片轮播",
                    "semantic_role": "hero_media",
                    "content_brief": "封面图",
                    "props": {"type": "CoverSwiper", "image_urls": []},
                    "style": {},
                    "asset_refs": [],
                    "fact_bindings": [],
                    "editable_targets": ["image_urls"],
                    "asset_support": "required",
                    "fact_binding_support": False,
                    "order": 0,
                },
                {
                    "id": "versus_1",
                    "type": "VersusCard",
                    "label": "对比卡",
                    "semantic_role": "comparison",
                    "content_brief": "优缺点对撞",
                    "props": {"type": "VersusCard", "title": "旧对比"},
                    "style": {},
                    "asset_refs": [],
                    "fact_bindings": [],
                    "editable_targets": ["title", "proText", "conText"],
                    "asset_support": "none",
                    "fact_binding_support": True,
                    "order": 1,
                },
                {
                    "id": "poll_1",
                    "type": "PollBlock",
                    "label": "投票卡",
                    "semantic_role": "interactive_opinion",
                    "content_brief": "互动投票",
                    "props": {"type": "PollBlock", "question": "旧互动"},
                    "style": {},
                    "asset_refs": [],
                    "fact_bindings": [],
                    "editable_targets": ["question", "option_a", "option_b"],
                    "asset_support": "none",
                    "fact_binding_support": False,
                    "order": 2,
                },
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
            "planner": {},
        },
    })

    blocks = result["note_document"]["blocks"]
    component_types = [block["type"] for block in blocks]

    assert component_types[0] == "TitleBlock"
    assert "StoryText" in component_types
    assert "CoverSwiper" in component_types
    assert result["note_document"]["document_meta"]["title"] == "旧页面"


@pytest.mark.asyncio
async def test_outline_synthesizer_rebuilds_from_planner_for_create_requests_on_existing_canvas():
    result = await outline_synthesizer({
        "intent_decision": {"task_type": "create"},
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
    })

    blocks = result["note_document"]["blocks"]
    block_ids = [block["id"] for block in blocks]
    component_types = [block["type"] for block in blocks]

    assert "cover_old" not in block_ids
    assert component_types[:2] == ["TitleBlock", "StoryText"]
    assert "VersusCard" in component_types
    assert "PollBlock" in component_types


@pytest.mark.asyncio
async def test_outline_synthesizer_rebuilds_for_create_like_query_even_without_intent_result():
    result = await outline_synthesizer({
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
            ],
            "scenario_scores": {"seeding": 1.0},
        },
    })

    blocks = result["note_document"]["blocks"]
    block_ids = [block["id"] for block in blocks]
    component_types = [block["type"] for block in blocks]

    assert "cover_old" not in block_ids
    assert component_types[:2] == ["TitleBlock", "StoryText"]
    assert "VersusCard" in component_types


@pytest.mark.asyncio
async def test_theme_compiler_compiles_distinct_scenario_theme_tokens():
    seeding = await theme_compiler({
        "active_archetype": "seeding",
        "has_controversy": True,
        "planner_policy": {"theme_policy": {"preset": "seeding_hot", "interaction_bias": "high"}},
        "document_view": {
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper"},
                {"id": "poll_1", "component_type": "PollBlock"},
            ]
        },
    })
    travel = await theme_compiler({
        "active_archetype": "travel",
        "has_controversy": False,
        "planner_policy": {"theme_policy": {"preset": "travel_clean", "interaction_bias": "low"}},
        "document_view": {
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper"},
                {"id": "poll_1", "component_type": "PollBlock"},
            ]
        },
    })

    seeding_theme = (seeding["note_document"].get("theme") or {})
    travel_theme = (travel["note_document"].get("theme") or {})
    seeding_vars = seeding_theme["global_vars"]
    travel_vars = travel_theme["global_vars"]
    seeding_blocks = {block["id"]: block for block in seeding["note_document"]["blocks"]}
    travel_blocks = {block["id"]: block for block in travel["note_document"]["blocks"]}

    assert seeding_vars["--theme-name"] == "seeding_hot"
    assert travel_vars["--theme-name"] == "travel_clean"
    assert seeding_vars["--primary-vibe"] != travel_vars["--primary-vibe"]
    assert seeding_blocks["poll_1"]["style"]["inline_styles"]["background"] == "var(--card-bg)"
    assert travel_blocks["cover_1"]["style"]["inline_styles"]["boxShadow"] == "var(--hero-shadow)"
    assert seeding["agent_backends"]["theme_compiler"] == "deterministic_compiler"
    assert seeding["turn_trace"]["theme_compiler"]["source"] == "planner_policy"


@pytest.mark.asyncio
async def test_theme_compiler_prefers_planner_theme_policy_over_legacy_intent_vibe():
    result = await theme_compiler({
        "active_archetype": "travel",
        "planner_policy": {"theme_policy": {"preset": "luxury_editorial", "interaction_bias": "high"}},
        "document_view": {
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper"},
                {"id": "poll_1", "component_type": "PollBlock"},
            ]
        },
    })

    vars_map = (result["note_document"].get("theme") or {}).get("global_vars") or {}
    cover_block = next(block for block in result["note_document"]["blocks"] if block["id"] == "cover_1")
    assert vars_map["--theme-name"] == "luxury_editorial"
    assert vars_map["--primary-vibe"] == "#d4af37"
    assert cover_block["style"]["inline_styles"]["transform"] == "translateY(-1px)"


def test_distill_extracts_structured_sources_and_conflicts():
    raw_content = """【官方资料】:
[1] 华为官网 Mate 60 参数页
链接: https://consumer.huawei.com/cn/phones/mate60/
电池容量 5000mAh，支持快充。

[2] 某媒体测评
链接: https://example.com/mate60-review
实测资料提到电池容量为 4500mAh，机身更轻薄。
"""

    sources = _extract_structured_sources(raw_content)
    conflicts = _extract_conflicts(raw_content, sources)

    assert len(sources) == 2
    assert sources[0]["title"] == "华为官网 Mate 60 参数页"
    assert conflicts[0]["field"] == "battery_capacity"
    assert {item["value"] for item in conflicts[0]["values"]} == {"4500", "5000"}


def test_distill_confidence_prefers_official_and_no_conflict():
    sources = [
        {"title": "华为官网", "url": "https://consumer.huawei.com", "source_type": "official"},
        {"title": "媒体评测", "url": "https://example.com/review", "source_type": "web"},
    ]

    assert _infer_fact_confidence(sources, []) == "high"
    assert _infer_fact_confidence(sources, [{"field": "battery_capacity"}]) == "low"


def test_apply_confirmed_facts_to_knowledge_resolves_conflict():
    knowledge = {
        "text_facts": "原始资料提到 Mate 60 电池容量有不同说法。",
        "core_attributes": {},
        "fact_conflicts": [
            {
                "field": "battery_capacity",
                "values": [{"value": "4500", "sources": ["媒体测评"]}, {"value": "5000", "sources": ["华为官网"]}],
            }
        ],
        "fact_confidence": "low",
        "confirmed_facts": {
            "battery_capacity": {"value": "5000", "sources": ["华为官网"]}
        },
    }

    updated = apply_confirmed_facts_to_knowledge(knowledge)

    assert updated["needs_fact_confirmation"] is False
    assert updated["fact_review_status"] == "confirmed"
    assert updated["core_attributes"]["battery_capacity"] == "5000mAh"
    assert updated["fact_conflicts"] == []
    assert "【已确认事实】" in updated["text_facts"]


def test_merge_confirmed_fact_selection_adds_structured_payload():
    updated = merge_confirmed_fact_selection(
        {"fact_conflicts": [{"field": "price", "values": []}], "fact_confidence": "low"},
        field="price",
        value="5499",
        sources=["华为官网"],
    )

    assert updated["confirmed_facts"]["price"]["value"] == "5499元"
    assert updated["confirmed_facts"]["price"]["sources"] == ["华为官网"]
    assert updated["fact_review_status"] == "confirmed"




@pytest.mark.asyncio
async def test_component_builder_node_emits_contract_first_trace_on_fallback(monkeypatch):
    from app.agents.nodes.component_builder import component_builder_node

    class _BrokenStructured:
        async def ainvoke(self, *_args, **_kwargs):
            raise RuntimeError("builder unavailable")

    class _BrokenLLM:
        def with_structured_output(self, *_args, **_kwargs):
            return _BrokenStructured()

    monkeypatch.setattr("app.agents.nodes.component_builder.get_builder_llm", lambda: _BrokenLLM())

    result = await component_builder_node({
        "component_id": "poll_1",
        "component_type": "PollBlock",
        "content_brief": "互动投票",
        "user_query": "给我一个站队投票",
        "active_archetype": "seeding",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60", "key_selling_points": ["影像表现"]},
        "creator_persona": "数码博主",
        "image_assets": [],
        "planner_policy": {"layout_policy": {"preferred_block_intents": ["interactive_opinion"]}},
        "content_messages": [],
    })

    assert result["agent_backends"]["component_builder"] == "contract_first_worker"
    trace = result["turn_trace"]["component_builder"]["poll_1"]
    assert trace["component_type"] == "PollBlock"
    assert trace["fallback_used"] is True
    assert trace["contract_first"] is True
    assert trace["prompt_mode"] == "compact_contract_first"
    assert trace["fact_summary_count"] >= 1
    assert trace["asset_count"] == 0
    assert "precheck_warning_count" in trace
    assert "contract_filter_count" in trace
    assert result["note_document"]["_block_update"]["id"] == "poll_1"
    assert "question" in result["note_document"]["_block_update"]["data"]["props"]


@pytest.mark.asyncio
async def test_component_builder_parallel_patches_do_not_collapse_document_blocks(monkeypatch):
    from app.agents.nodes.component_builder import component_builder_node

    class _BrokenStructured:
        async def ainvoke(self, *_args, **_kwargs):
            raise RuntimeError("builder unavailable")

    class _BrokenLLM:
        def with_structured_output(self, *_args, **_kwargs):
            return _BrokenStructured()

    monkeypatch.setattr("app.agents.nodes.component_builder.get_builder_llm", lambda: _BrokenLLM())

    base_document = {
        "document_meta": {"title": "测试页面"},
        "blocks": [
            {"id": "title_1", "type": "TitleBlock", "props": {}, "style": {}, "order": 0},
            {"id": "poll_1", "type": "PollBlock", "props": {}, "style": {}, "order": 1},
        ],
    }

    title_result = await component_builder_node({
        "component_id": "title_1",
        "component_type": "TitleBlock",
        "content_brief": "标题",
        "user_query": "做一篇华为 Mate 60 对比笔记",
        "active_archetype": "seeding",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60", "summary": "旗舰手机对比"},
        "creator_persona": "数码博主",
        "image_assets": [],
        "planner_policy": {},
        "content_messages": [],
        "note_document": base_document,
    })
    poll_result = await component_builder_node({
        "component_id": "poll_1",
        "component_type": "PollBlock",
        "content_brief": "互动投票",
        "user_query": "做一篇华为 Mate 60 对比笔记",
        "active_archetype": "seeding",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60", "summary": "旗舰手机对比"},
        "creator_persona": "数码博主",
        "image_assets": [],
        "planner_policy": {},
        "content_messages": [],
        "note_document": base_document,
    })

    merged_document = merge_state_patch(
        merge_state_patch(base_document, title_result["note_document"]),
        poll_result["note_document"],
    )

    assert len(merged_document["blocks"]) == 2
    merged_by_id = {block["id"]: block for block in merged_document["blocks"]}
    assert merged_by_id["title_1"]["props"]["title"]
    assert merged_by_id["poll_1"]["props"]["question"]

def test_component_builder_fallback_prefers_confirmed_fact_attributes():
    payload = build_component_fallback(
        comp_type="ProductSpecCard",
        comp_id="spec_1",
        content_brief="参数卡",
        user_query="帮我做 Mate 60 参数卡",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "core_attributes": {"battery_capacity": "5000mAh", "price": "5499元"},
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]},
                "price": {"value": "5499元", "field_label": "价格", "sources": ["华为官网"]},
            },
        },
        image_assets=[],
    )

    assert payload["core_features"][0] == "__verified__电池容量: 5000mAh"
    assert payload["core_features"][1] == "__verified__价格: 5499元"
    assert payload["feature_meta"][0]["kind"] == "verified"
    assert payload["feature_meta"][0]["sources"] == ["华为官网"]
    assert payload["feature_meta"][0]["field"] == "battery_capacity"
    assert payload["spec_items"][0]["label"] == "电池容量"
    assert payload["spec_items"][0]["status"] == "verified"
    assert payload["spec_items"][0]["decision_impact"]


def test_apply_confirmed_facts_to_knowledge_strips_unconfirmed_conflicting_attributes():
    knowledge = {
        "core_attributes": {"battery_capacity": "5000mAh", "price": "5499元"},
        "fact_conflicts": [{"field": "battery_capacity", "values": [{"value": "4500"}, {"value": "5000"}]}],
        "confirmed_facts": {},
        "fact_confidence": "low",
    }

    updated = apply_confirmed_facts_to_knowledge(knowledge)

    assert "battery_capacity" not in updated["core_attributes"]
    assert updated["core_attributes"]["price"] == "5499元"
    assert updated["fact_review_status"] == "pending"


def test_component_builder_fallback_uses_conflict_safe_notes_when_fact_unconfirmed():
    payload = build_component_fallback(
        comp_type="ProductSpecCard",
        comp_id="spec_1",
        content_brief="参数卡",
        user_query="帮我做 Mate 60 参数卡",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "core_attributes": {"price": "5499元"},
            "fact_conflicts": [
                {
                    "field": "battery_capacity",
                    "values": [
                        {"value": "4500", "sources": ["媒体测评"]},
                        {"value": "5000", "sources": ["华为官网"]},
                    ],
                }
            ],
        },
        image_assets=[],
    )

    assert "price: 5499元" in payload["core_features"]
    assert any("电池容量: 存在多版本说法" in item for item in payload["core_features"])
    assert any(item["status"] == "caution" for item in payload["spec_items"])


def test_story_text_fallback_includes_paragraph_meta_for_verified_and_caution():
    payload = build_component_fallback(
        comp_type="StoryText",
        comp_id="text_1",
        content_brief="正文总结",
        user_query="帮我做 Mate 60 正文",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "summary": "这是一台亮点和争议并存的高端机。",
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]},
            },
            "fact_conflicts": [
                {
                    "field": "price",
                    "values": [
                        {"value": "4999", "sources": ["媒体测评"]},
                        {"value": "5499", "sources": ["华为官网"]},
                    ],
                }
            ],
            "key_selling_points": ["续航稳定", "大屏沉浸"],
        },
        image_assets=[],
    )

    assert payload["paragraph_meta"][0]["kind"] == "default"
    assert payload["paragraph_meta"][1]["kind"] == "verified"
    assert payload["paragraph_meta"][1]["sources"] == ["华为官网"]
    assert payload["paragraph_meta"][1]["fields"] == ["battery_capacity"]
    assert payload["paragraph_meta"][2]["kind"] == "caution"
    assert "华为官网" in payload["paragraph_meta"][2]["sources"]
    assert payload["paragraph_meta"][2]["fields"] == ["price"]
    assert payload["sections"][0]["label"] == "开场判断"
    assert payload["sections"][1]["role"] == "verified"
    assert payload["sections"][2]["role"] == "caution"


def test_radar_chart_fallback_emits_structured_metrics():
    payload = build_component_fallback(
        comp_type="RadarChartBlock",
        comp_id="radar_1",
        content_brief="雷达图",
        user_query="帮我做 Mate 60 雷达图",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]},
            },
            "key_selling_points": ["影像辨识度高", "系统体验稳", "手感完整"],
        },
        image_assets=[],
    )

    assert len(payload["metrics"]) == len(payload["dimensions"])
    assert payload["metrics"][0]["label"] == payload["dimensions"][0]
    assert payload["metrics"][0]["reason"]
    assert payload["metrics"][0]["confidence"] in {"high", "medium", "low"}


def test_poll_block_fallback_emits_structured_option_cards():
    payload = build_component_fallback(
        comp_type="PollBlock",
        comp_id="poll_1",
        content_brief="互动投票",
        user_query="帮我做 Mate 60 站队卡",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "key_selling_points": ["影像风格"],
            "known_issues": ["价格门槛"],
        },
        image_assets=[],
    )

    assert payload["option_cards"][0]["label"] == payload["option_a"]
    assert payload["option_cards"][0]["stance"] == "主推理由"
    assert payload["option_cards"][1]["label"] == payload["option_b"]


def test_versus_card_fallback_emits_structured_routes():
    payload = build_component_fallback(
        comp_type="VersusCard",
        comp_id="versus_1",
        content_brief="对比卡",
        user_query="帮我做 Mate 60 对比",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "key_selling_points": ["上手氛围强", "影像更有记忆点"],
            "known_issues": ["价格门槛偏高", "生态协同没那么省心"],
        },
        image_assets=[],
    )

    assert payload["pros"]["summary"]
    assert payload["pros"]["points"]
    assert payload["cons"]["fit_for"]
    assert payload["decision_hint"]
