"""Main editing node for long-lived NoteDocument canvases.

This file keeps the top-level edit pipeline readable:
- gather the current document and user intent
- choose a structured editing action whenever possible
- apply the action and emit updated state/trace output

Heavier semantic targeting and scoring helpers live in `note_editor_support.py`
so this file can stay focused on orchestration instead of token-map sprawl.
"""

import json
from copy import deepcopy
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, field_validator

from app.agents.state import UIProjectState, merge_state_patch
from app.agents.tools_registry import LOCAL_NOTE_EDITOR_TOOLS, NOTE_EDITOR_TOOLS
from app.agents.utils.fact_utils import build_fact_grounding_context
from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.component_manifest import (
    filter_payload_for_component,
    normalize_component_type,
    resolve_component_for_block_intent,
)
from app.core.note_document import build_document_editing_context_from_state, build_note_document, build_note_document_from_state
from app.agents.nodes.component_builder import build_component_fallback, enforce_component_contract
from app.agents.nodes.note_editor_support import (
    COMPONENT_SIGNAL_TOKENS,
    SUPPORTED_COMPONENTS,
    _build_component_contract_text,
    _build_note_block_meta_map,
    _build_theme_patch_fallback,
    _extract_component_mentions,
    _extract_rewritable_payload_fields,
    _find_note_document_block,
    _has_edit_intent_language,
    _infer_replacement_component_type,
    _infer_target_component_type,
    _mentions_paragraph_reference,
    _normalize_component_type_name,
    _normalize_page_theme_patch,
    _score_block_for_query,
    _summarize_blocks,
    _summarize_note_document_blocks,
)


class NoteEditorAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: NotRequired[int]
    note_document: Annotated[dict, merge_state_patch]
    retrieved_knowledge: Any
    selected_element_id: str | None
    has_controversy: bool
    creator_persona: str | None


class LocalNoteEditOutput(BaseModel):
    thought_process: str | None = Field(default=None, description="局部编辑的推理过程")
    reason: str = Field(default="按用户要求完成局部编辑", description="本次局部编辑理由")
    action: Literal["update_block", "replace_block", "move_block", "remove_block", "append_block", "noop"] = Field(
        default="update_block",
        description="对当前选中区块执行的动作",
    )
    block_id: str = Field(..., description="当前被编辑的区块 ID")
    new_component_type: str | None = Field(default=None, description="替换后的组件类型")
    content_brief: str | None = Field(default=None, description="更新后的区块职责描述")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="组件数据补丁")
    style_patch: dict[str, Any] = Field(default_factory=dict, description="组件样式补丁")
    move_to_index: int | None = Field(default=None, description="目标顺序索引")

    @field_validator("new_component_type", mode="before")
    @classmethod
    def normalize_component_type(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return _normalize_component_type_name(value)
        return None


class LocalTextRewriteOutput(BaseModel):
    reason: str = Field(default="已补全文案补丁", description="补全文案补丁的理由")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="需要回写到组件中的文案字段补丁")


