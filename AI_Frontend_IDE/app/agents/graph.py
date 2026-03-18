import time
import functools
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

# 引入我们定义的全局状态
from app.agents.state import UIProjectState
from app.core.config import settings

# 引入节点（含资产打标）
from app.agents.nodes.asset_node import asset_processor_node
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.research_agent import research_agent, should_continue_research
from app.agents.tools_registry import RESEARCH_TOOLS
from langgraph.prebuilt import ToolNode
from app.agents.nodes.review_node import controversy_sniffer_node
from app.agents.nodes.content_node import content_agent
from app.agents.nodes.structure_node import structure_agent
from app.agents.nodes.patch_node import surgical_patch_agent # ✨ 引入手术刀节点
from app.agents.nodes.style_node import style_agent
from app.agents.nodes.render_node import render_node
from app.agents.nodes.battle_node import battle_node # ✨ 引入对冲引擎
from app.agents.nodes.distill_node import distill_node # ✨ 引入提纯器
from app.agents.nodes.outline_node import outline_agent # ✨ 引入大纲节点
from app.agents.nodes.component_builder import component_builder_node # ✨ 引入单体工兵节点
from app.services.location_enricher import enrich_page_dsl # ✨ 引入位置增强服务
from app.services.search_enricher import enrich_product_data # ✨ 引入事实增强服务
from app.services.image_generator import auto_generate_images # ✨ 引入智能配图服务
from langgraph.constants import Send # ✨ 引入 Send API
import json

def with_performance_profiling(node_name: str, func):
    """
    【高阶装饰器】：不侵入节点业务代码，动态计算每个节点的执行耗时。
    """
    @functools.wraps(func)
    async def wrapper(state: UIProjectState):
        start_time = time.perf_counter()
        try:
            result = await func(state)
            elapsed = time.perf_counter() - start_time
            # 终端打印彩色耗时统计（✨ 暂时去掉 get_openai_callback 以解决可能的阻塞延迟）
            print(f"⏱️ [性能监控] 节点 {node_name} 完毕, 耗时: \033[93m{elapsed:.2f}s\033[0m")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            print(f"❌ [性能监控] 节点 {node_name} 失败, 耗时: \033[91m{elapsed:.2f}s\033[0m")
            raise e
    return wrapper

async def enrichment_node(state: UIProjectState) -> dict:
    """
    【综合增强节点】：一站式完成位置补全、事实增强和智能配图。
    """
    data_dsl = state.get("data_dsl", {})
    active_archetype = state.get("active_archetype", "general")
    current_assets = state.get("image_assets", []) # 获取当前的图片画廊
    
    if not data_dsl:
        return {}
    
    # 1. 事实增强：校验商品参数与价格
    data_dsl = await enrich_product_data(data_dsl, active_archetype)
    
    # 2. 位置增强：补全地理坐标
    data_dsl = await enrich_page_dsl(data_dsl)
    
    # 3. 智能配图：如果没有图，自动生图并取色
    data_dsl, new_assets = await auto_generate_images(data_dsl, active_archetype)
    
    # ✨ 核心修复：如果生图产生了新资产（包含了从图里提取的 vibe 颜色），必须把它们装回画廊里
    if new_assets:
        # 因为我们在 state.py 里对 image_assets 用了 operator.add
        # 所以直接 return 新数组，LangGraph 会自动把它们 append 到原数组后面
        return {
            "data_dsl": data_dsl,
            "image_assets": new_assets 
        }
        
    return {
        "data_dsl": data_dsl
    }

def route_intent(state: UIProjectState) -> str:
    """
    【核心路由守卫 - 哨兵加固版】：强制要求新内容生成必须先经过调研。
    """
    route = state.get("intent_route", "").lower()
    
    print(f"🧭 [路由守卫] 截获的原始意图: {route}")
    
    # 模糊匹配
    if "patch" in route:
        return "patch_node"
    # ✨ 核心重构：无论是 RAG、搜索还是生成全新文案，统一先去 research_agent 报到
    elif any(kw in route for kw in ["content", "文案", "rag", "search", "image", "图"]):
        print("🔍 [路由守卫] 判定为生成任务，强制进入阻塞式调研模式。")
        return "research_agent" 
    elif "structure" in route or "结构" in route:
        return "structure_node"
    elif "style" in route or "样式" in route:
        return "style_node"
    else:
        # 只有在完全匹配不到任何已知业务时，才终止流程
        print("⚠️ [路由守卫] 未知意图，终止渲染流。")
        return END

def map_components(state: UIProjectState) -> list:
    """
    【区块流调度器】：遍历扁平的 blocks 列表，为每个积木发射并发生成任务。
    """
    # ✨ 核心重构：直接从统一事实来源 data_dsl 中读取区块流，彻底废弃 page_outline
    data_dsl = state.get("data_dsl") or {}
    blocks = data_dsl.get("blocks", [])
    
    if not blocks:
        print("⚠️ [并发调度] 区块列表为空，跳过并发阶段。")
        return ["style_node"]
        
    print(f"🚀 [并发调度] 发现 {len(blocks)} 个区块，发射特种兵进行内容填充！")
    
    # 构造共享上下文
    main_msgs = state.get("main_messages", [])
    user_query = main_msgs[-1].content if main_msgs else ""
    if isinstance(user_query, list):
        user_query = str([item["text"] for item in user_query if item["type"] == "text"])
        
    active_archetype = state.get("active_archetype", "general")
    retrieved_knowledge = state.get("retrieved_knowledge", "")
    creator_persona = state.get("creator_persona", "硬核数码博主")
    
    # 派发任务！
    return [
        Send("component_builder", {
            "component_id": b["id"],
            "component_type": b["component_type"],
            "content_brief": b.get("content_brief", "请根据上下文填充内容。"),
            "user_query": user_query,
            "active_archetype": active_archetype,
            "retrieved_knowledge": retrieved_knowledge,
            "creator_persona": creator_persona
        })
        for b in blocks
    ]

