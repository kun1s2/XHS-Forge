import json
import re
import os
import asyncio
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import IntentGatewayOutput
from app.core.note_document import build_note_document_layout_from_state
from app.core.query_heuristics import (
    infer_existing_canvas_edit_route,
    looks_like_existing_canvas_edit,
    mentions_paragraph_reference,
)
from app.core.prompt_engineering import build_chat_prompt, build_prompt_snapshot, render_prompt_messages
from app.services.scenario_manager import scenario_manager

# ✨ 性能优化：全局复用 LLM 实例
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
            max_retries=1
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


def _build_fast_path_result(*, user_query: str, selected_id: str | None, active_archetype: str, route: str = "patch_node") -> dict:
    scenario = str(active_archetype or "general")
    intent_v2 = IntentGatewayOutput(
        thought_process="",
        reason="局部编辑快速通道",
        task_type="edit",
        edit_scope="selected_paragraph" if mentions_paragraph_reference(user_query) else "selected_block",
        needs_research=False,
        needs_assets="none",
        scenario_scores={scenario: 1.0},
        risk_flags=[],
    ).model_dump()
    return {
        "intent_result_v2": intent_v2,
        "intent_route": route,
        "selected_element_id": selected_id,
        "scenarios": [scenario],
        "scenario_scores": intent_v2.get("scenario_scores", {}),
        "active_archetype": scenario,
        "node_prompts": {
            "intent_agent": [
                {
                    "role": "system",
                    "content": f"Gateway V2 Fast Path: task={intent_v2.get('task_type')}, scope={intent_v2.get('edit_scope')}, assets={intent_v2.get('needs_assets')}, scenarios={intent_v2.get('scenario_scores')}",
                }
            ]
        },
        "agent_backends": {"intent_agent": "deterministic_fast_path"},
    }


def _build_panel_edit_fast_path(*, user_query: str, active_panel: str, active_archetype: str, selected_id: str | None) -> dict:
    scenario = str(active_archetype or "general")
    route_by_panel = {
        "content": "note_editor",
        "style": "theme_compiler",
        "structure": "structure_node",
    }
    route = route_by_panel.get(str(active_panel or ""))
    if not route:
        return {}
    intent_v2 = IntentGatewayOutput(
        thought_process="",
        reason=f"{active_panel} 面板全局编辑快速通道",
        task_type="edit",
        edit_scope="global",
        needs_research=False,
        needs_assets="none",
        scenario_scores={scenario: 1.0},
        risk_flags=[],
    ).model_dump()
    return {
        "intent_result_v2": intent_v2,
        "intent_route": route,
        "selected_element_id": selected_id,
        "scenarios": [scenario],
        "scenario_scores": intent_v2.get("scenario_scores", {}),
        "active_archetype": scenario,
        "node_prompts": {
            "intent_agent": [
                {
                    "role": "system",
                    "content": f"Gateway V2 Panel Fast Path: panel={active_panel}, task={intent_v2.get('task_type')}, scope={intent_v2.get('edit_scope')}, scenarios={intent_v2.get('scenario_scores')}",
                }
            ]
        },
        "agent_backends": {"intent_agent": "deterministic_fast_path"},
    }


def _build_existing_canvas_edit_fast_path(*, user_query: str, active_archetype: str, selected_id: str | None) -> dict:
    scenario = str(active_archetype or "general")
    route = infer_existing_canvas_edit_route(user_query)
    intent_v2 = IntentGatewayOutput(
        thought_process="",
        reason="main 面板已有画布编辑快速通道",
        task_type="edit",
        edit_scope="global",
        needs_research=False,
        needs_assets="none",
        scenario_scores={scenario: 1.0},
        risk_flags=[],
    ).model_dump()
    return {
        "intent_result_v2": intent_v2,
        "intent_route": route,
        "selected_element_id": selected_id,
        "scenarios": [scenario],
        "scenario_scores": intent_v2.get("scenario_scores", {}),
        "active_archetype": scenario,
        "node_prompts": {
            "intent_agent": [
                {
                    "role": "system",
                    "content": f"Gateway V2 Existing Canvas Fast Path: route={route}, task={intent_v2.get('task_type')}, scope={intent_v2.get('edit_scope')}, scenarios={intent_v2.get('scenario_scores')}",
                }
            ]
        },
        "agent_backends": {"intent_agent": "deterministic_fast_path"},
    }

def _normalize_gateway_result(result: IntentGatewayOutput) -> dict:
    payload = result.model_dump()
    scenario_scores = payload.get("scenario_scores") or {}
    if not scenario_scores:
        scenario_scores = {"general": 1.0}
    payload["scenario_scores"] = {str(name): float(score) for name, score in scenario_scores.items()}
    return payload


def _derive_route_from_intent_v2(intent_v2: dict, *, user_query: str, selected_id: str | None) -> str:
    task_type = str(intent_v2.get("task_type") or "create").lower()
    edit_scope = str(intent_v2.get("edit_scope") or "none").lower()
    needs_assets = str(intent_v2.get("needs_assets") or "none").lower()
    needs_research = bool(intent_v2.get("needs_research"))

    if task_type == "refuse":
        return "refusal_node"
    if edit_scope in {"selected_block", "selected_paragraph"} and _has_valid_selection(selected_id):
        return "patch_node"
    if task_type == "edit":
        return infer_existing_canvas_edit_route(user_query)
    if task_type == "inspect":
        return "patch_node"
    if task_type == "confirm_fact":
        return "patch_node"
    if needs_assets == "search" or needs_research:
        return "research_agent"
    return "research_agent"