class GlobalCanvasEditOutput(BaseModel):
    reason: str = Field(default="已按要求完成整页编辑", description="本次整页编辑理由")
    action: Literal[
        "update_page_title",
        "update_page_theme",
        "update_block",
        "rewrite_paragraph",
        "replace_block",
        "move_block",
        "remove_block",
        "append_block",
        "noop",
    ] = Field(default="update_block", description="本次整页编辑动作")
    block_id: str | None = Field(default=None, description="目标区块 ID")
    block_index: int | None = Field(default=None, description="目标区块索引，从 0 开始")
    content_brief: str | None = Field(default=None, description="更新后的区块职责描述")
    page_title: str | None = Field(default=None, description="新的页面标题")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="区块数据补丁")
    style_patch: dict[str, Any] = Field(default_factory=dict, description="区块样式补丁")
    page_theme_patch: dict[str, Any] = Field(default_factory=dict, description="页面主题变量补丁")
    new_component_type: str | None = Field(default=None, description="替换后的组件类型")
    move_to_index: int | None = Field(default=None, description="移动后的目标索引")
    paragraph_index: int | None = Field(default=None, description="要重写的段落索引，从 0 开始")
    paragraph_text: str | None = Field(default=None, description="重写后的段落文本")

    @field_validator("new_component_type", mode="before")
    @classmethod
    def normalize_component_type(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return _normalize_component_type_name(value)
        return None

    @field_validator("page_theme_patch", mode="before")
    @classmethod
    def ensure_page_theme_patch_dict(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return _normalize_page_theme_patch(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return _normalize_page_theme_patch(parsed)
            except json.JSONDecodeError:
                pass

            theme_patch = {}
            for chunk in raw.split(";"):
                piece = chunk.strip()
                if not piece or ":" not in piece:
                    continue
                key, val = piece.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key and val:
                    theme_patch[key] = val
            return _normalize_page_theme_patch(theme_patch)
        return {}


class CanvasCreationBlockOutput(BaseModel):
    component_type: str = Field(..., description="创建的组件类型")
    content_brief: str = Field(default="", description="区块职责描述")
    payload: dict[str, Any] = Field(default_factory=dict, description="组件初始数据")
    intent_type: str | None = Field(default=None, description="对应的 block intent")

    @field_validator("component_type", mode="before")
    @classmethod
    def normalize_component_type(cls, value: Any) -> str:
        normalized = _normalize_component_type_name(str(value or ""))
        return normalized or "StoryText"


class CanvasCreationOutput(BaseModel):
    reason: str = Field(default="已根据页面策略创建首版笔记", description="创建理由")
    page_title: str | None = Field(default=None, description="页面标题")
    blocks: list[CanvasCreationBlockOutput] = Field(default_factory=list, description="首版区块列表")



def _has_local_selection(selected_element_id: str | None) -> bool:
    return selected_element_id not in [None, "", "无", "无 (全局修改)", "none"]


def _select_note_editor_tools(selected_element_id: str | None):
    return LOCAL_NOTE_EDITOR_TOOLS if _has_local_selection(selected_element_id) else NOTE_EDITOR_TOOLS


def _build_note_editor_prompt_snapshot(mode: str, prompt_text: str, plan: Any | None = None) -> dict[str, Any]:
    plan_payload = {}
    if plan is not None:
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump(exclude_none=True)
        elif isinstance(plan, dict):
            plan_payload = plan
    snapshot = {
        "note_editor": [
            {
                "role": "system",
                "content": f"Structured note_editor ({mode}) prompt. 优先走 NoteDocument + component_manifest + planner_policy，不直接依赖开放式 fallback。",
            },
            {
                "role": "user",
                "content": prompt_text,
            },
        ]
    }
    if plan_payload:
        snapshot["note_editor"].append({
            "role": "assistant",
            "content": json.dumps(plan_payload, ensure_ascii=False, indent=2),
        })
    return snapshot


def _build_next_note_document_from_execution(
    state: UIProjectState,
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


def _build_note_editor_prompt(state: NoteEditorAgentState) -> str:
    _note_document, document_view, _block_style_map, _image_assets = build_document_editing_context_from_state(state)
    knowledge = state.get("retrieved_knowledge", {}) or {}
    selected_element_id = state.get("selected_element_id")
    creator_persona = state.get("creator_persona", "硬核数码博主")
    has_controversy = state.get("has_controversy", False)
    current_blocks = document_view.get("blocks", [])
    selected_payload = document_view.get(selected_element_id, {}) if selected_element_id else {}
    local_mode = _has_local_selection(selected_element_id)

    component_contract_text = _build_component_contract_text()
    fact_grounding = build_fact_grounding_context(knowledge)
    planner_policy = state.get("planner_policy", {}) or {}
    note_document = build_note_document_from_state(state)
    selected_note_block = _find_note_document_block(note_document, selected_element_id)

    return f"""你是 XHS-Forge 的 Note Editor V2。
你的职责不是走流水线，而是像真正的编辑器一样，直接把用户自然语言改成一张可渲染的笔记。

【最高目标】
通过工具直接编辑 Note DSL，完成“创建笔记”或“修改笔记”。

【当前工作模式】
- 模式: {"局部选中编辑" if local_mode else "整页编辑"}

【当前画布状态】
- 页面标题: {document_view.get("page_title") or "未设置"}
- 当前区块数: {len(current_blocks)}
- 当前选中组件: {selected_element_id or "无"}
- 当前创作者人设: {creator_persona}

【当前区块清单】
{_summarize_blocks(document_view)}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【当前选中区块数据】
{json.dumps(selected_payload, ensure_ascii=False) if selected_payload else "无"}

【当前选中区块元数据】
{json.dumps(selected_note_block or {}, ensure_ascii=False)}

【可用事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【Planner 策略】
{json.dumps(planner_policy, ensure_ascii=False)}

【NoteDocument 快照】
{json.dumps(note_document, ensure_ascii=False)}

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


def _build_local_edit_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    _note_document, document_view, block_style_map, _image_assets = build_document_editing_context_from_state(state)
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
    selected_note_block = _find_note_document_block(note_document, selected_element_id)

    return f"""你是 XHS-Forge 的局部笔记编辑器。
你的任务不是重写整页，而是只围绕当前选中区块输出一个结构化补丁计划。

【用户指令】
{user_query}

【当前选中区块】
{json.dumps(target_block or {}, ensure_ascii=False)}

【当前选中区块元数据】
{json.dumps(selected_note_block or {}, ensure_ascii=False)}

【当前选中区块数据】
{json.dumps(target_payload, ensure_ascii=False)}

【当前选中区块样式】
{json.dumps(target_style, ensure_ascii=False)}

【当前画布摘要】
- 页面标题: {document_view.get("page_title") or "未设置"}
- 区块总数: {len(document_view.get("blocks", []))}
- 选中区块 ID: {selected_element_id or "无"}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【Planner 策略】
{json.dumps(planner_policy, ensure_ascii=False)}

【NoteDocument 快照】
{json.dumps(note_document, ensure_ascii=False)}

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


def _infer_append_insert_index(user_query: str, target_index: int | None, block_count: int) -> int:
    if target_index is None:
        return block_count
    query = user_query or ""
    if any(token in query for token in ["前面", "前边", "上面", "之前", "前插"]):
        return max(0, target_index)
    return min(block_count, target_index + 1)


def _default_canvas_block_intents(state: UIProjectState) -> list[dict[str, Any]]:
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
    if has_images or any(token in user_query for token in ["封面", "图片", "配图", "首图"]):
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


def _build_canvas_creation_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    knowledge = state.get("retrieved_knowledge", {}) or {}
    planner_output = state.get("planner_output", {}) or {}
    planner_policy = state.get("planner_policy", {}) or {}
    block_intents = _default_canvas_block_intents(state)
    component_contract_text = _build_component_contract_text()
    fact_grounding = build_fact_grounding_context(knowledge)
    scenarios = state.get("scenarios") or [state.get("active_archetype") or "general"]

    return f"""你是 XHS-Forge 的首版画布规划编辑器。
当前页面为空，你的任务是直接输出一份结构化的首版笔记创建计划，而不是进入自由工具循环。

【用户指令】
{user_query}

【场景信息】
- active_archetype: {state.get('active_archetype') or 'general'}
- scenarios: {json.dumps(scenarios, ensure_ascii=False)}

【Planner 输出】
{json.dumps(planner_output, ensure_ascii=False)}

【Planner 策略】
{json.dumps(planner_policy, ensure_ascii=False)}

【推荐 block intents】
{json.dumps(block_intents, ensure_ascii=False)}

【事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

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


def _guess_block_prefix(component_type: str) -> str:
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


def _build_canvas_creation_fallback(state: UIProjectState, user_query: str) -> CanvasCreationOutput:
    block_intents = _default_canvas_block_intents(state)
    knowledge = state.get("retrieved_knowledge") or {}
    image_assets = state.get("image_assets") or []
    entity_name = str(knowledge.get("entity_name") or user_query or "这篇笔记").strip()
    blocks: list[CanvasCreationBlockOutput] = []
    scenario_scores = (state.get("scenario_scores") or (state.get("planner_output") or {}).get("scenario_scores") or {})
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
            comp_id=f"{_guess_block_prefix(component_type)}_fallback",
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
        blocks.append(
            CanvasCreationBlockOutput(
                component_type=component_type,
                content_brief=content_brief,
                payload=payload,
                intent_type=intent.get("intent_type"),
            )
        )

    if not any(block.component_type == "TitleBlock" for block in blocks):
        blocks.insert(
            0,
            CanvasCreationBlockOutput(
                component_type="TitleBlock",
                content_brief="页面标题",
                payload={"type": "TitleBlock", "title": entity_name},
                intent_type="heading",
            ),
        )
    if not any(block.component_type == "StoryText" for block in blocks):
        fallback_payload = build_component_fallback("StoryText", "story_fallback", "正文叙事", user_query, knowledge, image_assets)
        payload = enforce_component_contract("StoryText", filter_payload_for_component("StoryText", fallback_payload), fallback_payload)
        insert_index = 1 if blocks and blocks[0].component_type == "TitleBlock" else 0
        blocks.insert(
            insert_index,
            CanvasCreationBlockOutput(
                component_type="StoryText",
                content_brief="正文叙事",
                payload=payload,
                intent_type="narrative_text",
            ),
        )

    return CanvasCreationOutput(
        reason="已根据 Planner 策略生成首版画布",
        page_title=f"{entity_name} 深度笔记",
        blocks=blocks[:6],
    )


def _apply_canvas_creation_plan(
    original_document_view: dict,
    original_block_style_map: dict,
    plan: CanvasCreationOutput,
    user_query: str,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    final_document_view = deepcopy(original_document_view or {})
    final_block_style_map = deepcopy(original_block_style_map or {})
    knowledge = retrieved_knowledge or {}
    assets = image_assets or []
    final_blocks: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    page_title = str(plan.page_title or final_document_view.get("page_title") or knowledge.get("entity_name") or "XHS-Forge Note").strip()
    final_document_view["page_title"] = page_title or "XHS-Forge Note"
    final_document_view["blocks"] = []

    for index, block_plan in enumerate(plan.blocks or []):
        component_type = _normalize_component_type_name(block_plan.component_type) or "StoryText"
        prefix = _guess_block_prefix(component_type)
        block_id = f"{prefix}_{index + 1}"
        serial = index + 1
        while block_id in used_ids:
            serial += 1
            block_id = f"{prefix}_{serial}"
        used_ids.add(block_id)

        content_brief = str(block_plan.content_brief or block_plan.intent_type or component_type).strip() or component_type
        fallback_payload = build_component_fallback(
            comp_type=component_type,
            comp_id=block_id,
            content_brief=content_brief,
            user_query=user_query,
            retrieved_knowledge=knowledge,
            image_assets=assets,
        )
        payload = filter_payload_for_component(component_type, dict(block_plan.payload or {}))
        payload = enforce_component_contract(component_type, payload, fallback_payload)

        final_blocks.append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": content_brief,
        })
        final_document_view[block_id] = payload
        final_block_style_map.setdefault(block_id, deepcopy(final_block_style_map.get(block_id) or {}))

    final_document_view["blocks"] = final_blocks
    return final_document_view, final_block_style_map


def _build_global_edit_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    _note_document, document_view, block_style_map, _image_assets = build_document_editing_context_from_state(state)
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

    return f"""你是 XHS-Forge 的整页笔记编辑器。
当前页面已经存在，你的任务是根据用户自然语言修改现有页面，而不是重新生成一整页。

【用户指令】
{user_query}

【当前页面标题】
{document_view.get("page_title") or "未设置"}

【当前区块清单】
{_summarize_blocks(document_view)}

【NoteDocument 区块能力摘要】
{_summarize_note_document_blocks(note_document)}

【当前区块数据】
{json.dumps(block_payloads, ensure_ascii=False)}

【当前区块样式】
{json.dumps(block_style_map, ensure_ascii=False)}

【事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【Planner 策略】
{json.dumps(planner_policy, ensure_ascii=False)}

【NoteDocument 快照】
{json.dumps(note_document, ensure_ascii=False)}

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


def _append_local_block_from_plan(
    selected_element_id: str | None,
    final_document_view: dict,
    final_block_style_map: dict,
    plan: LocalNoteEditOutput,
    user_query: str,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    if not _has_local_selection(selected_element_id):
        return final_document_view, final_block_style_map

    target_id = str(selected_element_id)
    blocks = list(final_document_view.get("blocks", []))
    target_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == target_id), None)
    if target_index is None:
        return final_document_view, final_block_style_map

    knowledge = retrieved_knowledge or {}
    assets = image_assets or []
    component_type = (
        _infer_replacement_component_type(user_query, plan.new_component_type)
        or _infer_target_component_type(user_query, "append_block", plan.new_component_type)
        or "StoryText"
    )
    component_type = _normalize_component_type_name(component_type) or "StoryText"
    prefix = _guess_block_prefix(component_type)
    existing_ids = {str(block.get("id") or "") for block in blocks}
    serial = len(blocks) + 1
    block_id = f"{prefix}_{serial}"
    while block_id in existing_ids:
        serial += 1
        block_id = f"{prefix}_{serial}"

    content_brief = str(plan.content_brief or plan.reason or component_type).strip() or component_type
    fallback_payload = build_component_fallback(
        comp_type=component_type,
        comp_id=block_id,
        content_brief=content_brief,
        user_query=user_query,
        retrieved_knowledge=knowledge,
        image_assets=assets,
    )
    payload = filter_payload_for_component(component_type, dict(plan.payload_patch or {}))
    payload = enforce_component_contract(component_type, payload, fallback_payload)

    new_block = {
        "id": block_id,
        "component_type": component_type,
        "content_brief": content_brief,
    }
    insert_index = _infer_append_insert_index(user_query, target_index, len(blocks))
    blocks.insert(insert_index, new_block)
    final_document_view["blocks"] = blocks
    final_document_view[block_id] = payload
    if plan.style_patch:
        final_block_style_map[block_id] = deepcopy(plan.style_patch)
    else:
        final_block_style_map.setdefault(block_id, deepcopy(final_block_style_map.get(block_id) or {}))
    return final_document_view, final_block_style_map


def _resolve_local_move_target_index(
    selected_element_id: str,
    document_view: dict,
    plan: LocalNoteEditOutput,
    user_query: str = "",
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
) -> int | None:
    blocks = list((document_view or {}).get("blocks", []))
    if not blocks:
        return None
    if plan.move_to_index is not None:
        return min(max(0, plan.move_to_index), max(0, len(blocks) - 1))

    anchor_query = _extract_move_anchor_query(user_query)
    if not anchor_query or anchor_query == user_query:
        return None

    anchor_plan = GlobalCanvasEditOutput(action="update_block", reason=plan.reason)
    anchor_id = _resolve_global_target_id(
        anchor_plan,
        document_view,
        user_query=anchor_query,
        planner_policy=planner_policy,
        note_document=note_document,
    )
    if not anchor_id or anchor_id == selected_element_id:
        return None

    remaining_blocks = [block for block in blocks if block.get("id") != selected_element_id]
    anchor_index = next((idx for idx, block in enumerate(remaining_blocks) if block.get("id") == anchor_id), None)
    if anchor_index is None:
        return None
    if any(token in anchor_query for token in ["前面", "前边", "之前", "上面"]):
        return anchor_index
    return anchor_index + 1


def _apply_local_edit_plan(
    selected_element_id: str | None,
    original_document_view: dict,
    original_block_style_map: dict,
    plan: LocalNoteEditOutput,
    user_query: str = "",
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    final_document_view = deepcopy(original_document_view or {})
    final_block_style_map = deepcopy(original_block_style_map or {})
    if not _has_local_selection(selected_element_id):
        return final_document_view, final_block_style_map

    target_id = str(selected_element_id)
    blocks = list(final_document_view.get("blocks", []))
    target_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == target_id), None)
    if target_index is None:
        return final_document_view, final_block_style_map

    target_block = deepcopy(blocks[target_index])
    current_payload = deepcopy(final_document_view.get(target_id, {}))
    current_style = deepcopy(final_block_style_map.get(target_id, {}))
    action = plan.action

    if action == "remove_block":
        final_document_view["blocks"] = [block for block in blocks if block.get("id") != target_id]
        final_document_view.pop(target_id, None)
        final_block_style_map.pop(target_id, None)
        return final_document_view, final_block_style_map

    if action == "append_block":
        return _append_local_block_from_plan(
            selected_element_id,
            final_document_view,
            final_block_style_map,
            plan,
            user_query=user_query,
            retrieved_knowledge=retrieved_knowledge,
            image_assets=image_assets,
        )

    if action == "replace_block":
        next_component_type = plan.new_component_type or target_block.get("component_type") or current_payload.get("type")
        if next_component_type:
            target_block["component_type"] = next_component_type
            current_payload = {"type": next_component_type, **(plan.payload_patch or {})}
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
    elif action in {"update_block", "move_block", "noop"}:
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
        current_payload = {**current_payload, **(plan.payload_patch or {})}
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]

    if plan.style_patch:
        inline_styles_patch = plan.style_patch.get("inline_styles", {})
        merged_style = {**current_style, **plan.style_patch}
        if isinstance(current_style.get("inline_styles"), dict) and isinstance(inline_styles_patch, dict):
            merged_style["inline_styles"] = {
                **current_style.get("inline_styles", {}),
                **inline_styles_patch,
            }
        final_block_style_map[target_id] = merged_style

    blocks[target_index] = target_block
    if action == "move_block":
        move_index = _resolve_local_move_target_index(
            target_id,
            final_document_view,
            plan,
            user_query=user_query,
            planner_policy=planner_policy,
            note_document=note_document,
        )
        if move_index is not None:
            moved_block = blocks.pop(target_index)
            safe_index = min(max(0, move_index), len(blocks))
            blocks.insert(safe_index, moved_block)
    final_document_view["blocks"] = blocks
    final_document_view[target_id] = current_payload
    return final_document_view, final_block_style_map


def _has_global_edit_request(user_query: str, document_view: dict, planner_policy: dict[str, Any] | None = None, note_document: dict[str, Any] | None = None) -> bool:
    blocks = list((document_view or {}).get("blocks", []))
    if not blocks:
        return False
    query = user_query or ""
    if _mentions_paragraph_reference(query):
        return True
    if _has_edit_intent_language(query) or any(token in query for token in COMPONENT_SIGNAL_TOKENS):
        return True
    block_meta_map = _build_note_block_meta_map(note_document=note_document, document_view=document_view)
    for block in blocks:
        block_id = block.get("id")
        if not block_id:
            continue
        payload = document_view.get(block_id, {})
        block_meta = block_meta_map.get(str(block_id), {})
        if _score_block_for_query(block, payload, query, block_meta=block_meta, planner_policy=planner_policy) > 0 and _has_edit_intent_language(query):
            return True
    return False


def _resolve_global_target_id(plan: GlobalCanvasEditOutput, document_view: dict, user_query: str = "", planner_policy: dict[str, Any] | None = None, note_document: dict[str, Any] | None = None) -> str | None:
    blocks = list((document_view or {}).get("blocks", []))
    block_meta_map = _build_note_block_meta_map(note_document=note_document, document_view=document_view)
    resolution_query = _extract_move_subject_query(user_query) if plan.action == "move_block" else user_query
    inferred_target_type = _infer_target_component_type(
        resolution_query,
        plan.action,
        plan.new_component_type,
        planner_policy=planner_policy,
        note_document=note_document,
    )

    if plan.block_id:
        explicit_type = next(
            (block.get("component_type") for block in blocks if block.get("id") == plan.block_id),
            None,
        )
        if inferred_target_type and explicit_type and explicit_type != inferred_target_type:
            hinted_block = next(
                (block for block in blocks if block.get("component_type") == inferred_target_type),
                None,
            )
            if hinted_block:
                return hinted_block.get("id")
        return plan.block_id
    if plan.block_index is not None and 0 <= plan.block_index < len(blocks):
        return blocks[plan.block_index].get("id")
    if plan.action == "rewrite_paragraph":
        for block in blocks:
            block_id = block.get("id")
            payload = document_view.get(block_id, {})
            paragraphs = payload.get("paragraphs")
            if isinstance(paragraphs, list) and paragraphs:
                return block_id
    scored_candidates: list[tuple[int, str]] = []
    for block in blocks:
        block_id = block.get("id")
        if not block_id:
            continue
        payload = document_view.get(block_id, {})
        block_meta = block_meta_map.get(str(block_id), {})
        score = _score_block_for_query(
            block,
            payload,
            resolution_query,
            inferred_target_type,
            block_meta=block_meta,
            planner_policy=planner_policy,
            action=plan.action,
        )
        if score > 0:
            scored_candidates.append((score, str(block_id)))

    if scored_candidates:
        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        return scored_candidates[0][1]

    if inferred_target_type:
        for block in blocks:
            if block.get("component_type") == inferred_target_type:
                return block.get("id")
    return blocks[0].get("id") if blocks else None


def _resolve_global_append_anchor_id(
    plan: GlobalCanvasEditOutput,
    document_view: dict,
    user_query: str = "",
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
) -> str | None:
    if plan.block_id:
        return str(plan.block_id)
    if plan.block_index is not None:
        blocks = list((document_view or {}).get("blocks", []))
        if 0 <= plan.block_index < len(blocks):
            return str(blocks[plan.block_index].get("id") or "") or None

    anchor_plan = plan.model_copy(deep=True)
    anchor_plan.action = "update_block"
    anchor_plan.new_component_type = None
    anchor_plan.payload_patch = {}
    anchor_plan.style_patch = {}
    anchor_plan.content_brief = None
    return _resolve_global_target_id(
        anchor_plan,
        document_view,
        user_query=user_query,
        planner_policy=planner_policy,
        note_document=note_document,
    )


def _extract_move_anchor_query(user_query: str) -> str:
    query = user_query or ""
    for splitter in ["放到", "移到", "挪到", "移至", "放在", "挪到"]:
        if splitter in query:
            return query.split(splitter, 1)[1].strip()
    return query


def _extract_move_subject_query(user_query: str) -> str:
    query = user_query or ""
    for splitter in ["放到", "移到", "挪到", "移至", "放在", "挪到"]:
        if splitter in query:
            return query.split(splitter, 1)[0].strip()
    return query


def _resolve_global_move_target_index(
    plan: GlobalCanvasEditOutput,
    document_view: dict,
    target_id: str,
    user_query: str = "",
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
) -> int | None:
    blocks = list((document_view or {}).get("blocks", []))
    if not blocks:
        return None
    if plan.move_to_index is not None:
        return min(max(0, plan.move_to_index), max(0, len(blocks) - 1))

    anchor_query = _extract_move_anchor_query(user_query)
    if not anchor_query or anchor_query == user_query:
        return None

    anchor_plan = GlobalCanvasEditOutput(action="update_block", reason=plan.reason)
    anchor_id = _resolve_global_target_id(
        anchor_plan,
        document_view,
        user_query=anchor_query,
        planner_policy=planner_policy,
        note_document=note_document,
    )
    if not anchor_id or anchor_id == target_id:
        return None

    remaining_blocks = [block for block in blocks if block.get("id") != target_id]
    anchor_index = next((idx for idx, block in enumerate(remaining_blocks) if block.get("id") == anchor_id), None)
    if anchor_index is None:
        return None
    if any(token in anchor_query for token in ["前面", "前边", "之前", "上面"]):
        return anchor_index
    return anchor_index + 1


def _append_structured_block_from_plan(
    final_document_view: dict,
    final_block_style_map: dict,
    plan: GlobalCanvasEditOutput,
    user_query: str,
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    knowledge = retrieved_knowledge or {}
    assets = image_assets or []
    blocks = list(final_document_view.get("blocks", []))
    component_type = (
        _infer_replacement_component_type(user_query, plan.new_component_type)
        or _infer_target_component_type(user_query, "append_block", plan.new_component_type)
        or "StoryText"
    )
    component_type = _normalize_component_type_name(component_type) or "StoryText"
    prefix = _guess_block_prefix(component_type)
    existing_ids = {str(block.get("id") or "") for block in blocks}
    serial = len(blocks) + 1
    block_id = f"{prefix}_{serial}"
    while block_id in existing_ids:
        serial += 1
        block_id = f"{prefix}_{serial}"

    content_brief = str(plan.content_brief or plan.reason or component_type).strip() or component_type
    fallback_payload = build_component_fallback(
        comp_type=component_type,
        comp_id=block_id,
        content_brief=content_brief,
        user_query=user_query,
        retrieved_knowledge=knowledge,
        image_assets=assets,
    )
    payload = filter_payload_for_component(component_type, dict(plan.payload_patch or {}))
    payload = enforce_component_contract(component_type, payload, fallback_payload)

    new_block = {
        "id": block_id,
        "component_type": component_type,
        "content_brief": content_brief,
    }
    anchor_index = None
    anchor_id = _resolve_global_append_anchor_id(
        plan,
        final_document_view,
        user_query=user_query,
        planner_policy=planner_policy,
        note_document=note_document,
    )
    if anchor_id:
        anchor_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == anchor_id), None)
    insert_index = _infer_append_insert_index(user_query, anchor_index, len(blocks))
    blocks.insert(insert_index, new_block)
    final_document_view["blocks"] = blocks
    final_document_view[block_id] = payload
    if plan.style_patch:
        final_block_style_map[block_id] = deepcopy(plan.style_patch)
    else:
        final_block_style_map.setdefault(block_id, deepcopy(final_block_style_map.get(block_id) or {}))
    return final_document_view, final_block_style_map


