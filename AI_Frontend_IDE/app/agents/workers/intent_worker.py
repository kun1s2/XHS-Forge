import asyncio
import json
import os
from datetime import datetime

from app.core.config import settings
from app.core.llm_factory import create_llm
from app.core.note_document import build_note_document_layout_from_state
from app.core.prompt_engineering import build_chat_prompt, build_prompt_snapshot, render_prompt_messages
from app.core.query_heuristics import (
    infer_existing_canvas_edit_route,
    looks_like_capability_query,
    looks_like_append_block_request,
    looks_like_existing_canvas_edit,
    looks_like_revision_review_request,
)
from app.core.schema import IntentDecision
from app.services.scenario_manager import scenario_manager

_llm_instance = None


def get_intent_llm():
    global _llm_instance
    if _llm_instance is None:
        os.environ["LANGSMITH_TRACING"] = "false"
        _llm_instance = create_llm(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0,
            max_retries=1,
        )
    return _llm_instance


def _has_valid_selection(selected_id: str | None) -> bool:
    return selected_id not in [None, "", "无", "无 (全局修改)", "none"]


def _extract_user_text(raw_content) -> str:
    if isinstance(raw_content, list):
        parts = []
        for part in raw_content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                parts.append(str(part.get("text")))
        return "".join(parts).strip()
    return str(raw_content or "").strip()


def _looks_like_asset_request(user_query: str) -> bool:
    return any(token in user_query for token in ("图片", "配图", "真机图", "海报", "封面", "大图", "补图", "加图"))


def _looks_like_ingest_request(user_query: str) -> bool:
    return any(token in user_query for token in ("上传资料", "导入资料", "导入知识", "加入知识库", "导入文档", "上传参数表"))


def _looks_like_review_request(user_query: str) -> bool:
    return any(token in user_query for token in ("确认", "采用", "驳回", "暂不使用", "审一下", "审批", "审查"))


def _infer_operation_type(*, user_query: str, active_panel: str, selected_id: str | None, has_existing_canvas: bool) -> str:
    if _looks_like_ingest_request(user_query):
        return "kb_import"
    if _looks_like_review_request(user_query):
        return "fact_review"
    if _looks_like_asset_request(user_query):
        return "asset_edit"
    if active_panel == "structure":
        return "layout_edit"
    if active_panel in {"content", "style"} or _has_valid_selection(selected_id) or has_existing_canvas:
        return "text_edit"
    return "generate"


def _infer_scope(*, active_panel: str, selected_id: str | None) -> str:
    if _has_valid_selection(selected_id):
        return "selected_block"
    if active_panel == "knowledge":
        return "session_workspace"
    if active_panel == "global":
        return "global_hub"
    return "global_canvas"


def _build_fast_path_result(
    *,
    user_query: str,
    selected_id: str | None,
    active_panel: str,
    active_archetype: str,
    has_existing_canvas: bool,
    route: str,
) -> dict:
    scenario = str(active_archetype or "notes")
    operation_type = _infer_operation_type(
        user_query=user_query,
        active_panel=active_panel,
        selected_id=selected_id,
        has_existing_canvas=has_existing_canvas,
    )
    intent_decision = IntentDecision(
        thought_process="",
        reason="快速路由",
        task_type="edit" if operation_type not in {"kb_import", "fact_review"} else ("ingest" if operation_type == "kb_import" else "review"),
        operation_type=operation_type,
        scope=_infer_scope(active_panel=active_panel, selected_id=selected_id),
        needs_research=operation_type == "asset_edit",
        needs_assets=operation_type == "asset_edit",
        confidence=0.94,
        fallback_required=False,
        risk_flags=[],
    ).model_dump()
    return {
        "intent_decision": intent_decision,
        "intent_route": route,
        "selected_element_id": selected_id,
        "scenarios": [scenario],
        "scenario_scores": {scenario: 1.0},
        "active_archetype": scenario,
        "worker_prompts": {
            "intent_worker": [
                {
                    "role": "system",
                    "content": (
                        f"Intent Fast Path: task={intent_decision.get('task_type')}, "
                        f"op={intent_decision.get('operation_type')}, scope={intent_decision.get('scope')}, "
                        f"assets={intent_decision.get('needs_assets')}"
                    ),
                }
            ]
        },
        "agent_backends": {"intent_worker": "deterministic_fast_path"},
    }


