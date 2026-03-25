import json

import pytest

from app.agents.services.composition_service import composition_service
from app.agents.services.composition_service import (
    CanvasCreationBlockOutput,
    CanvasCreationOutput,
    _apply_canvas_creation_plan,
)
from langchain_core.messages import HumanMessage
from app.agents.services.artifact_quality_service import apply_artifact_quality_fixes
from app.agents.services.research_service import _cache_keyword_matches_entity, _cache_payload_matches_entity
from app.agents.services.research_service import _build_asset_search_query
from app.agents.workers.intent_worker import intent_worker
from app.core.query_heuristics import looks_like_append_block_request
from app.agents.utils.entity_utils import (
    is_generic_entity_name,
    mentions_other_specific_entity,
    normalize_entity_name,
    resolve_state_entity_name,
)
from app.agents.services.artifact_service import infer_revision_reason
from app.core.request_semantics import latest_user_text_from_state


def test_normalize_entity_name_prefers_specific_product_model():
    query = "我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买。"
    assert normalize_entity_name(query) == "华为 Mate 60"
    assert is_generic_entity_name("买一台 4500 元左右的手机") is True
    assert mentions_other_specific_entity("Find X8 Ultra 的影像更猛。", "华为 Mate 60") is True


def test_cache_matching_rejects_generic_hot_topic_for_specific_entity():
    assert _cache_keyword_matches_entity("华为 Mate 60", "华为 Mate 60") is True
    assert _cache_keyword_matches_entity("买一台 4500 元左右的手机", "华为 Mate 60") is False
    assert _cache_payload_matches_entity({"entity_name": "OPPO Find X8 Ultra"}, "华为 Mate 60") is False


def test_asset_search_query_prefers_current_entity_over_raw_edit_instruction():
    assert _build_asset_search_query(
        entity_name="华为 Mate 60",
        user_query="这份档案图片太少了，补几张更像真机质感的图片。",
        asset_mode="SEARCH",
    ) == "华为 Mate 60 真机图 产品图"


def test_append_block_heuristic_recognizes_supported_expansion_prompts():
    assert looks_like_append_block_request("在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。") is True
    assert looks_like_append_block_request("继续补一个新块，专门讲华为 Mate 60 的发展史。") is True
    assert looks_like_append_block_request("再补一个新块，专门讲华为 Mate 60 适合什么人群。") is True
    assert looks_like_append_block_request("把这一段改短一点。") is False


def test_resolve_state_entity_name_prefers_existing_artifact_entity_for_edit_queries():
    state = {
        "note_document": {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
        },
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
    }
    assert resolve_state_entity_name(state, "这份档案图片太少了，补几张更像真机质感的图片。") == "华为 Mate 60"


def test_resolve_state_entity_name_prefers_resume_directive_when_turn_has_no_new_user_text():
    state = {
        "artifact": {"title": "XHS-Forge Note"},
        "resume_directive": {"resume_query": "已确认页面骨架方向，继续围绕「华为 Mate 60」补齐关键事实并开始搭建购买决策档案。"},
    }
    assert resolve_state_entity_name(state, state["resume_directive"]["resume_query"]) == "华为 Mate 60"