async def intent_agent(state: UIProjectState) -> dict:
    """
    【意图路由大脑 3.0】：具备动态场景发现能力的智能网关。
    """
    # 1. 动态获取当前系统安装的所有场景 ID（解耦核心）
    VALID_SCENARIOS = scenario_manager.list_all_scenarios()
    
    # 2. 状态提取
    execution_view = build_note_document_layout_from_state(state)
    selected_id = state.get("selected_element_id")
    active_archetype = state.get("active_archetype", "general")
    has_existing_canvas = bool(execution_view.get("blocks"))
    active_panel = state.get("active_panel", "main")
    
    messages = state.get(f"{active_panel}_messages", [])
    if not messages:
        return {"intent_route": "END", "agent_backends": {"intent_agent": "skipped_no_messages"}}
    user_query = _extract_user_text(messages[-1].content)

    if active_panel != "main" and _has_valid_selection(selected_id):
        print(f"⚡ [意图网关] 命中局部编辑快速通道: panel={active_panel} | selected={selected_id}")
        return _build_fast_path_result(
            user_query=user_query,
            selected_id=selected_id,
            active_archetype=active_archetype,
            route="patch_node",
        )

    if active_panel in {"content", "style", "structure"} and user_query:
        print(f"⚡ [意图网关] 命中子面板全局编辑快速通道: panel={active_panel}")
        return _build_panel_edit_fast_path(
            user_query=user_query,
            active_panel=active_panel,
            active_archetype=active_archetype,
            selected_id=selected_id,
        )

    if active_panel == "main" and has_existing_canvas and user_query and looks_like_existing_canvas_edit(user_query):
        print("⚡ [意图网关] 命中 main 面板已有画布编辑快速通道")
        return _build_existing_canvas_edit_fast_path(
            user_query=user_query,
            active_archetype=active_archetype,
            selected_id=selected_id,
        )

    llm = get_intent_llm()

    # 获取页面大纲 (ID + Type)
    outline = [
        {"id": str(block.get("id") or ""), "type": str(block.get("component_type") or "")}
        for block in list(execution_view.get("blocks") or [])
        if block.get("id") and block.get("component_type")
    ]

    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %A")

    # 3. 加载提示词
    prompt = build_chat_prompt(
        system_template_name="intent_gateway_v2.xml",
        human_template="【当前时间】: {{ current_time }}\n【可用场景池】: {{ valid_scenarios }}\n【用户指令】: {{ query }}",
    )

    structured_llm = llm.with_structured_output(IntentGatewayOutput, method="function_calling")
    
    try:
        inputs = {
            "current_time": current_time,
            "valid_scenarios": ", ".join(VALID_SCENARIOS),
            "data_context": json.dumps(outline, ensure_ascii=False),
            "selected_element": selected_id if selected_id else "无", 
            "active_archetype": active_archetype, 
            "query": user_query
        }
        prompt_messages = render_prompt_messages(prompt, inputs)
        
        try:
            print(f"📡 [意图路由] 正在分析指令 4.0，支持场景: {VALID_SCENARIOS}")
            chain = prompt | structured_llm
            # 自定义重试回路
            from pydantic import ValidationError
            max_retries = 2
            attempt = 0
            result = None
            while attempt < max_retries:
                try:
                    result = await chain.ainvoke(inputs, config={"timeout": 45.0})
                    break
                except Exception as loop_e:
                    attempt += 1
                    print(f"⚠️ [Intent Agent] 内部调用出错 (尝试 {attempt}/{max_retries}): {loop_e}")
                    if attempt >= max_retries:
                        raise loop_e
                    await asyncio.sleep(1)
            
            effective_id = selected_id
            intent_v2 = _normalize_gateway_result(result)
            filtered_scores = {
                scenario: score
                for scenario, score in (intent_v2.get("scenario_scores") or {}).items()
                if scenario in VALID_SCENARIOS or scenario == "general"
            }
            if not filtered_scores:
                filtered_scores = {"general": 1.0}
            intent_v2["scenario_scores"] = filtered_scores
            final_scenarios = list(filtered_scores.keys()) or ["general"]
            derived_route = _derive_route_from_intent_v2(intent_v2, user_query=user_query, selected_id=effective_id)
            print(f"🧭 [意图网关] task={intent_v2.get('task_type')} | scope={intent_v2.get('edit_scope')} | research={intent_v2.get('needs_research')} | assets={intent_v2.get('needs_assets')} | scenarios={intent_v2.get('scenario_scores')}")

            return {
                "intent_result_v2": intent_v2,
                "intent_route": derived_route,
                "selected_element_id": effective_id,
                "scenarios": final_scenarios,
                "scenario_scores": intent_v2.get("scenario_scores", {}),
                "active_archetype": final_scenarios[0],
                "thought_process": result.thought_process,
                "node_prompts": build_prompt_snapshot("intent_agent", messages=prompt_messages),
                "agent_backends": {"intent_agent": "structured_function_calling"}
            }
                    
        except Exception as e:
            from pydantic import ValidationError
            if isinstance(e, ValidationError):
                # 触发本地自纠错回路
                print(f"⚠️ [Intent Agent] 遇到 Schema 校验错误，进行本地自纠错重试...")
                # 这里我们假设框架会自动重试或者可以简易进行最多 1 次重试
                pass
            print(f"❌ Intent Agent 失败: {e}")
            return {"intent_route": "structure_node", "scenarios": ["general"], "agent_backends": {"intent_agent": "fallback_route"}}
                    
    except Exception as e:
        print(f"❌ Intent Agent 外层失败: {e}")
        return {"intent_route": "structure_node", "scenarios": ["general"], "agent_backends": {"intent_agent": "fallback_route"}}
