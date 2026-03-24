"""长期 NoteDocument 画布的主编辑节点。

这个文件只保留顶层编辑编排：
- 读取当前文档和用户请求
- 尽量选择结构化编辑动作
- 把动作落成确定性 patch，并输出新的文档与 trace

更重的语义命中、评分和规则细节下沉到 `note_editor_support.py`，
避免这里重新堆成 token-map 大杂烩。
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
from app.core.context_engineering import (
    build_asset_summary,
    build_document_summary,
    build_fact_summary,
    build_policy_summary,
    build_retrieval_evidence_slice,
    build_selection_context,
)
from app.core.llm_factory import create_llm
from app.core.query_heuristics import wants_attention_hook, wants_before_position, wants_image_search, wants_sharper_tone
from app.core.prompt_engineering import build_prompt_snapshot
from app.core.component_manifest import (
    filter_payload_for_component,
    normalize_component_type,
    resolve_component_for_block_intent,
)
from app.core.note_document import build_note_document_editing_context, build_note_document, build_note_document_from_state
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
from app.agents.nodes.note_editor_prompts import (
    build_canvas_creation_fallback as _prompt_build_canvas_creation_fallback,
    build_canvas_creation_prompt as _prompt_build_canvas_creation_prompt,
    build_global_edit_prompt as _prompt_build_global_edit_prompt,
    build_local_edit_prompt as _prompt_build_local_edit_prompt,
    build_next_note_document_from_execution as _prompt_build_next_note_document_from_execution,
    build_note_editor_prompt as _prompt_build_note_editor_prompt,
    build_note_editor_prompt_snapshot as _prompt_build_note_editor_prompt_snapshot,
    default_canvas_block_intents as _prompt_default_canvas_block_intents,
    guess_block_prefix as _prompt_guess_block_prefix,
    infer_append_insert_index as _prompt_infer_append_insert_index,
)


class NoteEditorAgentState(TypedDict):
    """编辑节点在提示词与结构化输出阶段使用的最小状态。"""
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: NotRequired[int]
    note_document: Annotated[dict, merge_state_patch]
    retrieved_knowledge: Any
    selected_element_id: str | None
    has_controversy: bool
    creator_persona: str | None


class LocalNoteEditOutput(BaseModel):
    """局部区块编辑的结构化输出模型。"""
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
    """局部文案补写的结构化输出模型。"""
    reason: str = Field(default="已补全文案补丁", description="补全文案补丁的理由")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="需要回写到组件中的文案字段补丁")


class GlobalCanvasEditOutput(BaseModel):
    """整页编辑动作的结构化输出模型。"""
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
    """新建画布时单个区块的结构化输出模型。"""
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
    """新建整页画布时的结构化输出模型。"""
    reason: str = Field(default="已根据页面策略创建首版笔记", description="创建理由")
    page_title: str | None = Field(default=None, description="页面标题")
    blocks: list[CanvasCreationBlockOutput] = Field(default_factory=list, description="首版区块列表")



def _has_local_selection(selected_element_id: str | None) -> bool:
    """判断当前是否处于局部编辑模式。"""
    return selected_element_id not in [None, "", "无", "无 (全局修改)", "none"]


def _select_note_editor_tools(selected_element_id: str | None):
    """按编辑范围选择 note_editor 可用工具集。"""
    return LOCAL_NOTE_EDITOR_TOOLS if _has_local_selection(selected_element_id) else NOTE_EDITOR_TOOLS


def _build_note_editor_prompt_snapshot(mode: str, prompt_text: str, plan: Any | None = None) -> dict[str, Any]:
    """构造编辑节点在 Prompt Lab 中展示的快照。"""
    return _prompt_build_note_editor_prompt_snapshot(mode, prompt_text, plan)


def _build_next_note_document_from_execution(
    state: UIProjectState,
    updated_document_view: dict[str, Any],
    updated_block_style_map: dict[str, Any],
) -> dict[str, Any]:
    """把执行视图与样式映射重新折叠回正式 NoteDocument。"""
    return _prompt_build_next_note_document_from_execution(state, updated_document_view, updated_block_style_map)


def _build_note_editor_prompt(state: NoteEditorAgentState) -> str:
    """构造通用编辑提示词。"""
    return _prompt_build_note_editor_prompt(state)


def _build_local_edit_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    """构造局部编辑模式的提示词。"""
    return _prompt_build_local_edit_prompt(state, user_query)


def _infer_append_insert_index(user_query: str, target_index: int | None, block_count: int) -> int:
    """推断 append 动作最终应插入的位置。"""
    return _prompt_infer_append_insert_index(user_query, target_index, block_count)


def _default_canvas_block_intents(state: UIProjectState) -> list[dict[str, Any]]:
    """在缺少 planner block intents 时给出一套保守默认结构。"""
    return _prompt_default_canvas_block_intents(state)


def _build_canvas_creation_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    """构造新建整页画布的提示词。"""
    return _prompt_build_canvas_creation_prompt(state, user_query)


def _guess_block_prefix(component_type: str) -> str:
    """根据组件类型猜一个更自然的 block id 前缀。"""
    return _prompt_guess_block_prefix(component_type)


def _build_canvas_creation_fallback(state: UIProjectState, user_query: str) -> CanvasCreationOutput:
    """在模型无法稳定产出首版画布时生成保守 fallback。"""
    return _prompt_build_canvas_creation_fallback(state, user_query, CanvasCreationOutput)


def _apply_canvas_creation_plan(
    original_document_view: dict,
    original_block_style_map: dict,
    plan: CanvasCreationOutput,
    user_query: str,
    retrieved_knowledge: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
) -> tuple[dict, dict]:
    """把新建画布计划落成初始 document_view 与样式映射。"""
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
    """构造整页编辑模式的提示词。"""
    return _prompt_build_global_edit_prompt(state, user_query)


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
    if wants_before_position(anchor_query):
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
    if wants_before_position(anchor_query):
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
    """把整页结构化编辑计划应用到紧凑执行视图。"""
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
    return wants_sharper_tone(user_query) or wants_attention_hook(user_query)


def _build_tone_rewrite_fallback(
    user_query: str,
    block_descriptor: dict[str, Any] | None,
    current_payload: dict[str, Any],
) -> dict[str, Any]:
    if not _has_tone_rewrite_request(user_query):
        return {}

    wants_sharp = wants_sharper_tone(user_query)
    wants_hook = wants_attention_hook(user_query)

    component_type = (block_descriptor or {}).get("component_type") or current_payload.get("type")
    if component_type == "PollBlock":
        fallback = {}
        question = current_payload.get("question")
        option_a = current_payload.get("option_a")
        option_b = current_payload.get("option_b")
        if isinstance(question, str) and question.strip():
            stripped = question.rstrip("？?！!。.")
            if wants_sharp:
                fallback["question"] = f"说句难听的，{stripped}？"
            elif wants_hook:
                fallback["question"] = f"先说重点，{stripped}到底值不值得看？"
        if isinstance(option_a, str) and option_a.strip():
            fallback["option_a"] = f"真爱粉硬冲：{option_a}" if wants_sharp else f"亮点党先看：{option_a}"
        if isinstance(option_b, str) and option_b.strip():
            fallback["option_b"] = f"清醒党避雷：{option_b}" if wants_sharp else f"理性党先想想：{option_b}"
        return fallback

    if component_type == "StoryText":
        paragraphs = current_payload.get("paragraphs")
        if isinstance(paragraphs, list) and paragraphs and all(isinstance(item, str) for item in paragraphs):
            return {
                "paragraphs": [
                    (
                        f"说句难听的，{paragraphs[0]}"
                        if wants_sharp
                        else f"先说结论，{paragraphs[0]}"
                    )
                    if idx == 0 else text
                    for idx, text in enumerate(paragraphs)
                ]
            }

    if component_type == "VersusCard":
        fallback: dict[str, Any] = {}
        title = str(current_payload.get("title") or "").strip()
        decision_hint = str(current_payload.get("decision_hint") or "").strip()
        pros = current_payload.get("pros") if isinstance(current_payload.get("pros"), dict) else {}
        cons = current_payload.get("cons") if isinstance(current_payload.get("cons"), dict) else {}
        pro_text = str(current_payload.get("proText") or "").strip()
        con_text = str(current_payload.get("conText") or "").strip()

        if title:
            fallback["title"] = f"先看结论：{title}" if wants_hook and not wants_sharp else f"说句难听的，{title}"
        if wants_sharp:
            fallback["decision_hint"] = decision_hint or "别只看热度，先看你到底愿不愿意接受它的代价。"
        elif wants_hook:
            fallback["decision_hint"] = decision_hint or "先看哪边更接近你的使用路线，再决定值不值得继续往下看。"

        if pros:
            next_pros = dict(pros)
            summary = str(next_pros.get("summary") or "").strip()
            if summary:
                next_pros["summary"] = f"亮点先摆出来：{summary}" if wants_hook and not wants_sharp else f"真要夸的话，{summary}"
            fallback["pros"] = next_pros
        elif pro_text:
            fallback["proText"] = f"亮点先摆出来：{pro_text}" if wants_hook and not wants_sharp else f"真要夸的话，{pro_text}"

        if cons:
            next_cons = dict(cons)
            summary = str(next_cons.get("summary") or "").strip()
            if summary:
                next_cons["summary"] = f"但也别忽略：{summary}" if wants_hook and not wants_sharp else f"先把代价说清楚：{summary}"
            fallback["cons"] = next_cons
        elif con_text:
            fallback["conText"] = f"但也别忽略：{con_text}" if wants_hook and not wants_sharp else f"先把代价说清楚：{con_text}"

        return fallback

    if component_type == "ProductSpecCard":
        if isinstance(current_payload.get("spec_items"), list) and current_payload.get("spec_items"):
            spec_items = [dict(item) if isinstance(item, dict) else item for item in current_payload.get("spec_items")]
            first_item = spec_items[0] if spec_items and isinstance(spec_items[0], dict) else None
            if first_item:
                next_first = dict(first_item)
                impact = str(next_first.get("decision_impact") or "").strip()
                value = str(next_first.get("value") or "").strip()
                if wants_sharp:
                    next_first["decision_impact"] = impact or "这条如果都不能打动你，后面的参数大概率也不会更有说服力。"
                elif wants_hook:
                    next_first["decision_impact"] = impact or "先看这条，它最能决定你会不会继续往下看。"
                if wants_hook and value:
                    next_first["value"] = f"先看：{value}"
                spec_items[0] = next_first
                return {"spec_items": spec_items}

        core_features = current_payload.get("core_features")
        if isinstance(core_features, list) and core_features and all(isinstance(item, str) for item in core_features):
            updated = list(core_features)
            first = str(updated[0]).strip()
            if first:
                updated[0] = f"先看这条：{first}" if wants_hook and not wants_sharp else f"说句难听的，{first}"
            return {"core_features": updated}

    if component_type == "TitleBlock":
        fallback = {}
        title = current_payload.get("title")
        subtitle = current_payload.get("subtitle")
        if isinstance(title, str) and title.strip():
            fallback["title"] = f"先看结论：{title}" if wants_hook and not wants_sharp else f"说句难听的，{title}"
        if isinstance(subtitle, str) and subtitle.strip():
            fallback["subtitle"] = f"把最关键的判断直接放到台面上。" if wants_hook else subtitle
        return fallback

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
        print(f"⚠️ [Composition Agent] 文案补丁回填失败: {e}")

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
    Unified editor node for long-lived NoteDocument canvases.

    Flow:
    1. build compact editing context
    2. prefer structured edit actions
    3. apply deterministic patches
    4. fall back only when the structured path cannot cover the request
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
    _execution_note_document, document_view, block_style_map, _image_assets = build_note_document_editing_context(state)
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
        model=settings.LLM_MODEL,
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
            print(f"⚠️ [Composition Agent] 结构化首版创建失败，回退确定性创建: {e}")
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
        print(f"✅ [Composition Agent] 首版画布创建完成: blocks={len(updated_document_view.get('blocks', []))}")
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
                f"✅ [Composition Agent] 局部编辑完成: block={selected_element_id} | action={plan.action}"
            )
            return {
                "note_document": next_note_document,
                "node_prompts": _build_note_editor_prompt_snapshot("local", local_prompt, plan),
                "main_messages": [AIMessage(content=plan.reason or "已完成当前选中区块的更新。")],
                "turn_trace": {"note_editor": {"mode": "local", "action": plan.action, "reason": plan.reason, "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "target_block_id": plan.block_id, "new_component_type": plan.new_component_type}},
                "agent_backends": {"note_editor": "structured_function_calling"},
            }
        except Exception as e:
            print(f"❌ [Composition Agent] 局部编辑失败: {e}")
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
        print(f"✅ [Composition Agent] 整页编辑完成: action={plan.action} | block={plan.block_id or plan.block_index}")
        return {
            "note_document": next_note_document,
            "main_messages": [AIMessage(content=plan.reason or "已完成页面更新。")],
            "turn_trace": {"note_editor": {"mode": "global", "action": plan.action, "reason": plan.reason, "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "target_block_id": plan.block_id, "target_block_index": plan.block_index, "new_component_type": plan.new_component_type, "paragraph_index": plan.paragraph_index}},
            "agent_backends": {"note_editor": "structured_function_calling"},
        }
    except Exception as e:
        print(f"❌ [Composition Agent] 整页编辑失败: {e}")
        return {
            "main_messages": [AIMessage(content="整页编辑失败，已保留原页面状态。")],
            "turn_trace": {"note_editor": {"mode": "global", "action": "error", "structured": True, "fallback_used": False, "selected_element_id": selected_element_id, "error": str(e)}},
            "agent_backends": {"note_editor": "structured_function_calling"},
        }
