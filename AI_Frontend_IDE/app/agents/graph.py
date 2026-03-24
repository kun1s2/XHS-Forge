"""笔记工作台的主 LangGraph 运行时。

这张图负责把用户请求编排成一条明确的执行链：
- agent 节点负责路由、规划和编辑决策
- 确定性节点负责大纲解析、组件构建、主题编译、校验和渲染
- 状态集中在统一 state 中，保证回滚、追踪和 workspace 恢复稳定
"""

import time
import functools
import json
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.store.base import BaseStore
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

# 引入我们定义的全局状态
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.query_heuristics import looks_like_existing_canvas_edit
from app.core.request_semantics import (
    has_local_selection as request_has_local_selection,
    latest_user_text_from_messages,
    state_requests_create,
)
from app.core.schema import OutlineOutput
from app.core.note_document import build_note_document_layout_from_state, build_note_document_from_state, build_note_document_from_structure_patch
from app.core.component_manifest import (
    normalize_component_type,
    resolve_component_candidates_for_block_intent,
    resolve_component_for_block_intent,
)

# 引入节点
from app.agents.nodes.asset_node import asset_processor_node
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.direct_chat_node import direct_chat_node
from app.agents.nodes.retrieval_agent_node import retrieval_agent_node
from app.agents.nodes.distill_node import distill_node # ✨ 导入提纯节点
from app.agents.nodes.review_node import controversy_sniffer_node
from app.agents.nodes.structure_node import structure_agent
from app.agents.nodes.patch_node import surgical_patch_agent
from app.agents.nodes.theme_compiler_node import theme_compiler
from app.agents.nodes.document_renderer_node import document_renderer
from app.agents.nodes.refusal_node import refusal_node
from app.agents.nodes.battle_node import battle_node
from app.agents.nodes.component_builder import component_builder_node
from app.agents.nodes.composition_agent_node import composition_agent_node
from app.agents.nodes.planner_node import planner_node
from app.agents.nodes.retrieval_gap_fill_node import retrieval_gap_fill_node
from app.agents.nodes.conversational_checkpoint_nodes import (
    asset_checkpoint_node,
    fact_conflict_checkpoint_node,
    fact_gap_checkpoint_node,
    knowledge_review_checkpoint_node,
    structure_checkpoint_node,
    truth_mode_checkpoint_node,
)
from app.agents.nodes.verify_note_node import verify_note_node
from app.agents.nodes.critique_agent import critique_node
from app.agents.tools_registry import RESEARCH_TOOLS
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import summarize_confirmed_attributes
from app.core.runtime_log import append_latest_console_log

def with_performance_profiling(node_name: str, func):
    """给节点包一层耗时统计，并统一写入运行日志。"""
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
        except GraphInterrupt:
            elapsed = time.perf_counter() - start_time
            message = f"⏸️ [性能监控] 节点 {node_name} 等待用户确认, 耗时: {elapsed:.2f}s"
            print(f"⏸️ [性能监控] 节点 {node_name} 等待用户确认, 耗时: \033[96m{elapsed:.2f}s\033[0m")
            append_latest_console_log(message)
            raise
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            message = f"❌ [性能监控] 节点 {node_name} 失败, 耗时: {elapsed:.2f}s"
            print(f"❌ [性能监控] 节点 {node_name} 失败, 耗时: \033[91m{elapsed:.2f}s\033[0m")
            append_latest_console_log(message)
            raise e
    return wrapper

def with_context_engineering(node_func):
    """为节点提供轻量上下文隔离，避免历史消息直接污染局部调用。"""
    @functools.wraps(node_func)
    async def wrapper(state: UIProjectState):
        cloned_state = state.copy()
        cloned_state["messages"] = [] 
        return await node_func(cloned_state)
    return wrapper


def _has_local_selection(state: UIProjectState) -> bool:
    """判断当前请求是否已经命中了局部选中目标。"""
    return request_has_local_selection(state.get("selected_element_id"))


def _has_existing_canvas(state: UIProjectState) -> bool:
    """判断当前工作台是否已经存在可编辑画布。"""
    execution_view = build_note_document_layout_from_state(state)
    return bool(execution_view.get("blocks"))


def _latest_user_text(state: UIProjectState) -> str:
    """提取主会话里最后一条用户文本。"""
    return latest_user_text_from_messages(state.get("main_messages", []) or [])


def _is_create_request(state: UIProjectState) -> bool:
    """判断当前请求是否属于需要重新铺开页面的创建任务。"""
    return state_requests_create(state)


