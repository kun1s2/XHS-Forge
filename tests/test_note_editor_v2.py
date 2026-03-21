import pytest

from app.api.chat import _build_turn_end_payload
from app.agents.graph import route_intent
from app.agents.nodes.note_editor_node import (
    CanvasCreationBlockOutput,
    CanvasCreationOutput,
    GlobalCanvasEditOutput,
    LocalNoteEditOutput,
    LocalTextRewriteOutput,
    _apply_canvas_creation_plan,
    _build_component_contract_text,
    _apply_global_edit_plan,
    _build_canvas_creation_fallback,
    _build_global_edit_prompt,
    _apply_local_edit_plan,
    _build_local_edit_prompt,
    _build_theme_patch_fallback,
    _build_tone_rewrite_fallback,
    _extract_rewritable_payload_fields,
    _has_global_edit_request,
    _infer_replacement_component_type,
    _infer_target_component_type,
    _maybe_backfill_local_payload_patch,
    _build_note_editor_prompt,
    _resolve_global_target_id,
    _score_block_for_query,
    _restrict_local_edit_scope,
    _select_note_editor_tools,
    _summarize_blocks,
    note_editor_node,
)
from app.agents.nodes.style_node import style_agent
from app.agents.nodes.verify_note_node import verify_note_node
from app.agents.tools_registry import NOTE_EDITOR_TOOLS
from app.tools.note_tools import move_note_block, replace_note_block


def test_route_intent_prefers_note_editor_for_structure_and_style():
    assert route_intent({"intent_route": "structure_node"}) == "note_editor"
    assert route_intent({"intent_route": "style_node"}) == "note_editor"


def test_build_component_contract_text_surfaces_semantic_role_and_quick_actions():
    contract_text = _build_component_contract_text()
    assert "PollBlock (投票卡) | 语义 interactive_opinion" in contract_text
    assert "快捷动作" in contract_text


def test_route_intent_prefers_note_editor_for_local_selected_edits():
    assert route_intent({"intent_route": "patch_node", "selected_element_id": "poll_1"}) == "note_editor"
    assert route_intent({"intent_route": "content_node", "selected_element_id": "story_1"}) == "note_editor"
    assert route_intent({"intent_route": "style_node", "selected_element_id": "title_1"}) == "note_editor"


def test_route_intent_keeps_patch_node_when_no_local_selection():
    assert route_intent({"intent_route": "patch_node", "selected_element_id": "无 (全局修改)"}) == "patch_node"
    assert route_intent({"intent_route": "patch_node", "selected_element_id": None}) == "patch_node"


def test_route_intent_prefers_note_editor_for_existing_canvas_global_edit():
    state = {
        "intent_route": "content_node",
        "selected_element_id": "无 (全局修改)",
        "main_messages": [type("Msg", (), {"content": "保留标题，重写第二段"})()],
        "document_view": {
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ]
        },
    }

    assert route_intent(state) == "note_editor"


def test_route_intent_prefers_note_editor_for_existing_canvas_brief_edit_commands():
    state = {
        "intent_route": "content_node",
        "selected_element_id": "无 (全局修改)",
        "main_messages": [type("Msg", (), {"content": "文本简短一点"})()],
        "document_view": {
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ]
        },
    }

    assert route_intent(state) == "note_editor"




def test_route_intent_prefers_v2_gateway_contract_for_create_and_edit():
    assert route_intent({"intent_result_v2": {"task_type": "create", "edit_scope": "none", "needs_research": True}}) == "research_agent"
    assert route_intent({"intent_result_v2": {"task_type": "edit", "edit_scope": "global", "needs_research": False}}) == "note_editor"
    assert route_intent({"intent_result_v2": {"task_type": "refuse", "edit_scope": "none", "needs_research": False}}) == "refusal_node"


def test_route_intent_prefers_selected_scope_from_v2_contract():
    state = {
        "intent_result_v2": {"task_type": "edit", "edit_scope": "selected_block", "needs_research": False},
        "selected_element_id": "story_1",
    }
    assert route_intent(state) == "note_editor"


def test_note_editor_tools_do_not_include_inspect_loop_tool():
    tool_names = [tool.name for tool in NOTE_EDITOR_TOOLS]
    assert "inspect_note_state" not in tool_names


def test_local_selection_uses_restricted_note_editor_tools():
    global_tool_names = [tool.name for tool in _select_note_editor_tools(None)]
    local_tool_names = [tool.name for tool in _select_note_editor_tools("poll_1")]

    assert "create_note_block" in global_tool_names
    assert "create_note_block" not in local_tool_names
    assert "update_note_block" in local_tool_names
    assert "finish_layout" in local_tool_names


def test_apply_local_edit_plan_appends_structured_block_after_selected():
    document_view = {
        "page_title": "Mate 60 页面",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }
    block_style_map = {"story_1": {"css_classes": "story", "inline_styles": {}}}

    updated_document_view, updated_block_style_map = _apply_local_edit_plan(
        "story_1",
        document_view,
        block_style_map,
        LocalNoteEditOutput(
            block_id="story_1",
            action="append_block",
            reason="在后面补一个投票",
            new_component_type="投票",
            content_brief="互动站队",
            payload_patch={"question": "买吗？", "option_a": "买", "option_b": "不买"},
        ),
        user_query="在这个后面加一个投票区块",
    )

    assert [block["component_type"] for block in updated_document_view["blocks"]] == ["StoryText", "PollBlock"]
    assert updated_document_view["poll_2"]["type"] == "PollBlock"
    assert updated_document_view["poll_2"]["question"] == "买吗？"
    assert updated_block_style_map["story_1"]["css_classes"] == "story"


def test_apply_local_edit_plan_appends_structured_block_before_selected_when_requested():
    document_view = {
        "page_title": "Mate 60 页面",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }

    updated_document_view, _ = _apply_local_edit_plan(
        "story_1",
        document_view,
        {},
        LocalNoteEditOutput(
            block_id="story_1",
            action="append_block",
            reason="在前面补一个标题",
            new_component_type="标题",
            content_brief="标题引导",
            payload_patch={"title": "新的导语标题"},
        ),
        user_query="在这个前面加一个标题块",
    )

    assert [block["component_type"] for block in updated_document_view["blocks"]] == ["TitleBlock", "StoryText"]
    assert updated_document_view["title_2"]["title"] == "新的导语标题"