def _apply_global_edit_plan(
    original_document_view: dict,
    original_block_style_map: dict,
    plan: GlobalCanvasEditOutput,
    user_query: str = "",
    planner_policy: dict[str, Any] | None = None,
    note_document: dict[str, Any] | None = None,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    final_document_view = deepcopy(original_document_view or {})
    final_block_style_map = deepcopy(original_block_style_map or {})
    blocks = list(final_document_view.get("blocks", []))

    if plan.action == "noop":
        return final_document_view, final_block_style_map

    if plan.action == "update_page_title" and plan.page_title:
        final_document_view["page_title"] = plan.page_title
        return final_document_view, final_block_style_map

    if plan.action == "update_page_theme" and plan.page_theme_patch:
        current_theme = deepcopy(final_document_view.get("page_theme", {}))
        final_document_view["page_theme"] = {**current_theme, **plan.page_theme_patch}
        return final_document_view, final_block_style_map

    if plan.action == "append_block":
        return _append_structured_block_from_plan(
            final_document_view,
            final_block_style_map,
            plan,
            user_query=user_query,
            planner_policy=planner_policy,
            note_document=note_document,
            retrieved_knowledge=retrieved_knowledge,
            image_assets=image_assets,
        )

    target_id = _resolve_global_target_id(
        plan,
        final_document_view,
        user_query=user_query,
        planner_policy=planner_policy,
        note_document=note_document,
    )
    if not target_id:
        return final_document_view, final_block_style_map

    target_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == target_id), None)
    if target_index is None:
        return final_document_view, final_block_style_map

    target_block = deepcopy(blocks[target_index])
    current_payload = deepcopy(final_document_view.get(target_id, {}))
    current_style = deepcopy(final_block_style_map.get(target_id, {}))

    if plan.action == "remove_block":
        final_document_view["blocks"] = [block for block in blocks if block.get("id") != target_id]
        final_document_view.pop(target_id, None)
        final_block_style_map.pop(target_id, None)
        return final_document_view, final_block_style_map

    if plan.action == "replace_block":
        next_component_type = (
            _infer_replacement_component_type(user_query, plan.new_component_type)
            or target_block.get("component_type")
            or current_payload.get("type")
        )
        if next_component_type:
            target_block["component_type"] = next_component_type
            current_payload = {"type": next_component_type, **(plan.payload_patch or {})}
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
    elif plan.action == "rewrite_paragraph":
        paragraphs = list(current_payload.get("paragraphs", []))
        paragraph_index = plan.paragraph_index if plan.paragraph_index is not None else 0
        if 0 <= paragraph_index < len(paragraphs) and plan.paragraph_text:
            paragraphs[paragraph_index] = plan.paragraph_text
            current_payload["paragraphs"] = paragraphs
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]
    elif plan.action in {"update_block", "move_block"}:
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
        current_payload = {**current_payload, **(plan.payload_patch or {})}
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]

    if plan.style_patch:
        inline_styles_patch = plan.style_patch.get("inline_styles", {})
        merged_style = {**current_style, **plan.style_patch}
        if isinstance(current_style.get("inline_styles"), dict) and isinstance(inline_styles_patch, dict):
            merged_style["inline_styles"] = {
                **current_style.get("inline_styles", {}),
                **inline_styles_patch,
            }
        final_block_style_map[target_id] = merged_style

    blocks[target_index] = target_block
    if plan.action == "move_block":
        move_index = _resolve_global_move_target_index(
            plan,
            final_document_view,
            target_id,
            user_query=user_query,
            planner_policy=planner_policy,
            note_document=note_document,
        )
        if move_index is not None:
            moved_block = blocks.pop(target_index)
            safe_index = min(max(0, move_index), len(blocks))
            blocks.insert(safe_index, moved_block)

    final_document_view["blocks"] = blocks
    final_document_view[target_id] = current_payload
    return final_document_view, final_block_style_map

