import pytest

from app.api.chat import _build_turn_end_payload
from app.agents.graph import route_intent
from app.agents.nodes.note_editor_node import (
    GlobalCanvasEditOutput,
    LocalNoteEditOutput,
    LocalTextRewriteOutput,
    _apply_global_edit_plan,
    _build_global_edit_prompt,
    _apply_local_edit_plan,
    _build_local_edit_prompt,
    _build_theme_patch_fallback,
    _build_tone_rewrite_fallback,
    _extract_rewritable_payload_fields,
    _infer_replacement_component_type,
    _infer_target_component_type,
    _maybe_backfill_local_payload_patch,
    _build_note_editor_prompt,
    _resolve_global_target_id,
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
        "data_dsl": {
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
        "data_dsl": {
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ]
        },
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


@pytest.mark.asyncio
async def test_verify_note_fills_required_poll_fields():
    state = {
        "main_messages": [],
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "image_assets": [],
        "data_dsl": {
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
    payload = result["data_dsl"]["poll_1"]
    assert result["data_dsl"]["page_title"] == "XHS-Forge Note"
    assert payload["question"]
    assert payload["option_a"]
    assert payload["option_b"]


def test_turn_end_payload_keeps_snake_and_camel_case_fields():
    payload = _build_turn_end_payload(
        "ckpt_123",
        oss_url="https://example.com/page",
        image_assets=[{"url": "https://img.example/a.jpg", "desc": "hero"}],
        page_data={"page_title": "Mate 60", "blocks": []},
        style_data={"global_vars": {"--bg-color": "#fff"}},
        source_code="<html></html>",
        node_prompts={"intent_agent": "prompt"},
    )

    assert payload["checkpoint_id"] == "ckpt_123"
    assert payload["checkpointId"] == "ckpt_123"
    assert payload["page_data"]["page_title"] == "Mate 60"
    assert payload["pageData"]["page_title"] == "Mate 60"
    assert payload["noteData"]["page_title"] == "Mate 60"
    assert payload["source_code"] == "<html></html>"
    assert payload["htmlPreview"] == "<html></html>"
    assert payload["node_prompts"]["intent_agent"] == "prompt"
    assert payload["nodePrompts"]["intent_agent"] == "prompt"


def test_note_editor_prompt_reflects_current_canvas_and_selection():
    state = {
        "data_dsl": {
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

    summary = _summarize_blocks(state["data_dsl"])
    prompt = _build_note_editor_prompt(state)

    assert "story_1" in summary
    assert "poll_1" in summary
    assert "当前区块数: 2" in prompt
    assert "当前选中组件: poll_1" in prompt
    assert "模式: 局部选中编辑" in prompt
    assert "replace_note_block" in prompt
    assert "move_note_block" in prompt
    assert '"question": "买吗？"' in prompt
    assert "直接开始编辑，不要停留在重复诊断" in prompt
    assert "默认只允许改动选中的那个区块" in prompt
    assert "【事实可信度约束】" in prompt
    assert "电池容量: 5000mAh" in prompt


def test_local_edit_prompt_includes_target_payload_and_style():
    state = {
        "data_dsl": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
        },
        "style_dsl": {
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
        "data_dsl": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "style_dsl": {
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
        "data_dsl": {
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

    update = command.update["data_dsl"]
    assert update["_blocks_override"] is True
    assert [block["id"] for block in update["blocks"]] == ["c", "a", "b"]


def test_replace_note_block_swaps_component_type_and_payload():
    state = {
        "data_dsl": {
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

    update = command.update["data_dsl"]
    assert update["_block_update"]["id"] == "poll_1"
    assert update["_block_update"]["data"]["component_type"] == "RadarChartBlock"
    assert update["poll_1"]["type"] == "RadarChartBlock"
    assert update["poll_1"]["dimensions"] == ["性能", "影像"]


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
        "把整体页面改成更克制的灰蓝风格",
        {"visual_vibe": "minimalist"},
    )

    assert patch["--bg-color"] == "#e2e8f0"
    assert patch["--primary-vibe"] == "#475569"
    assert patch["--border-color"] == "#cbd5e1"


def test_infer_replacement_component_type_prefers_target_after_replace_phrase():
    assert _infer_replacement_component_type("把投票换成雷达图") == "RadarChartBlock"


def test_infer_target_component_type_prefers_source_component_for_replace():
    assert _infer_target_component_type("把投票换成雷达图", "replace_block", "RadarChartBlock") == "PollBlock"
    assert _infer_target_component_type("删掉参数卡", "remove_block") == "ProductSpecCard"


def test_resolve_global_target_id_uses_query_component_hints():
    data_dsl = {
        "blocks": [
            {"id": "vs_1", "component_type": "VersusCard", "content_brief": "对比"},
            {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数"},
            {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
        ]
    }

    replace_plan = GlobalCanvasEditOutput(action="replace_block", new_component_type="RadarChartBlock")
    remove_plan = GlobalCanvasEditOutput(action="remove_block")

    assert _resolve_global_target_id(replace_plan, data_dsl, "把投票换成雷达图") == "poll_1"
    assert _resolve_global_target_id(remove_plan, data_dsl, "删掉参数卡") == "spec_1"


def test_resolve_global_target_id_overrides_wrong_explicit_block_when_query_mentions_text():
    data_dsl = {
        "blocks": [
            {"id": "cover_1", "component_type": "CoverSwiper", "content_brief": "封面"},
            {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
        ]
    }

    plan = GlobalCanvasEditOutput(action="update_block", block_id="cover_1")

    assert _resolve_global_target_id(plan, data_dsl, "修改文本内容") == "story_1"


@pytest.mark.asyncio
async def test_style_agent_respects_page_theme_over_vibe_defaults():
    result = await style_agent(
        {
            "data_dsl": {
                "page_theme": {"--bg-color": "#e2e8f0", "--primary-vibe": "#0f172a"},
                "blocks": [{"id": "story_1", "component_type": "StoryText", "content_brief": "正文"}],
            },
            "intent_result": {"visual_vibe": "minimalist", "intensity_level": 0.0},
        }
    )

    assert result["style_dsl"]["global_vars"]["--bg-color"] == "#e2e8f0"
    assert result["style_dsl"]["global_vars"]["--primary-vibe"] == "#0f172a"


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
        "data_dsl": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
            "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
        },
        "style_dsl": {
            "poll_1": {"css_classes": "old-poll", "inline_styles": {}},
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["poll_1"]["question"] == "你还会继续买吗？"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["原正文"]
    assert result["style_dsl"]["poll_1"]["css_classes"] == "updated-poll"
    assert result["style_dsl"]["story_1"]["css_classes"] == "old-story"
    assert result["main_messages"][0].content == "已按要求修改选中投票"


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
        "data_dsl": {
            "page_title": "Mate 60 页面",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["原正文"]},
            "poll_1": {"type": "PollBlock", "question": "原问题", "option_a": "A", "option_b": "B"},
        },
        "style_dsl": {
            "poll_1": {"css_classes": "old-poll", "inline_styles": {}},
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "poll_1",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": True,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["poll_1"]["question"] == "这波你还敢买吗？"
    assert result["data_dsl"]["poll_1"]["option_a"] == "继续冲"
    assert result["data_dsl"]["poll_1"]["option_b"] == "直接避雷"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["原正文"]


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
        "data_dsl": {
            "page_title": "原标题",
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段", "第三段"]},
        },
        "style_dsl": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["page_title"] == "原标题"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["第一段", "这是更尖锐的新第二段", "第三段"]
    assert result["style_dsl"]["story_1"]["css_classes"] == "old-story"
    assert result["main_messages"][0].content == "已按要求重写第二段"


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
        "data_dsl": {
            "page_title": "原标题",
            "page_theme": {"--bg-color": "#ffffff"},
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "style_dsl": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["page_theme"]["--bg-color"] == "#e2e8f0"
    assert result["data_dsl"]["page_theme"]["--primary-vibe"] == "#0f172a"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["第一段", "第二段"]


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
        "data_dsl": {
            "page_title": "原标题",
            "page_theme": {"--bg-color": "#ffffff"},
            "blocks": [
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "story_1": {"type": "StoryText", "paragraphs": ["第一段", "第二段"]},
        },
        "style_dsl": {
            "story_1": {"css_classes": "old-story", "inline_styles": {}},
        },
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "intent_result": {"visual_vibe": "minimalist"},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["page_theme"]["--bg-color"] == "#e2e8f0"
    assert result["data_dsl"]["page_theme"]["--primary-vibe"] == "#475569"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["第一段", "第二段"]


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
        "data_dsl": {
            "page_title": "原标题",
            "blocks": [
                {"id": "poll_1", "component_type": "PollBlock", "content_brief": "投票"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "poll_1": {"type": "PollBlock", "question": "买吗？", "option_a": "买", "option_b": "不买"},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "style_dsl": {"poll_1": {"css_classes": "poll", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "intent_result": {"visual_vibe": "general"},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert result["data_dsl"]["blocks"][0]["component_type"] == "RadarChartBlock"
    assert result["data_dsl"]["poll_1"]["type"] == "RadarChartBlock"
    assert result["data_dsl"]["story_1"]["paragraphs"] == ["第一段"]


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
        "data_dsl": {
            "page_title": "原标题",
            "blocks": [
                {"id": "spec_1", "component_type": "ProductSpecCard", "content_brief": "参数"},
                {"id": "story_1", "component_type": "StoryText", "content_brief": "正文"},
            ],
            "spec_1": {"type": "ProductSpecCard", "core_features": ["麒麟芯片", "66W 快充"]},
            "story_1": {"type": "StoryText", "paragraphs": ["第一段"]},
        },
        "style_dsl": {"spec_1": {"css_classes": "spec", "inline_styles": {}}},
        "selected_element_id": "无 (全局修改)",
        "retrieved_knowledge": {"entity_name": "华为 Mate 60"},
        "creator_persona": "硬核数码博主",
        "intent_result": {"visual_vibe": "general"},
        "has_controversy": False,
    }

    result = await note_editor_node(state)

    assert [block["id"] for block in result["data_dsl"]["blocks"]] == ["story_1"]
    assert "spec_1" not in result["data_dsl"]