def test_apply_local_edit_plan_moves_selected_block_after_semantic_anchor():
    document_view = {
        "page_title": "原标题",
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        "title_1": {"type": "TitleBlock", "title": "原标题"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }
    note_document = {
        "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
        "theme": {"page_theme": {}, "global_vars": {}},
        "blocks": [
            {
                "id": "poll_1",
                "type": "PollBlock",
                "semantic_role": "interactive_opinion",
                "content_brief": "互动",
                "editable_targets": ["question", "option_a", "option_b"],
                "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                "style": {},
            },
            {
                "id": "title_1",
                "type": "TitleBlock",
                "semantic_role": "heading",
                "content_brief": "标题",
                "editable_targets": ["title"],
                "props": {"type": "TitleBlock", "title": "原标题"},
                "style": {},
            },
            {
                "id": "story_1",
                "type": "StoryText",
                "semantic_role": "narrative_text",
                "content_brief": "正文",
                "editable_targets": ["paragraphs"],
                "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                "style": {},
            },
        ],
        "assets": [],
        "fact_bindings": [],
        "provenance": {},
        "ui_state": {},
    }
    planner_policy = {
        "layout_policy": {"preferred_block_intents": ["interactive_opinion", "heading", "narrative_text"]}
    }

    updated_document_view, _ = _apply_local_edit_plan(
        "poll_1",
        document_view,
        {},
        LocalNoteEditOutput(
            block_id="poll_1",
            action="move_block",
            reason="把这个放到标题后面",
        ),
        user_query="把这个放到标题后面",
        planner_policy=planner_policy,
        note_document=note_document,
    )

    assert [block["id"] for block in updated_document_view["blocks"]] == ["title_1", "poll_1", "story_1"]


def test_apply_global_edit_plan_appends_structured_block_after_anchor():
    document_view = {
        "page_title": "Mate 60 页面",
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "title_1": {"type": "TitleBlock", "title": "原标题"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }

    updated_document_view, _ = _apply_global_edit_plan(
        document_view,
        {},
        GlobalCanvasEditOutput(
            action="append_block",
            reason="在正文后补一个投票",
            block_id="story_1",
            new_component_type="投票",
            content_brief="互动站队",
            payload_patch={"question": "买吗？", "option_a": "买", "option_b": "不买"},
        ),
        user_query="在正文后面加一个投票区块",
    )

    assert [block["component_type"] for block in updated_document_view["blocks"]] == ["TitleBlock", "StoryText", "PollBlock"]
    assert updated_document_view["poll_3"]["question"] == "买吗？"


@pytest.mark.asyncio
async def test_verify_note_fills_required_poll_fields():
    state = {
        "main_messages": [],
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "image_assets": [],
        "document_view": {
            "page_title": "",
            "blocks": [
                {
                    "id": "poll_1",
                    "component_type": "PollBlock",
                    "content_brief": "互动投票：你觉得华为 Mate 60 值得买吗？",
                }
            ],
            "poll_1": {
                "title": "普通文案卡"
            },
        },
    }

    result = await verify_note_node(state)
    poll_block = next(block for block in result["note_document"]["blocks"] if block["id"] == "poll_1")
    payload = poll_block["props"]
    assert result["note_document"]["document_meta"]["title"] == "XHS-Forge Note"
    assert payload["question"]
    assert payload["option_a"]
    assert payload["option_b"]


def test_turn_end_payload_keeps_modern_snake_and_camel_case_fields():
    payload = _build_turn_end_payload(
        "ckpt_123",
        oss_url="https://example.com/page",
        image_assets=[{"url": "https://img.example/a.jpg", "desc": "hero"}],
        source_code="<html></html>",
        node_prompts={"intent_agent": "prompt"},
        note_document={"document_meta": {"title": "Mate 60"}, "blocks": [], "assets": []},
        agent_backends={"note_editor": "structured_function_calling"},
    )

    assert payload["checkpoint_id"] == "ckpt_123"
    assert payload["checkpointId"] == "ckpt_123"
    assert "page_data" not in payload
    assert "pageData" not in payload
    assert "style_data" not in payload
    assert "styleData" not in payload
    assert "noteData" not in payload
    assert payload["source_code"] == "<html></html>"
    assert payload["htmlPreview"] == "<html></html>"
    assert payload["node_prompts"]["intent_agent"] == "prompt"
    assert payload["nodePrompts"]["intent_agent"] == "prompt"
    assert payload["agent_backends"]["note_editor"] == "structured_function_calling"
    assert payload["agentBackends"]["note_editor"] == "structured_function_calling"


def test_component_contract_text_includes_editable_targets():
    state = {
        "document_view": {"blocks": []},
        "selected_element_id": None,
        "retrieved_knowledge": {},
        "has_controversy": False,
        "creator_persona": "硬核数码博主",
    }

    prompt = _build_note_editor_prompt(state)

    assert "StoryText (正文块) | 语义 narrative_text: 必填字段 paragraphs | 可编辑目标 paragraphs, paragraphs[0], paragraphs[1], paragraphs[2]" in prompt
    assert "快捷动作 简短一点, 更尖锐, 重写这一段" in prompt
    assert "ProductSpecCard (参数卡) | 语义 evidence_summary: 必填字段 core_features | 可编辑目标 core_features" in prompt


def test_note_editor_prompt_reflects_current_canvas_and_selection():
    state = {
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]}
            },
        },
        "has_controversy": True,
        "creator_persona": "硬核数码博主",
    }

    summary = _summarize_blocks(state["document_view"])
    prompt = _build_note_editor_prompt(state)

    assert "story_1" in summary
    assert "poll_1" in summary
    assert "当前区块数: 2" in prompt
    assert "当前选中组件: poll_1" in prompt
    assert "模式: 局部选中编辑" in prompt
    assert "【NoteDocument 区块能力摘要】" in prompt
    assert '"semantic_role": "interactive_opinion"' in prompt
    assert '"editable_targets": ["question", "option_a", "option_b"]' in prompt
    assert "replace_note_block" in prompt
    assert "move_note_block" in prompt
    assert '"question": "买吗？"' in prompt
    assert 'role=interactive_opinion | editable=question, option_a, option_b' in prompt
    assert "直接开始编辑，不要停留在重复诊断" in prompt
    assert "默认只允许改动选中的那个区块" in prompt
    assert "【事实可信度约束】" in prompt
    assert "电池容量: 5000mAh" in prompt


def test_local_edit_prompt_includes_target_payload_and_style():
    state = {
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        },
        "block_style_map": {
            "poll_1": {"css_classes": "rounded-xl", "inline_styles": {"color": "#111"}},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]}
            },
        },
    }

    prompt = _build_local_edit_prompt(state, "把这个投票改得更毒舌一点")

    assert "只能编辑 block_id=poll_1 这个区块" in prompt
    assert '"question": "买吗？"' in prompt
    assert '"css_classes": "rounded-xl"' in prompt
    assert "把这个投票改得更毒舌一点" in prompt
    assert "电池容量: 5000mAh" in prompt


def test_global_edit_prompt_includes_canvas_state_and_rules():
    state = {
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "block_style_map": {
            "story_1": {"css_classes": "rounded-xl", "inline_styles": {}},
        },
        "retrieved_knowledge": {
            "entity_name": "华为 Mate 60",
            "confirmed_facts": {
                "battery_capacity": {"value": "5000mAh", "field_label": "电池容量", "sources": ["华为官网"]}
            },
        },
    }

    prompt = _build_global_edit_prompt(state, "保留标题，重写第二段")

    assert "当前页面已经存在" in prompt
    assert '"story_1"' in prompt
    assert "保留标题，重写第二段" in prompt
    assert "如果用户提到“第一段/第二段/第三段”" in prompt
    assert "电池容量: 5000mAh" in prompt


def test_move_note_block_reorders_existing_blocks():
    state = {
        "document_view": {
            "blocks": [
                {"id": "a", "component_type": "StoryText", "content_brief": "A"},
                {"id": "b", "component_type": "PollBlock", "content_brief": "B"},
                {"id": "c", "component_type": "VersusCard", "content_brief": "C"},
            ]
        }
    }

    command = move_note_block.func(  # type: ignore[attr-defined]
        block_id="c",
        new_index=0,
        tool_call_id="tool_move_1",
        state=state,
    )

    blocks = command.update["note_document"]["blocks"]
    assert [block["id"] for block in blocks] == ["c", "a", "b"]


def test_replace_note_block_swaps_component_type_and_payload():
    state = {
        "document_view": {
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "旧投票"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        }
    }

    command = replace_note_block.func(  # type: ignore[attr-defined]
        block_id="poll_1",
        new_component_type="RadarChartBlock",
        content_brief="替换成雷达图",
        data_json='{"dimensions":["性能","影像"],"scores":[88,92]}',
        tool_call_id="tool_replace_1",
        state=state,
    )

    note_document = command.update["note_document"]
    block = note_document["blocks"][0]
    assert block["id"] == "poll_1"
    assert block["type"] == "RadarChartBlock"
    assert block["props"]["type"] == "RadarChartBlock"
    assert block["props"]["dimensions"] == ["性能", "影像"]


