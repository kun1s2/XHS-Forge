from __future__ import annotations

import pytest

from app.agents.nodes.critique_agent import NoteCritiqueAgent
from app.core.note_document import build_note_document


def test_timeline_recommended_mode_softens_precise_times_in_event_descriptions():
    note_document = build_note_document(
        document_view={
            "page_title": "去金沙湾的游记",
            "blocks": [
                {"id": "timeline_1", "component_type": "TimelineBlock", "content_brief": "行程顺序"},
            ],
            "timeline_1": {
                "type": "TimelineBlock",
                "events": [
                    {"timestamp": "2024-06-16T09:00:00", "title": "出发", "description": "早上8点，从湛江市区出发。"},
                    {"timestamp": "2024-06-16T10:30:00", "title": "抵达", "description": "9点半到达金沙湾，阳光很好。"},
                    {"timestamp": "2024-06-16T12:00:00", "title": "午餐", "description": "中午12点，在附近吃海鲜。"},
                ],
            },
        },
        active_archetype="travel",
    )

    events = note_document["blocks"][0]["props"]["events"]
    descriptions = " ".join(str(item.get("description") or "") for item in events)
    timestamps = [str(item.get("timestamp") or "") for item in events]

    assert "8点" not in descriptions
    assert "9点半" not in descriptions
    assert "12点" not in descriptions
    assert timestamps == ["上午", "中午", "下午"]


def test_location_grounding_filters_obviously_mismatched_sources_when_context_exists():
    note_document = build_note_document(
        document_view={
            "page_title": "去金沙湾的游记",
            "blocks": [
                {"id": "loc_1", "component_type": "LocationBlock", "content_brief": "地点信息"},
            ],
            "loc_1": {
                "type": "LocationBlock",
                "poi_name": "金沙湾",
                "location": "湛江市赤坎区东海岸",
                "lat": 21.2573,
                "lng": 110.4056,
            },
        },
        active_archetype="travel",
        retrieved_knowledge={
            "fact_confidence": "low",
            "fact_sources": [
                {"title": "湛江金沙湾游记", "url": "https://example.com/zhanjiang", "source_scope": "official"},
                {"title": "青海湖金沙湾自然保护区", "url": "https://example.com/qinghai", "source_scope": "official"},
                {"title": "深圳佳兆业金沙湾利弊分析", "url": "https://example.com/shenzhen", "source_scope": "official"},
            ],
            "confirmed_facts": {"location": {"value": "湛江市赤坎区东海岸"}},
        },
    )

    binding = note_document["blocks"][0]["fact_bindings"][0]
    labels = [item["label"] for item in binding["source_items"]]

    assert "湛江金沙湾游记" in labels
    assert all("青海湖" not in label for label in labels)
    assert all("深圳" not in label for label in labels)


@pytest.mark.asyncio
async def test_critique_agent_falls_back_to_deterministic_feedback_when_llm_fails():
    agent = NoteCritiqueAgent()

    class _BrokenLLM:
        async def ainvoke(self, _messages):
            raise RuntimeError("boom")

    agent.llm = _BrokenLLM()
    result = await agent.critique(
        {
            "note_document": {
                "document_meta": {"title": "去金沙湾的游记"},
                "blocks": [
                    {
                        "type": "StoryText",
                        "props": {
                            "paragraphs": [
                                "金沙湾位于湛江海边，适合一日游。",
                                "建议上午到海边，中午吃饭，下午散步。",
                                "如果担心路线和交通，最好提前确认公交或打车方式。",
                            ]
                        },
                    }
                ],
                "provenance": {
                    "fact_sources": [
                        {"title": "湛江金沙湾游记", "url": "https://example.com/zhanjiang"},
                    ]
                },
            }
        }
    )

    assert isinstance(result.get("critique_feedback"), dict)
    assert result["critique_feedback"]["score"] > 0
    assert "suggestions" in result["critique_feedback"]
    assert result["critique_feedback"]["action_recipes"]


def test_critique_agent_renders_note_document_props_instead_of_legacy_data_fields():
    agent = NoteCritiqueAgent()
    note_text = agent._render_note_text(
        {
            "document_meta": {"title": "去金沙湾的游记"},
            "blocks": [
                {"type": "TitleBlock", "props": {"title": "金沙湾", "subtitle": "海边一日游"}},
                {"type": "StoryText", "props": {"paragraphs": ["第一段", "第二段"]}},
                {
                    "type": "TimelineBlock",
                    "props": {"events": [{"timestamp": "上午", "title": "到达", "description": "先去海边"}]},
                },
            ],
        }
    )

    assert "去金沙湾的游记" in note_text
    assert "金沙湾" in note_text
    assert "第一段" in note_text
    assert "上午 到达 先去海边" in note_text


def test_critique_agent_flags_over_componentized_travel_pages():
    agent = NoteCritiqueAgent()
    feedback = agent._finalize_feedback(
        {
            "score": 88,
            "emoji_density": 0.0,
            "emotional_intensity": "Low",
            "has_hook": True,
            "has_call_to_action": False,
            "factual_issues": [],
            "completeness_issues": [],
            "suggestions": [],
            "needs_revision": False,
        },
        note_doc={
            "blocks": [
                {"type": "TitleBlock"},
                {"type": "ProductSpecCard"},
                {"type": "RadarChartBlock"},
                {"type": "LocationBlock"},
                {"type": "TimelineBlock"},
            ]
        },
        active_archetype="travel",
    )

    joined = " ".join(feedback["suggestions"])
    assert "模板墙" in joined or "特殊积木" in joined
    assert feedback["needs_revision"] is True
