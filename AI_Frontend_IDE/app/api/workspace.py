import uuid
from copy import deepcopy
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from app.schemas.requests import ForkRequest, SelectRegionRequest
from app.schemas.responses import WorkspaceDataResponse, ForkResponse, BaseResponse
from app.services.showcase_manager import showcase_manager
from app.tools.serpapi_search import search_google_images
from app.agents.utils.fact_utils import (
    FACT_FIELD_LABELS,
    apply_confirmed_facts_to_knowledge,
    merge_confirmed_fact_selection,
)

router = APIRouter(prefix="/workspace", tags=["Workspace Operations"])

class SessionInfo(BaseModel):
    thread_id: str
    updated_at: str
    title: str = "未命名种草页面"

class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]


class AssetSearchResult(BaseModel):
    url: str
    desc: str
    source_type: str = "search"
    query: Optional[str] = None


class AssetSearchResponse(BaseResponse):
    results: List[AssetSearchResult]


class AssetMutationRequest(BaseModel):
    url: str
    desc: str = "外部素材"
    source_type: str = "search"
    query: Optional[str] = None


class FactConfirmationRequest(BaseModel):
    field: str
    value: str
    sources: List[str] = []


def normalize_human_content(content):
    if isinstance(content, list):
        text_parts = []
        image_urls = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and part.get("text"):
                text_parts.append(str(part.get("text")))
            elif part.get("type") == "image_url":
                image_url = (part.get("image_url") or {}).get("url")
                if image_url:
                    image_urls.append(image_url)
        return "".join(text_parts).strip(), image_urls
    return str(content or "").strip(), []


def _extract_session_title(values: dict, thread_id: str) -> str:
    for msg in values.get("main_messages", []) or []:
        if not isinstance(msg, HumanMessage):
            continue
        text, _ = normalize_human_content(msg.content)
        if text:
            compact = " ".join(text.split())
            return compact[:24] + ("..." if len(compact) > 24 else "")

    page_title = str((values.get("data_dsl") or {}).get("page_title") or "").strip()
    if page_title and page_title != "XHS-Forge Note":
        return page_title[:24] + ("..." if len(page_title) > 24 else "")

    return f"项目 {thread_id[:8]}"


def _pick_row_value(row, key: str, index: int = 0):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except Exception:
        return row[index]


async def _aupdate_state_compat(agent, config, values, *, as_node: str):
    """
    LangGraph 1.x 在部分场景下要求显式传 as_node。
    为兼容测试桩/旧 mock，这里先尝试带 as_node，再在 TypeError 时回退。
    """
    try:
        return await agent.aupdate_state(config, values, as_node=as_node)
    except TypeError:
        return await agent.aupdate_state(config, values)


# 这类接口属于“工作台直接改状态”，不应该给图留下待执行尾巴。
# 统一记在终态节点 render 上，避免后续 WebSocket 误从 verify/style/render 继续自动续火。
WORKSPACE_STATE_NODE = "render"


def _format_checkpoint_timestamp(created_at) -> str:
    if isinstance(created_at, str) and created_at:
        return created_at
    if created_at:
        return created_at.isoformat()
    return datetime.now().isoformat()

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
    await _aupdate_state_compat(agent, config, patch, as_node=WORKSPACE_STATE_NODE)
    
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


@router.get("/showcase/profiles")
async def get_showcase_profiles():
    """
    【求职展示面接口】
    返回当前项目最推荐展示的业务赛道与演示提示词，
    用于前端 demo 面板或面试时快速切换脚本。
    """
    return {"profiles": showcase_manager.list_profiles()}


@router.get("/{thread_id}/assets/search", response_model=AssetSearchResponse)
async def search_workspace_images(thread_id: str, query: str, limit: int = 8):
    """
    显式搜图接口：给前端素材库使用，避免把搜图完全藏在 agent 黑箱里。
    """
    final_query = (query or "").strip()
    if not final_query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    links = await search_google_images(final_query, num=max(1, min(limit, 12)))
    results = [
        AssetSearchResult(
            url=url,
            desc=f"{final_query} 搜索结果",
            source_type="search",
            query=final_query,
        )
        for url in links
    ]
    return AssetSearchResponse(results=results)