def _materialize_blocks_from_planner(state: UIProjectState) -> list[dict[str, Any]]:
    """把 planner 的 block intents 物化成最小 block skeleton。"""
    planner_output = state.get("planner_output") or {}
    block_intents = list(planner_output.get("block_intents") or [])
    if not block_intents:
        return []

    scenario_scores = planner_output.get("scenario_scores") or {}
    active_archetype = str(state.get("active_archetype") or "seeding")
    user_query = _latest_user_text(state)
    retrieved_knowledge = state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {}
    has_images = bool(state.get("image_assets"))

    def _supports_component(component_type: str, intent_type: str) -> bool:
        normalized_type = normalize_component_type(component_type) or component_type
        query = user_query
        fact_slots = retrieved_knowledge.get("fact_slots") if isinstance(retrieved_knowledge.get("fact_slots"), dict) else {}
        confirmed_facts = retrieved_knowledge.get("confirmed_facts") if isinstance(retrieved_knowledge.get("confirmed_facts"), dict) else {}
        if normalized_type == "CoverSwiper":
            return has_images
        if normalized_type == "WeatherPolaroid":
            return has_images or any(token in query for token in ("氛围", "天气", "风景", "照片", "海边", "夜景"))
        if normalized_type == "TimelineBlock":
            return any(token in query for token in ("行程", "路线", "一日游", "攻略", "顺序", "安排", "怎么玩")) or any(
                key in fact_slots for key in ("timeline", "route", "duration", "transport")
            )
        if normalized_type == "LocationBlock":
            return any(
                token in query for token in ("地点", "地址", "位置", "怎么去", "店铺")
            ) or any(key in fact_slots or key in confirmed_facts for key in ("location",))
        if normalized_type == "ProductSpecCard":
            if active_archetype == "seeding":
                return True
            return any(token in query for token in ("价格", "预算", "参数", "配置", "规格", "套餐", "门票", "人均", "值不值得", "怎么选")) or bool(
                retrieved_knowledge.get("core_attributes") or confirmed_facts
            )
        if normalized_type == "RadarChartBlock":
            if active_archetype == "seeding":
                return True
            return any(token in query for token in ("评分", "雷达", "维度", "综合判断", "优缺点", "对比")) and (
                len(retrieved_knowledge.get("key_selling_points") or []) >= 3 or len(confirmed_facts) >= 3
            )
        if normalized_type == "QuoteBlock":
            return any(token in query for token in ("一句话", "金句", "引用", "原话", "总结"))
        if normalized_type == "VersusCard":
            return bool(retrieved_knowledge.get("battle_report")) or any(token in query for token in ("对比", "区别", "优缺点", "更适合", "pk", "vs"))
        if normalized_type == "PollBlock":
            return any(token in query for token in ("投票", "站队", "你选", "更喜欢")) or bool(state.get("has_controversy"))
        if normalized_type == "StoryText":
            return True
        return True

    def _select_component(intent: dict[str, Any], intent_type: str) -> str | None:
        candidates = [
            normalize_component_type(item) or str(item or "").strip()
            for item in list(intent.get("candidate_components") or [])
            if str(item or "").strip()
        ]
        if not candidates:
            candidates = resolve_component_candidates_for_block_intent(
                intent_type,
                has_images=has_images,
                scenario_scores=scenario_scores,
                user_query=user_query,
                active_archetype=active_archetype,
                retrieved_knowledge=retrieved_knowledge,
                preferred_component=intent.get("preferred_component"),
            )
        if not candidates:
            preferred_component = intent.get("preferred_component")
            fallback = preferred_component or resolve_component_for_block_intent(
                intent_type,
                has_images=has_images,
                scenario_scores=scenario_scores,
            )
            candidates = [fallback] if fallback else []
        for candidate in candidates:
            if _supports_component(candidate, intent_type):
                return candidate
        return candidates[0] if candidates else None

    blocks = []
    seen_types: set[str] = set()
    for idx, intent in enumerate(block_intents):
        intent_type = str(intent.get("intent_type") or "narrative_text")
        component_type = _select_component(intent, intent_type)
        if not component_type:
            continue
        base_id = component_type.replace("Block", "").replace("Card", "").lower()
        block_id = f"{base_id}_{idx + 1}"
        if component_type in seen_types and intent_type not in {"narrative_text"} and component_type not in {"StoryText"}:
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
    """把网关输出映射到下一个工作流节点。

    这里特别强调顺序：明显的编辑请求先走便宜的确定性判断，再决定是否进入
    更重的创建/搜证链路，避免已有画布编辑多绕一层。
    """
    intent_decision = state.get("intent_decision") or {}
    task_type = str(intent_decision.get("task_type") or "").lower()
    scope = str(intent_decision.get("scope") or "").lower()
    operation_type = str(intent_decision.get("operation_type") or "").lower()
    needs_research = bool(intent_decision.get("needs_research"))
    needs_assets = bool(intent_decision.get("needs_assets"))
    fallback_required = bool(intent_decision.get("fallback_required"))

    route = str(state.get("intent_route", "") or "").lower()
    has_local_selection = _has_local_selection(state)
    has_existing_canvas = _has_existing_canvas(state)
    latest_user_text = _latest_user_text(state)

    if route == "direct_chat_node":
        return "direct_chat_node"

    if fallback_required:
        return "knowledge_review_checkpoint"

    if task_type in {"review", "ingest"}:
        return "knowledge_review_checkpoint"

    if scope == "selected_block" or has_local_selection:
        return "composition_agent"

    if task_type == "edit":
        if operation_type == "asset_edit" or needs_assets or needs_research:
            return "retrieval_agent"
        return "composition_agent"

    if has_existing_canvas and looks_like_existing_canvas_edit(latest_user_text):
        return "composition_agent"

    if task_type == "create":
        return "retrieval_agent"

    if task_type == "inspect":
        return "direct_chat_node"

    if "patch" in route:
        return "patch_node"
    if any(kw in route for kw in ["content", "文案", "rag", "search", "image", "图"]) or needs_research or needs_assets:
        return "retrieval_agent"
    if "structure" in route or "结构" in route or "theme_compiler" in route or "style" in route or "样式" in route:
        return "composition_agent"
    return END