def _has_tone_rewrite_request(user_query: str) -> bool:
    return any(token in (user_query or "") for token in ["毒舌", "犀利", "更狠", "尖锐", "刻薄"])


def _build_tone_rewrite_fallback(
    user_query: str,
    block_descriptor: dict[str, Any] | None,
    current_payload: dict[str, Any],
) -> dict[str, Any]:
    if not _has_tone_rewrite_request(user_query):
        return {}

    component_type = (block_descriptor or {}).get("component_type") or current_payload.get("type")
    if component_type == "PollBlock":
        fallback = {}
        question = current_payload.get("question")
        option_a = current_payload.get("option_a")
        option_b = current_payload.get("option_b")
        if isinstance(question, str) and question.strip():
            stripped = question.rstrip("？?！!。.")
            fallback["question"] = f"说句难听的，{stripped}？"
        if isinstance(option_a, str) and option_a.strip():
            fallback["option_a"] = f"真爱粉硬冲：{option_a}"
        if isinstance(option_b, str) and option_b.strip():
            fallback["option_b"] = f"清醒党避雷：{option_b}"
        return fallback

    if component_type == "StoryText":
        paragraphs = current_payload.get("paragraphs")
        if isinstance(paragraphs, list) and paragraphs and all(isinstance(item, str) for item in paragraphs):
            return {
                "paragraphs": [
                    f"说句难听的，{paragraphs[0]}" if idx == 0 else text
                    for idx, text in enumerate(paragraphs)
                ]
            }

    return {}