def test_latest_user_text_from_state_prefers_user_messages_over_trailing_ai_messages():
    state = {
        "user_messages": [HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。")],
        "main_messages": [
            HumanMessage(content="我想买一台 4500 元左右的手机"),
            HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。"),
            {"content": "已在当前档案后面补充“华为 Mate 60 的销量”新块。", "role": "assistant"},
        ],
    }
    assert latest_user_text_from_state(state) == "在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。"


def test_canvas_creation_plan_sanitizes_placeholder_and_foreign_entity_payloads():
    plan = CanvasCreationOutput(
        reason="创建页面",
        page_title="TitleBlock",
        blocks=[
            CanvasCreationBlockOutput(
                component_type="TitleBlock",
                content_brief="页面标题",
                payload={"type": "TitleBlock", "title": "TitleBlock"},
                intent_type="heading",
            ),
            CanvasCreationBlockOutput(
                component_type="StoryText",
                content_brief="正文叙事",
                payload={
                    "type": "StoryText",
                    "paragraphs": [
                        "StoryText",
                        "Find X8 Ultra 的影像取向更激进，但这段不该落到 Mate 60 页面。",
                    ],
                },
                intent_type="narrative_text",
            ),
        ],
    )

    document_view, _style_map = _apply_canvas_creation_plan(
        {},
        {},
        plan,
        user_query="判断华为 Mate 60 值不值得买",
        retrieved_knowledge={
            "entity_name": "华为 Mate 60",
            "summary": "华为 Mate 60 更适合先从购买结论、关键参数和真实代价三个角度来判断。",
            "key_selling_points": ["拍照和续航是它更容易打动人的地方。"],
        },
        image_assets=[],
    )

    title_block = document_view["title_1"]
    story_block = document_view["story_2"]
    assert title_block["title"] != "TitleBlock"
    assert "Mate 60" in title_block["title"]
    assert story_block["paragraphs"]
    assert all("StoryText" not in paragraph for paragraph in story_block["paragraphs"])
    assert all("Find X8 Ultra" not in paragraph for paragraph in story_block["paragraphs"])


def test_infer_revision_reason_does_not_use_failure_reason_when_visible_change_exists():
    reason = infer_revision_reason(
        {
            "turn_trace": {
                "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
            },
            "last_worker_result": {"failure_reason": "composition_no_effect"},
            "main_messages": [{"content": "把这段结论改得更直接一点"}],
        }
    )

    assert reason != "composition_no_effect"


def test_artifact_quality_autofixes_cover_and_missing_decision_blocks():
    state = {
        "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "summary": "华为 Mate 60 更适合先看拍照、续航和价格之间的取舍。",
            "key_selling_points": ["拍照和续航是它更容易打动人的地方。"],
            "known_issues": ["价格门槛偏高。"],
            "core_attributes": {"price": "4199 元", "battery": "4750mAh"},
        },
        "intent_decision": {"task_type": "create", "operation_type": "generate", "needs_assets": True},
        "note_document": {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
            "blocks": [
                {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {}},
                {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看购买结论。"]}},
            ],
            "assets": [
                {"url": "https://img.example-real.com/mate-60-a.jpg", "desc": "Mate 60 正面图", "selection_state": "available"},
                {"url": "https://img.example-real.com/mate-60-b.jpg", "desc": "Mate 60 背面图", "selection_state": "available"},
            ],
            "ui_state": {},
        },
    }

    patch = apply_artifact_quality_fixes(state)
    note_document = patch["note_document"]
    blocks = note_document["blocks"]
    block_types = [block["type"] for block in blocks]
    cover_block = next(block for block in blocks if block["type"] == "CoverSwiper")

    assert patch["artifact_quality"]["passed"] is True
    assert "ProductSpecCard" in block_types
    assert "VersusCard" in block_types
    assert cover_block["props"]["image_urls"]
    assert note_document["ui_state"]["cover_asset_url"] == "https://img.example-real.com/mate-60-a.jpg"


def test_artifact_quality_autofixes_minimum_purchase_decision_structure():
    patch = apply_artifact_quality_fixes(
        {
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "summary": "华为 Mate 60 更适合先从拍照、续航和价格取舍来判断。",
                "fact_slots": {
                    "price": {"summary": "价格目前大致在 4500 元上下。"},
                    "battery": {"summary": "续航更适合重度日用。"},
                },
            },
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                ],
                "assets": [],
            },
        }
    )

    assert patch["artifact_quality"]["passed"] is True
    block_types = [block["type"] for block in patch["note_document"]["blocks"]]
    assert "StoryText" in block_types
    assert "ProductSpecCard" in block_types
    assert "VersusCard" in block_types


def test_artifact_quality_does_not_require_optional_interactive_block():
    patch = apply_artifact_quality_fixes(
        {
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买，并生成购买决策档案")],
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "summary": "华为 Mate 60 更适合先从拍照、续航和价格取舍来判断。",
            },
            "planner_output": {
                "block_intents": [
                    {"intent_type": "heading", "required": True},
                    {"intent_type": "narrative_text", "required": True},
                    {"intent_type": "comparison", "required": False},
                    {"intent_type": "interactive_opinion", "required": False},
                ]
            },
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                    {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看购买结论和预算边界。"]}},
                    {"id": "risk_1", "type": "StoryText", "props": {"paragraphs": ["如果你更在意性价比，这不是唯一答案。"]}},
                    {"id": "spec_1", "type": "ProductSpecCard", "semantic_role": "evidence_summary", "props": {"core_features": ["价格：4199 元"]}},
                    {"id": "vs_1", "type": "VersusCard", "semantic_role": "comparison", "props": {"title": "优缺点速览", "pros": {"summary": "拍照风格稳"}, "cons": {"summary": "价格偏高"}}},
                ],
                "assets": [],
            },
        }
    )

    assert patch["artifact_quality"]["passed"] is True
    assert "interactive_opinion" not in patch["artifact_quality"]["missing_intents"]


def test_artifact_quality_fails_when_entity_is_not_reflected_in_document():
    patch = apply_artifact_quality_fixes(
        {
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买")],
            "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "note_document": {
                "document_meta": {"title": "这台手机值不值得买"},
                "blocks": [
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "这台手机值不值得买"}},
                    {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["它的表现还不错。"]}},
                    {"id": "spec_1", "type": "ProductSpecCard", "semantic_role": "evidence_summary", "props": {"core_features": ["价格：4199 元"]}},
                    {"id": "vs_1", "type": "VersusCard", "semantic_role": "comparison", "props": {"title": "优缺点速览", "pros": {"summary": "拍照强"}, "cons": {"summary": "价格偏高"}}},
                ],
                "assets": [],
            },
        }
    )

    assert patch["artifact_quality"]["passed"] is False
    assert "华为 Mate 60" in patch["artifact_quality"]["issues"][0]


