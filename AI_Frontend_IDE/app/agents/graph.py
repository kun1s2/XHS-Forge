"""Primary LangGraph runtime for the note workspace.

The graph keeps user-facing orchestration explicit:
- agent nodes handle routing/planning/edit decisions
- deterministic nodes resolve blocks, compile themes, verify, and render
- state stays centralized so rollback, tracing, and workspace restore remain stable
"""

import time
import functools
import json
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

# 引入我们定义的全局状态
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.query_heuristics import looks_like_existing_canvas_edit
from app.core.schema import OutlineOutput
from app.core.note_document import build_note_document_layout_from_state, build_note_document_from_state, build_note_document_from_structure_patch
from app.core.component_manifest import resolve_component_for_block_intent

# 引入节点
from app.agents.nodes.asset_node import asset_processor_node
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.research_agent import research_agent
from app.agents.nodes.distill_node import distill_node # ✨ 导入提纯节点
from app.agents.nodes.review_node import controversy_sniffer_node
from app.agents.nodes.structure_node import structure_agent
from app.agents.nodes.patch_node import surgical_patch_agent
from app.agents.nodes.style_node import style_agent
from app.agents.nodes.render_node import render_node
from app.agents.nodes.refusal_node import refusal_node
from app.agents.nodes.battle_node import battle_node
from app.agents.nodes.component_builder import component_builder_node
from app.agents.nodes.note_editor_node import note_editor_node
from app.agents.nodes.planner_node import planner_node
from app.agents.nodes.verify_note_node import verify_note_node
from app.agents.tools_registry import RESEARCH_TOOLS
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import summarize_confirmed_attributes
from app.core.runtime_log import append_latest_console_log

def with_performance_profiling(node_name: str, func):
    @functools.wraps(func)
    async def wrapper(state: UIProjectState):
        start_time = time.perf_counter()
        try:
            result = await func(state)
            elapsed = time.perf_counter() - start_time
            message = f"⏱️ [性能监控] 节点 {node_name} 完毕, 耗时: {elapsed:.2f}s"
            print(f"⏱️ [性能监控] 节点 {node_name} 完毕, 耗时: \033[93m{elapsed:.2f}s\033[0m")
            append_latest_console_log(message)
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            message = f"❌ [性能监控] 节点 {node_name} 失败, 耗时: {elapsed:.2f}s"
            print(f"❌ [性能监控] 节点 {node_name} 失败, 耗时: \033[91m{elapsed:.2f}s\033[0m")
            append_latest_console_log(message)
            raise e
    return wrapper

def with_context_engineering(node_func):
    @functools.wraps(node_func)
    async def wrapper(state: UIProjectState):
        cloned_state = state.copy()
        cloned_state["messages"] = [] 
        return await node_func(cloned_state)
    return wrapper


def _has_local_selection(state: UIProjectState) -> bool:
    selected = state.get("selected_element_id")
    return selected not in [None, "", "无", "无 (全局修改)", "none"]


def _has_existing_canvas(state: UIProjectState) -> bool:
    execution_view = build_note_document_layout_from_state(state)
    return bool(execution_view.get("blocks"))


def _latest_user_text(state: UIProjectState) -> str:
    main_msgs = state.get("main_messages", []) or []
    if not main_msgs:
        return ""
    content = getattr(main_msgs[-1], "content", "") or ""
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                text_parts.append(str(part.get("text")))
        return "".join(text_parts).strip()
    return str(content)


def _materialize_blocks_from_planner(state: UIProjectState) -> list[dict[str, Any]]:
    planner_output = state.get("planner_output") or {}
    block_intents = list(planner_output.get("block_intents") or [])
    if not block_intents:
        return []

    blocks = []
    seen_types: set[str] = set()
    for idx, intent in enumerate(block_intents):
        intent_type = str(intent.get("intent_type") or "narrative_text")
        preferred_component = intent.get("preferred_component")
        component_type = preferred_component or resolve_component_for_block_intent(
            intent_type,
            has_images=bool(state.get("image_assets")),
            scenario_scores=planner_output.get("scenario_scores") or {},
        )
        if not component_type:
            continue
        base_id = component_type.replace("Block", "").replace("Card", "").lower()
        block_id = f"{base_id}_{idx + 1}"
        if component_type in seen_types and intent_type not in {"narrative_text"}:
            continue
        seen_types.add(component_type)
        brief = str(intent.get("goal") or intent_type.replace("_", " ")).strip()
        if component_type == "TitleBlock":
            brief = brief or "页面标题"
        elif component_type == "StoryText":
            brief = brief or "正文叙事"
        blocks.append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": brief,
        })
    return blocks