async def _maybe_backfill_local_payload_patch(
    llm,
    user_query: str,
    block_descriptor: dict[str, Any] | None,
    current_payload: dict[str, Any],
    plan: LocalNoteEditOutput,
) -> LocalNoteEditOutput:
    if plan.action != "update_block" or plan.payload_patch:
        return plan

    rewritable_fields = _extract_rewritable_payload_fields(current_payload)
    if not rewritable_fields:
        return plan

    component_type = (block_descriptor or {}).get("component_type") or current_payload.get("type") or "UnknownBlock"
    rewrite_prompt = f"""你要为一个已选中的组件补全文案补丁。

【用户指令】
{user_query}

【组件类型】
{component_type}

【当前可改写字段】
{json.dumps(rewritable_fields, ensure_ascii=False)}

【规则】
1. 只返回需要改写的可见文案字段，不要返回其他结构字段。
2. 如果用户是在调语气、风格、攻击性、温柔度、简洁度，必须把变化写进 payload_patch，不能只停留在说明层。
3. 尽量保留原意和字段结构；如果字段是字符串列表，返回同样结构。
4. 如果用户要求不明确，也尽量给出最小但可见的文案变化。
"""

    try:
        rewriter = llm.with_structured_output(LocalTextRewriteOutput, method="function_calling")
        rewrite = await rewriter.ainvoke(rewrite_prompt)
        if rewrite.payload_patch:
            plan.payload_patch = rewrite.payload_patch
            if not plan.reason:
                plan.reason = rewrite.reason
    except Exception as e:
        print(f"⚠️ [Note Editor V2] 文案补丁回填失败: {e}")

    if not plan.payload_patch:
        fallback_patch = _build_tone_rewrite_fallback(user_query, block_descriptor, current_payload)
        if fallback_patch:
            plan.payload_patch = fallback_patch
    return plan


