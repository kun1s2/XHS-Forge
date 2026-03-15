import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from app.schemas.requests import ForkRequest, SelectRegionRequest
from app.schemas.responses import WorkspaceDataResponse, ForkResponse, BaseResponse

router = APIRouter(prefix="/workspace", tags=["Workspace Operations"])

def get_agent(request: Request):
    """依赖注入：从 FastAPI 生命周期中安全获取编译好的 Agent 引擎"""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="AI 前端 IDE 引擎未就绪，请检查 Postgres 连接")
    return agent

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