def _normalize_intent_decision(result: IntentDecision) -> dict:
    payload = result.model_dump()
    payload["confidence"] = max(0.0, min(1.0, float(payload.get("confidence") or 0.0)))
    if payload.get("operation_type") == "kb_import":
        payload["task_type"] = "ingest"
    elif payload.get("operation_type") == "fact_review":
        payload["task_type"] = "review"
    return payload


def _derive_route_from_intent_decision(intent_decision: dict, *, user_query: str, selected_id: str | None) -> str:
    task_type = str(intent_decision.get("task_type") or "create").lower()
    operation_type = str(intent_decision.get("operation_type") or "generate").lower()
    scope = str(intent_decision.get("scope") or "global_canvas").lower()
    needs_assets = bool(intent_decision.get("needs_assets"))
    needs_research = bool(intent_decision.get("needs_research"))
    fallback_required = bool(intent_decision.get("fallback_required"))

    if fallback_required:
        return "fact_gap_checkpoint"
    if task_type in {"review", "ingest"}:
        return "retrieval_worker"
    if task_type == "inspect":
        return "supervisor_agent"
    if scope == "selected_block" and _has_valid_selection(selected_id):
        return "composition_worker"
    if task_type == "edit":
        if operation_type == "asset_edit" or needs_assets or needs_research:
            return "retrieval_worker"
        return infer_existing_canvas_edit_route(user_query)
    return "retrieval_worker"