def test_apply_local_edit_plan_updates_selected_block_and_style():
    original_data = {
        "page_title": "原页面",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
        "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
    }
    original_style = {
        "poll_1": {"css_classes": "old-poll", "inline_styles": {"color": "#111"}},
        "story_1": {"css_classes": "old-story", "inline_styles": {}},
    }

    plan = LocalNoteEditOutput(
        block_id="poll_1",
        action="update_block",
        reason="改成更有攻击性的投票文案",
        content_brief="毒舌投票",
        payload_patch={"question": "这波你还会买吗？", "option_a": "继续冲", "option_b": "直接避雷"},
        style_patch={"css_classes": "new-poll", "inline_styles": {"background": "#fee2e2"}},
    )

    final_data, final_style = _apply_local_edit_plan("poll_1", original_data, original_style, plan)

    assert final_data["poll_1"]["question"] == "这波你还会买吗？"
    assert final_data["poll_1"]["type"] == "PollBlock"
    assert final_data["story_1"]["paragraphs"] == ["原正文"]
    assert final_data["blocks"][1]["content_brief"] == "毒舌投票"
    assert final_style["poll_1"]["css_classes"] == "new-poll"
    assert final_style["poll_1"]["inline_styles"]["color"] == "#111"
    assert final_style["poll_1"]["inline_styles"]["background"] == "#fee2e2"


def test_apply_local_edit_plan_replaces_component_type_in_place():
    original_data = {
        "page_title": "原页面",
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ],
        "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
    }

    plan = LocalNoteEditOutput(
        block_id="poll_1",
        action="replace_block",
        reason="替换为更适合比较的雷达图",
        new_component_type="RadarChartBlock",
        content_brief="性能雷达图",
        payload_patch={"dimensions": ["性能", "影像"], "scores": [88, 92]},
    )

    final_data, final_style = _apply_local_edit_plan("poll_1", original_data, {}, plan)

    assert final_data["blocks"][0]["component_type"] == "RadarChartBlock"
    assert final_data["blocks"][0]["content_brief"] == "性能雷达图"
    assert final_data["poll_1"]["type"] == "RadarChartBlock"
    assert final_data["poll_1"]["dimensions"] == ["性能", "影像"]
    assert final_style == {}


def test_build_canvas_creation_fallback_guarantees_title_and_story_blocks():
    state = {
        "main_messages": [type("Msg", (), {"content": "帮我做一篇 Mate 60 深度种草笔记"})()],
        "planner_output": {
            "block_intents": [
                {"intent_type": "evidence_summary", "goal": "参数证据", "preferred_component": "ProductSpecCard"},
                {"intent_type": "interactive_opinion", "goal": "互动站队", "preferred_component": "PollBlock"},
            ]
        },
        "retrieved_knowledge": {"entity_name": "华为 Mate 60", "confirmed_facts": {"battery": {"value": "5000mAh"}}},
        "has_controversy": True,
    }

    plan = _build_canvas_creation_fallback(state, "帮我做一篇 Mate 60 深度种草笔记")
    component_types = [block.component_type for block in plan.blocks]

    assert component_types[0] == "TitleBlock"
    assert "StoryText" in component_types
    assert any(block.component_type == "ProductSpecCard" for block in plan.blocks)


def test_apply_canvas_creation_plan_materializes_structured_blocks():
    plan = CanvasCreationOutput(
        reason="已创建首版页面",
        page_title="Mate 60 值不值得买",
        blocks=[
            CanvasCreationBlockOutput(
                component_type="TitleBlock",
                content_brief="页面标题",
                payload={"title": "Mate 60 值不值得买"},
                intent_type="heading",
            ),
            CanvasCreationBlockOutput(
                component_type="StoryText",
                content_brief="正文叙事",
                payload={"paragraphs": ["第一段", "第二段"]},
                intent_type="narrative_text",
            ),
            CanvasCreationBlockOutput(
                component_type="ProductSpecCard",
                content_brief="参数证据",
                payload={"core_features": ["电池容量: 5000mAh"]},
                intent_type="evidence_summary",
            ),
        ],
    )

    final_data, final_style = _apply_canvas_creation_plan(
        {},
        {},
        plan,
        user_query="帮我做一篇 Mate 60 深度种草笔记",
        retrieved_knowledge={"entity_name": "华为 Mate 60"},
        image_assets=[],
    )

    assert final_data["page_title"] == "Mate 60 值不值得买"
    assert [block["component_type"] for block in final_data["blocks"]] == ["TitleBlock", "StoryText", "ProductSpecCard"]
    assert final_data["title_1"]["type"] == "TitleBlock"
    assert final_data["story_2"]["paragraphs"] == ["第一段", "第二段"]
    assert final_data["spec_3"]["core_features"] == ["电池容量: 5000mAh"]
    assert final_style == {"title_1": {}, "story_2": {}, "spec_3": {}}


def test_apply_global_edit_plan_moves_block_after_semantic_anchor():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        "title_1": {"type": "TitleBlock", "title": "原标题"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }
    note_document = {
        "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
        "theme": {"page_theme": {}, "global_vars": {}},
        "blocks": [
            {
                "id": "poll_1",
                "type": "PollBlock",
                "semantic_role": "interactive_opinion",
                "content_brief": "互动",
                "editable_targets": ["question", "option_a", "option_b"],
                "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                "style": {},
            },
            {
                "id": "title_1",
                "type": "TitleBlock",
                "semantic_role": "heading",
                "content_brief": "标题",
                "editable_targets": ["title"],
                "props": {"type": "TitleBlock", "title": "原标题"},
                "style": {},
            },
            {
                "id": "story_1",
                "type": "StoryText",
                "semantic_role": "narrative_text",
                "content_brief": "正文",
                "editable_targets": ["paragraphs"],
                "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                "style": {},
            },
        ],
        "assets": [],
        "fact_bindings": [],
        "provenance": {},
        "ui_state": {},
    }
    planner_policy = {
        "layout_policy": {"preferred_block_intents": ["interactive_opinion", "heading", "narrative_text"]}
    }

    plan = GlobalCanvasEditOutput(
        action="move_block",
        reason="把互动那块放到标题后面",
    )

    final_data, _ = _apply_global_edit_plan(
        original_data,
        {},
        plan,
        user_query="把互动那块放到标题后面",
        planner_policy=planner_policy,
        note_document=note_document,
    )

    assert [block["id"] for block in final_data["blocks"]] == ["title_1", "poll_1", "story_1"]


def test_apply_global_edit_plan_rewrites_specific_paragraph_without_touching_title():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段", "第三段"]},
    }

    plan = GlobalCanvasEditOutput(
        action="rewrite_paragraph",
        reason="按要求重写第二段",
        block_id="story_1",
        paragraph_index=1,
        paragraph_text="这是重写后的第二段",
    )

    final_data, final_style = _apply_global_edit_plan(original_data, {}, plan)

    assert final_data["page_title"] == "原标题"
    assert final_data["story_1"]["paragraphs"] == ["第一段", "这是重写后的第二段", "第三段"]
    assert final_style == {}


def test_apply_global_edit_plan_updates_page_title():
    original_data = {
        "page_title": "旧标题",
        "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}],
        "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
    }

    plan = GlobalCanvasEditOutput(
        action="update_page_title",
        reason="更新页面标题",
        page_title="新标题",
    )

    final_data, _ = _apply_global_edit_plan(original_data, {}, plan)
    assert final_data["page_title"] == "新标题"
    assert final_data["story_1"]["paragraphs"] == ["原正文"]