async def outline_synthesizer(state: UIProjectState) -> dict:
    """
    【大纲合成器】：验证并收束 block skeleton，直接产出 NoteDocument。
    """
    force_rebuild = _is_create_request(state)
    current_note_document = build_note_document_from_state(state)
    if force_rebuild:
        current_note_document = build_note_document_from_structure_patch(
            current_note_document,
            blocks=[],
        )
        blocks: list[dict[str, Any]] = []
    else:
        execution_view = build_note_document_layout_from_state(state)
        blocks = [
            {
                "id": block.get("id"),
                "component_type": block.get("component_type"),
                "content_brief": block.get("content_brief", ""),
            }
            for block in execution_view.get("blocks", [])
        ]

    if force_rebuild or not blocks:
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


async def outline_resolver(state: UIProjectState) -> dict:
    """
    【现代化大纲解析器】：
    直接消费 planner.block_intents 与 component manifest，确定性产出 block skeleton。
    不再走 历史工具循环。
    """
    note_document = build_note_document_from_state(state)
    if _is_create_request(state) or not (note_document.get("blocks") or []):
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
    """把解析后的区块骨架分发成 builder 任务。"""
    execution_view = build_note_document_layout_from_state(state)
    blocks = execution_view.get("blocks", [])
    if not blocks: return ["theme_compiler"]
    
    user_query = _latest_user_text(state)
    active_archetype = state.get("active_archetype", "seeding")
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
            "content_messages": [],
            "note_document": state.get("note_document", {}),
            "user_provided_facts": state.get("user_provided_facts", {}),
        })
        for b in blocks
    ]


def _after_truth_mode_checkpoint(state: UIProjectState) -> str:
    progress = state.get("checkpoint_progress") or {}
    truth_mode = dict(progress.get("truth_mode") or {}) if isinstance(progress, dict) else {}
    if truth_mode.get("awaiting_user_facts"):
        return END
    return "structure_checkpoint"