async def intent_worker(state: dict[str, object]) -> dict:
    """持续笔记工作台的统一意图网关。"""
    valid_scenarios = scenario_manager.list_all_scenarios() or ["notes"]
    execution_view = build_note_document_layout_from_state(state)
    selected_id = state.get("selected_element_id")
    active_archetype = "notes"
    note_document = state.get("note_document") if isinstance(state.get("note_document"), dict) else {}
    has_existing_canvas = bool(execution_view.get("blocks")) or bool(note_document.get("blocks"))
    active_panel = str(state.get("active_panel", "main") or "main")

    messages = state.get(f"{active_panel}_messages", [])
    if not messages:
        return {"intent_route": "END", "agent_backends": {"intent_worker": "skipped_no_messages"}}

    latest_message = messages[-1]
    raw_content = getattr(latest_message, "content", None)
    if raw_content is None and isinstance(latest_message, dict):
        raw_content = latest_message.get("content")
    user_query = _extract_user_text(raw_content)
    if not user_query:
        return {"intent_route": "END", "agent_backends": {"intent_worker": "skipped_empty_query"}}

    if active_panel != "main" and _has_valid_selection(selected_id):
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=selected_id,
            active_panel=active_panel,
            active_archetype=active_archetype,
            has_existing_canvas=has_existing_canvas,
            route="composition_worker",
        )

    if active_panel in {"content", "style", "structure"}:
        route = "composition_worker"
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=selected_id,
            active_panel=active_panel,
            active_archetype=active_archetype,
            has_existing_canvas=has_existing_canvas,
            route=route,
        )

    if active_panel == "main" and (
        _looks_like_asset_request(user_query)
        or _looks_like_ingest_request(user_query)
        or _looks_like_review_request(user_query)
    ):
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=selected_id,
            active_panel=active_panel,
            active_archetype=active_archetype,
            has_existing_canvas=has_existing_canvas,
            route="retrieval_worker",
        )

    if active_panel == "main" and has_existing_canvas and looks_like_append_block_request(user_query):
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=None,
            active_panel=active_panel,
            active_archetype=active_archetype,
            has_existing_canvas=has_existing_canvas,
            route="retrieval_worker",
        )

    if active_panel == "main" and has_existing_canvas and looks_like_revision_review_request(user_query):
        return {
            "intent_decision": IntentDecision(
                thought_process="",
                reason="复盘建议快速路由",
                task_type="inspect",
                operation_type="generate",
                scope="selected_block" if _has_valid_selection(selected_id) else "global_canvas",
                needs_research=False,
                needs_assets=False,
                confidence=0.95,
                fallback_required=False,
                risk_flags=[],
            ).model_dump(),
            "intent_route": "critique_worker",
            "selected_element_id": selected_id,
            "scenarios": ["notes"],
            "scenario_scores": {"notes": 1.0},
            "active_archetype": "notes",
            "worker_prompts": {
                "intent_worker": [
                    {
                        "role": "system",
                        "content": "Intent Fast Path: critique review requested on existing artifact",
                    }
                ]
            },
            "agent_backends": {"intent_worker": "deterministic_revision_review_fast_path"},
        }

    if active_panel == "main" and has_existing_canvas and looks_like_existing_canvas_edit(user_query):
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=selected_id,
            active_panel=active_panel,
            active_archetype=active_archetype,
            has_existing_canvas=has_existing_canvas,
            route=infer_existing_canvas_edit_route(user_query),
        )

    if looks_like_capability_query(user_query):
        return {
            "intent_decision": IntentDecision(
                thought_process="",
                reason="能力问答",
                task_type="inspect",
                operation_type="generate",
                scope="session_workspace",
                needs_research=False,
                needs_assets=False,
                confidence=0.96,
                fallback_required=False,
                risk_flags=[],
            ).model_dump(),
            "intent_route": "supervisor_agent",
            "selected_element_id": selected_id,
            "scenarios": ["notes"],
            "scenario_scores": {"notes": 1.0},
            "active_archetype": "notes",
            "agent_backends": {"intent_worker": "deterministic_capability_fast_path"},
        }

    llm = get_intent_llm()
    outline = [
        {"id": str(block.get("id") or ""), "type": str(block.get("component_type") or "")}
        for block in list(execution_view.get("blocks") or [])
        if block.get("id") and block.get("component_type")
    ]
    current_time = datetime.now().strftime("%Y-%m-%d %A")
    prompt = build_chat_prompt(
        system_template_name="workers/intent_system.md",
        human_template="【当前时间】: {{ current_time }}\n【正式业务】: 持续笔记协作\n【用户指令】: {{ query }}",
    )
    structured_llm = llm.with_structured_output(IntentDecision, method="function_calling")

    try:
        inputs = {
            "current_time": current_time,
            "valid_scenarios": ", ".join(valid_scenarios),
            "data_context": json.dumps(outline, ensure_ascii=False),
            "selected_element": selected_id if selected_id else "无",
            "active_archetype": active_archetype,
            "query": user_query,
        }
        prompt_messages = render_prompt_messages(prompt, inputs)
        chain = prompt | structured_llm
        attempt = 0
        result = None
        while attempt < 2:
            try:
                result = await chain.ainvoke(inputs, config={"timeout": 45.0})
                break
            except Exception as loop_error:
                attempt += 1
                if attempt >= 2:
                    raise loop_error
                await asyncio.sleep(1)

        intent_decision = _normalize_intent_decision(result)
        derived_route = _derive_route_from_intent_decision(intent_decision, user_query=user_query, selected_id=selected_id)
        print(
            f"🧭 [意图网关] task={intent_decision.get('task_type')} | "
            f"op={intent_decision.get('operation_type')} | scope={intent_decision.get('scope')} | "
            f"research={intent_decision.get('needs_research')} | assets={intent_decision.get('needs_assets')} | "
            f"confidence={intent_decision.get('confidence')}"
        )
        return {
            "intent_decision": intent_decision,
            "intent_route": derived_route,
            "selected_element_id": selected_id,
            "scenarios": ["notes"],
            "scenario_scores": {"notes": 1.0},
            "active_archetype": "notes",
            "thought_process": result.thought_process,
            "worker_prompts": build_prompt_snapshot("intent_worker", messages=prompt_messages),
            "agent_backends": {"intent_worker": "structured_function_calling"},
        }
    except Exception as error:
        print(f"❌ Intent Agent 失败: {error}")
        return {
            "intent_route": "retrieval_worker",
            "scenarios": ["notes"],
            "scenario_scores": {"notes": 1.0},
            "active_archetype": "notes",
            "agent_backends": {"intent_worker": "fallback_route"},
        }


