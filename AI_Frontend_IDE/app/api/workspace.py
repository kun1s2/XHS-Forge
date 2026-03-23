import json
import uuid
from copy import deepcopy
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from app.schemas.requests import ForkRequest, SelectRegionRequest, ThreadRollbackRequest
from app.schemas.responses import (
    BlockGalleryOverviewResponse,
    BlockGalleryComponentPayloadResponse,
    BlockGalleryScenarioPayloadResponse,
    WorkspaceDataResponse,
    ForkResponse,
    BaseResponse,
    BenchmarkOverviewResponse,
    EvaluationOverviewResponse,
    TrendListResponse,
)
from app.services.block_gallery import (
    get_block_gallery_component,
    get_block_gallery_overview,
    get_block_gallery_scenario,
)
from app.services.showcase_manager import showcase_manager
from app.services.trend_pipeline import process_new_trend_background
from app.tools.serpapi_search import search_google_images
from app.agents.utils.fact_utils import (
    FACT_FIELD_LABELS,
    apply_confirmed_facts_to_knowledge,
    merge_confirmed_fact_selection,
)
from app.core.note_document import (
    build_note_document_from_state,
    remove_note_document_asset,
    update_note_document_asset_preferences,
    update_note_document_cover_preference,
)
from app.core.runtime_log import append_latest_console_log, append_log_divider, reset_latest_console_log, summarize_turn_completion, write_latest_frontend_observation
from app.api.workspace_diagnostics import (
    build_benchmark_overview as _present_benchmark_overview,
    build_evaluation_overview as _present_evaluation_overview,
    build_inspector_summary as _present_inspector_summary,
    dedupe_assets as _present_dedupe_assets,
    fetch_latest_session_snapshots as _present_fetch_latest_session_snapshots,
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


class AssetPreferenceRequest(BaseModel):
    url: str
    role: Optional[str] = None
    locked: Optional[bool] = None
    selection_state: Optional[str] = None


class FactConfirmationRequest(BaseModel):
    field: str
    value: str
    sources: List[str] = []


class FrontendObservationRequest(BaseModel):
    thread_id: Optional[str] = None
    event_type: str
    message: str = ''
    payload: Dict[str, Any] = {}


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

    document_title = str((((values.get("note_document") or {}).get("document_meta") or {}).get("title")) or "").strip()
    if document_title and document_title != "XHS-Forge Note":
        return document_title[:24] + ("..." if len(document_title) > 24 else "")

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
# 统一记在终态节点 document_renderer 上，避免后续 WebSocket 误从 verify/theme compiler/document renderer 继续自动续火。
WORKSPACE_STATE_NODE = "document_renderer"


def _extract_document_blocks(note_document: dict | None) -> list[dict]:
    if not isinstance(note_document, dict):
        return []
    blocks = note_document.get("blocks") or []
    return [block for block in blocks if isinstance(block, dict)]


def _summarize_document_state(values: dict | None) -> dict:
    note_document = (values or {}).get("note_document") or build_note_document_from_state(values or {})
    blocks = _extract_document_blocks(note_document)
    return {
        "title": str(((note_document or {}).get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "block_count": len(blocks),
        "block_order": [
            {"id": str(block.get("id") or ""), "type": str(block.get("type") or "")}
            for block in blocks
        ],
    }


def _build_workspace_block_change_set(before_values: dict | None, after_values: dict | None) -> list[dict]:
    before_blocks = {str(block.get("id") or ""): block for block in _extract_document_blocks((before_values or {}).get("note_document") or build_note_document_from_state(before_values or {})) if block.get("id")}
    after_blocks = {str(block.get("id") or ""): block for block in _extract_document_blocks((after_values or {}).get("note_document") or build_note_document_from_state(after_values or {})) if block.get("id")}
    before_order = {bid: idx for idx, bid in enumerate(before_blocks.keys())}
    after_order = {bid: idx for idx, bid in enumerate(after_blocks.keys())}
    changes = []
    for block_id in sorted(set(before_blocks) | set(after_blocks)):
        before_block = before_blocks.get(block_id)
        after_block = after_blocks.get(block_id)
        if before_block is None and after_block is not None:
            changes.append({"id": block_id, "type": str(after_block.get("type") or ""), "changed_fields": ["added"]})
            continue
        if after_block is None and before_block is not None:
            changes.append({"id": block_id, "type": str(before_block.get("type") or ""), "changed_fields": ["removed"]})
            continue
        changed_fields = []
        if str(before_block.get("type") or "") != str(after_block.get("type") or ""):
            changed_fields.append("type")
        if before_order.get(block_id) != after_order.get(block_id):
            changed_fields.append("order")
        if json.dumps(before_block.get("props") or {}, sort_keys=True, ensure_ascii=False) != json.dumps(after_block.get("props") or {}, sort_keys=True, ensure_ascii=False):
            changed_fields.append("props")
        if json.dumps(before_block.get("style") or {}, sort_keys=True, ensure_ascii=False) != json.dumps(after_block.get("style") or {}, sort_keys=True, ensure_ascii=False):
            changed_fields.append("style")
        if changed_fields:
            changes.append({"id": block_id, "type": str(after_block.get("type") or before_block.get("type") or ""), "changed_fields": changed_fields})
    return changes


async def _record_workspace_operation(agent, config: dict, *, action: str, reason: str, before_values: dict | None, selected_element_id: str | None = None, warnings: list[str] | None = None):
    latest_state = await agent.aget_state(config)
    after_values = latest_state.values or {}
    turn_trace = {
        "query": reason,
        "selected_element_id": selected_element_id or after_values.get("selected_element_id") or "global",
        "panel": str(after_values.get("active_panel") or "main"),
        "timeline": [{"event": "workspace_action", "node": action}],
        "route": {
            "intent_route": str(after_values.get("intent_route") or "workspace_operation"),
            "active_archetype": str(after_values.get("active_archetype") or ""),
        },
        "planner": {},
        "note_editor": {},
        "workspace_action": {
            "action": action,
            "reason": reason,
            "structured": True,
            "fallback_used": False,
            "target_block_id": selected_element_id or after_values.get("selected_element_id") or "global",
        },
        "before_summary": _summarize_document_state(before_values or {}),
        "after_summary": _summarize_document_state(after_values or {}),
        "changed_blocks": _build_workspace_block_change_set(before_values or {}, after_values or {}),
        "warnings": list(warnings or []),
    }
    await _aupdate_state_compat(agent, config, {"turn_trace": turn_trace}, as_node=WORKSPACE_STATE_NODE)
    reset_latest_console_log(f"[DEBUG] 最新工作台动作 thread={config.get('configurable', {}).get('thread_id', '')}")
    append_log_divider('WORKSPACE ACTION')
    append_latest_console_log(f"🧭 [WORKSPACE] action={action} | selected={selected_element_id or 'global'} | reason={reason}")
    append_log_divider('TURN END')
    append_latest_console_log(f"🏁 [TURN END]: {summarize_turn_completion(turn_trace, latest_state.values or {})}")
    return turn_trace


def _format_checkpoint_timestamp(created_at) -> str:
    if isinstance(created_at, str) and created_at:
        return created_at
    if created_at:
        return created_at.isoformat()
    return datetime.now().isoformat()


def _build_turn_anchor_map(values: dict | None, panel: str) -> dict[int, str]:
    anchors = (values or {}).get("turn_anchors") or []
    anchor_map: dict[int, str] = {}
    for item in anchors:
        if not isinstance(item, dict):
            continue
        if str(item.get("panel") or "main") != panel:
            continue
        checkpoint_id = str(item.get("checkpoint_id") or "").strip()
        if not checkpoint_id:
            continue
        try:
            turn_index = int(item.get("turn_index") or 0)
        except Exception:
            continue
        anchor_map[turn_index] = checkpoint_id
    return anchor_map


def _build_next_note_document(values: dict | None, **overrides):
    merged = dict(values or {})
    merged.update(overrides)
    return build_note_document_from_state(merged)

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
    await cache_service.update_trend_rank(req.keyword, score_increment=10.0, source="manual_track")
    import asyncio
    asyncio.create_task(process_new_trend_background(req.keyword))
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

    patch = {
        **patch,
        "note_document": _build_next_note_document(values, **patch),
    }
        
    # 3. ✨ 面试亮点：利用 update_state 直接修改持久化 Checkpoint
    await _aupdate_state_compat(agent, config, patch, as_node=WORKSPACE_STATE_NODE)
    await _record_workspace_operation(agent, config, action="workspace_rollback_component", reason=f"组件回滚: {req.element_id}@{req.version_index}", before_values=values, selected_element_id=req.element_id)
    
    print(f"⏳ [原子回溯成功] 组件: {req.element_id} | 版本索引: {req.version_index}")
    return {"status": "success", "message": f"组件 {req.element_id} 已恢复至历史版本"}

@router.get("/trends", response_model=TrendListResponse)
async def get_trending_topics():
    """
    【热点榜接口】：返回真实热点对象，而不是硬编码按钮字符串。
    """
    trends = await cache_service.get_top_trend_items(limit=10)
    return TrendListResponse(trends=trends)


@router.post('/frontend-observe', response_model=BaseResponse)
async def observe_frontend_state(req: FrontendObservationRequest):
    payload = {
        'thread_id': req.thread_id or '',
        'event_type': req.event_type,
        'message': req.message,
        'payload': req.payload or {},
    }
    write_latest_frontend_observation(payload)
    append_latest_console_log(
        f"🖥️ [FRONTEND] type={req.event_type} | thread={req.thread_id or '-'} | message={req.message[:120]}"
    )
    return BaseResponse(message='前端观测已记录')


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

    new_asset = {
        "url": req.url,
        "desc": req.desc,
        "source_type": req.source_type,
        "query": req.query,
    }
    next_assets = [*current_assets, new_asset]

    await _aupdate_state_compat(
        agent,
        config,
        {
            "image_assets": [new_asset],
            "note_document": _build_next_note_document(values, image_assets=next_assets),
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    await _record_workspace_operation(agent, config, action="workspace_import_asset", reason=f"素材入池: {req.desc}", before_values=values)
    return BaseResponse(message="素材已加入资产池")


@router.post("/{thread_id}/assets/cover", response_model=BaseResponse)
async def set_workspace_cover_asset(thread_id: str, req: AssetMutationRequest, request: Request):
    """
    将指定素材标记为封面偏好，只更新资产池与文档偏好，不提前创建封面区块。
    """
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    current_assets = values.get("image_assets", []) or []
    note_document = build_note_document_from_state(values)
    normalized_assets: list[dict[str, Any]] = []
    asset_exists = False
    for asset in current_assets:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        next_asset = deepcopy(asset)
        if str(next_asset.get("url") or "") == req.url:
            asset_exists = True
            next_asset.update({
                "desc": req.desc or next_asset.get("desc", ""),
                "source_type": req.source_type or next_asset.get("source_type", "search"),
                "query": req.query or next_asset.get("query"),
                "role": "cover",
            })
        elif str(next_asset.get("role") or "") == "cover":
            next_asset["role"] = "supporting"
        normalized_assets.append(next_asset)

    if not asset_exists:
        normalized_assets.append({
            "url": req.url,
            "desc": req.desc,
            "source_type": req.source_type,
            "query": req.query,
            "role": "cover",
        })

    note_document = update_note_document_cover_preference(note_document, req.url)
    cover_asset_bound = False
    next_document_assets: list[dict[str, Any]] = []
    for asset in note_document.get("assets") or []:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        next_asset = deepcopy(asset)
        if str(next_asset.get("url") or "") == req.url:
            cover_asset_bound = True
            next_asset.update({
                "desc": req.desc or next_asset.get("desc", ""),
                "source_type": req.source_type or next_asset.get("source_type"),
                "query": req.query or next_asset.get("query"),
                "role": "cover",
            })
        elif str(next_asset.get("role") or "") == "cover":
            next_asset["role"] = "supporting"
        next_document_assets.append(next_asset)

    if not cover_asset_bound:
        next_document_assets.append({
            "id": req.url,
            "url": req.url,
            "desc": req.desc or "封面图",
            "source_type": req.source_type,
            "query": req.query,
            "role": "cover",
            "locked": False,
            "selection_state": "available",
            "source_reason": req.desc or "封面图",
            "used_by_blocks": [],
        })
    note_document["assets"] = next_document_assets

    patch = {}
    if not asset_exists:
        patch["image_assets"] = [normalized_assets[-1]]

    patch["note_document"] = note_document

    await _aupdate_state_compat(agent, config, patch, as_node=WORKSPACE_STATE_NODE)
    await _record_workspace_operation(agent, config, action="workspace_set_cover", reason=f"设为封面: {req.desc}", before_values=values)
    return BaseResponse(message="已设为封面图")


@router.delete("/{thread_id}/assets", response_model=BaseResponse)
async def remove_workspace_asset(thread_id: str, url: str, request: Request):
    """
    删除当前线程中的素材资产，并同步清理封面偏好与直接图片引用。
    """
    normalized_url = str(url or "").strip()
    if not normalized_url:
        raise HTTPException(status_code=400, detail="缺少素材 URL")

    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    current_assets = [asset for asset in (values.get("image_assets") or []) if isinstance(asset, dict)]
    target_asset = next((asset for asset in current_assets if str(asset.get("url") or "") == normalized_url), None)
    if target_asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")

    next_assets = [
        deepcopy(asset)
        for asset in current_assets
        if str(asset.get("url") or "") != normalized_url
    ]
    note_document = remove_note_document_asset(build_note_document_from_state(values), normalized_url)

    await _aupdate_state_compat(
        agent,
        config,
        {
            "image_assets": [{"__replace__": True}, *next_assets],
            "note_document": note_document,
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    await _record_workspace_operation(
        agent,
        config,
        action="workspace_remove_asset",
        reason=f"删除素材: {target_asset.get('desc') or normalized_url}",
        before_values=values,
    )
    return BaseResponse(message="素材已删除")


@router.patch("/{thread_id}/assets/preferences", response_model=BaseResponse)
async def update_workspace_asset_preferences(thread_id: str, req: AssetPreferenceRequest, request: Request):
    """
    更新当前线程素材的使用偏好：封面、正文图、必用、暂不使用。
    """
    normalized_url = str(req.url or "").strip()
    if not normalized_url:
        raise HTTPException(status_code=400, detail="缺少素材 URL")

    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)
    values = state.values or {}
    current_assets = [deepcopy(asset) for asset in (values.get("image_assets") or []) if isinstance(asset, dict) and asset.get("url")]
    target_asset = next((asset for asset in current_assets if str(asset.get("url") or "") == normalized_url), None)
    if target_asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")

    normalized_role = str(req.role or "").strip() or None
    normalized_selection_state = str(req.selection_state or "").strip() or None

    next_assets: list[dict[str, Any]] = []
    for asset in current_assets:
        next_asset = deepcopy(asset)
        if str(next_asset.get("url") or "") == normalized_url:
            if normalized_role is not None:
                next_asset["role"] = normalized_role
            if req.locked is not None:
                next_asset["locked"] = bool(req.locked)
            if normalized_selection_state is not None:
                next_asset["selection_state"] = normalized_selection_state
                if normalized_selection_state == "excluded":
                    next_asset["locked"] = False
                    if str(next_asset.get("role") or "") == "cover":
                        next_asset["role"] = "supporting"
            if normalized_role == "cover":
                next_asset["selection_state"] = "available"
        elif normalized_role == "cover" and str(next_asset.get("role") or "") == "cover":
            next_asset["role"] = "supporting"
        next_assets.append(next_asset)

    note_document = update_note_document_asset_preferences(
        build_note_document_from_state(values),
        normalized_url,
        role=normalized_role,
        locked=req.locked,
        selection_state=normalized_selection_state,
    )

    await _aupdate_state_compat(
        agent,
        config,
        {
            "image_assets": [{"__replace__": True}, *next_assets],
            "note_document": note_document,
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    await _record_workspace_operation(
        agent,
        config,
        action="workspace_update_asset_preferences",
        reason=f"更新素材偏好: {target_asset.get('desc') or normalized_url}",
        before_values=values,
    )
    return BaseResponse(message="素材偏好已更新")


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
        {
            "retrieved_knowledge": next_knowledge,
            "note_document": _build_next_note_document(values, retrieved_knowledge=next_knowledge),
        },
        as_node=WORKSPACE_STATE_NODE,
    )

    fact_label = FACT_FIELD_LABELS.get(req.field, req.field)
    await _record_workspace_operation(agent, config, action="workspace_confirm_fact", reason=f"确认事实: {fact_label}={req.value}", before_values=values)
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

def format_messages(messages_list: list, *, turn_anchor_map: dict[int, str] | None = None) -> list[dict]:
    """
    格式化消息列表，保留 [工具信息] 的结构，供前端渲染
    """
    formatted = []
    user_turn_index = 0
    for msg in messages_list:
        if isinstance(msg, HumanMessage):
            content, image_urls = normalize_human_content(msg.content)
            payload = {
                "role": "user",
                "content": content,
                "messageKind": "user_prompt",
            }
            if image_urls:
                payload["imageUrls"] = image_urls
            checkpoint_id = (turn_anchor_map or {}).get(user_turn_index)
            if checkpoint_id:
                payload["checkpointId"] = checkpoint_id
            formatted.append(payload)
            user_turn_index += 1
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
    return _present_dedupe_assets(assets)


def _build_inspector_summary(values: dict) -> dict:
    return _present_inspector_summary(values)


def _build_benchmark_overview(session_snapshots: list[dict]) -> dict:
    return _present_benchmark_overview(session_snapshots, _extract_session_title)


def _build_evaluation_overview(session_snapshots: list[dict]) -> dict:
    return _present_evaluation_overview(session_snapshots, _extract_session_title)


async def _fetch_latest_session_snapshots(agent) -> list[dict]:
    return await _present_fetch_latest_session_snapshots(agent, _extract_session_title)


@router.get("/benchmark/overview", response_model=BenchmarkOverviewResponse)
async def get_benchmark_overview(request: Request):
    """
    Benchmark dashboard for interview demos:
    aggregate multi-session RAG/cache/execution metrics into one overview payload.
    """
    agent = get_agent(request)
    snapshots = await _fetch_latest_session_snapshots(agent)
    overview = _build_benchmark_overview(snapshots)
    return BenchmarkOverviewResponse(data=overview)


@router.get("/evaluation/overview", response_model=EvaluationOverviewResponse)
async def get_evaluation_overview(request: Request):
    """
    正式评估面板：
    用固定评估目录和最近会话样本，对路由、规划、执行、RAG、缓存和系统级稳定性做统一评分。
    """
    agent = get_agent(request)
    snapshots = await _fetch_latest_session_snapshots(agent)
    overview = _build_evaluation_overview(snapshots)
    return EvaluationOverviewResponse(data=overview)


@router.get("/block-gallery/overview", response_model=BlockGalleryOverviewResponse)
async def get_block_gallery_overview_route():
    """积木大全总览：同时提供单积木样例和整页场景样例。"""
    return BlockGalleryOverviewResponse(data=get_block_gallery_overview())


@router.get("/block-gallery/components/{component_type}", response_model=BlockGalleryComponentPayloadResponse)
async def get_block_gallery_component_route(component_type: str):
    """单积木真实样例：用于观察结构化 props 和真实观感。"""
    payload = get_block_gallery_component(component_type)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"未知积木类型: {component_type}")
    return BlockGalleryComponentPayloadResponse(data=payload)


@router.get("/block-gallery/scenarios/{scenario_id}", response_model=BlockGalleryScenarioPayloadResponse)
async def get_block_gallery_scenario_route(scenario_id: str):
    """整页场景样例：用于观察积木组合后的比例、节奏和主题统一性。"""
    payload = get_block_gallery_scenario(scenario_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"未知场景样例: {scenario_id}")
    return BlockGalleryScenarioPayloadResponse(data=payload)

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
        return WorkspaceDataResponse(
            is_new=True,
            messages={"main": [], "content": [], "style": [], "structure": [], "image": []},
            active_panel="main",
            selected_element_id=None,
            image_assets=[],
            node_prompts={},
            note_document={},
            planner_output={},
            planner_policy={},
            turn_trace={},
            agent_backends={},
            oss_url=None,
            source_code="",
            checkpoints=[]
        )
        
    values = state.values
    note_document = values.get("note_document") or build_note_document_from_state(values)
    checkpoints = []
    turn_anchor_map_by_panel = {
        "main": _build_turn_anchor_map(values, "main"),
        "content": _build_turn_anchor_map(values, "content"),
        "style": _build_turn_anchor_map(values, "style"),
        "structure": _build_turn_anchor_map(values, "structure"),
        "image": _build_turn_anchor_map(values, "image"),
    }
    
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
            "node": source_node,                     # 产生该快照的节点 (如 document_renderer)
            "intent": values.get("intent_route", ""),# 当时的路由意图
            "timestamp": timestamp_str               # 绝对精准的本轮结束时间！
        })

    # 3. 组装返回数据给前端渲染
    return WorkspaceDataResponse(
        is_new=False,
        messages={
            "main": format_messages(values.get("main_messages", []), turn_anchor_map=turn_anchor_map_by_panel["main"]),
            "content": format_messages(values.get("content_messages", []), turn_anchor_map=turn_anchor_map_by_panel["content"]),
            "style": format_messages(values.get("style_messages", []), turn_anchor_map=turn_anchor_map_by_panel["style"]),
            "structure": format_messages(values.get("structure_messages", []), turn_anchor_map=turn_anchor_map_by_panel["structure"]),
            "image": format_messages(values.get("image_messages", []), turn_anchor_map=turn_anchor_map_by_panel["image"])
        },
        active_panel=values.get("active_panel", "main"),
        selected_element_id=values.get("selected_element_id"),
        image_assets=dedupe_assets(values.get("image_assets", [])),
        node_prompts=values.get("node_prompts", {}),
        note_document=note_document,
        planner_output=values.get("planner_output", {}),
        planner_policy=values.get("planner_policy", {}),
        turn_trace=values.get("turn_trace", {}),
        agent_backends=values.get("agent_backends", {}),
        inspector_summary=_build_inspector_summary(values),
        oss_url=values.get("final_oss_url"),
        source_code=values.get("final_html", ""),
        checkpoints=checkpoints
    )


@router.post("/{thread_id}/rollback", response_model=BaseResponse)
async def rollback_thread_to_checkpoint(thread_id: str, req: ThreadRollbackRequest, request: Request):
    """
    正式线程级回滚：
    把当前会话整体恢复到指定 checkpoint 的状态，而不是只在前端本地截断消息。
    """
    agent = get_agent(request)
    latest_config = {"configurable": {"thread_id": thread_id}}
    target_config = {"configurable": {"thread_id": thread_id, "checkpoint_id": req.checkpoint_id}}

    target_state = await agent.aget_state(target_config)
    if not target_state.values:
        raise HTTPException(status_code=404, detail="找不到该历史节点，可能已被清理或 ID 错误")

    latest_state = await agent.aget_state(latest_config)
    latest_values = latest_state.values or {}
    cloned_values = deepcopy(target_state.values or {})
    cloned_values["note_document"] = cloned_values.get("note_document") or build_note_document_from_state(cloned_values)
    cloned_values["active_panel"] = req.panel or cloned_values.get("active_panel") or "main"

    await _aupdate_state_compat(agent, latest_config, cloned_values, as_node=WORKSPACE_STATE_NODE)
    await _record_workspace_operation(
        agent,
        latest_config,
        action="workspace_rollback_thread",
        reason=f"回到历史节点: {req.checkpoint_id}",
        before_values=latest_values,
        selected_element_id=None,
    )
    return BaseResponse(message="已回到该历史节点。")



@router.get("/{thread_id}/trace/latest")
async def get_latest_turn_trace(thread_id: str, request: Request):
    agent = get_agent(request)
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = await agent.aget_state(config)
    values = (state_snapshot.values or {}) if state_snapshot else {}
    return {"status": "success", "data": values.get("turn_trace", {})}

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
        "needs_disambiguation": values.get("needs_disambiguation", False), # 是否需要人类消歧
        "planner_output": values.get("planner_output", {}),
        "planner_policy": values.get("planner_policy", {}),
        "note_document": values.get("note_document") or build_note_document_from_state(values),
        "turn_trace": values.get("turn_trace", {}),
        "agent_backends": values.get("agent_backends", {}),
        "inspector_summary": _build_inspector_summary(values),
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
    cloned_values["note_document"] = cloned_values.get("note_document") or build_note_document_from_state(cloned_values)
    
    # 只有当用户真的传了新指令，才去追加消息和触发 LLM
    if req.new_instruction:
        msg_key = f"{req.panel}_messages"
        messages_list = list(cloned_values.get(msg_key, []))
        messages_list.append(HumanMessage(content=req.new_instruction))
        cloned_values[msg_key] = messages_list
        cloned_values["active_panel"] = req.panel
        
        await _aupdate_state_compat(agent, new_config, cloned_values, as_node=WORKSPACE_STATE_NODE)
        await _record_workspace_operation(agent, new_config, action="workspace_fork", reason=f"从 {req.old_thread_id} 分叉并追加新指令", before_values={}, selected_element_id=None)
        return ForkResponse(new_thread_id=new_thread_id, parent_checkpoint=req.checkpoint_id, message="分支已创建，请用新ID连接WS继续流式生成。")
    else:
        # 如果没有新指令，仅仅做纯粹的状态克隆 (例如用户点击了"复制副本")
        await _aupdate_state_compat(agent, new_config, cloned_values, as_node=WORKSPACE_STATE_NODE)
        await _record_workspace_operation(agent, new_config, action="workspace_fork", reason=f"从 {req.old_thread_id} 创建项目副本", before_values={}, selected_element_id=None)
        return ForkResponse(new_thread_id=new_thread_id, parent_checkpoint=req.checkpoint_id, message="项目副本已创建完成。")

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
    state = await agent.aget_state(config)
    values = state.values or {}
    await _aupdate_state_compat(
        agent,
        config,
        {
            "selected_element_id": req.element_id,
            "note_document": _build_next_note_document(values, selected_element_id=req.element_id),
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    await _record_workspace_operation(agent, config, action="workspace_select_region", reason=f"锁定区块: {req.element_id}", before_values=values, selected_element_id=req.element_id)
    
    return BaseResponse(message=f"已成功锁定前端元素: {req.element_id}")