@router.post("/{thread_id}/assets/import", response_model=BaseResponse)
async def import_workspace_asset(thread_id: str, req: AssetMutationRequest, request: Request):
    """
    将素材显式收进当前线程资产池，供后续组件生成或页面编辑复用。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    current_assets = values.get("image_assets", []) or []

    if any(asset.get("url") == req.url for asset in current_assets if isinstance(asset, dict)):
        return BaseResponse(message="素材已存在于资产池")

    await _aupdate_state_compat(
        agent,
        config,
        {
            "image_assets": [{
                "url": req.url,
                "desc": req.desc,
                "source_type": req.source_type,
                "query": req.query,
            }]
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    return BaseResponse(message="素材已加入资产池")


@router.post("/{thread_id}/assets/cover", response_model=BaseResponse)
async def set_workspace_cover_asset(thread_id: str, req: AssetMutationRequest, request: Request):
    """
    将指定素材设为封面图。若页面尚无 CoverSwiper，则自动补一个。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    current_assets = values.get("image_assets", []) or []
    data_dsl = deepcopy(values.get("data_dsl", {}) or {})
    blocks = list(data_dsl.get("blocks", []) or [])

    cover_block = next((block for block in blocks if block.get("component_type") == "CoverSwiper"), None)
    if cover_block:
        cover_id = cover_block.get("id")
    else:
        cover_id = f"cover_{uuid.uuid4().hex[:8]}"
        cover_block = {
            "id": cover_id,
            "component_type": "CoverSwiper",
            "props": {},
        }
        blocks.insert(0, cover_block)

    data_dsl["blocks"] = blocks
    data_dsl[cover_id] = {
        **(data_dsl.get(cover_id, {}) or {}),
        "type": "CoverSwiper",
        "image_urls": [req.url],
    }

    patch = {"data_dsl": data_dsl}
    if not any(asset.get("url") == req.url for asset in current_assets if isinstance(asset, dict)):
        patch["image_assets"] = [{
            "url": req.url,
            "desc": req.desc,
            "source_type": req.source_type,
            "query": req.query,
        }]

    await _aupdate_state_compat(agent, config, patch, as_node=WORKSPACE_STATE_NODE)
    return BaseResponse(message="已设为封面图")


@router.post("/{thread_id}/facts/confirm", response_model=BaseResponse)
async def confirm_workspace_fact(thread_id: str, req: FactConfirmationRequest, request: Request):
    """
    人工确认单个冲突事实，写回 retrieved_knowledge，供后续持续编辑沿用。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    knowledge = deepcopy(values.get("retrieved_knowledge", {}) or {})

    if not isinstance(knowledge, dict) or not knowledge:
        raise HTTPException(status_code=400, detail="当前线程还没有可确认的事实资料")

    conflict_fields = {
        str(conflict.get("field") or ""): conflict
        for conflict in (knowledge.get("fact_conflicts") or [])
        if isinstance(conflict, dict)
    }
    if req.field and conflict_fields and req.field not in conflict_fields and req.field not in (knowledge.get("confirmed_facts") or {}):
        readable = "、".join(FACT_FIELD_LABELS.get(field, field) for field in conflict_fields.keys())
        raise HTTPException(status_code=400, detail=f"当前仅支持确认这些冲突字段: {readable}")

    selected_sources = req.sources
    if not selected_sources and req.field in conflict_fields:
        for item in conflict_fields[req.field].get("values", []) or []:
            if str(item.get("value") or "") == str(req.value):
                selected_sources = [str(source) for source in (item.get("sources") or [])]
                break

    next_knowledge = merge_confirmed_fact_selection(
        knowledge,
        field=req.field,
        value=req.value,
        sources=selected_sources,
    )
    next_knowledge = apply_confirmed_facts_to_knowledge(next_knowledge)

    await _aupdate_state_compat(
        agent,
        config,
        {"retrieved_knowledge": next_knowledge},
        as_node=WORKSPACE_STATE_NODE,
    )

    fact_label = FACT_FIELD_LABELS.get(req.field, req.field)
    return BaseResponse(message=f"已确认 {fact_label}: {req.value}")

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
                tid = _pick_row_value(row, "thread_id", 0)
                state = await agent.aget_state({"configurable": {"thread_id": tid}})
                values = state.values or {}
                sessions.append(SessionInfo(
                    thread_id=tid,
                    updated_at=datetime.now().isoformat(), # 后续可从 checkpoint 提取精准时间
                    title=_extract_session_title(values, tid)
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
            content, image_urls = normalize_human_content(msg.content)
            payload = {"role": "user", "content": content}
            if image_urls:
                payload["imageUrls"] = image_urls
            formatted.append(payload)
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


def dedupe_assets(assets: list) -> list[dict]:
    """
    基于 url 做轻量去重，尽量保留更完整的描述与来源字段。
    """
    deduped: dict[str, dict] = {}
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("url") or "").strip()
        if not url:
            continue
        existing = deduped.get(url, {})
        merged = {**existing, **asset}
        if existing.get("desc") and not asset.get("desc"):
            merged["desc"] = existing["desc"]
        deduped[url] = merged
    return list(deduped.values())

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
            image_assets=[],
            node_prompts={},
            oss_url=None,
            source_code="",
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
        timestamp_str = _format_checkpoint_timestamp(created_at)
        
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
        image_assets=dedupe_assets(values.get("image_assets", [])),
        node_prompts=values.get("node_prompts", {}),
        oss_url=values.get("final_oss_url"),
        source_code=values.get("final_html", ""),
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
        
        await _aupdate_state_compat(agent, new_config, cloned_values, as_node=WORKSPACE_STATE_NODE)
        return ForkResponse(new_thread_id=new_thread_id, message="分支已创建，请用新ID连接WS继续流式生成。")
    else:
        # 如果没有新指令，仅仅做纯粹的状态克隆 (例如用户点击了"复制副本")
        await _aupdate_state_compat(agent, new_config, cloned_values, as_node=WORKSPACE_STATE_NODE)
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
    await _aupdate_state_compat(agent, config, {"selected_element_id": req.element_id}, as_node=WORKSPACE_STATE_NODE)
    
    return BaseResponse(message=f"已成功锁定前端元素: {req.element_id}")
