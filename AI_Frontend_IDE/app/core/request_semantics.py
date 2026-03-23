"""请求语义的唯一判断源。

这里集中处理“当前请求更像新建还是编辑”这类高频判断，避免 planner、
graph、API 层各自维护一份近似但不完全相同的逻辑。
"""

from __future__ import annotations

from typing import Any

from app.core.query_heuristics import looks_like_existing_canvas_edit


GLOBAL_SELECTION_VALUES = {"", "无", "无 (全局修改)", "none", "null"}


def normalize_selected_element_id(value: Any) -> str:
    """把各种“全局未选中”写法统一折叠成空串。"""
    text = str(value or "").strip()
    return "" if text.lower() in GLOBAL_SELECTION_VALUES else text


def has_local_selection(value: Any) -> bool:
    """判断当前请求是否已经锁定了局部组件。"""
    return bool(normalize_selected_element_id(value))


def latest_user_text_from_messages(messages: list[Any] | None) -> str:
    """从 LangChain message 列表中提取最后一条用户文本。"""
    safe_messages = list(messages or [])
    if not safe_messages:
        return ""
    content = getattr(safe_messages[-1], "content", "") or ""
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                text_parts.append(str(part.get("text")))
        return "".join(text_parts).strip()
    return str(content).strip()


def is_create_like_request(
    *,
    task_type: str | None,
    selected_element_id: Any,
    active_panel: Any,
    user_text: str | None,
) -> bool:
    """判断当前请求是否属于“需要铺开整页骨架”的创建任务。"""
    normalized_task = str(task_type or "").strip().lower()
    if normalized_task == "create":
        return True
    if normalized_task in {"edit", "inspect", "confirm_fact", "refuse"}:
        return False
    if has_local_selection(selected_element_id):
        return False
    if str(active_panel or "main").strip().lower() != "main":
        return False
    latest_text = str(user_text or "").strip()
    return bool(latest_text) and not looks_like_existing_canvas_edit(latest_text)


def state_requests_create(state: dict[str, Any] | None) -> bool:
    """从统一 state 判断当前请求是否是 create-like。"""
    safe_state = state or {}
    intent_v2 = safe_state.get("intent_result_v2") or {}
    return is_create_like_request(
        task_type=str(intent_v2.get("task_type") or ""),
        selected_element_id=safe_state.get("selected_element_id"),
        active_panel=safe_state.get("active_panel"),
        user_text=latest_user_text_from_messages(safe_state.get("main_messages") or []),
    )


def payload_requests_create(*, content: str, panel: str, selected_element_id: Any) -> bool:
    """从 WebSocket payload 判断当前是否属于全局创建。"""
    return is_create_like_request(
        task_type="",
        selected_element_id=selected_element_id,
        active_panel=panel,
        user_text=content,
    )