def test_artifact_quality_fails_when_hero_image_does_not_match_entity():
    patch = apply_artifact_quality_fixes(
        {
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买")],
            "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
            "intent_decision": {"task_type": "edit", "operation_type": "asset_edit", "needs_assets": True},
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {
                        "id": "cover_1",
                        "type": "CoverSwiper",
                        "semantic_role": "hero_media",
                        "props": {"image_urls": ["https://img.example.com/landscape.jpg"]},
                    },
                    {
                        "id": "title_1",
                        "type": "TitleBlock",
                        "semantic_role": "heading",
                        "props": {"title": "华为 Mate 60 值不值得买"},
                    },
                    {
                        "id": "story_1",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {"paragraphs": ["这页主要看拍照、续航和价格取舍。"]},
                    },
                    {
                        "id": "spec_1",
                        "type": "ProductSpecCard",
                        "semantic_role": "evidence_summary",
                        "props": {"core_features": ["价格：4199 元"]},
                    },
                    {
                        "id": "vs_1",
                        "type": "VersusCard",
                        "semantic_role": "comparison",
                        "props": {
                            "title": "优缺点速览",
                            "pros": {"summary": "拍照强"},
                            "cons": {"summary": "价格偏高"},
                        },
                    },
                ],
                "assets": [
                    {
                        "url": "https://img.example.com/landscape.jpg",
                        "desc": "风景图",
                        "query": "手机壁纸",
                        "selection_state": "available",
                    }
                ],
            },
        }
    )

    assert patch["artifact_quality"]["passed"] is False
    assert any("首屏图片与当前数码实体不匹配" in issue for issue in patch["artifact_quality"]["issues"])


def test_artifact_quality_repairs_foreign_entity_blocks():
    patch = apply_artifact_quality_fixes(
        {
            "main_messages": [HumanMessage(content="帮我判断华为 Mate 60 值不值得买")],
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "summary": "华为 Mate 60 更适合先看拍照、续航和价格之间的取舍。",
                "key_selling_points": ["拍照表现更稳。"],
                "known_issues": ["价格门槛偏高。"],
            },
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {
                        "id": "title_1",
                        "type": "TitleBlock",
                        "semantic_role": "heading",
                        "props": {"title": "Find X8 Ultra 值不值得买"},
                    },
                    {
                        "id": "story_1",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {"paragraphs": ["iPhone 17 的路线更适合影像党。"]},
                    },
                ],
                "assets": [],
            },
        }
    )

    blocks = patch["note_document"]["blocks"]
    visible_text = " ".join(str(block.get("props") or {}) for block in blocks)
    assert "Find X8 Ultra" not in visible_text
    assert "iPhone 17" not in visible_text


@pytest.mark.asyncio
async def test_composition_service_materializes_asset_edit_into_existing_hero():
    state = {
        "main_messages": [HumanMessage(content="这份档案图片太少了，补几张更像真机质感的图片。")],
        "intent_decision": {"task_type": "edit", "operation_type": "asset_edit", "needs_assets": True},
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "summary": "华为 Mate 60 更适合先从拍照、续航和价格取舍来判断。",
        },
        "image_assets": [
            {
                "url": "https://img.example-real.com/mate-60-front.jpg",
                "desc": "华为 Mate 60 真机正面图",
                "query": "华为 Mate 60 真机图 产品图",
                "selection_state": "available",
            }
        ],
        "note_document": {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
            "blocks": [
                {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {}},
                {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看结论。"]}},
            ],
            "assets": [],
            "ui_state": {},
        },
    }

    payload = await composition_service(state)
    note_document = payload["note_document"]
    cover_block = next(block for block in note_document["blocks"] if block["type"] == "CoverSwiper")

    assert payload["turn_trace"]["composition_worker"]["action"] == "bind_hero_media"
    assert cover_block["props"]["image_urls"] == ["https://img.example-real.com/mate-60-front.jpg"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt", "keyword"),
    [
        ("在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。", "销量"),
        ("继续补一个新块，专门讲华为 Mate 60 的发展史。", "发展史"),
        ("再补一个新块，专门讲华为 Mate 60 适合什么人群。", "适合人群"),
    ],
)
async def test_composition_service_deterministically_appends_topic_blocks(prompt: str, keyword: str):
    state = {
        "main_messages": [HumanMessage(content=prompt)],
        "intent_decision": {"task_type": "edit", "operation_type": "generate", "scope": "global_canvas"},
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "text_facts": (
                "【补搜 review】:\n"
                "华为 Mate 60 的销量表现明显回升，上市后销量同比显著增长。\n"
                "Mate 60 的发展史和定位变化，决定了它更适合在意鸿蒙生态和影像体验的人群。"
            ),
            "fact_sources": [{"title": "华为 Mate 60 销量与用户口碑观察"}],
        },
        "note_document": {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
            "blocks": [
                {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看结论。"]}},
                {"id": "vs_1", "type": "VersusCard", "semantic_role": "comparison", "props": {"title": "优缺点速览", "pros": {"summary": "拍照稳"}, "cons": {"summary": "价格偏高"}}},
            ],
            "assets": [],
        },
        "image_assets": [],
    }

    payload = await composition_service(state)
    note_document = payload["note_document"]
    blocks = note_document["blocks"]
    changed_block_id = payload["turn_trace"]["changed_blocks"][-1]["id"]
    appended_block = next(block for block in blocks if block["id"] == changed_block_id)
    paragraphs = appended_block["props"]["paragraphs"]

    assert len(blocks) == 4
    assert payload["agent_backends"]["composition_worker"] == "deterministic_append_block"
    assert payload["turn_trace"]["composition_worker"]["action"] == "append_block"
    assert payload["turn_trace"]["changed_blocks"][0]["changed_fields"] == ["added", "props"]
    assert appended_block["type"] == "StoryText"
    assert keyword in " ".join(paragraphs)
    assert "华为 Mate 60" in " ".join(paragraphs)