def route_intent(state: UIProjectState) -> str:
    intent_v2 = state.get("intent_result_v2") or {}
    task_type = str(intent_v2.get("task_type") or "").lower()
    edit_scope = str(intent_v2.get("edit_scope") or "").lower()
    needs_research = bool(intent_v2.get("needs_research"))

    route = str(state.get("intent_route", "") or "").lower()
    has_local_selection = _has_local_selection(state)
    has_existing_canvas = _has_existing_canvas(state)
    latest_user_text = _latest_user_text(state)

    if task_type == "refuse" or "refusal" in route:
        return "refusal_node"

    if edit_scope in {"selected_block", "selected_paragraph"} or has_local_selection:
        return "note_editor"

    if task_type == "edit":
        return "note_editor"

    if has_existing_canvas and looks_like_existing_canvas_edit(latest_user_text):
        return "note_editor"

    if task_type == "create":
        return "research_agent"

    if task_type in {"inspect", "confirm_fact"}:
        return END

    if "patch" in route:
        return "patch_node"
    if any(kw in route for kw in ["content", "文案", "rag", "search", "image", "图"]) or needs_research:
        return "research_agent"
    if "structure" in route or "结构" in route or "style" in route or "样式" in route:
        return "note_editor"
    return END

async def outline_synthesizer(state: UIProjectState) -> dict:
    """
    【大纲合成器】：验证并收束 block skeleton，直接产出 NoteDocument。
    """
    current_note_document = build_note_document_from_state(state)
    execution_view = build_note_document_layout_from_state(state)
    blocks = [
        {
            "id": block.get("id"),
            "component_type": block.get("component_type"),
            "content_brief": block.get("content_brief", ""),
        }
        for block in execution_view.get("blocks", [])
    ]
    if not blocks and settings.ENABLE_PLANNER_V2:
        blocks = _materialize_blocks_from_planner(state)
    retrieved_knowledge = state.get("retrieved_knowledge", {}) if isinstance(state.get("retrieved_knowledge", {}), dict) else {}
    planner_output = state.get("planner_output") or {}
    main_msgs = state.get("main_messages", []) or []
    user_query = str(getattr(main_msgs[-1], "content", "") or "") if main_msgs else ""
    entity_name = normalize_entity_name(retrieved_knowledge.get("entity_name") or user_query or "这篇笔记")
    summary = str(retrieved_knowledge.get("summary") or "").strip()
    selling_points = [str(item).strip() for item in (retrieved_knowledge.get("key_selling_points") or []) if str(item).strip()]
    confirmed_summaries = summarize_confirmed_attributes(retrieved_knowledge)

    def _append_guard_block(component_type: str, content_brief: str, *, insert_at: int | None = None):
        nonlocal blocks
        existing_ids = {str(block.get("id") or "") for block in blocks}
        prefix = "title" if component_type == "TitleBlock" else "story"
        candidate_id = f"{prefix}_{len(blocks) + 1}"
        serial = 1
        while candidate_id in existing_ids:
            serial += 1
            candidate_id = f"{prefix}_{serial}"
        guard_block = {
            "id": candidate_id,
            "component_type": component_type,
            "content_brief": content_brief,
        }
        if insert_at is None or insert_at >= len(blocks):
            blocks.append(guard_block)
        else:
            blocks.insert(max(insert_at, 0), guard_block)

    has_title = any(block.get("component_type") == "TitleBlock" for block in blocks)
    has_story = any(block.get("component_type") == "StoryText" for block in blocks)

    if not has_title:
        _append_guard_block("TitleBlock", f"{entity_name} 深度种草", insert_at=0)

    if not has_story:
        story_parts = []
        if summary:
            story_parts.append(summary)
        if confirmed_summaries:
            story_parts.append("已确认参数：" + " / ".join(confirmed_summaries[:3]))
        if selling_points:
            story_parts.append("亮点速读：" + " / ".join(selling_points[:3]))
        if not story_parts:
            story_parts.append(f"围绕 {entity_name} 做一段有观点、有节奏的正文总结。")
        title_index = next((idx for idx, block in enumerate(blocks) if block.get("component_type") == "TitleBlock"), -1)
        _append_guard_block("StoryText", " ".join(story_parts), insert_at=title_index + 1 if title_index >= 0 else 0)
    
    # 校验并强制填充必要的字段
    for i, b in enumerate(blocks):
        if not b.get("id"): b["id"] = f"block_{i}"

    current_title = str(((current_note_document.get("document_meta") or {}).get("title") or "")).strip()
    resolved_page_title = current_title if current_title and current_title != "XHS-Forge Note" else f"{entity_name} 深度种草"
    print(f"✅ [大纲合成] 画布定稿，共 {len(blocks)} 个区块。")
    next_note_document = build_note_document_from_structure_patch(
        current_note_document,
        page_title=resolved_page_title,
        blocks=blocks,
    )
    return {"note_document": next_note_document}


