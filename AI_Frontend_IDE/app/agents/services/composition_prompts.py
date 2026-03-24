"""Prompt/context builders for the composition service.

Keeping prompt assembly here helps `composition_service.py` stay focused on the
execution pipeline instead of carrying long prompt templates inline.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing import Annotated, NotRequired, TypedDict

from app.agents.utils.fact_utils import build_fact_grounding_context
from app.core.context_engineering import (
    build_asset_summary,
    build_document_summary,
    build_fact_summary,
    build_policy_summary,
    build_retrieval_evidence_slice,
    build_selection_context,
)
from app.core.prompt_engineering import build_prompt_snapshot
from app.core.component_manifest import filter_payload_for_component, resolve_component_for_block_intent
from app.core.note_document import build_note_document, build_note_document_editing_context, build_note_document_from_state
from app.agents.services.component_builder import build_component_fallback, enforce_component_contract
from app.agents.services.composition_support import (
    _build_component_contract_text,
    _infer_replacement_component_type,
    _infer_target_component_type,
    _normalize_component_type_name,
    _summarize_blocks,
    _summarize_note_document_blocks,
)
from app.core.query_heuristics import wants_before_position, wants_image_search


class CompositionPromptState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: NotRequired[int]
    note_document: dict[str, Any]
    retrieved_knowledge: Any
    selected_element_id: str | None
    has_controversy: bool
    creator_persona: str | None
    planner_output: dict[str, Any]
    planner_policy: dict[str, Any]
    active_archetype: str | None
    scenarios: list[str]
    image_assets: list[dict[str, Any]]
    patch_tracks: dict[str, Any]
    active_panel: str | None


def build_composition_prompt_snapshot(mode: str, prompt_text: str, plan: Any | None = None) -> dict[str, Any]:
    plan_payload = {}
    if plan is not None:
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump(exclude_none=True)
        elif isinstance(plan, dict):
            plan_payload = plan
    return build_prompt_snapshot(
        "composition_worker",
        system_prompt=f"Structured composition_worker ({mode}) prompt. 优先走 NoteDocument + component_manifest + planner_policy，不直接依赖开放式 fallback。",
        user_prompt=prompt_text,
        assistant_payload=plan_payload or None,
    )


def build_next_note_document_from_execution(
    state: dict[str, Any],
    updated_document_view: dict[str, Any],
    updated_block_style_map: dict[str, Any],
) -> dict[str, Any]:
    return build_note_document(
        document_view=updated_document_view,
        block_style_map=updated_block_style_map,
        image_assets=state.get("image_assets"),
        patch_tracks=state.get("patch_tracks"),
        selected_element_id=state.get("selected_element_id"),
        active_panel=state.get("active_panel"),
        scenarios=state.get("scenarios"),
        active_archetype=state.get("active_archetype"),
        retrieved_knowledge=state.get("retrieved_knowledge"),
        planner_output=state.get("planner_output"),
    )


def build_composition_prompt(state: CompositionPromptState) -> str:
    _note_document, document_view, block_style_map, image_assets = build_note_document_editing_context(state)
    knowledge = state.get("retrieved_knowledge", {}) or {}
    selected_element_id = state.get("selected_element_id")
    creator_persona = state.get("creator_persona", "硬核数码博主")
    has_controversy = state.get("has_controversy", False)
    current_blocks = document_view.get("blocks", [])
    local_mode = selected_element_id not in [None, "", "无", "无 (全局修改)", "none"]

    component_contract_text = _build_component_contract_text()
    fact_grounding = build_fact_grounding_context(knowledge)
    planner_policy = state.get("planner_policy", {}) or {}
    note_document = build_note_document_from_state(state)
    document_summary = build_document_summary(note_document)
    selection_context = build_selection_context(
        note_document=note_document,
        document_view=document_view,
        block_style_map=block_style_map,
        selected_element_id=selected_element_id,
    )
    policy_summary = build_policy_summary(planner_policy)
    fact_summary = build_fact_summary(knowledge, image_assets)
    evidence_slice = build_retrieval_evidence_slice(
        knowledge,
        semantic_role=selection_context.get("semantic_role") if selection_context else None,
        limit=4,
    )
    asset_summary = build_asset_summary(image_assets, limit=4)

    return f"""你是 XHS-Forge 的数码购买决策 Composition Agent。
