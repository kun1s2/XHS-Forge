import pytest

from app.agents.nodes.component_builder import apply_component_contract_layer, apply_component_contract_with_trace, build_component_fallback, enforce_component_contract
from app.agents.nodes.distill_node import distill_node
from app.agents.nodes.distill_node import _extract_conflicts, _extract_structured_sources, _infer_fact_confidence
from app.agents.utils.fact_utils import apply_confirmed_facts_to_knowledge, merge_confirmed_fact_selection
from app.agents.nodes.style_node import style_agent
from app.agents.nodes.render_node import render_node
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.graph import outline_synthesizer


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

    styled = await style_agent(state)
    state["note_document"] = styled["note_document"]
    rendered = await render_node(state)
    html = rendered["final_html"]

    assert knowledge["entity_name"] == "华为 Mate 60"
    assert knowledge["is_fact_ready"] is True
    assert "华为 Mate 60 深度种草" in html
    assert "五维表现雷达" in html
    assert "最打动你的是哪一点" in html


@pytest.mark.asyncio
async def test_outline_synthesizer_injects_title_and_story_guards():
    result = await outline_synthesizer({
        "main_messages": [type("Msg", (), {"content": "帮我针对华为 Mate 60 做一个深度种草笔记"})()],
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "summary": "这是一台亮点和争议并存的高端机。",
            "key_selling_points": ["续航稳定", "大屏沉浸", "辨识度高"],
        },
        "document_view": {
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面图"},
                {"id": "versus_1", "component_type": "VersusCard", "content_brief": "优缺点对撞"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动投票"},
            ]
        },
    })

    blocks = result["note_document"]["blocks"]
    component_types = [block["type"] for block in blocks]

    assert component_types[0] == "TitleBlock"
    assert "StoryText" in component_types
    assert "CoverSwiper" in component_types
    assert result["note_document"]["document_meta"]["title"] == "华为 Mate 60 深度种草"


@pytest.mark.asyncio
async def test_style_agent_compiles_distinct_scenario_theme_tokens():
    seeding = await style_agent({
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
    travel = await style_agent({
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
async def test_style_agent_prefers_planner_theme_policy_over_legacy_intent_vibe():
    result = await style_agent({
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
    poll_block = next(block for block in result["note_document"]["blocks"] if block["id"] == "poll_1")
    assert "question" in poll_block["props"]

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