def _restrict_local_edit_scope(
    selected_element_id: str | None,
    original_document_view: dict,
    updated_document_view: dict,
    original_block_style_map: dict,
    updated_block_style_map: dict,
    action: str | None = None,
) -> tuple[dict, dict]:
    if not _has_local_selection(selected_element_id):
        return updated_document_view, updated_block_style_map

    target_id = str(selected_element_id)
    original_blocks = list((original_document_view or {}).get("blocks", []))
    updated_blocks = list((updated_document_view or {}).get("blocks", original_blocks))
    original_ids = [block.get("id") for block in original_blocks]
    updated_ids = [block.get("id") for block in updated_blocks]

    original_target_block = next((block for block in original_blocks if block.get("id") == target_id), None)
    updated_target_block = next((block for block in updated_blocks if block.get("id") == target_id), None)

    final_document_view = deepcopy(original_document_view or {})
    final_block_style_map = deepcopy(original_block_style_map or {})

    if original_target_block is None:
        return final_document_view, final_block_style_map

    if target_id not in updated_ids:
        final_blocks = [block for block in original_blocks if block.get("id") != target_id]
        final_document_view["blocks"] = final_blocks
        final_document_view.pop(target_id, None)
        final_block_style_map.pop(target_id, None)
        return final_document_view, final_block_style_map

    final_blocks = []
    if action == "move_block":
        original_block_map = {block.get("id"): block for block in original_blocks}
        for block in updated_blocks:
            block_id = block.get("id")
            if block_id == target_id:
                final_blocks.append(deepcopy(updated_target_block or original_target_block))
            elif block_id in original_block_map:
                final_blocks.append(deepcopy(original_block_map[block_id]))
    else:
        for block in original_blocks:
            if block.get("id") == target_id:
                final_blocks.append(deepcopy(updated_target_block or original_target_block))
            else:
                final_blocks.append(deepcopy(block))

    if action == "append_block":
        appended_blocks = [
            deepcopy(block)
            for block in updated_blocks
            if block.get("id") not in original_ids
        ]
        final_blocks.extend(appended_blocks)

    final_document_view["blocks"] = final_blocks

    if target_id in updated_document_view:
        final_document_view[target_id] = deepcopy(updated_document_view[target_id])

    if target_id in updated_block_style_map:
        final_block_style_map[target_id] = deepcopy(updated_block_style_map[target_id])

    if action == "append_block":
        for block in updated_blocks:
            block_id = block.get("id")
            if block_id and block_id not in original_ids and block_id in updated_document_view:
                final_document_view[block_id] = deepcopy(updated_document_view[block_id])
            if block_id and block_id not in original_ids and block_id in updated_block_style_map:
                final_block_style_map[block_id] = deepcopy(updated_block_style_map[block_id])

    for block_id in list(final_document_view.keys()):
        if block_id in {"blocks", "page_title", "page_theme"}:
            continue
        if action == "append_block" and block_id not in original_ids and block_id in [b.get("id") for b in updated_blocks]:
            continue
        if block_id != target_id and block_id not in original_ids:
            final_document_view.pop(block_id, None)

    for style_id in list(final_block_style_map.keys()):
        if style_id == "global_vars":
            continue
        if action == "append_block" and style_id not in original_ids and style_id in [b.get("id") for b in updated_blocks]:
            continue
        if style_id != target_id and style_id not in original_ids:
            final_block_style_map.pop(style_id, None)

    return final_document_view, final_block_style_map


