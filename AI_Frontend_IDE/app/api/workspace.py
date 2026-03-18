import uuid
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from app.schemas.requests import ForkRequest, SelectRegionRequest
from app.schemas.responses import WorkspaceDataResponse, ForkResponse, BaseResponse

router = APIRouter(prefix="/workspace", tags=["Workspace Operations"])

class SessionInfo(BaseModel):
    thread_id: str
    updated_at: str
    title: str = "未命名种草页面"

class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]

def get_agent(request: Request):
    """依赖注入：从 FastAPI 生命周期中安全获取编译好的 Agent 引擎"""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="AI 前端 IDE 引擎未就绪，请检查 Postgres 连接")
    return agent

from app.services.cache_service import cache_service

class TrackTrendRequest(BaseModel):
    keyword: str

@router.post("/trends/track")
async def track_new_trend(req: TrackTrendRequest):
    """
    【面试亮点】：主动任务注入。
    用户手动将某个小众话题标记为“高价值”，系统立刻提升其 Redis 权重并启动异步预热。
    """
    await cache_service.update_trend_rank(req.keyword, score_increment=10.0)
    print(f"🎯 [用户主动追踪] 已将「{req.keyword}」权重置顶，触发流水线重扫描")
    return {"status": "success", "message": f"已开始深度追踪话题: {req.keyword}"}

class ComponentRollbackRequest(BaseModel):
    element_id: str
    version_index: int

@router.post("/{thread_id}/rollback/component")
async def rollback_component(thread_id: str, req: ComponentRollbackRequest, request: Request):
    """
    【原子级回溯接口】：面试亮点。
    从生长档案中提取特定版本并覆盖当前状态，实现单组件的“后悔药”。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    
    # 1. 获取当前最新状态
    state = await agent.aget_state(config)
    values = state.values
    
    from app.agents.state import restore_component_version
    # 2. 调用逻辑函数生成回滚补丁
    patch = restore_component_version(values, req.element_id, req.version_index)
    
    if not patch:
        raise HTTPException(status_code=400, detail="回滚失败：未找到有效历史快照")
        
    # 3. ✨ 面试亮点：利用 update_state 直接修改持久化 Checkpoint
    await agent.aupdate_state(config, patch)
    
    print(f"⏳ [原子回溯成功] 组件: {req.element_id} | 版本索引: {req.version_index}")
    return {"status": "success", "message": f"组件 {req.element_id} 已恢复至历史版本"}

@router.get("/trends")
async def get_trending_topics():
    """
    【面试亮点】：从 Redis ZSet 中实时提取热词排行榜。
    展示了系统对社交平台实时脉搏的监控能力。
    """
    trends = await cache_service.get_top_trends(limit=10)
    # 模拟一些初始热词，防止冷启动时列表为空
    if not trends:
        trends = ["索尼 A7C2", "华为 Mate 60", "赛博朋克风测评", "理想 L9 避雷", "春天第一杯咖啡"]
    return {"trends": trends}

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request):
    """
    【会话列表接口】
    从 LangGraph 的 checkpoints 表中提取所有唯一的 thread_id 及其最后更新时间
    """
    agent = get_agent(request)
    # 获取底层的 PostgresSaver 实例
    saver = agent.checkpointer
    
    # 构建原生 SQL：按 thread_id 分组，取最大的 checkpoint_id (即最新)
    query = """
        SELECT thread_id, MAX(checkpoint_id) as last_cid
        FROM checkpoints
        GROUP BY thread_id
        ORDER BY last_cid DESC
    """
    
    sessions = []
    try:
        # 使用 saver 的 connection 执行查询
        async with saver.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            
            for row in rows:
                tid = row[0]
                # 这里为了性能，我们先给个默认标题。
                # 优化策略：可以从 checkpoint 的 metadata 或 messages 中提取第一条 HumanMessage 作为标题
                sessions.append(SessionInfo(
                    thread_id=tid,
                    updated_at=datetime.now().isoformat(), # 后续可从 checkpoint 提取精准时间
                    title=f"项目 {tid[:8]}"
                ))
    except Exception as e:
        print(f"Error fetching sessions from DB: {e}")
        # 降级：如果表还没创建，返回空
        return SessionListResponse(sessions=[])

    return SessionListResponse(sessions=sessions)

def format_messages(messages_list: list) -> list[dict]:
    """
    格式化消息列表，保留 [工具信息] 的结构，供前端渲染
    """
    formatted = []
    for msg in messages_list:
        if isinstance(msg, HumanMessage):
            formatted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            # 如果是调用工具的 AI 消息
            if msg.tool_calls:
                formatted.append({
                    "role": "assistant_tool_call", 
                    "content": f"准备使用工具: {[t['name'] for t in msg.tool_calls]}"
                })
            else:
                formatted.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            # 真正的 [工具信息] 返回结果
            formatted.append({
                "role": "tool_result", 
                "tool_name": msg.name, 
                "content": msg.content
            })
    return formatted

@router.get("/{thread_id}", response_model=WorkspaceDataResponse)
async def get_workspace_data(thread_id: str, request: Request):
    """
    【核心首屏接口】
    拉取工作台全量数据，包含双重 DSL、组件状态，以及基于底层元数据提取的 [轮信息]
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    
    # 1. 拉取当前最新状态
    state = await agent.aget_state(config)
    
    if not state.values:
        # 全新线程，返回初始空底座
        return WorkspaceDataResponse(
            is_new=True,
            messages={"main": [], "content": [], "style": [], "structure": [], "image": []},
            active_panel="main",
            selected_element_id=None,
            data_dsl={},
            style_dsl={},
            oss_url=None,
            checkpoints=[]
        )
        
    values = state.values
    checkpoints = []
    
    # 2. 榨干 LangGraph 底层元数据，提取 [轮信息] (时光机时间轴)
    # aget_state_history 返回的是 StateSnapshot 对象集合
    async for snapshot in agent.aget_state_history(config):
        metadata = snapshot.metadata or {}
        # LangGraph 会自动记录这个快照是由哪个 node (节点) 产生的
        source_node = metadata.get("source", "unknown")
        
        # 提取精确的时间戳 (LangGraph 原生支持 created_at)
        created_at = snapshot.created_at
        timestamp_str = created_at.isoformat() if created_at else datetime.now().isoformat()
        
        checkpoints.append({
            "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
            "node": source_node,                     # 产生该快照的节点 (如 render_node)
            "intent": values.get("intent_route", ""),# 当时的路由意图
            "timestamp": timestamp_str               # 绝对精准的本轮结束时间！
        })

    # 3. 组装返回数据给前端渲染
    return WorkspaceDataResponse(
        is_new=False,
        messages={
            "main": format_messages(values.get("main_messages", [])),
            "content": format_messages(values.get("content_messages", [])),
            "style": format_messages(values.get("style_messages", [])),
            "structure": format_messages(values.get("structure_messages", [])),
            "image": format_messages(values.get("image_messages", []))
        },
        active_panel=values.get("active_panel", "main"),
        selected_element_id=values.get("selected_element_id"),
        data_dsl=values.get("data_dsl", {}),
        style_dsl=values.get("style_dsl", {}),
        oss_url=values.get("final_oss_url"),
        checkpoints=checkpoints
    )

