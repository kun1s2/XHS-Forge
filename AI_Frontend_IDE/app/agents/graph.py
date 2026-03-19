import time
import functools
import json
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from langgraph.prebuilt import ToolNode
from langgraph.constants import Send

# 引入我们定义的全局状态
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import OutlineOutput

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
from app.agents.nodes.outline_node import outline_agent, should_continue_outlining
from app.agents.nodes.component_builder import component_builder_node
from app.agents.tools_registry import RESEARCH_TOOLS, OUTLINE_TOOLS

def with_performance_profiling(node_name: str, func):
    @functools.wraps(func)
    async def wrapper(state: UIProjectState):
        start_time = time.perf_counter()
        try:
            result = await func(state)
            elapsed = time.perf_counter() - start_time
            print(f"⏱️ [性能监控] 节点 {node_name} 完毕, 耗时: \033[93m{elapsed:.2f}s\033[0m")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"❌ [性能监控] 节点 {node_name} 失败, 耗时: \033[91m{elapsed:.2f}s\033[0m")
            raise e
    return wrapper

def with_context_engineering(node_func):
    @functools.wraps(node_func)
    async def wrapper(state: UIProjectState):
        cloned_state = state.copy()
        cloned_state["messages"] = [] 
        return await node_func(cloned_state)
    return wrapper

def route_intent(state: UIProjectState) -> str:
    route = state.get("intent_route", "").lower()
    if "refusal" in route: return "refusal_node"
    if "patch" in route: return "patch_node"
    elif any(kw in route for kw in ["content", "文案", "rag", "search", "image", "图"]):
        return "research_agent" 
    elif "structure" in route or "结构" in route: return "structure_node"
    elif "style" in route or "样式" in route: return "style_node"
    return END

async def outline_synthesizer(state: UIProjectState) -> dict:
    """
    【大纲合成器】：验证并收束由画布工具直接修改的 data_dsl 状态。
    """
    # 此时 data_dsl 已经被 append_block 等工具直接修改好了
    data_dsl = state.get("data_dsl", {})
    blocks = data_dsl.get("blocks", [])
    
    # 校验并强制填充必要的字段
    for i, b in enumerate(blocks):
        if not b.get("id"): b["id"] = f"block_{i}"
        
    print(f"✅ [大纲合成] 画布定稿，共 {len(blocks)} 个区块。")
    return {
        "data_dsl": {
            "page_title": data_dsl.get("page_title", "XHS-Forge Note"),
            "page_theme": data_dsl.get("page_theme", {}),
            "blocks": blocks
        }
    }

def map_components(state: UIProjectState) -> list:
    data_dsl = state.get("data_dsl") or {}
    blocks = data_dsl.get("blocks", [])
    if not blocks: return ["style_node"]
    
    main_msgs = state.get("main_messages", [])
    user_query = str(main_msgs[-1].content) if main_msgs else ""
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
    
    # ✨ 核心重构：大纲 ReAct 节点组
    workflow.add_node("outline_node", with_performance_profiling("outline_node", outline_agent))
    workflow.add_node("outline_tools", ToolNode(OUTLINE_TOOLS))
    workflow.add_node("outline_synthesizer", outline_synthesizer)

    workflow.add_node("component_builder", component_builder_node)
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
        "structure_node": "structure_node",
        "style_node": "style_node",
        "refusal_node": "refusal_node",
        END: END
    })

    workflow.add_edge("patch_node", "render")
    workflow.add_edge("refusal_node", END)

    # RAG 链：决策与物理强取 -> 提纯 -> 争议嗅探
    workflow.add_edge("research_agent", "distill_node")
    workflow.add_edge("distill_node", "controversy_sniffer")
    workflow.add_edge("controversy_sniffer", "battle_node")
    
    # ✨ 核心重构：大纲 ReAct 循环
    workflow.add_edge("battle_node", "outline_node")
    workflow.add_conditional_edges(
        "outline_node", 
        should_continue_outlining, 
        {
            "outline_tools": "outline_tools",
            "outline_synthesizer": "outline_synthesizer"
        }
    )
    workflow.add_edge("outline_tools", "outline_node") # 循环连回思考节点
    
    # 合成完毕后分发并发任务
    workflow.add_conditional_edges("outline_synthesizer", map_components, ["component_builder", "style_node"])
    
    workflow.add_edge("style_node", "render")
    workflow.add_edge("render", END)

    interrupt_nodes = ["controversy_sniffer"] if settings.HITL_ENABLED else []

    return workflow.compile(checkpointer=checkpointer, store=store, interrupt_before=interrupt_nodes)