def test_apply_global_edit_plan_updates_page_theme():
    original_data = {
        "page_title": "旧标题",
        "page_theme": {"--bg-color": "#ffffff"},
        "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}],
        "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
    }

    plan = GlobalCanvasEditOutput(
        action="update_page_theme",
        reason="改成更克制的灰蓝风格",
        page_theme_patch={"--bg-color": "#e2e8f0", "--primary-vibe": "#0f172a"},
    )

    final_data, _ = _apply_global_edit_plan(original_data, {}, plan)

    assert final_data["page_theme"]["--bg-color"] == "#e2e8f0"
    assert final_data["page_theme"]["--primary-vibe"] == "#0f172a"
    assert final_data["story_1"]["paragraphs"] == ["原正文"]


def test_apply_global_edit_plan_appends_structured_block():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }

    plan = GlobalCanvasEditOutput(
        action="append_block",
        reason="补一个投票区块",
        new_component_type="投票",
        content_brief="互动站队",
        payload_patch={"question": "你会买吗？", "option_a": "会", "option_b": "不会"},
    )

    final_data, final_style = _apply_global_edit_plan(
        original_data,
        {},
        plan,
        user_query="补一个投票区块",
    )

    assert [block["component_type"] for block in final_data["blocks"]] == ["StoryText", "PollBlock"]
    assert final_data["poll_2"]["type"] == "PollBlock"
    assert final_data["poll_2"]["question"] == "你会买吗？"
    assert final_style["poll_2"] == {}


def test_apply_global_edit_plan_appends_structured_block_after_semantic_anchor():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "title_1": {"type": "TitleBlock", "title": "原标题"},
        "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }
    note_document = {
        "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
        "theme": {"page_theme": {}, "global_vars": {}},
        "blocks": [
            {
                "id": "title_1",
                "type": "TitleBlock",
                "semantic_role": "heading",
                "content_brief": "标题",
                "editable_targets": ["title"],
                "props": {"type": "TitleBlock", "title": "原标题"},
                "style": {},
            },
            {
                "id": "poll_1",
                "type": "PollBlock",
                "semantic_role": "interactive_opinion",
                "content_brief": "互动",
                "editable_targets": ["question", "option_a", "option_b"],
                "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                "style": {},
            },
            {
                "id": "story_1",
                "type": "StoryText",
                "semantic_role": "narrative_text",
                "content_brief": "正文",
                "editable_targets": ["paragraphs"],
                "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                "style": {},
            },
        ],
        "assets": [],
        "fact_bindings": [],
        "provenance": {},
        "ui_state": {},
    }
    planner_policy = {
        "layout_policy": {"preferred_block_intents": ["interactive_opinion", "narrative_text"]}
    }

    plan = GlobalCanvasEditOutput(
        action="append_block",
        reason="在互动那块后面补一个参数卡",
        new_component_type="参数卡",
        content_brief="参数证据",
        payload_patch={"core_features": ["麒麟芯片", "卫星通信"]},
    )

    final_data, _ = _apply_global_edit_plan(
        original_data,
        {},
        plan,
        user_query="在互动那块后面补一个参数卡",
        planner_policy=planner_policy,
        note_document=note_document,
    )

    assert [block["component_type"] for block in final_data["blocks"]] == ["TitleBlock", "PollBlock", "ProductSpecCard", "StoryText"]
    assert final_data["spec_4"]["type"] == "ProductSpecCard"
    assert final_data["spec_4"]["core_features"] == ["麒麟芯片", "卫星通信"]


def test_apply_global_edit_plan_replaces_component_by_query_hint_when_block_missing():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }

    plan = GlobalCanvasEditOutput(
        action="replace_block",
        reason="把投票换成雷达图",
        new_component_type="雷达图",
        payload_patch={"dimensions": ["性能", "影像"], "scores": [88, 92]},
    )

    final_data, _ = _apply_global_edit_plan(original_data, {}, plan, user_query="把投票换成雷达图")

    assert final_data["blocks"][0]["component_type"] == "RadarChartBlock"
    assert final_data["poll_1"]["type"] == "RadarChartBlock"
    assert final_data["poll_1"]["dimensions"] == ["性能", "影像"]