def compile_my_graph(checkpointer: BaseCheckpointSaver, store: BaseStore = None):
    workflow = StateGraph(UIProjectState)

    # 1. 注册节点。这里的名字直接对应运行时和诊断面板术语。
    workflow.add_node("asset_processor", with_performance_profiling("asset_processor", asset_processor_node))
    workflow.add_node("intent_agent", with_performance_profiling("intent_agent", intent_agent))
    workflow.add_node("direct_chat_node", with_performance_profiling("direct_chat_node", direct_chat_node))
    workflow.add_node("refusal_node", with_performance_profiling("refusal_node", refusal_node))
    workflow.add_node("retrieval_agent", with_performance_profiling("retrieval_agent", retrieval_agent_node))
    workflow.add_node("tools", ToolNode(RESEARCH_TOOLS)) 
    workflow.add_node("distill_node", with_performance_profiling("distill_node", distill_node)) # ✨ 注册提纯节点
    workflow.add_node("controversy_sniffer", with_performance_profiling("controversy_sniffer", controversy_sniffer_node))
    workflow.add_node("battle_node", with_performance_profiling("battle_node", battle_node))
    
    workflow.add_node("outline_resolver", with_performance_profiling("outline_resolver", outline_resolver))

    workflow.add_node("component_builder", component_builder_node)
    workflow.add_node("planner", with_performance_profiling("planner", planner_node))
    workflow.add_node("truth_mode_checkpoint", with_performance_profiling("truth_mode_checkpoint", truth_mode_checkpoint_node))
    workflow.add_node("structure_checkpoint", with_performance_profiling("structure_checkpoint", structure_checkpoint_node))
    workflow.add_node("retrieval_gap_fill", with_performance_profiling("retrieval_gap_fill", retrieval_gap_fill_node))
    workflow.add_node("knowledge_review_checkpoint", with_performance_profiling("knowledge_review_checkpoint", knowledge_review_checkpoint_node))
    workflow.add_node("fact_gap_checkpoint", with_performance_profiling("fact_gap_checkpoint", fact_gap_checkpoint_node))
    workflow.add_node("asset_checkpoint", with_performance_profiling("asset_checkpoint", asset_checkpoint_node))
    workflow.add_node("fact_conflict_checkpoint", with_performance_profiling("fact_conflict_checkpoint", fact_conflict_checkpoint_node))
    workflow.add_node("composition_agent", with_performance_profiling("composition_agent", composition_agent_node))
    workflow.add_node("verify_note", with_performance_profiling("verify_note", verify_note_node))
    workflow.add_node("critique", with_performance_profiling("critique", critique_node))  # ✨ 注册质量评审节点
    workflow.add_node("structure_node", with_performance_profiling("structure_node", structure_agent))
    workflow.add_node("patch_node", with_performance_profiling("patch_node", surgical_patch_agent))
    workflow.add_node("theme_compiler", with_performance_profiling("theme_compiler", theme_compiler))
    workflow.add_node("document_renderer", with_performance_profiling("document_renderer", document_renderer))

    # 2. 核心连接：从瘦网关分流，再进入规划 / 大纲 / 构建 / 主题 / 渲染主线。
    workflow.add_edge(START, "asset_processor")
    workflow.add_edge("asset_processor", "intent_agent")

    workflow.add_conditional_edges("intent_agent", route_intent, {
        "patch_node": "patch_node",
        "retrieval_agent": "retrieval_agent",
        "composition_agent": "composition_agent",
        "direct_chat_node": "direct_chat_node",
        "refusal_node": "refusal_node",
        END: END
    })

    workflow.add_edge("direct_chat_node", END)

    workflow.add_edge("patch_node", "document_renderer")
    workflow.add_edge("composition_agent", "verify_note")
    workflow.add_edge("verify_note", "theme_compiler")
    
    workflow.add_edge("refusal_node", END)

    # RAG 链：决策与物理强取 -> 提纯 -> 争议嗅探
    workflow.add_edge("retrieval_agent", "distill_node")
    workflow.add_edge("distill_node", "controversy_sniffer")
    workflow.add_edge("controversy_sniffer", "battle_node")
    
    workflow.add_edge("battle_node", "planner")
    workflow.add_edge("planner", "truth_mode_checkpoint")
    workflow.add_conditional_edges("truth_mode_checkpoint", _after_truth_mode_checkpoint, {
        "structure_checkpoint": "structure_checkpoint",
        END: END,
    })
    workflow.add_edge("structure_checkpoint", "retrieval_gap_fill")
    workflow.add_edge("retrieval_gap_fill", "knowledge_review_checkpoint")
    workflow.add_edge("knowledge_review_checkpoint", "fact_gap_checkpoint")
    workflow.add_edge("fact_gap_checkpoint", "asset_checkpoint")
    workflow.add_edge("asset_checkpoint", "fact_conflict_checkpoint")
    workflow.add_edge("fact_conflict_checkpoint", "outline_resolver")

    # 解析完毕后分发并发任务
    workflow.add_conditional_edges("outline_resolver", map_components, ["component_builder", "theme_compiler"])
    workflow.add_edge("component_builder", "theme_compiler")

    workflow.add_edge("theme_compiler", "document_renderer")
    workflow.add_edge("document_renderer", "critique")
    workflow.add_edge("critique", END)

    interrupt_nodes = ["controversy_sniffer"] if settings.HITL_ENABLED else []

    return workflow.compile(checkpointer=checkpointer, store=store, interrupt_before=interrupt_nodes)
