import json
import uuid
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.core.component_manifest import filter_payload_for_component, normalize_component_type
from app.core.note_document import (
    append_note_document_block,
    build_note_document_layout_from_state,
    build_note_document_from_state,
    remove_note_document_block,
    replace_note_document_blocks,
    update_note_document_block,
    update_note_document_theme,
    update_note_document_title,
)


def _safe_json_loads(raw: str, default: dict | list):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


@tool
def inspect_note_state(
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    查看当前整张笔记的状态，包括页面标题、区块列表、事实知识与当前选中组件。
    """
    note_document = build_note_document_from_state(state)
    execution_view = build_note_document_layout_from_state(state)
    knowledge = state.get("retrieved_knowledge", {})
    blocks = execution_view.get("blocks", [])

    summary = {
        "page_title": execution_view.get("page_title"),
        "selected_element_id": state.get("selected_element_id"),
        "blocks": blocks,
        "components": {b.get("id"): b.get("props", {}) for b in blocks},
        "facts": {
            "entity_name": knowledge.get("entity_name") if isinstance(knowledge, dict) else None,
            "key_selling_points": knowledge.get("key_selling_points", []) if isinstance(knowledge, dict) else [],
            "known_issues": knowledge.get("known_issues", []) if isinstance(knowledge, dict) else [],
            "battle_report": knowledge.get("battle_report") if isinstance(knowledge, dict) else None,
            "has_controversy": state.get("has_controversy", False),
        },
    }
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=json.dumps(summary, ensure_ascii=False, indent=2),
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )


@tool
def create_note_block(
    component_type: str,
    content_brief: str,
    data_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    创建一个新积木并同时写入其数据。
    - component_type: 组件类型，如 TitleBlock / StoryText / VersusCard / PollBlock
    - content_brief: 该积木在页面中的职责描述
    - data_json: 该组件 props 的 JSON 字符串
    """
    normalized_component_type = normalize_component_type(component_type) or component_type
    block_id = f"{normalized_component_type.lower()}_{uuid.uuid4().hex[:6]}"
    payload = filter_payload_for_component(normalized_component_type, _safe_json_loads(data_json, {}))
    note_document = append_note_document_block(
        build_note_document_from_state(state),
        {
            "id": block_id,
            "component_type": normalized_component_type,
            "content_brief": content_brief,
        },
        props=payload,
    )

    return Command(
        update={
            "note_document": note_document,
            "messages": [
                ToolMessage(
                    content=f"✅ 已创建积木 {block_id} ({normalized_component_type})",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool
def update_note_block(
    block_id: str,
    data_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    更新现有积木的数据。data_json 必须是组件 props 的 JSON 字符串。
    """
    note_document = build_note_document_from_state(state)
    current_block = next((block for block in (note_document.get("blocks") or []) if block.get("id") == block_id), {})
    current = current_block.get("props") or {}
    patch = _safe_json_loads(data_json, {})
    component_type = current_block.get("type")
    new_payload = filter_payload_for_component(component_type, {**current, **patch})

    return Command(
        update={
            "note_document": update_note_document_block(note_document, block_id, props=new_payload),
            "messages": [
                ToolMessage(
                    content=f"✅ 已更新积木 {block_id} 的数据字段: {list(patch.keys())}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool
def set_note_title(
    title: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    设置笔记页面标题。
    """
    return Command(
        update={
            "note_document": update_note_document_title(build_note_document_from_state(state), title),
            "messages": [ToolMessage(content=f"✅ 页面标题已更新为: {title}", tool_call_id=tool_call_id)],
        }
    )


@tool
def set_note_theme(
    theme_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    设置页面主题变量。theme_json 需要是 JSON 字符串，如 {"--bg-color":"#f8fafc"}。
    """
    theme = _safe_json_loads(theme_json, {})
    return Command(
        update={
            "note_document": update_note_document_theme(build_note_document_from_state(state), page_theme=theme),
            "messages": [ToolMessage(content=f"✅ 页面主题已更新。", tool_call_id=tool_call_id)],
        }
    )


@tool
def move_note_block(
    block_id: str,
    new_index: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    调整区块顺序。
    - block_id: 要移动的区块 ID
    - new_index: 目标位置索引，从 0 开始
    """
    note_document = build_note_document_from_state(state)
    blocks = list(note_document.get("blocks", []))
    current_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == block_id), None)

    if current_index is None:
        return Command(
            update={
                "messages": [ToolMessage(content=f"❌ 未找到区块 {block_id}，无法移动。", tool_call_id=tool_call_id)]
            }
        )

    block = blocks.pop(current_index)
    safe_index = min(max(0, new_index), len(blocks))
    blocks.insert(safe_index, block)

    return Command(
        update={
            "note_document": replace_note_document_blocks(note_document, blocks),
            "messages": [
                ToolMessage(
                    content=f"✅ 已将区块 {block_id} 移动到索引 {safe_index}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


@tool
def replace_note_block(
    block_id: str,
    new_component_type: str,
    content_brief: str,
    data_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState],
) -> Command:
    """
    保留区块位置与 ID，直接把现有区块替换成另一种组件类型。
    适用于“把投票换成雷达图”这类自然语言修改。
    """
    note_document = build_note_document_from_state(state)
    blocks = note_document.get("blocks", [])
    exists = any(block.get("id") == block_id for block in blocks)
    if not exists:
        return Command(
            update={
                "messages": [ToolMessage(content=f"❌ 未找到区块 {block_id}，无法替换。", tool_call_id=tool_call_id)]
            }
        )

    normalized_component_type = normalize_component_type(new_component_type) or new_component_type
    payload = filter_payload_for_component(normalized_component_type, _safe_json_loads(data_json, {}))
    updated_document = update_note_document_block(
        note_document,
        block_id,
        props=payload,
        metadata={
            "type": normalized_component_type,
            "label": normalized_component_type,
            "content_brief": content_brief,
        },
    )

    return Command(
        update={
            "note_document": updated_document,
            "messages": [
                ToolMessage(
                    content=f"✅ 已将区块 {block_id} 替换为 {normalized_component_type}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