@pytest.mark.asyncio
async def test_composition_service_prioritizes_append_block_over_stale_asset_intent():
    payload = await composition_service(
        {
            "main_messages": [HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。")],
            "intent_decision": {"task_type": "edit", "operation_type": "asset_edit", "scope": "global_canvas", "needs_assets": True},
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "text_facts": "华为 Mate 60 的销量表现明显回升，上市后销量同比显著增长。",
            },
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": ["https://img.example-real.com/mate-60-front.jpg"]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                    {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看结论。"]}},
                ],
                "assets": [{"url": "https://img.example-real.com/mate-60-front.jpg", "desc": "Mate 60 正面图", "selection_state": "available"}],
            },
        }
    )

    assert payload["turn_trace"]["composition_worker"]["action"] == "append_block"
    assert payload["agent_backends"]["composition_worker"] == "deterministic_append_block"


@pytest.mark.asyncio
async def test_composition_service_recovers_missing_prior_append_topics_from_user_messages():
    payload = await composition_service(
        {
            "user_messages": [
                HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。"),
                HumanMessage(content="继续补一个新块，专门讲华为 Mate 60 的发展史。"),
            ],
            "main_messages": [HumanMessage(content="继续补一个新块，专门讲华为 Mate 60 的发展史。")],
            "intent_decision": {"task_type": "edit", "operation_type": "text_edit", "scope": "global_canvas", "needs_assets": False},
            "retrieved_knowledge": {
                "entity_name": "华为 Mate 60",
                "text_facts": (
                    "华为 Mate 60 的销量表现明显回升，上市后销量同比显著增长。\n"
                    "华为 Mate 60 的发展史值得单独看一眼，决定了它当前的定位。"
                ),
            },
            "note_document": {
                "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": ["https://img.example-real.com/mate-60-front.jpg"]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60 值不值得买"}},
                    {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "props": {"paragraphs": ["先看结论。"]}},
                    {"id": "vs_1", "type": "VersusCard", "semantic_role": "comparison", "props": {"title": "优缺点速览", "pros": {"summary": "拍照稳"}, "cons": {"summary": "价格偏高"}}},
                    {"id": "spec_1", "type": "ProductSpecCard", "semantic_role": "evidence_summary", "props": {"core_features": ["关键参数"]}},
                ],
                "assets": [{"url": "https://img.example-real.com/mate-60-front.jpg", "desc": "Mate 60 正面图", "selection_state": "available"}],
            },
        }
    )

    blocks = payload["note_document"]["blocks"]
    joined = json.dumps(blocks, ensure_ascii=False)
    assert "销量" in joined
    assert "发展史" in joined
    assert len(payload["turn_trace"]["changed_blocks"]) == 2
    assert payload["agent_backends"]["composition_worker"] == "deterministic_append_block"


@pytest.mark.asyncio
async def test_intent_worker_fast_paths_append_block_requests_to_retrieval():
    payload = await intent_worker(
        {
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
            "main_messages": [HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。")],
            "note_document": {
                "blocks": [
                    {"id": "title_1", "component_type": "TitleBlock"},
                    {"id": "story_1", "component_type": "StoryText"},
                ]
            },
        }
    )

    assert payload["intent_route"] == "retrieval_worker"
    assert payload["intent_decision"]["operation_type"] == "text_edit"