async def note_editor_node(state: UIProjectState) -> dict:
    """
    Note Editor V2：统一处理自然语言的新建/全局修改请求。
    核心思想：直接编辑 Note DSL，而不是把请求拆成过多下游创意节点。
    """
    main_msgs = state.get("main_messages", [])
    raw_user_content = getattr(main_msgs[-1], "content", "") if main_msgs else "请整理当前笔记"
    if isinstance(raw_user_content, list):
        user_query = "".join(
            str(part.get("text"))
            for part in raw_user_content
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
        ).strip() or "请整理当前笔记"
    else:
        user_query = str(raw_user_content)
    selected_element_id = state.get("selected_element_id")
    _execution_note_document, document_view, block_style_map, _image_assets = build_document_editing_context_from_state(state)
    knowledge = state.get("retrieved_knowledge", {})
    note_document = build_note_document_from_state(state)
    planner_policy = state.get("planner_policy", {}) or {}
    creator_persona = state.get("creator_persona", "硬核数码博主")
    has_controversy = state.get("has_controversy", False)
    local_mode = _has_local_selection(selected_element_id)
    target_exists = any(
        block.get("id") == selected_element_id
        for block in (document_view or {}).get("blocks", [])
    )

    llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.2,
    )

    if not (document_view or {}).get("blocks"):
        original_document_view = deepcopy(document_view or {})
        original_block_style_map = deepcopy(block_style_map or {})
        creation_prompt = ""
        try:
            creation_planner = llm.with_structured_output(CanvasCreationOutput, method="function_calling")
            creation_prompt = _build_canvas_creation_prompt(state, user_query)
            plan = await creation_planner.ainvoke(creation_prompt)
        except Exception as e:
            print(f"⚠️ [Note Editor V2] 结构化首版创建失败，回退确定性创建: {e}")
            plan = _build_canvas_creation_fallback(state, user_query)

        updated_document_view, updated_block_style_map = _apply_canvas_creation_plan(
            original_document_view,
            original_block_style_map,
            plan,
            user_query=user_query,
            retrieved_knowledge=knowledge if isinstance(knowledge, dict) else {},
            image_assets=state.get("image_assets", []) or [],
        )
        next_note_document = _build_next_note_document_from_execution(state, updated_document_view, updated_block_style_map)
        print(f"✅ [Note Editor V2] 首版画布创建完成: blocks={len(updated_document_view.get('blocks', []))}")
        return {
            "note_document": next_note_document,
            "node_prompts": _build_note_editor_prompt_snapshot("create", creation_prompt, plan),
            "main_messages": [AIMessage(content=plan.reason or "已完成首版笔记创建。")],
            "turn_trace": {"note_editor": {"mode": "create", "action": "create_canvas", "reason": plan.reason, "structured": True, "fallback_used": False, "selected_element_id": selected_element_id}},
            "agent_backends": {"note_editor": "structured_function_calling"},
        }

    if local_mode and target_exists:
        try:
            original_document_view = deepcopy(document_view or {})
            original_block_style_map = deepcopy(block_style_map or {})
            local_editor = llm.with_structured_output(LocalNoteEditOutput, method="function_calling")
            local_prompt = _build_local_edit_prompt(state, user_query)
            plan = await local_editor.ainvoke(local_prompt)
            current_target_block = next(
                (block for block in original_document_view.get("blocks", []) if block.get("id") == selected_element_id),
                None,
            )
            current_target_payload = original_document_view.get(selected_element_id, {})
            plan = await _maybe_backfill_local_payload_patch(
                llm,
                user_query,
                current_target_block,
                current_target_payload,
                plan,
            )
            updated_document_view, updated_block_style_map = _apply_local_edit_plan(
                selected_element_id,
                original_document_view,
                original_block_style_map,
                plan,
                user_query=user_query,
                planner_policy=planner_policy,
                note_document=note_document,
                retrieved_knowledge=knowledge if isinstance(knowledge, dict) else {},
                image_assets=state.get("image_assets", []) or [],
            )
            updated_document_view, updated_block_style_map = _restrict_local_edit_scope(
                selected_element_id,
                original_document_view,
                updated_document_view,
                original_block_style_map,
                updated_block_style_map,
                action=plan.action,
            )
            next_note_document = _build_next_note_document_from_execution(state, updated_document_view, updated_block_style_map)
            print(
                f"✅ [Note Editor V2] 局部编辑完成: block={selected_element_id} | action={plan.action}"
            )
            return {
                "note_document": next_note_document,
                "node_prompts": _build_note_editor_prompt_snapshot("local", local_prompt, plan),
                "main_messages": [AIMessage(content=plan.reason or "已完成当前选中区块的更新。")],
                "turn_trace": {"note_editor": {"mode": "local", "action": plan.action, "reason": plan.reason, "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "target_block_id": plan.block_id, "new_component_type": plan.new_component_type}},
                "agent_backends": {"note_editor": "structured_function_calling"},
            }
        except Exception as e:
            print(f"❌ [Note Editor V2] 局部编辑失败: {e}")
            return {
                "main_messages": [AIMessage(content="当前区块编辑失败，已保留原页面状态。")],
                "turn_trace": {"note_editor": {"mode": "local", "action": "error", "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "error": str(e)}},
                "agent_backends": {"note_editor": "structured_function_calling"},
            }

    try:
        original_document_view = deepcopy(document_view or {})
        original_block_style_map = deepcopy(block_style_map or {})
        global_editor = llm.with_structured_output(GlobalCanvasEditOutput, method="function_calling")
        global_prompt = _build_global_edit_prompt(state, user_query)
        plan = await global_editor.ainvoke(global_prompt)
        if plan.action == "update_page_theme" and not plan.page_theme_patch:
            plan.page_theme_patch = _build_theme_patch_fallback(user_query, state.get("planner_policy", {}) or {})
        updated_document_view, updated_block_style_map = _apply_global_edit_plan(
            original_document_view,
            original_block_style_map,
            plan,
            user_query=user_query,
            planner_policy=state.get("planner_policy", {}) or {},
            note_document=note_document,
            retrieved_knowledge=knowledge if isinstance(knowledge, dict) else {},
            image_assets=state.get("image_assets", []) or [],
        )
        next_note_document = _build_next_note_document_from_execution(state, updated_document_view, updated_block_style_map)
        print(f"✅ [Note Editor V2] 整页编辑完成: action={plan.action} | block={plan.block_id or plan.block_index}")
        return {
            "note_document": next_note_document,
            "main_messages": [AIMessage(content=plan.reason or "已完成页面更新。")],
            "turn_trace": {"note_editor": {"mode": "global", "action": plan.action, "reason": plan.reason, "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "target_block_id": plan.block_id, "target_block_index": plan.block_index, "new_component_type": plan.new_component_type, "paragraph_index": plan.paragraph_index}},
            "agent_backends": {"note_editor": "structured_function_calling"},
        }
    except Exception as e:
        print(f"❌ [Note Editor V2] 整页编辑失败: {e}")
        return {
            "main_messages": [AIMessage(content="整页编辑失败，已保留原页面状态。")],
            "turn_trace": {"note_editor": {"mode": "global", "action": "error", "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "error": str(e)}},
            "agent_backends": {"note_editor": "structured_function_calling"},
        }
