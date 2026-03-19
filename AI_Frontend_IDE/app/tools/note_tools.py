import json
import uuid
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command


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
    data_dsl = state.get("data_dsl", {})
    knowledge = state.get("retrieved_knowledge", {})
    blocks = data_dsl.get("blocks", [])

    summary = {
        "page_title": data_dsl.get("page_title"),
        "selected_element_id": state.get("selected_element_id"),
        "blocks": blocks,
        "components": {b.get("id"): data_dsl.get(b.get("id"), {}) for b in blocks},
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
    block_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
    payload = _safe_json_loads(data_json, {})
    payload["type"] = component_type

    return Command(
        update={
            "data_dsl": {
                "_block_append": {
                    "id": block_id,
                    "component_type": component_type,
                    "content_brief": content_brief,
                },
                block_id: payload,
            },
            "messages": [
                ToolMessage(
                    content=f"✅ 已创建积木 {block_id} ({component_type})",
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
    data_dsl = state.get("data_dsl", {})
    current = data_dsl.get(block_id, {})
    patch = _safe_json_loads(data_json, {})
    new_payload = {**current, **patch}

    return Command(
        update={
            "data_dsl": {block_id: new_payload},
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
) -> Command:
    """
    设置笔记页面标题。
    """
    return Command(
        update={
            "data_dsl": {"page_title": title},
            "messages": [ToolMessage(content=f"✅ 页面标题已更新为: {title}", tool_call_id=tool_call_id)],
        }
    )


@tool
def set_note_theme(
    theme_json: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    设置页面主题变量。theme_json 需要是 JSON 字符串，如 {"--bg-color":"#f8fafc"}。
    """
    theme = _safe_json_loads(theme_json, {})
    return Command(
        update={
            "data_dsl": {"page_theme": theme},
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
    data_dsl = state.get("data_dsl", {})
    blocks = list(data_dsl.get("blocks", []))
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
            "data_dsl": {"_blocks_override": True, "blocks": blocks},
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
    data_dsl = state.get("data_dsl", {})
    blocks = data_dsl.get("blocks", [])
    exists = any(block.get("id") == block_id for block in blocks)
    if not exists:
        return Command(
            update={
                "messages": [ToolMessage(content=f"❌ 未找到区块 {block_id}，无法替换。", tool_call_id=tool_call_id)]
            }
        )

    payload = _safe_json_loads(data_json, {})
    payload["type"] = new_component_type

    return Command(
        update={
            "data_dsl": {
                "_block_update": {
                    "id": block_id,
                    "data": {
                        "component_type": new_component_type,
                        "content_brief": content_brief,
                    },
                },
                block_id: payload,
            },
            "messages": [
                ToolMessage(
                    content=f"✅ 已将区块 {block_id} 替换为 {new_component_type}",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