你的职责不是走流水线，而是像真正的编辑器一样，直接把用户自然语言改成一张可渲染的笔记。

【最高目标】
通过工具直接编辑 Note DSL，完成“创建笔记”或“修改笔记”。

【当前工作模式】
- 模式: {"局部选中编辑" if local_mode else "整页编辑"}

【document_summary】
{json.dumps(document_summary, ensure_ascii=False, indent=2)}

【selection_context】
{json.dumps(selection_context, ensure_ascii=False, separators=(", ", ": ")) if selection_context else "无"}

【当前画布状态】
- 页面标题: {document_view.get("page_title") or "未设置"}
- 当前区块数: {len(current_blocks)}
- 当前选中组件: {selected_element_id or "无"}
- 当前创作者人设: {creator_persona}

【当前区块清单】
{_summarize_blocks(document_view)}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【fact_summary】
{json.dumps(fact_summary, ensure_ascii=False, indent=2)}

【evidence_slice】
{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}

【asset_summary】
{json.dumps(asset_summary, ensure_ascii=False, indent=2)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【policy_summary】
{json.dumps(policy_summary, ensure_ascii=False, indent=2)}

【组件白名单与必填字段】
{component_contract_text}

【编辑铁律】
1. 所有页面修改必须通过工具完成，严禁空想最终 JSON。
2. 当前 prompt 已经提供了页面标题、区块清单、选中区块数据和事实知识，直接开始编辑，不要停留在重复诊断。
3. 如果页面为空，创建 4-6 个高完成度区块。
4. 如果页面不为空，优先更新现有区块；只有在用户明确要求新增，或者现有区块明显不够时，才创建新区块。
5. 如果用户选中了某个组件，优先修改该组件，不要擅自改整页。
6. 如果用户要求“替换组件类型”，优先使用 replace_note_block；如果用户要求调整顺序，使用 move_note_block。
7. 如果 battle_report 存在，优先创建或保留 VersusCard。
8. 如果 has_controversy = {str(has_controversy).lower()}，优先创建或保留 PollBlock。
9. 每个区块必须满足其必填字段，否则不能结束。
10. 除非用户明确要求，不要无意义地删除已有可用内容。
11. 同一个区块不要重复修改两次以上；如果已经达到用户要求，立即调用 finish_layout 结束。
12. 如果当前是局部选中编辑模式，默认只允许改动选中的那个区块；除非用户明确要求，不要新增区块、不要重写整页、不要修改其他区块。
13. 若“已确认事实”存在，正文、参数卡、对比结论都优先沿用这些值。
14. 若某个参数仍冲突且未确认，不要把它写成绝对参数。
"""


def build_local_edit_prompt(state: CompositionPromptState, user_query: str) -> str:
    _note_document, document_view, block_style_map, image_assets = build_note_document_editing_context(state)
    selected_element_id = state.get("selected_element_id")
    knowledge = state.get("retrieved_knowledge", {}) or {}
    target_block = next(
        (block for block in document_view.get("blocks", []) if block.get("id") == selected_element_id),
        None,
    )
    target_payload = document_view.get(selected_element_id, {}) if selected_element_id else {}
    target_style = block_style_map.get(selected_element_id, {}) if selected_element_id else {}
    component_contract_text = _build_component_contract_text()
    fact_grounding = build_fact_grounding_context(knowledge)
    planner_policy = state.get("planner_policy", {}) or {}
    note_document = build_note_document_from_state(state)
    selection_context = build_selection_context(
        note_document=note_document,
        document_view=document_view,
        block_style_map=block_style_map,
        selected_element_id=selected_element_id,
    )
    document_summary = build_document_summary(note_document)
    policy_summary = build_policy_summary(planner_policy)
    fact_summary = build_fact_summary(knowledge, image_assets)
    evidence_slice = build_retrieval_evidence_slice(
        knowledge,
        semantic_role=selection_context.get("semantic_role") if selection_context else None,
        limit=4,
    )

    return f"""你是 XHS-Forge 的局部笔记编辑器。
你的任务不是重写整页，而是只围绕当前选中区块输出一个结构化补丁计划。

【用户指令】
{user_query}

【当前选中区块】
{json.dumps(target_block or {}, ensure_ascii=False)}

【selection_context】
{json.dumps(selection_context, ensure_ascii=False, indent=2)}

【当前选中区块数据】
{json.dumps(target_payload, ensure_ascii=False)}

【当前选中区块样式】
{json.dumps(target_style, ensure_ascii=False)}

【document_summary】
{json.dumps(document_summary, ensure_ascii=False, indent=2)}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【fact_summary】
{json.dumps(fact_summary, ensure_ascii=False, indent=2)}

【evidence_slice】
{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【policy_summary】
{json.dumps(policy_summary, ensure_ascii=False, indent=2)}

【组件白名单与必填字段】
{component_contract_text}

【输出规则】
1. 只能编辑 block_id={selected_element_id} 这个区块。
2. 如果只是改文案或样式，优先使用 action=update_block 或 action=noop，不要删除区块。
3. 如果用户明确要求“换成另一种组件”，使用 action=replace_block，并提供 new_component_type 与 payload_patch。
4. 如果用户明确要求调整顺序，使用 action=move_block，并填写 move_to_index。
5. 如果用户明确要求删除当前区块，才允许 action=remove_block。
6. payload_patch 只写需要变动的字段；style_patch 只写 css_classes 或 inline_styles。
7. 如果用户明确要求“在这个前面/后面新增一个区块”，允许使用 action=append_block，并提供 new_component_type、content_brief 和 payload_patch。默认把新区块插在当前选中区块后面。
8. 除非用户明确要求，否则不要输出任何其他区块的信息，不要修改页面标题，不要新增新区块。
9. 如果用户指令不够明确，保持 action=noop，并给出最小 style_patch 或空补丁。
10. 若“已确认事实”存在，payload_patch 必须优先沿用这些值。
"""


def default_canvas_block_intents(state: dict[str, Any]) -> list[dict[str, Any]]:
    planner_output = state.get("planner_output") or {}
    block_intents = list(planner_output.get("block_intents") or [])
    if block_intents:
        return block_intents

    knowledge = state.get("retrieved_knowledge") or {}
    scenario_scores = (state.get("scenario_scores") or planner_output.get("scenario_scores") or {})
    user_query = str(getattr((state.get("main_messages") or [])[-1], "content", "") or "") if state.get("main_messages") else ""
    has_images = bool(state.get("image_assets"))
    intents: list[dict[str, Any]] = [
        {"intent_type": "heading", "goal": "页面标题", "preferred_component": "TitleBlock", "required": True},
        {"intent_type": "narrative_text", "goal": "正文叙事", "preferred_component": "StoryText", "required": True},
    ]
    if has_images or wants_image_search(user_query):
        intents.insert(
            0,
            {
                "intent_type": "hero_media",
                "goal": "封面视觉",
                "preferred_component": resolve_component_for_block_intent(
                    "hero_media",
                    has_images=has_images,
                    scenario_scores=scenario_scores,
                ),
                "required": False,
            },
        )
    if knowledge.get("core_attributes") or knowledge.get("confirmed_facts"):
        intents.append(
            {
                "intent_type": "evidence_summary",
                "goal": "关键参数证据",
                "preferred_component": resolve_component_for_block_intent(
                    "evidence_summary",
                    has_images=has_images,
                    scenario_scores=scenario_scores,
                ),
                "required": False,
            }
        )
    if state.get("has_controversy"):
        intents.append(
            {
                "intent_type": "interactive_opinion",
                "goal": "互动站队",
                "preferred_component": "PollBlock",
                "required": False,
            }
        )
    return intents


def build_canvas_creation_prompt(state: CompositionPromptState, user_query: str) -> str:
    knowledge = state.get("retrieved_knowledge", {}) or {}
    planner_output = state.get("planner_output", {}) or {}
    planner_policy = state.get("planner_policy", {}) or {}
    block_intents = default_canvas_block_intents(state)
    component_contract_text = _build_component_contract_text()
    fact_grounding = build_fact_grounding_context(knowledge)
    scenarios = state.get("scenarios") or [state.get("active_archetype") or "seeding"]
    policy_summary = build_policy_summary(planner_policy)
    fact_summary = build_fact_summary(knowledge, state.get("image_assets") or [])
    evidence_slice = build_retrieval_evidence_slice(knowledge, semantic_role="narrative_text", limit=4)

    return f"""你是 XHS-Forge 的首版画布规划编辑器。
当前页面为空，你的任务是直接输出一份结构化的首版笔记创建计划，而不是进入自由工具循环。

【用户指令】
{user_query}

【场景信息】
- active_archetype: {state.get('active_archetype') or 'seeding'}
- scenarios: {json.dumps(scenarios, ensure_ascii=False)}

【Planner 输出】
{json.dumps(planner_output, ensure_ascii=False)}

【policy_summary】
{json.dumps(policy_summary, ensure_ascii=False, indent=2)}

【推荐 block intents】
{json.dumps(block_intents, ensure_ascii=False)}

【fact_summary】
{json.dumps(fact_summary, ensure_ascii=False, indent=2)}

【evidence_slice】
{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}

【事实可信度约束】
{fact_grounding or '暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。'}

【组件白名单与必填字段】
{component_contract_text}

【输出规则】
1. 直接创建 4-6 个高完成度区块，优先覆盖标题、正文，再补封面/证据/互动/对比等。
2. blocks 中的 component_type 必须来自白名单，且尽量贴合推荐 block intents。
3. payload 只写该组件的可见核心字段；复杂字段缺省可留给 verifier 补全，但不要留空必填字段。
4. 若存在已确认事实，参数卡、正文、对比块应优先沿用；若存在未确认冲突，采用保守表达。
5. page_title 要可直接用于页面标题，避免输出空值。
6. blocks 顺序应符合用户要求和 Planner 策略，不要输出额外解释。"""


def guess_block_prefix(component_type: str) -> str:
    mapping = {
        "TitleBlock": "title",
        "StoryText": "story",
        "CoverSwiper": "cover",
        "ProductSpecCard": "spec",
        "RadarChartBlock": "radar",
        "VersusCard": "versus",
        "PollBlock": "poll",
        "LocationBlock": "location",
        "WeatherPolaroid": "weather",
        "QuoteBlock": "quote",
        "TimelineBlock": "timeline",
    }
    return mapping.get(component_type, component_type.replace("Block", "").replace("Card", "").lower() or "block")


def build_canvas_creation_fallback(
    state: dict[str, Any],
    user_query: str,
    canvas_creation_output_cls: Callable[..., Any],
):
    block_intents = default_canvas_block_intents(state)
    knowledge = state.get("retrieved_knowledge") or {}
    image_assets = state.get("image_assets") or []
    entity_name = str(knowledge.get("entity_name") or user_query or "这篇笔记").strip()
    blocks = []
    scenario_scores = (state.get("scenario_scores") or (state.get("planner_output") or {}).get("scenario_scores") or {})
    block_output_cls = canvas_creation_output_cls.__annotations__.get("blocks")
    for intent in block_intents[:6]:
        component_type = _normalize_component_type_name(
            intent.get("preferred_component")
            or resolve_component_for_block_intent(
                intent.get("intent_type") or "narrative_text",
                has_images=bool(image_assets),
                scenario_scores=scenario_scores,
            )
        ) or "StoryText"
        content_brief = str(intent.get("goal") or intent.get("intent_type") or component_type).replace("_", " ").strip()
        fallback_payload = build_component_fallback(
            comp_type=component_type,
            comp_id=f"{guess_block_prefix(component_type)}_fallback",
            content_brief=content_brief,
            user_query=user_query,
            retrieved_knowledge=knowledge,
            image_assets=image_assets,
        )
        payload = enforce_component_contract(
            component_type,
            filter_payload_for_component(component_type, fallback_payload),
            fallback_payload,
        )
        blocks.append({
            "component_type": component_type,
            "content_brief": content_brief,
            "payload": payload,
            "intent_type": intent.get("intent_type"),
        })

    if not any(block["component_type"] == "TitleBlock" for block in blocks):
        blocks.insert(0, {
            "component_type": "TitleBlock",
            "content_brief": "页面标题",
            "payload": {"type": "TitleBlock", "title": entity_name},
            "intent_type": "heading",
        })
    if not any(block["component_type"] == "StoryText" for block in blocks):
        fallback_payload = build_component_fallback("StoryText", "story_fallback", "正文叙事", user_query, knowledge, image_assets)
        payload = enforce_component_contract("StoryText", filter_payload_for_component("StoryText", fallback_payload), fallback_payload)
        insert_index = 1 if blocks and blocks[0]["component_type"] == "TitleBlock" else 0
        blocks.insert(insert_index, {
            "component_type": "StoryText",
            "content_brief": "正文叙事",
            "payload": payload,
            "intent_type": "narrative_text",
        })

    return canvas_creation_output_cls(
        reason="已根据 Planner 策略生成首版画布",
        page_title=f"{entity_name} 深度笔记",
        blocks=blocks[:6],
    )


def build_global_edit_prompt(state: CompositionPromptState, user_query: str) -> str:
    _note_document, document_view, block_style_map, image_assets = build_note_document_editing_context(state)
    knowledge = state.get("retrieved_knowledge", {}) or {}
    component_contract_text = _build_component_contract_text()
    blocks = document_view.get("blocks", [])
    block_payloads = {
        block.get("id"): document_view.get(block.get("id"), {})
        for block in blocks
        if block.get("id")
    }
    block_style_map = {
        block.get("id"): block_style_map.get(block.get("id"), {})
        for block in blocks
        if block.get("id")
    }
    fact_grounding = build_fact_grounding_context(knowledge)
    planner_policy = state.get("planner_policy", {}) or {}
    note_document = build_note_document_from_state(state)
    document_summary = build_document_summary(note_document)
    policy_summary = build_policy_summary(planner_policy)
    fact_summary = build_fact_summary(knowledge, image_assets)
    evidence_slice = build_retrieval_evidence_slice(knowledge, semantic_role="narrative_text", limit=4)

    return f"""你是 XHS-Forge 的整页笔记编辑器。
当前页面已经存在，你的任务是根据用户自然语言修改现有页面，而不是重新生成一整页。

【用户指令】
{user_query}

【document_summary】
{json.dumps(document_summary, ensure_ascii=False, indent=2)}

【当前区块清单】
{_summarize_blocks(document_view)}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【当前区块数据】
{json.dumps(block_payloads, ensure_ascii=False)}

【当前区块样式】
{json.dumps(block_style_map, ensure_ascii=False)}

【fact_summary】
{json.dumps(fact_summary, ensure_ascii=False, indent=2)}

【evidence_slice】
{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【policy_summary】
{json.dumps(policy_summary, ensure_ascii=False, indent=2)}

【组件白名单与必填字段】
{component_contract_text}

【输出规则】
1. 当前页面已经存在，默认是在修改现有页面，不要重新生成整页。
2. 如果用户说“保留标题”，不要改 page_title。
3. 如果用户提到“第一段/第二段/第三段”，优先使用 action=rewrite_paragraph，并填写 paragraph_index。
4. 如果用户要改某个区块内容，使用 action=update_block 并给出 block_id 或 block_index。
5. 如果用户要替换组件类型，使用 action=replace_block。
6. 如果用户要新增一个区块，使用 action=append_block，并提供 new_component_type、content_brief 和 payload_patch。若用户指定“在某块前面/后面新增”，同时填写 block_id 或 block_index 作为插入锚点。
7. 如果用户要调整顺序，使用 action=move_block。
8. 如果用户要改整体视觉主题、背景色、主色，使用 action=update_page_theme，并填写 page_theme_patch。
9. 如果用户要删除某个区块，使用 action=remove_block。
10. payload_patch 只写必要字段；style_patch 只写样式变化；page_theme_patch 只写页面级 CSS 变量。
11. 除非用户明确要求，不要删除其他区块，不要改写整页标题。
12. 如果指令不明确，使用 action=noop。
13. 若“已确认事实”存在，修改正文、参数卡、对比卡时必须优先沿用这些值。
"""


def infer_append_insert_index(user_query: str, target_index: int | None, block_count: int) -> int:
    if target_index is None:
        return block_count
    if wants_before_position(user_query):
        return max(0, target_index)
    return min(block_count, target_index + 1)