def test_apply_global_edit_plan_removes_component_by_query_hint_when_block_missing():
    original_data = {
        "page_title": "原标题",
        "blocks": [
            {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "spec_1": {"type": "ProductSpecCard", "core_features": ["麒麟芯片", "66W 快充"]},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
    }

    plan = GlobalCanvasEditOutput(
        action="remove_block",
        reason="删掉参数卡",
    )

    final_data, _ = _apply_global_edit_plan(original_data, {}, plan, user_query="删掉参数卡")

    assert [block["id"] for block in final_data["blocks"]] == ["story_1"]
    assert "spec_1" not in final_data


def test_global_canvas_edit_output_parses_string_theme_patch():
    output = GlobalCanvasEditOutput(
        action="update_page_theme",
        page_theme_patch="--bg-color: #f0f4f8; --primary-vibe: #475569; --border-color: #d0d0d0;",
    )

    assert output.page_theme_patch["--bg-color"] == "#f0f4f8"
    assert output.page_theme_patch["--primary-vibe"] == "#475569"
    assert output.page_theme_patch["--border-color"] == "#d0d0d0"


def test_global_canvas_edit_output_normalizes_theme_alias_keys():
    output = GlobalCanvasEditOutput(
        action="update_page_theme",
        page_theme_patch={
            "--bg-color": "#f0f4f8",
            "--primary-color": "#34495e",
            "--secondary-color": "#7f8c8d",
        },
    )

    assert output.page_theme_patch["--primary-vibe"] == "#34495e"
    assert output.page_theme_patch["--muted-color"] == "#7f8c8d"


def test_global_canvas_edit_output_normalizes_component_type_alias():
    output = GlobalCanvasEditOutput(
        action="replace_block",
        new_component_type="雷达图",
    )

    assert output.new_component_type == "RadarChartBlock"


def test_build_theme_patch_fallback_recognizes_gray_blue_request():
    patch = _build_theme_patch_fallback(
        "把整体页面改成更克制的灰蓝风格"
    )

    assert patch["--bg-color"] == "#e2e8f0"
    assert patch["--primary-vibe"] == "#475569"
    assert patch["--border-color"] == "#cbd5e1"


def test_build_theme_patch_fallback_can_use_planner_theme_policy_hint():
    patch = _build_theme_patch_fallback(
        "整体页面再高级一点",
        {"theme_policy": {"preset": "luxury_editorial"}},
    )

    assert patch["--bg-color"] == "#111111"
    assert patch["--primary-vibe"] == "#d4af37"


def test_infer_replacement_component_type_prefers_target_after_replace_phrase():
    assert _infer_replacement_component_type("把投票换成雷达图") == "RadarChartBlock"


def test_infer_target_component_type_prefers_source_component_for_replace():
    assert _infer_target_component_type("把投票换成雷达图", "replace_block", "RadarChartBlock") == "PollBlock"
    assert _infer_target_component_type("删掉参数卡", "remove_block") == "ProductSpecCard"
    assert _infer_target_component_type("重写第二段", "rewrite_paragraph") == "StoryText"


def test_infer_target_component_type_can_use_planner_policy_hints():
    planner_policy = {
        "primary_scenario": "seeding",
        "layout_policy": {"preferred_block_intents": ["heading", "evidence_summary", "narrative_text"]},
    }

    assert _infer_target_component_type(
        "把证据那块收敛一点",
        "update_block",
        planner_policy=planner_policy,
    ) == "RadarChartBlock"


def test_infer_target_component_type_can_use_note_document_semantic_hints():
    note_document = {
        "blocks": [
            {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text"},
            {"id": "custom_1", "type": "StoryText", "semantic_role": "interactive_opinion"},
        ]
    }

    assert _infer_target_component_type(
        "把互动那块改得更毒舌一点",
        "update_block",
        note_document=note_document,
    ) == "StoryText"


def test_resolve_global_target_id_uses_query_component_hints():
    document_view = {
        "blocks": [
            {"id": "vs_1", "component_type": "VersusCard", "content_brief": "对比"},
            {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ]
    }

    replace_plan = GlobalCanvasEditOutput(action="replace_block", new_component_type="RadarChartBlock")
    remove_plan = GlobalCanvasEditOutput(action="remove_block")

    assert _resolve_global_target_id(replace_plan, document_view, "把投票换成雷达图") == "poll_1"
    assert _resolve_global_target_id(remove_plan, document_view, "删掉参数卡") == "spec_1"


def test_resolve_global_target_id_overrides_wrong_explicit_block_when_query_mentions_text():
    document_view = {
        "blocks": [
            {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ]
    }

    plan = GlobalCanvasEditOutput(action="update_block", block_id="cover_1")

    assert _resolve_global_target_id(plan, document_view, "修改文本内容") == "story_1"


def test_score_block_for_query_uses_content_brief_and_payload_context():
    story_block = {"id": "story_2", "component_type": "StoryText", "content_brief": "结论总结"}
    story_payload = {"type": "StoryText", "paragraphs": ["这段是最终结论", "建议更克制表达"]}
    title_block = {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"}
    title_payload = {"type": "TitleBlock", "title": "Mate 60 结论"}

    assert _score_block_for_query(story_block, story_payload, "把结论那块简短一点") > _score_block_for_query(title_block, title_payload, "把结论那块简短一点")


def test_score_block_for_query_uses_action_aware_editable_targets():
    rewrite_block = {"id": "story_1", "component_type": "StoryText", "content_brief": "普通区块"}
    rewrite_payload = {"type": "StoryText", "paragraphs": ["第一段", "第二段"]}
    rewrite_meta = {"semantic_role": "narrative_text", "editable_targets": ["paragraphs"]}

    interactive_block = {"id": "poll_1", "component_type": "PollBlock", "content_brief": "普通区块"}
    interactive_payload = {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"}
    interactive_meta = {"semantic_role": "interactive_opinion", "editable_targets": ["question", "option_a", "option_b"]}

    assert _score_block_for_query(
        rewrite_block,
        rewrite_payload,
        "重写一下",
        block_meta=rewrite_meta,
        action="rewrite_paragraph",
    ) > _score_block_for_query(
        interactive_block,
        interactive_payload,
        "重写一下",
        block_meta=interactive_meta,
        action="rewrite_paragraph",
    )


def test_score_block_for_query_uses_manifest_quick_actions_and_label_hints():
    interactive_block = {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动站队"}
    interactive_payload = {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"}
    interactive_meta = {"type": "PollBlock", "semantic_role": "interactive_opinion", "editable_targets": ["question", "option_a", "option_b"]}

    story_block = {"id": "story_1", "component_type": "StoryText", "content_brief": "正文总结"}
    story_payload = {"type": "StoryText", "paragraphs": ["第一段", "第二段"]}
    story_meta = {"type": "StoryText", "semantic_role": "narrative_text", "editable_targets": ["paragraphs"]}

    assert _score_block_for_query(
        interactive_block,
        interactive_payload,
        "把投票卡改得更毒舌一点",
        block_meta=interactive_meta,
    ) > _score_block_for_query(
        story_block,
        story_payload,
        "把投票卡改得更毒舌一点",
        block_meta=story_meta,
    )


def test_resolve_global_target_id_matches_block_context_without_component_alias():
    document_view = {
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
            {"id": "story_2", "component_type": "StoryText", "content_brief": "结论总结"},
        ],
        "title_1": {"type": "TitleBlock", "title": "Mate 60 到底值不值"},
        "story_2": {"type": "StoryText", "paragraphs": ["最终结论是更适合稳健党", "建议观望"]},
    }
    plan = GlobalCanvasEditOutput(action="update_block")

    assert _resolve_global_target_id(plan, document_view, "把结论那块简短一点") == "story_2"


def test_resolve_global_target_id_uses_note_document_semantic_role_metadata():
    document_view = {
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动站队"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
    }
    plan = GlobalCanvasEditOutput(action="update_block")

    assert _resolve_global_target_id(plan, document_view, "把互动那块改得更毒舌一点") == "poll_1"
    assert _has_global_edit_request("把互动那块改得更毒舌一点", document_view) is True


def test_resolve_global_target_id_uses_planner_policy_intent_hint():
    document_view = {
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文总结"},
            {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数证据"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["这是一段正文", "这里有总结"]},
        "spec_1": {"type": "ProductSpecCard", "core_features": ["续航稳定", "屏幕亮度高"]},
    }
    planner_policy = {
        "layout_policy": {
            "preferred_block_intents": ["heading", "narrative_text", "evidence_summary"]
        }
    }
    plan = GlobalCanvasEditOutput(action="update_block")

    assert _resolve_global_target_id(
        plan,
        document_view,
        "把证据那块收敛一点",
        planner_policy=planner_policy,
    ) == "spec_1"
    assert _has_global_edit_request(
        "把证据那块收敛一点",
        document_view,
        planner_policy=planner_policy,
    ) is True


def test_resolve_global_target_id_prefers_passed_note_document_metadata():
    document_view = {
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "custom_1", "component_type": "StoryText", "content_brief": "自定义互动摘要"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        "custom_1": {"type": "StoryText", "paragraphs": ["互动引导文案"]},
    }
    note_document = {
        "blocks": [
            {"id": "story_1", "type": "StoryText", "semantic_role": "narrative_text", "editable_targets": ["paragraphs"]},
            {"id": "custom_1", "type": "StoryText", "semantic_role": "interactive_opinion", "editable_targets": ["question", "option_a", "option_b"]},
        ]
    }
    plan = GlobalCanvasEditOutput(action="update_block")

    assert _resolve_global_target_id(
        plan,
        document_view,
        "把互动那块改得更毒舌一点",
        note_document=note_document,
    ) == "custom_1"
    assert _has_global_edit_request(
        "把互动那块改得更毒舌一点",
        document_view,
        note_document=note_document,
    ) is True


@pytest.mark.asyncio
async def test_style_agent_respects_page_theme_over_vibe_defaults():
    result = await style_agent(
        {
            "document_view": {
                "page_theme": {"--bg-color": "#e2e8f0", "--primary-vibe": "#0f172a"},
                "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}],
            },
            "planner_policy": {"theme_policy": {"preset": "travel_clean", "interaction_bias": "low"}},
        }
    )

    theme = result["note_document"]["theme"]
    assert theme["global_vars"]["--bg-color"] == "#e2e8f0"
    assert theme["global_vars"]["--primary-vibe"] == "#0f172a"


def test_extract_rewritable_payload_fields_only_keeps_visible_text_fields():
    payload = {
        "type": "PollBlock",
        "question": "买吗？",
        "option_a": "买",
        "option_b": "不买",
        "scores": [88, 92],
        "metadata": {"foo": "bar"},
    }

    fields = _extract_rewritable_payload_fields(payload)

    assert fields == {
        "question": "买吗？",
        "option_a": "买",
        "option_b": "不买",
    }


def test_build_tone_rewrite_fallback_for_poll_block():
    patch = _build_tone_rewrite_fallback(
        "把这个投票改得更毒舌一点",
        {"id": "poll_1", "component_type": "PollBlock"},
        {"type": "PollBlock", "question": "你怎么看？", "option_a": "支持", "option_b": "反对"},
    )

    assert patch["question"].startswith("说句难听的，")
    assert patch["option_a"].startswith("真爱粉硬冲：")
    assert patch["option_b"].startswith("清醒党避雷：")


def test_restrict_local_edit_scope_only_keeps_selected_block_changes():
    original_data = {
        "page_title": "原页面",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            {"id": "vs_1", "component_type": "VersusCard", "content_brief": "对比"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
        "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
        "vs_1": {"type": "VersusCard", "title": "原对比", "proText": "原优点", "conText": "原缺点"},
    }
    updated_data = {
        "page_title": "被误改的新标题",
        "blocks": [
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "新投票"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "vs_1", "component_type": "VersusCard", "content_brief": "对比"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["被误改"]},
        "poll_1": {"type": "PollBlock", "question": "新问题", "option_a": "新A", "option_b": "新B"},
        "vs_1": {"type": "VersusCard", "title": "被误改", "proText": "被误改", "conText": "被误改"},
    }
    original_style = {
        "global_vars": {"--bg-color": "#fff"},
        "poll_1": {"css_classes": "old-poll", "inline_styles": {}},
        "story_1": {"css_classes": "old-story", "inline_styles": {}},
    }
    updated_style = {
        "global_vars": {"--bg-color": "#000"},
        "poll_1": {"css_classes": "new-poll", "inline_styles": {}},
        "story_1": {"css_classes": "new-story", "inline_styles": {}},
    }

    final_data, final_style = _restrict_local_edit_scope(
        "poll_1",
        original_data,
        updated_data,
        original_style,
        updated_style,
    )

    assert final_data["page_title"] == "原页面"
    assert [block["id"] for block in final_data["blocks"]] == ["story_1", "poll_1", "vs_1"]
    assert final_data["poll_1"]["question"] == "新问题"
    assert final_data["story_1"]["paragraphs"] == ["原正文"]
    assert final_data["vs_1"]["title"] == "原对比"
    assert final_style["poll_1"]["css_classes"] == "new-poll"
    assert final_style["story_1"]["css_classes"] == "old-story"


def test_restrict_local_edit_scope_allows_selected_block_removal_only():
    original_data = {
        "page_title": "原页面",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
        "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
    }
    updated_data = {
        "page_title": "被误改的新标题",
        "blocks": [
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ],
        "story_1": {"type": "StoryText", "paragraphs": ["被误改"]},
    }

    final_data, final_style = _restrict_local_edit_scope(
        "poll_1",
        original_data,
        updated_data,
        {"poll_1": {"css_classes": "poll", "inline_styles": {}}},
        {"story_1": {"css_classes": "new-story", "inline_styles": {}}},
    )

    assert [block["id"] for block in final_data["blocks"]] == ["story_1"]
    assert "poll_1" not in final_data
    assert "poll_1" not in final_style
    assert final_data["story_1"]["paragraphs"] == ["原正文"]


@pytest.mark.asyncio
async def test_backfill_local_payload_patch_rewrites_visible_copy(monkeypatch):
    class FakeRewriteRunner:
        async def ainvoke(self, prompt):
            assert "必须把变化写进 payload_patch" in prompt
            return LocalTextRewriteOutput(
                reason="已补全投票文案",
                payload_patch={
                    "question": "这波你还敢买吗？",
                    "option_a": "继续闭眼冲",
                    "option_b": "直接拉黑避雷",
                },
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is LocalTextRewriteOutput
            assert method == "function_calling"
            return FakeRewriteRunner()

    plan = LocalNoteEditOutput(
        block_id="poll_1",
        action="update_block",
        reason="按用户要求完成局部编辑",
        content_brief="更毒舌一点",
        payload_patch={},
    )

    result = await _maybe_backfill_local_payload_patch(
        FakeLLM(),
        "把这个投票改得更毒舌一点",
        {"id": "poll_1", "component_type": "PollBlock"},
        {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        plan,
    )

    assert result.payload_patch["question"] == "这波你还敢买吗？"
    assert result.payload_patch["option_a"] == "继续闭眼冲"
    assert result.payload_patch["option_b"] == "直接拉黑避雷"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_canvas_creation_path(monkeypatch):
    class FakeCreationRunner:
        async def ainvoke(self, prompt):
            assert "当前页面为空" in prompt
            return CanvasCreationOutput(
                reason="已生成首版画布",
                page_title="Mate 60 深度种草",
                blocks=[
                    CanvasCreationBlockOutput(component_type="TitleBlock", content_brief="页面标题", payload={"title": "Mate 60 深度种草"}),
                    CanvasCreationBlockOutput(component_type="StoryText", content_brief="正文叙事", payload={"paragraphs": ["第一段", "第二段"]}),
                    CanvasCreationBlockOutput(component_type="ProductSpecCard", content_brief="参数证据", payload={"core_features": ["电池容量: 5000mAh"]}),
                ],
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is CanvasCreationOutput
            assert method == "function_calling"
            return FakeCreationRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "帮我生成一篇关于华为 Mate 60 的深度种草笔记"})()],
        "document_view": {},
        "block_style_map": {},
        "planner_output": {
            "block_intents": [
                {"intent_type": "heading", "goal": "页面标题", "preferred_component": "TitleBlock"},
                {"intent_type": "narrative_text", "goal": "正文叙事", "preferred_component": "StoryText"},
                {"intent_type": "evidence_summary", "goal": "参数证据", "preferred_component": "ProductSpecCard"},
            ]
        },
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
    }

    result = await note_editor_node(state)

    assert result["note_document"]["document_meta"]["title"] == "Mate 60 深度种草"
    assert "note_editor" in result["node_prompts"]
    assert result["node_prompts"]["note_editor"][0]["role"] == "system"
    blocks = result["note_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["TitleBlock", "StoryText", "ProductSpecCard"]
    assert next(block for block in blocks if block["id"] == "title_1")["props"]["type"] == "TitleBlock"
    assert next(block for block in blocks if block["id"] == "story_2")["props"]["paragraphs"] == ["第一段", "第二段"]
    assert result["main_messages"][0].content == "已生成首版画布"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_local_edit_path(monkeypatch):
    class FakeStructuredRunner:
        async def ainvoke(self, prompt):
            assert "只能编辑 block_id=poll_1 这个区块" in prompt
            return LocalNoteEditOutput(
                block_id="poll_1",
                action="update_block",
                reason="已按要求修改选中投票",
                payload_patch={"question": "你还会继续买吗？", "option_a": "会", "option_b": "不会"},
                style_patch={"css_classes": "updated-poll"},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is LocalNoteEditOutput
            assert method == "function_calling"
            return FakeStructuredRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把这个投票改得更直接一点"})()],
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
            "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
        },
        "block_style_map": {
            "poll_1": {"css_classes": "old-poll", "inline_styles": {}},
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    blocks = {block["id"]: block for block in result["note_document"]["blocks"]}
    assert blocks["poll_1"]["props"]["question"] == "你还会继续买吗？"
    assert blocks["story_1"]["props"]["paragraphs"] == ["原正文"]
    assert blocks["poll_1"]["style"]["css_classes"] == "updated-poll"
    assert blocks["story_1"]["style"]["css_classes"] == "old-story"
    assert result["main_messages"][0].content == "已按要求修改选中投票"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_local_move_path_with_semantic_anchor(monkeypatch):
    class FakeStructuredRunner:
        async def ainvoke(self, prompt):
            assert "只能编辑 block_id=poll_1 这个区块" in prompt
            assert "把这个放到标题后面" in prompt
            return LocalNoteEditOutput(
                block_id="poll_1",
                action="move_block",
                reason="已把这个放到标题后面",
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is LocalNoteEditOutput
            assert method == "function_calling"
            return FakeStructuredRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把这个放到标题后面"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
                {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
            "title_1": {"type": "TitleBlock", "title": "原标题"},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {
            "poll_1": {"css_classes": "poll", "inline_styles": {}},
            "title_1": {"css_classes": "title", "inline_styles": {}},
            "story_1": {"css_classes": "story", "inline_styles": {}},
        },
        "note_document": {
            "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "poll_1",
                    "type": "PollBlock",
                    "semantic_role": "interactive_opinion",
                    "content_brief": "互动",
                    "editable_targets": ["question", "option_a", "option_b"],
                    "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                    "style": {},
                },
                {
                    "id": "title_1",
                    "type": "TitleBlock",
                    "semantic_role": "heading",
                    "content_brief": "标题",
                    "editable_targets": ["title"],
                    "props": {"type": "TitleBlock", "title": "原标题"},
                    "style": {},
                },
                {
                    "id": "story_1",
                    "type": "StoryText",
                    "semantic_role": "narrative_text",
                    "content_brief": "正文",
                    "editable_targets": ["paragraphs"],
                    "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                    "style": {},
                },
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
        },
        "planner_policy": {
            "layout_policy": {"preferred_block_intents": ["interactive_opinion", "heading", "narrative_text"]}
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["agent_backends"]["note_editor"] == "structured_function_calling"
    assert [block["id"] for block in result["note_document"]["blocks"]] == ["title_1", "poll_1", "story_1"]
    assert result["main_messages"][0].content == "已把这个放到标题后面"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_local_append_path(monkeypatch):
    class FakeStructuredRunner:
        async def ainvoke(self, prompt):
            assert "只能编辑 block_id=story_1 这个区块" in prompt
            return LocalNoteEditOutput(
                block_id="story_1",
                action="append_block",
                reason="已在当前正文后补一个投票",
                new_component_type="投票",
                content_brief="互动站队",
                payload_patch={"question": "你会买吗？", "option_a": "会", "option_b": "不会"},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is LocalNoteEditOutput
            assert method == "function_calling"
            return FakeStructuredRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "在这个后面加一个投票区块"})()],
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
        },
        "block_style_map": {"story_1": {"css_classes": "old-story", "inline_styles": {}}},
        "selected_element_id": "story_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["agent_backends"]["note_editor"] == "structured_function_calling"
    blocks = result["note_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["StoryText", "PollBlock"]
    assert next(block for block in blocks if block["id"] == "poll_2")["props"]["question"] == "你会买吗？"
    assert result["main_messages"][0].content == "已在当前正文后补一个投票"


@pytest.mark.asyncio
async def test_note_editor_node_backfills_visible_copy_when_plan_patch_is_empty(monkeypatch):
    class FakePlanRunner:
        async def ainvoke(self, prompt):
            assert "只能编辑 block_id=poll_1 这个区块" in prompt
            return LocalNoteEditOutput(
                block_id="poll_1",
                action="update_block",
                reason="按用户要求完成局部编辑",
                content_brief="更毒舌的投票",
                payload_patch={},
                style_patch={},
            )

    class FakeRewriteRunner:
        async def ainvoke(self, prompt):
            assert "必须把变化写进 payload_patch" in prompt
            return LocalTextRewriteOutput(
                reason="已补全投票文案",
                payload_patch={
                    "question": "这波你还敢买吗？",
                    "option_a": "继续冲",
                    "option_b": "直接避雷",
                },
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            if schema is LocalNoteEditOutput:
                return FakePlanRunner()
            if schema is LocalTextRewriteOutput:
                return FakeRewriteRunner()
            raise AssertionError(f"unexpected schema: {schema}")

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把这个投票改得更毒舌一点"})()],
        "document_view": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
            "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
        },
        "block_style_map": {
            "poll_1": {"css_classes": "old-poll", "inline_styles": {}},
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    blocks = {block["id"]: block for block in result["note_document"]["blocks"]}
    assert blocks["poll_1"]["props"]["question"] == "这波你还敢买吗？"
    assert blocks["poll_1"]["props"]["option_a"] == "继续冲"
    assert blocks["poll_1"]["props"]["option_b"] == "直接避雷"
    assert blocks["story_1"]["props"]["paragraphs"] == ["原正文"]


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_global_edit_path(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "保留标题，重写第二段" in prompt
            return GlobalCanvasEditOutput(
                action="rewrite_paragraph",
                reason="已按要求重写第二段",
                block_id="story_1",
                paragraph_index=1,
                paragraph_text="这是更尖锐的新第二段",
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "保留标题，重写第二段"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段", "第三段"]},
        },
        "block_style_map": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    story_block = next(block for block in result["note_document"]["blocks"] if block["id"] == "story_1")
    assert result["note_document"]["document_meta"]["title"] == "原标题"
    assert story_block["props"]["paragraphs"] == ["第一段", "这是更尖锐的新第二段", "第三段"]
    assert story_block["style"]["css_classes"] == "old-story"
    assert result["main_messages"][0].content == "已按要求重写第二段"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_global_append_path(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "新增一个区块" in prompt or "新增一个区块" not in prompt
            return GlobalCanvasEditOutput(
                action="append_block",
                reason="已补一个互动投票",
                new_component_type="投票",
                content_brief="互动站队",
                payload_patch={"question": "你会买吗？", "option_a": "会", "option_b": "不会"},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "再加一个投票区块"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {"story_1": {"css_classes": "story", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    blocks = result["note_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["StoryText", "PollBlock"]
    poll_block = next(block for block in blocks if block["id"] == "poll_2")
    assert poll_block["props"]["type"] == "PollBlock"
    assert poll_block["props"]["question"] == "你会买吗？"
    assert result["main_messages"][0].content == "已补一个互动投票"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_global_append_path_with_semantic_anchor(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "在互动那块后面补一个参数卡" in prompt
            return GlobalCanvasEditOutput(
                action="append_block",
                reason="已在互动那块后补一个参数卡",
                new_component_type="参数卡",
                content_brief="参数证据",
                payload_patch={"core_features": ["麒麟芯片", "卫星通信"]},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "在互动那块后面补一个参数卡"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "title_1": {"type": "TitleBlock", "title": "原标题"},
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {
            "title_1": {"css_classes": "title", "inline_styles": {}},
            "poll_1": {"css_classes": "poll", "inline_styles": {}},
            "story_1": {"css_classes": "story", "inline_styles": {}},
        },
        "note_document": {
            "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "title_1",
                    "type": "TitleBlock",
                    "semantic_role": "heading",
                    "content_brief": "标题",
                    "editable_targets": ["title"],
                    "props": {"type": "TitleBlock", "title": "原标题"},
                    "style": {},
                },
                {
                    "id": "poll_1",
                    "type": "PollBlock",
                    "semantic_role": "interactive_opinion",
                    "content_brief": "互动",
                    "editable_targets": ["question", "option_a", "option_b"],
                    "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                    "style": {},
                },
                {
                    "id": "story_1",
                    "type": "StoryText",
                    "semantic_role": "narrative_text",
                    "content_brief": "正文",
                    "editable_targets": ["paragraphs"],
                    "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                    "style": {},
                },
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
        },
        "planner_policy": {
            "layout_policy": {"preferred_block_intents": ["interactive_opinion", "evidence_summary", "narrative_text"]}
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["agent_backends"]["note_editor"] == "structured_function_calling"
    blocks = result["note_document"]["blocks"]
    assert [block["type"] for block in blocks] == ["TitleBlock", "PollBlock", "ProductSpecCard", "StoryText"]
    assert next(block for block in blocks if block["id"] == "spec_4")["props"]["type"] == "ProductSpecCard"
    assert result["main_messages"][0].content == "已在互动那块后补一个参数卡"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_global_move_path_with_semantic_anchor(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "把互动那块放到标题后面" in prompt
            return GlobalCanvasEditOutput(
                action="move_block",
                reason="已把互动那块放到标题后面",
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把互动那块放到标题后面"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "互动"},
                {"id": "title_1", "component_type": "TitleBlock", "content_brief": "标题"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
            "title_1": {"type": "TitleBlock", "title": "原标题"},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {
            "poll_1": {"css_classes": "poll", "inline_styles": {}},
            "title_1": {"css_classes": "title", "inline_styles": {}},
            "story_1": {"css_classes": "story", "inline_styles": {}},
        },
        "note_document": {
            "document_meta": {"title": "原标题", "scenarios": ["seeding"]},
            "theme": {"page_theme": {}, "global_vars": {}},
            "blocks": [
                {
                    "id": "poll_1",
                    "type": "PollBlock",
                    "semantic_role": "interactive_opinion",
                    "content_brief": "互动",
                    "editable_targets": ["question", "option_a", "option_b"],
                    "props": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
                    "style": {},
                },
                {
                    "id": "title_1",
                    "type": "TitleBlock",
                    "semantic_role": "heading",
                    "content_brief": "标题",
                    "editable_targets": ["title"],
                    "props": {"type": "TitleBlock", "title": "原标题"},
                    "style": {},
                },
                {
                    "id": "story_1",
                    "type": "StoryText",
                    "semantic_role": "narrative_text",
                    "content_brief": "正文",
                    "editable_targets": ["paragraphs"],
                    "props": {"type": "StoryText", "paragraphs": ["第一段"]},
                    "style": {},
                },
            ],
            "assets": [],
            "fact_bindings": [],
            "provenance": {},
            "ui_state": {},
        },
        "planner_policy": {
            "layout_policy": {"preferred_block_intents": ["interactive_opinion", "heading", "narrative_text"]}
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["agent_backends"]["note_editor"] == "structured_function_calling"
    assert [block["id"] for block in result["note_document"]["blocks"]] == ["title_1", "poll_1", "story_1"]
    assert result["main_messages"][0].content == "已把互动那块放到标题后面"


@pytest.mark.asyncio
async def test_note_editor_node_uses_structured_global_path_for_generic_edit_copy(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "整体再打磨一下" in prompt
            return GlobalCanvasEditOutput(
                action="update_block",
                reason="已整体收敛当前正文表达",
                block_id="story_1",
                payload_patch={"paragraphs": ["更收敛的新正文"]},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "整体再打磨一下"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
        },
        "block_style_map": {"story_1": {"css_classes": "story", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert result["agent_backends"]["note_editor"] == "structured_function_calling"
    assert next(block for block in result["note_document"]["blocks"] if block["id"] == "story_1")["props"]["paragraphs"] == ["更收敛的新正文"]
    assert result["main_messages"][0].content == "已整体收敛当前正文表达"


@pytest.mark.asyncio
async def test_note_editor_node_supports_structured_page_theme_edit(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "如果用户要改整体视觉主题" in prompt
            return GlobalCanvasEditOutput(
                action="update_page_theme",
                reason="已切换成灰蓝主题",
                page_theme_patch={"--bg-color": "#e2e8f0", "--primary-vibe": "#0f172a"},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把整体页面改成更克制的灰蓝风格"})()],
        "document_view": {
            "page_title": "原标题",
            "page_theme": {"--bg-color": "#ffffff"},
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "block_style_map": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    theme = result["note_document"]["theme"]["page_theme"]
    assert theme["--bg-color"] == "#e2e8f0"
    assert theme["--primary-vibe"] == "#0f172a"
    assert next(block for block in result["note_document"]["blocks"] if block["id"] == "story_1")["props"]["paragraphs"] == ["第一段", "第二段"]


@pytest.mark.asyncio
async def test_note_editor_node_backfills_page_theme_when_model_returns_empty_patch(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "如果用户要改整体视觉主题" in prompt
            return GlobalCanvasEditOutput(
                action="update_page_theme",
                reason="已切换风格",
                page_theme_patch={},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把整体页面改成更克制的灰蓝风格"})()],
        "document_view": {
            "page_title": "原标题",
            "page_theme": {"--bg-color": "#ffffff"},
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "block_style_map": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "planner_policy": {"theme_policy": {"preset": "travel_clean"}},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    theme = result["note_document"]["theme"]["page_theme"]
    assert theme["--bg-color"] == "#e2e8f0"
    assert theme["--primary-vibe"] == "#475569"
    assert next(block for block in result["note_document"]["blocks"] if block["id"] == "story_1")["props"]["paragraphs"] == ["第一段", "第二段"]


@pytest.mark.asyncio
async def test_note_editor_node_replaces_block_by_query_hint_when_model_omits_block_id(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "把投票换成雷达图" in prompt
            return GlobalCanvasEditOutput(
                action="replace_block",
                reason="已按要求替换组件",
                new_component_type="雷达图",
                payload_patch={"dimensions": ["性能", "影像"], "scores": [88, 92]},
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "把投票换成雷达图"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {"poll_1": {"css_classes": "poll", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "planner_policy": {"theme_policy": {"preset": "seeding_hot"}},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    blocks = result["note_document"]["blocks"]
    assert blocks[0]["type"] == "RadarChartBlock"
    assert next(block for block in blocks if block["id"] == "poll_1")["props"]["type"] == "RadarChartBlock"
    assert next(block for block in blocks if block["id"] == "story_1")["props"]["paragraphs"] == ["第一段"]


@pytest.mark.asyncio
async def test_note_editor_node_removes_block_by_query_hint_when_model_omits_block_id(monkeypatch):
    class FakeGlobalRunner:
        async def ainvoke(self, prompt):
            assert "删掉参数卡" in prompt
            return GlobalCanvasEditOutput(
                action="remove_block",
                reason="已删除参数卡",
            )

    class FakeLLM:
        def with_structured_output(self, schema, method="function_calling"):
            assert schema is GlobalCanvasEditOutput
            assert method == "function_calling"
            return FakeGlobalRunner()

    monkeypatch.setattr("app.agents.nodes.note_editor_node.create_llm", lambda **kwargs: FakeLLM())

    state = {
        "main_messages": [type("Msg", (), {"content": "删掉参数卡"})()],
        "document_view": {
            "page_title": "原标题",
            "blocks": [
                {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "spec_1": {"type": "ProductSpecCard", "core_features": ["麒麟芯片", "66W 快充"]},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "block_style_map": {"spec_1": {"css_classes": "spec", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "planner_policy": {"theme_policy": {"preset": "seeding_hot"}},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    blocks = result["note_document"]["blocks"]
    assert [block["id"] for block in blocks] == ["story_1"]
    assert all(block["id"] != "spec_1" for block in blocks)


def test_has_global_edit_request_uses_manifest_aliases_and_paragraph_cues():
    document_view = {
        "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}]
    }

    assert _has_global_edit_request("把参数卡改得更克制一点", document_view) is True
    assert _has_global_edit_request("重写第2段", document_view) is True
    assert _has_global_edit_request("把投票换成雷达图", document_view) is True
    assert _has_global_edit_request("你好", document_view) is False
