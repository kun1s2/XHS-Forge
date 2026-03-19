import pytest

from app.agents.nodes.component_builder import build_component_fallback, enforce_component_contract
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
    knowledge_seed = {
        "entity_name": "华为 Mate 60",
        "text_facts": "麒麟芯片回归，影像和卫星通信是亮点，价格门槛较高。",
    }

    distilled = await distill_node({
        "messages": [],
        "retrieved_knowledge": knowledge_seed,
        "image_assets": [],
    })
    knowledge = distilled["retrieved_knowledge"]

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
        "intent_result": {"visual_vibe": "general", "intensity_level": 0.8},
        "style_dsl": {},
        "data_dsl": {
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
    state["style_dsl"] = styled["style_dsl"]
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
        "data_dsl": {
            "blocks": [
                {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面图"},
                {"id": "versus_1", "component_type": "VersusCard", "content_brief": "优缺点对撞"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动投票"},
            ]
        },
    })

    blocks = result["data_dsl"]["blocks"]
    component_types = [block["component_type"] for block in blocks]

    assert component_types[0] == "TitleBlock"
    assert "StoryText" in component_types
    assert "CoverSwiper" in component_types
    assert result["data_dsl"]["page_title"] == "华为 Mate 60 深度种草"


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

    assert payload["core_features"][0] == "电池容量: 5000mAh"
    assert payload["core_features"][1] == "价格: 5499元"