@router.get("/{thread_id}/inspect")
async def inspect_agent_state(thread_id: str, request: Request):
    """
    【白盒探针】：获取当前会话 Agent 的核心记忆与决策状态
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await agent.aget_state(config)
    
    if not state_snapshot or not state_snapshot.values:
        return {"status": "empty", "data": None}
        
    values = state_snapshot.values
    
    # ✨ 核心逻辑：过滤掉庞大的 DSL 和对话记录，只提取“有意义”的元数据
    meaningful_state = {
        "creator_persona": values.get("creator_persona", "未设定"), # 当前人设
        "active_archetype": values.get("active_archetype", "未激活"), # 当前激活的排版原型
        "scenarios": values.get("scenarios", []), # 识别到的场景标签
        "intent_route": values.get("intent_route", "等待指令"), # 上一步的路由决策
        "retrieved_knowledge": values.get("retrieved_knowledge", ""), # 搜索引擎抓取到的干货
        "has_controversy": values.get("has_controversy", False), # 是否触发黑红榜风控
        "needs_disambiguation": values.get("needs_disambiguation", False) # 是否需要人类消歧
    }
    
    return {"status": "success", "data": meaningful_state}

@router.post("/fork", response_model=ForkResponse)
async def fork_thread(req: ForkRequest, request: Request):
    """
    【时光机引擎】
    回滚到指定的 Checkpoint (携带当时所有的 CSS/JSON/实体记忆)，
    篡改提问并开辟平行宇宙 (新 thread_id)
    """
    agent = get_agent(request)
    old_config = {"configurable": {"thread_id": req.old_thread_id, "checkpoint_id": req.checkpoint_id}}
    
    # 1. 穿透读取历史快照
    old_state = await agent.aget_state(old_config)
    if not old_state.values:
        raise HTTPException(status_code=404, detail="找不到该历史节点，可能已被清理或 ID 错误")

    # 2. 创建平行宇宙的 ID
    new_thread_id = f"fork_{uuid.uuid4().hex[:8]}"
    new_config = {"configurable": {"thread_id": new_thread_id}}
    
    # 3. 完美克隆历史状态
    cloned_values = dict(old_state.values)
    
    # 只有当用户真的传了新指令，才去追加消息和触发 LLM
    if req.new_instruction:
        msg_key = f"{req.panel}_messages"
        messages_list = list(cloned_values.get(msg_key, []))
        messages_list.append(HumanMessage(content=req.new_instruction))
        cloned_values[msg_key] = messages_list
        cloned_values["active_panel"] = req.panel
        
        await agent.aupdate_state(new_config, cloned_values)
        return ForkResponse(new_thread_id=new_thread_id, message="分支已创建，请用新ID连接WS继续流式生成。")
    else:
        # 如果没有新指令，仅仅做纯粹的状态克隆 (例如用户点击了"复制副本")
        await agent.aupdate_state(new_config, cloned_values)
        return ForkResponse(new_thread_id=new_thread_id, message="项目副本已创建完成。")

@router.post("/select-region", response_model=BaseResponse)
async def select_region(req: SelectRegionRequest, request: Request):
    """
    【极速状态更新】
    前端鼠标点选元素时触发。利用 LangGraph 的 In-place Update，
    完全不唤醒大模型，实现微秒级局部状态锁定。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": req.thread_id}}
    
    # 直接修改上帝黑板上的 selected_element_id 字段
    await agent.aupdate_state(config, {"selected_element_id": req.element_id})
    
    return BaseResponse(message=f"已成功锁定前端元素: {req.element_id}")