def compile_my_graph(checkpointer: BaseCheckpointSaver, store: BaseStore = None):
    """
    【图纸编译中心】：将节点与边组装为可运行的图结构。
    这个函数会在 app/main.py 的 Lifespan 中被调用。
    """
    # 1. 声明图的载体：UIProjectState
    workflow = StateGraph(UIProjectState)

    # 2. 注册所有特种兵 (Nodes) —— 注入性能监控
    workflow.add_node("asset_processor", with_performance_profiling("asset_processor", asset_processor_node))
    workflow.add_node("intent_agent", with_performance_profiling("intent_agent", intent_agent))
    workflow.add_node("research_agent", with_performance_profiling("research_agent", research_agent))
    workflow.add_node("tools", ToolNode(RESEARCH_TOOLS)) # ✨ 注册工具执行节点
    workflow.add_node("distill_node", with_performance_profiling("distill_node", distill_node)) # ✨ 注册事实提纯器
    workflow.add_node("controversy_sniffer", with_performance_profiling("controversy_sniffer", controversy_sniffer_node))

    workflow.add_node("battle_node", with_performance_profiling("battle_node", battle_node)) # ✨ 注册对冲引擎
    workflow.add_node("content_node", with_performance_profiling("content_node", content_agent))
    workflow.add_node("outline_node", with_performance_profiling("outline_node", outline_agent)) # ✨ 引入大纲节点
    workflow.add_node("component_builder", component_builder_node) # ✨ 引入单体工兵节点 (由于 Send API 限制，这里不加耗时包装，或者确保包装器兼容 Send 状态)
    workflow.add_node("structure_node", with_performance_profiling("structure_node", structure_agent))
    workflow.add_node("patch_node", with_performance_profiling("patch_node", surgical_patch_agent)) # ✨ 注册手术刀节点
    workflow.add_node("enrichment_node", with_performance_profiling("enrichment_node", enrichment_node)) # ✨ 注册综合增强节点
    workflow.add_node("style_node", with_performance_profiling("style_node", style_agent))
    workflow.add_node("render", with_performance_profiling("render", render_node))

    # 3. 规划路线 (Edges)
    # 起点先走资产打标（有待处理图片则打标并入图库），再走意图
    workflow.add_edge(START, "asset_processor")
    workflow.add_edge("asset_processor", "intent_agent")
    # 4. 动态分发 (Conditional Edges)
    workflow.add_conditional_edges(
        "intent_agent",
        route_intent,
        {
            "patch_node": "patch_node",
            "research_agent": "research_agent", # ✨ content / rag / search 现在统一走这里
            "structure_node": "structure_node",
            "style_node": "style_node",
            END: END
        }
    )

    # 5. 【瀑布流式级联向下】(Cascading Edges)
    # 这是我们架构的精髓所在：调研先行，事实为本。

    # 手术刀通道：微调完直接渲染
    workflow.add_edge("patch_node", "render")

    # 第一步：调研决策
    # 🌟 核心重构：事实性三段论
    # 意图路由 -> research_agent (决策) -> (如有 tool_call) -> tools -> distill_node -> sniffer
    from app.agents.nodes.research_agent import should_continue_research
    workflow.add_conditional_edges(
        "research_agent",
        should_continue_research,
        {
            "tools": "tools",
            "distill_node": "distill_node"
        }
    )
    workflow.add_edge("tools", "distill_node")
    workflow.add_edge("distill_node", "controversy_sniffer")

    # ✨ 舆情嗅探后，进入并发对冲引擎
    workflow.add_edge("controversy_sniffer", "battle_node")

    # 第二步：观点合成完毕，主编写文案
    workflow.add_edge("battle_node", "content_node")

    # 第三步：文案定调，策划出大纲
    workflow.add_edge("content_node", "outline_node")

    # 第四步：大纲出完，裂变工兵并行拼装
    workflow.add_conditional_edges("outline_node", map_components, ["style_node", "component_builder"])

    # 第五步：工兵收束，严禁再次发起任何网络搜索！直接进入样式层
    # 彻底废弃 enrichment_node 在后端的 RAG 权力，防止“童颜针”式事故二次发生
    workflow.add_edge("component_builder", "style_node")

    # 第六步：物理渲染
    workflow.add_edge("style_node", "render")
    # 终点
    workflow.add_edge("render", END)

    # 6. 注入灵魂：正式编译！
    # ✨ 哨兵全自动升级：根据配置动态决定是否开启 HITL 中断点
    interrupt_nodes = ["content_node", "controversy_sniffer"] if settings.HITL_ENABLED else []
    
    app_graph = workflow.compile(
        checkpointer=checkpointer, 
        store=store,
        interrupt_before=interrupt_nodes
    )
    
    return app_graph