async def outline_resolver_node(state: UIProjectState) -> dict:
    """
    【现代化大纲解析器】：
    直接消费 planner.block_intents 与 component manifest，确定性产出 block skeleton。
    不再走 历史工具循环。
    """
    note_document = build_note_document_from_state(state)
    if not (note_document.get("blocks") or []):
        synthesized = await outline_synthesizer(state)
    else:
        synthesized = {"note_document": note_document}

    planner_output = state.get("planner_output") or {}
    block_intents = [
        str(item.get("intent_type") or "")
        for item in list(planner_output.get("block_intents") or [])
        if str(item.get("intent_type") or "").strip()
    ]
    blocks = list((synthesized.get("note_document") or {}).get("blocks") or [])
    return {
        **synthesized,
        "turn_trace": {
            "outline": {
                "mode": "resolver",
                "resolution_source": "manifest_semantic_role",
                "block_intents": block_intents,
                "resolved_components": [str(block.get("type") or "") for block in blocks],
                "block_count": len(blocks),
            }
        },
        "agent_backends": {"outline_resolver": "deterministic_resolver"},
    }

def map_components(state: UIProjectState) -> list:
    execution_view = build_note_document_layout_from_state(state)
    blocks = execution_view.get("blocks", [])
    if not blocks: return ["style_node"]
    
    user_query = _latest_user_text(state)
    active_archetype = state.get("active_archetype", "general")
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    creator_persona = state.get("creator_persona", "硬核数码博主")
    
    return [
        Send("component_builder", {
            "component_id": b["id"],
            "component_type": b["component_type"],
            "content_brief": b.get("content_brief", "填充内容"),
            "user_query": user_query,
            "active_archetype": active_archetype,
            "retrieved_knowledge": retrieved_knowledge,
            "creator_persona": creator_persona,
            "image_assets": state.get("image_assets", []),
            "planner_policy": state.get("planner_policy", {}),
            "content_messages": [] 
        })
        for b in blocks
    ] + ["style_node"]

def compile_my_graph(checkpointer: BaseCheckpointSaver, store: BaseStore = None):
    workflow = StateGraph(UIProjectState)

    # 1. 注册节点
    workflow.add_node("asset_processor", with_performance_profiling("asset_processor", asset_processor_node))
    workflow.add_node("intent_agent", with_performance_profiling("intent_agent", intent_agent))
    workflow.add_node("refusal_node", with_performance_profiling("refusal_node", refusal_node))
    workflow.add_node("research_agent", with_performance_profiling("research_agent", research_agent))
    workflow.add_node("tools", ToolNode(RESEARCH_TOOLS)) 
    workflow.add_node("distill_node", with_performance_profiling("distill_node", distill_node)) # ✨ 注册提纯节点
    workflow.add_node("controversy_sniffer", with_performance_profiling("controversy_sniffer", controversy_sniffer_node))
    workflow.add_node("battle_node", with_performance_profiling("battle_node", battle_node))
    
    workflow.add_node("outline_resolver", with_performance_profiling("outline_resolver", outline_resolver_node))

    workflow.add_node("component_builder", component_builder_node)
    workflow.add_node("planner", with_performance_profiling("planner", planner_node))
    workflow.add_node("note_editor", with_performance_profiling("note_editor", note_editor_node))
    workflow.add_node("verify_note", with_performance_profiling("verify_note", verify_note_node))
    workflow.add_node("structure_node", with_performance_profiling("structure_node", structure_agent))
    workflow.add_node("patch_node", with_performance_profiling("patch_node", surgical_patch_agent))
    workflow.add_node("style_node", with_performance_profiling("style_node", style_agent))
    workflow.add_node("render", with_performance_profiling("render", render_node))

    # 2. 核心连接
    workflow.add_edge(START, "asset_processor")
    workflow.add_edge("asset_processor", "intent_agent")

    workflow.add_conditional_edges("intent_agent", route_intent, {
        "patch_node": "patch_node",
        "research_agent": "research_agent",
        "note_editor": "note_editor",
        "refusal_node": "refusal_node",
        END: END
    })

    workflow.add_edge("patch_node", "render")
    workflow.add_edge("note_editor", "verify_note")
    workflow.add_edge("verify_note", "style_node")
    workflow.add_edge("refusal_node", END)

    # RAG 链：决策与物理强取 -> 提纯 -> 争议嗅探
    workflow.add_edge("research_agent", "distill_node")
    workflow.add_edge("distill_node", "controversy_sniffer")
    workflow.add_edge("controversy_sniffer", "battle_node")
    
    if settings.ENABLE_PLANNER_V2:
        workflow.add_edge("battle_node", "planner")
        workflow.add_edge("planner", "outline_resolver")
    else:
        workflow.add_edge("battle_node", "outline_resolver")

    # 解析完毕后分发并发任务
    workflow.add_conditional_edges("outline_resolver", map_components, ["component_builder", "style_node"])
    
    workflow.add_edge("style_node", "render")
    workflow.add_edge("render", END)

    interrupt_nodes = ["controversy_sniffer"] if settings.HITL_ENABLED else []

    return workflow.compile(checkpointer=checkpointer, store=store, interrupt_before=interrupt_nodes)
