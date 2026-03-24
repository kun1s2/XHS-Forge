import json
import asyncio
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocketState
from pydantic import ValidationError
from langgraph.types import Command
from app.schemas.requests import ChatWSPayload
from langchain_core.messages import AIMessage, HumanMessage
from app.services.cache_service import get_trend_cache, set_trend_cache, RiskControlCache
from app.services.trend_pipeline import process_new_trend_background
from app.services.trend_intelligence import infer_trend_profile
from app.core.config import settings
from app.core.note_document import build_note_document_from_state
from app.core.capability_response import build_capability_reply
from app.core.query_heuristics import looks_like_capability_query, looks_like_existing_canvas_edit
from app.core.request_semantics import payload_requests_create
from app.agents.utils.entity_utils import normalize_entity_name
from app.core.runtime_log import (
    append_latest_console_log,
    append_log_divider,
    reset_latest_console_log,
    summarize_node_output,
    summarize_turn_completion,
    truncate_text,
)

router = APIRouter()

# 定义思考状态映射表 (全局，供所有路由逻辑共用)
NODE_THOUGHT_MAP = {
    "intent_agent": "🔍 正在深度解析您的创作意图...",
    "research_agent": "🧠 正在为您搜寻最硬核的专业背景资料...",
    "tools": "🔧 正在调用专业工具执行任务...",
    "controversy_sniffer": "🛡️ 正在进行内容合规与舆情审计...",
    "note_editor": "✍️ 正在为您整理页面内容与编辑策略...",
    "truth_mode_checkpoint": "🧾 正在和您确认是否需要按真实经历或已确认事实来写...",
    "structure_checkpoint": "🧩 正在和您确认页面骨架方向...",
    "knowledge_review_checkpoint": "🧠 正在和您确认这轮候选知识怎么采用...",
    "fact_gap_checkpoint": "📌 正在和您确认缺失的关键信息...",
    "asset_checkpoint": "🖼️ 正在和您确认素材使用方案...",
    "fact_conflict_checkpoint": "⚖️ 正在和您确认冲突事实采用哪种说法...",
    "outline_resolver": "🧭 正在根据策略稳定解析页面骨架...",
    "component_builder": "👷 工兵正在全力搭建组件...",
    "theme_compiler": "🎨 正在为您生成高定版页面样式...",
    "document_renderer": "📺 正在进行云端打包渲染..."
}

TOOL_THOUGHT_MAP = {
    "retrieve_private_knowledge": "📚 正在访问企业私域机密知识库...",
    "search_public_internet": "🌐 正在触发全网搜索获取最新资讯...",
    "analyze_uploaded_images": "👁️ 正在利用视觉模型深度解析图片...",
    "enrich_product_tool": "📊 正在核实商品参数与最新定价...",
    "enrich_location_tool": "📍 正在通过高德地图精准定位坐标...",
    "generate_images_tool": "🎨 正在调用 CogView 绘制视觉素材..."
}

TRACE_STATE_NODE = "document_renderer"


def _safe_json_signature(value):
    try:
        return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _extract_note_document(values):
    current = (values or {}).get("note_document")
    if isinstance(current, dict) and current:
        return current
    return build_note_document_from_state(values or {})


def _get_document_blocks(doc):
    return list((doc or {}).get("blocks") or [])


def _summarize_document(values):
    doc = _extract_note_document(values)
    blocks = _get_document_blocks(doc)
    return {
        "title": ((doc.get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "block_count": len(blocks),
        "block_order": [
            {"id": str(block.get("id") or ""), "type": str(block.get("type") or "")}
            for block in blocks
        ],
    }


def _build_block_change_set(before_values, after_values):
    before_doc = _extract_note_document(before_values)
    after_doc = _extract_note_document(after_values)
    before_blocks = {str(block.get("id") or ""): block for block in _get_document_blocks(before_doc) if block.get("id")}
    after_blocks = {str(block.get("id") or ""): block for block in _get_document_blocks(after_doc) if block.get("id")}
    before_order = {str(block.get("id") or ""): idx for idx, block in enumerate(_get_document_blocks(before_doc)) if block.get("id")}
    after_order = {str(block.get("id") or ""): idx for idx, block in enumerate(_get_document_blocks(after_doc)) if block.get("id")}
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
        if _safe_json_signature(before_block.get("props") or {}) != _safe_json_signature(after_block.get("props") or {}):
            changed_fields.append("props")
        if _safe_json_signature(before_block.get("style") or {}) != _safe_json_signature(after_block.get("style") or {}):
            changed_fields.append("style")
        if changed_fields:
            changes.append({"id": block_id, "type": str(after_block.get("type") or before_block.get("type") or ""), "changed_fields": changed_fields})
    return changes


def _build_status_timeline(timeline: list[dict[str, Any]] | None) -> list[str]:
    statuses: list[str] = []
    seen: set[str] = set()
    for item in timeline or []:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("event") or "")
        node_name = str(item.get("node") or "")
        status = ""
        if event_type == "tool_start":
            status = TOOL_THOUGHT_MAP.get(node_name, f"我正在调用工具补齐这轮关键信息。")
        elif event_type == "node_start":
            status = NODE_THOUGHT_MAP.get(node_name, "")
        normalized = str(status or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            statuses.append(normalized)
    return statuses[:6]


def _build_agent_plan(turn_context: dict[str, Any] | None, after_values: dict[str, Any] | None) -> dict[str, Any]:
    context = turn_context or {}
    values = after_values or {}
    query = str(context.get("user_query") or "").strip()
    message_kind = str(context.get("message_kind") or "user_prompt").strip() or "user_prompt"
    selected_element_id = str(context.get("selected_element_id") or "").strip()
    active = str(values.get("active_archetype") or "").strip()
    if message_kind == "critique_action":
        return {
            "title": "我先按你刚才选中的复盘建议继续收口",
            "summary": "这次我会沿着最需要优先处理的问题继续优化当前页面，而不是重新起一版。",
            "steps": [
                "先锁定这次要改的重点范围",
                "按建议定向调整页面内容或结构",
                "最后再检查这一轮是否还有明显缺口",
            ],
            "watch_points": ["如果你只想改局部，我会尽量不动无关区块。"],
        }
    if selected_element_id and selected_element_id not in {"无", "无 (全局修改)", "none", "global"}:
        return {
            "title": "我会先按你的指令定向修改当前选中的积木",
            "summary": "这次会优先处理你刚刚点中的区域，尽量不扩大到整页重写。",
            "steps": [
                "先锁定这块当前承担的作用",
                "只修改你提到的标题、段落或局部信息",
                "改完后再把变化明确标出来给你看",
            ],
            "watch_points": ["如果这块和别的区域强耦合，我会尽量保持其它部分不被顺手改乱。"],
        }

    if active == "seeding":
        steps = [
            "先判断这页更适合购买判断、参数对比还是体验分流",
            "再补足影响判断的关键信息和图片",
            "最后把结论、事实、对比和风险边界收紧成完整档案",
        ]
        watch_points = ["如果事实或素材不够稳，我会先给你推荐方案，再继续往下搭。"]
    else:
        steps = [
            "先把这轮内容收成更像数码购买决策档案的判断结构",
            "再补当前最影响结论可信度的关键信息",
            "最后把判断、事实和素材收成完整版本",
        ]
        watch_points = ["如果中途出现关键信息缺口，我会先在聊天里和你确认，而不是硬写成完整结论。"]

    return {
        "title": "我先按当前目标把这页搭起来",
        "summary": f"我理解你这轮想处理的是：{query or '当前页面'}。",
        "steps": steps,
        "watch_points": watch_points,
    }


def _build_agent_summary(turn_context: dict[str, Any] | None, after_values: dict[str, Any] | None, critique_summary: dict[str, Any] | None) -> dict[str, Any]:
    values = after_values or {}
    critique = critique_summary or {}
    after_summary = _summarize_document(values)
    block_count = int(after_summary.get("block_count") or 0)
    changed_blocks = _build_block_change_set((turn_context or {}).get("before_values") or {}, values or {})
    remaining_gaps: list[str] = []
    for item in (critique.get("factual_issues") or [])[:2]:
        normalized = str(item).strip()
        if normalized:
            remaining_gaps.append(normalized)
    for item in (critique.get("completeness_issues") or [])[:2]:
        normalized = str(item).strip()
        if normalized and normalized not in remaining_gaps:
            remaining_gaps.append(normalized)
    next_actions: list[str] = []
    for item in (critique.get("action_recipes") or [])[:3]:
        label = str((item or {}).get("label") or "").strip()
        if label:
            next_actions.append(label)
    changed_count = len(changed_blocks)
    summary = f"这一轮我已经把页面更新成 {block_count} 个区块。"
    if changed_count > 0:
        summary = f"这一轮我更新了 {changed_count} 个重点区块，当前页面共有 {block_count} 个区块。"
    return {
        "title": "这一轮我已经先帮你推进到这里",
        "summary": summary,
        "remaining_gaps": remaining_gaps[:3],
        "next_actions": next_actions[:3],
    }


def _build_turn_trace(*, turn_context, before_values, after_values, timeline):
    changed_blocks = _build_block_change_set(before_values or {}, after_values or {})
    existing_trace = (after_values or {}).get("turn_trace") or {}
    note_editor_trace = existing_trace.get("note_editor") or {}
    content_like_fields = {"props", "type", "order", "added", "removed"}
    style_only = bool(changed_blocks) and any("style" in item.get("changed_fields", []) for item in changed_blocks) and not any(content_like_fields & set(item.get("changed_fields", [])) for item in changed_blocks)
    warnings = []
    if note_editor_trace.get("action") == "noop":
        warnings.append("noop")
    if note_editor_trace.get("fallback_used"):
        warnings.append("fallback_used")
    if style_only:
        warnings.append("style_changed_without_content")
    critique_feedback = (after_values or {}).get("critique_feedback") if isinstance((after_values or {}).get("critique_feedback"), dict) else {}
    critique_summary = {
        "score": critique_feedback.get("score"),
        "needs_revision": bool((after_values or {}).get("needs_revision")),
        "suggestions": [str(item) for item in (critique_feedback.get("suggestions") or []) if str(item).strip()][:3],
        "factual_issues": [str(item) for item in (critique_feedback.get("factual_issues") or []) if str(item).strip()][:3],
        "completeness_issues": [str(item) for item in (critique_feedback.get("completeness_issues") or []) if str(item).strip()][:3],
        "has_hook": critique_feedback.get("has_hook"),
        "has_call_to_action": critique_feedback.get("has_call_to_action"),
        "action_recipes": [
            {
                "label": str(item.get("label") or "").strip(),
                "prompt": str(item.get("prompt") or "").strip(),
                "scope": str(item.get("scope") or "").strip() or None,
                "why_now": str(item.get("why_now") or "").strip() or None,
                "expected_effect": str(item.get("expected_effect") or "").strip() or None,
                "expected_blocks": [
                    str(block).strip()
                    for block in (item.get("expected_blocks") or [])
                    if str(block).strip()
                ][:4],
            }
            for item in (critique_feedback.get("action_recipes") or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ][:4],
    } if critique_feedback else {}
    status_timeline = _build_status_timeline(timeline)
    return {
        "query": turn_context.get("user_query", ""),
        "message_kind": turn_context.get("message_kind") or "user_prompt",
        "selected_element_id": turn_context.get("selected_element_id"),
        "panel": turn_context.get("panel", "main"),
        "timeline": timeline,
        "status_timeline": status_timeline,
        "route": {
            "intent_route": (after_values or {}).get("intent_route", ""),
            "active_archetype": (after_values or {}).get("active_archetype", ""),
        },
        "planner": existing_trace.get("planner") or {},
        "note_editor": note_editor_trace,
        "before_summary": _summarize_document(before_values or {}),
        "after_summary": _summarize_document(after_values or {}),
        "changed_blocks": changed_blocks,
        "warnings": warnings,
        "conversation_checkpoints": existing_trace.get("conversation_checkpoints") or {},
        "critique": critique_summary,
        "agent_plan": _build_agent_plan(turn_context, after_values),
        "agent_summary": _build_agent_summary(turn_context, after_values, critique_summary),
    }


async def _aupdate_state_compat(agent, config, values, *, as_node: str):
    try:
        return await agent.aupdate_state(config, values, as_node=as_node)
    except TypeError:
        return await agent.aupdate_state(config, values)


def _latest_thread_config(config: dict | None) -> dict:
    configurable = dict((config or {}).get("configurable") or {})
    configurable.pop("checkpoint_id", None)
    return {"configurable": configurable}


def _build_turn_end_payload(
    checkpoint_id: str,
    *,
    oss_url,
    image_assets,
    source_code,
    node_prompts=None,
    note_document=None,
    planner_output=None,
    planner_policy=None,
    turn_trace=None,
    agent_backends=None,
):
    """
    统一构造 turn_end 包。正式协议以 note_document / planner / trace 为主，
    不再向前端公开旧页面协议字段，legacy 页面状态仅允许在 store/workspace 内部兼容层派生。
    """
    payload = {
        "checkpoint_id": checkpoint_id,
        "checkpointId": checkpoint_id,
        "oss_url": oss_url,
        "ossUrl": oss_url,
        "image_assets": image_assets or [],
        "imageAssets": image_assets or [],
        "source_code": source_code or "",
        "sourceCode": source_code or "",
        "htmlPreview": source_code or "",
    }
    if node_prompts is not None:
        payload["node_prompts"] = node_prompts
        payload["nodePrompts"] = node_prompts
    resolved_note_document = note_document or build_note_document_from_state({
        "note_document": note_document or {},
        "image_assets": image_assets or [],
    })
    if resolved_note_document is not None:
        payload["note_document"] = resolved_note_document
        payload["noteDocument"] = resolved_note_document
    if planner_output is not None:
        payload["planner_output"] = planner_output
    if planner_policy is not None:
        payload["planner_policy"] = planner_policy
        payload["plannerPolicy"] = planner_policy
    if turn_trace is not None:
        payload["turn_trace"] = turn_trace
        payload["turnTrace"] = turn_trace
    if agent_backends is not None:
        payload["agent_backends"] = agent_backends
        payload["agentBackends"] = agent_backends
    return payload


def _count_human_turns(values: dict | None, panel: str) -> int:
    messages = (values or {}).get(f"{panel}_messages") or []
    return sum(1 for msg in messages if isinstance(msg, HumanMessage))


def _build_turn_anchor_patch(values: dict | None, *, panel: str, checkpoint_id: str) -> dict[str, Any]:
    """
    为当前用户轮次写入正式历史锚点。

    这样“回到这里 / 从这里分支”不会只依赖前端内存，刷新页面后仍能挂在对应用户消息下面。
    """
    human_turns = _count_human_turns(values or {}, panel)
    if human_turns <= 0:
        return {}
    return {
        "turn_anchors": [
            {
                "panel": panel,
                "turn_index": human_turns - 1,
                "checkpoint_id": checkpoint_id,
            }
        ]
    }


def _payload_has_runtime_assets(payload: "ChatWSPayload") -> bool:
    """判断当前请求是否已经携带线程级素材上下文。"""
    return any(
        isinstance(asset, dict) and str(asset.get("url") or "").strip()
        for asset in (payload.current_assets or [])
    )


def _can_use_trend_cache_fast_path(payload: "ChatWSPayload") -> bool:
    """判断当前请求是否适合直接旁路到热词缓存页。

    只有真正空白的新建请求才允许直接复用整页缓存：
    - 没有本轮新上传图片
    - 没有线程级素材资产
    - 没有父 checkpoint（说明不是沿着已有工作区继续创作）
    """
    return (
        not bool(payload.image_urls or [])
        and not _payload_has_runtime_assets(payload)
        and not bool(payload.parent_checkpoint_id)
    )


def _build_runtime_image_assets(payload: "ChatWSPayload") -> list[dict[str, Any]]:
    """把前端线程资产池作为本轮图片上下文的唯一真相源。"""
    runtime_assets = [
        asset
        for asset in (payload.current_assets or [])
        if isinstance(asset, dict) and str(asset.get("url") or "").strip()
    ]
    return [{"__replace__": True}, *runtime_assets]


def _extract_truth_mode_progress(values: dict[str, Any] | None) -> dict[str, Any]:
    progress = ((values or {}).get("checkpoint_progress") or {}) if isinstance(values, dict) else {}
    if not isinstance(progress, dict):
        return {}
    return dict(progress.get("truth_mode") or {})


def _should_use_capability_reply(*, payload: "ChatWSPayload", query: str, awaiting_user_facts: bool) -> bool:
    normalized_query = str(query or "").strip()
    normalized_selected = str(payload.selected_element_id or "").strip()
    return (
        bool(normalized_query)
        and not awaiting_user_facts
        and not bool(payload.image_urls or [])
        and not looks_like_existing_canvas_edit(normalized_query)
        and looks_like_capability_query(normalized_query)
        and normalized_selected in {"", "无", "无 (全局修改)", "none", "global"}
    )


async def _send_capability_reply(
    *,
    agent,
    thread_id: str,
    payload: "ChatWSPayload",
    websocket: WebSocket,
    user_query_str: str,
):
    latest_config = {"configurable": {"thread_id": thread_id}}
    before_state = await agent.aget_state(latest_config)
    reply = build_capability_reply(before_state.values or {})
    msg_key = f"{payload.panel}_messages"
    human_msg = HumanMessage(content=user_query_str)
    await _aupdate_state_compat(
        agent,
        latest_config,
        {
            msg_key: [human_msg, AIMessage(content=reply)],
            "intent_route": "direct_chat_node",
            "agent_backends": {
                "intent_agent": "deterministic_capability_fast_path",
                "direct_chat_node": "deterministic_capability_reply",
            },
        },
        as_node="direct_chat_node",
    )
    snapshot = await agent.aget_state(latest_config)
    checkpoint_id = snapshot.config["configurable"]["checkpoint_id"]
    turn_trace = {
        "query": user_query_str,
        "message_kind": payload.message_kind or "user_prompt",
        "selected_element_id": payload.selected_element_id or "无 (全局修改)",
        "panel": payload.panel,
        "timeline": [
            {"event": "node_start", "node": "intent_agent"},
            {"event": "node_end", "node": "intent_agent"},
            {"event": "node_start", "node": "direct_chat_node"},
            {"event": "node_end", "node": "direct_chat_node"},
        ],
        "status_timeline": ["我先直接告诉你我现在能怎么配合。"],
        "route": {
            "intent_route": "direct_chat_node",
            "active_archetype": snapshot.values.get("active_archetype", "seeding"),
        },
        "changed_blocks": [],
        "warnings": [],
    }
    trace_patch = {"turn_trace": turn_trace}
    trace_patch.update(
        _build_turn_anchor_patch(
            snapshot.values or {},
            panel=payload.panel,
            checkpoint_id=checkpoint_id,
        )
    )
    await _aupdate_state_compat(agent, latest_config, trace_patch, as_node=TRACE_STATE_NODE)
    snapshot = await agent.aget_state(latest_config)

    append_latest_console_log("🧭 [DIRECT CHAT] 命中能力问答，直接走聊天答复，不触发页面生成。")
    await websocket.send_json({"event": "thought", "data": "🧭 我先直接告诉你我现在能怎么配合。"})
    await websocket.send_json({"event": "token", "node": "direct_chat_node", "data": reply})
    await websocket.send_json(
        {
            "event": "turn_end",
            "data": _build_turn_end_payload(
                checkpoint_id,
                oss_url=snapshot.values.get("final_oss_url"),
                image_assets=snapshot.values.get("image_assets", []),
                source_code=snapshot.values.get("final_html", ""),
                node_prompts=snapshot.values.get("node_prompts"),
                note_document=snapshot.values.get("note_document"),
                planner_output=snapshot.values.get("planner_output"),
                planner_policy=snapshot.values.get("planner_policy"),
                turn_trace=turn_trace,
                agent_backends=snapshot.values.get("agent_backends"),
            ),
        }
    )


def _normalize_checkpoint_action_payload(raw_interrupt: Any) -> dict[str, Any] | None:
    """把 LangGraph interrupt value 归一化成聊天区 action_required 载荷。"""
    if not isinstance(raw_interrupt, dict):
        return None
    action_type = str(raw_interrupt.get("action_type") or raw_interrupt.get("action") or "").strip()
    if not action_type:
        return None
    options = []
    for item in raw_interrupt.get("options") or []:
        if not isinstance(item, dict):
            continue
        options.append(
            {
                "label": str(item.get("label") or ""),
                "value": str(item.get("value") or ""),
                "description": str(item.get("description") or ""),
                "recommended": bool(item.get("recommended")),
                "asset_url": str(item.get("asset_url") or "") or None,
                "selected_asset_ids": list(item.get("selected_asset_ids") or []),
                "selected_fact_value": str(item.get("selected_fact_value") or "") or None,
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
            }
        )
    return {
        "action_type": action_type,
        "action": action_type,
        "checkpoint_id": str(raw_interrupt.get("checkpoint_id") or action_type),
        "title": str(raw_interrupt.get("title") or raw_interrupt.get("message") or "需要你确认一个关键决策"),
        "summary": str(raw_interrupt.get("summary") or raw_interrupt.get("message") or ""),
        "message": str(raw_interrupt.get("summary") or raw_interrupt.get("message") or ""),
        "recommended_option": str(raw_interrupt.get("recommended_option") or ""),
        "recommended_reason": str(raw_interrupt.get("recommended_reason") or ""),
        "proposal_summary": str(raw_interrupt.get("proposal_summary") or ""),
        "other_allowed": bool(raw_interrupt.get("other_allowed")),
        "other_placeholder": str(raw_interrupt.get("other_placeholder") or "") or None,
        "blocking": bool(raw_interrupt.get("blocking", True)),
        "input_schema": raw_interrupt.get("input_schema") if isinstance(raw_interrupt.get("input_schema"), dict) else None,
        "options": options,
    }

@router.websocket("/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    agent = websocket.app.state.agent
    if not agent:
        await websocket.send_json({"event": "error", "data": "AI 引擎未就绪"})
        await websocket.close()
        return

    try:
        while True:
            # 每一轮开始前，强制检查连接状态
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break

            try:
                data = await websocket.receive_text()
                
                # --- DEBUG 模式：打印原始输入 ---
                reset_latest_console_log(f"[DEBUG] 最新请求 thread={thread_id}")
                append_log_divider('REQUEST')
                append_latest_console_log(f"[DEBUG] 收到前端消息: {data[:200]}...")
                if settings.XHS_FORGE_DEBUG:
                    print(f"\n\033[95m[DEBUG] 收到前端消息: {data[:200]}...\033[0m")

                # 1. 解析 Payload
                payload_dict = json.loads(data)
                
                # --- HITL / Checkpoint 唤醒处理逻辑 ---
                if payload_dict.get("type") in ["submit_stance", "submit_disambiguation", "submit_checkpoint_decision"]:
                    print(f"📥 [HITL 唤醒] 收到决策: {payload_dict.get('type')}")
                    config = {"configurable": {"thread_id": thread_id}}

                    if payload_dict.get("type") == "submit_checkpoint_decision":
                        resume_payload = {
                            "action_type": payload_dict.get("action_type"),
                            "checkpoint_id": payload_dict.get("checkpoint_id"),
                            "decision": payload_dict.get("decision"),
                            "selected_asset_ids": payload_dict.get("selected_asset_ids") or [],
                            "selected_fact_value": payload_dict.get("selected_fact_value"),
                            "user_provided_facts": payload_dict.get("user_provided_facts") or {},
                            "custom_note": payload_dict.get("custom_note"),
                        }
                        await _run_graph_loop(
                            agent,
                            Command(resume=resume_payload),
                            config,
                            websocket,
                            turn_context={
                                "user_query": "",
                                "selected_element_id": payload_dict.get("selected_element_id"),
                                "panel": payload_dict.get("panel", "main"),
                                "message_kind": payload_dict.get("message_kind") or "checkpoint_decision",
                                "before_values": {},
                            },
                        )
                        continue

                    if payload_dict.get("type") == "submit_stance":
                        await agent.aupdate_state(config, {"user_stance": payload_dict.get("stance")})
                    else:
                        await agent.aupdate_state(config, {
                            "retrieved_knowledge": f"【指挥官校准结论】：{payload_dict.get('choice')}",
                            "needs_disambiguation": False
                        })
                    
                    # 续火执行
                    await _run_graph_loop(agent, None, config, websocket, turn_context={"user_query": "", "selected_element_id": payload_dict.get("selected_element_id"), "panel": payload_dict.get("panel", "main"), "before_values": {}})
                    continue

                # 2. 正常消息解析
                try:
                    payload = ChatWSPayload.model_validate_json(data)
                    append_latest_console_log(
                        f"🧾 [REQUEST] panel={payload.panel} | selected={payload.selected_element_id or 'global'} | "
                        f"assets={len(payload.current_assets or [])} | text={truncate_text(payload.content, 120) or '(empty)'}"
                    )
                except ValidationError as ve:
                    await websocket.send_json({"event": "error", "data": f"请求格式错误: {ve}"})
                    continue

                user_query_str = (payload.content or "").strip()
                pending_urls = payload.image_urls or []

                if not user_query_str and not pending_urls:
                    await websocket.send_json({"event": "error", "data": "请输入修改指令，或上传本轮要使用的新图片。"})
                    continue

                thread_state = await agent.aget_state({"configurable": {"thread_id": thread_id}})
                truth_mode_progress = _extract_truth_mode_progress(thread_state.values or {})
                awaiting_user_facts = bool(truth_mode_progress.get("awaiting_user_facts"))
                if awaiting_user_facts:
                    append_latest_console_log("🧾 [TRUTH MODE] 当前消息将作为用户补充事实继续执行。")

                if _should_use_capability_reply(payload=payload, query=user_query_str, awaiting_user_facts=awaiting_user_facts):
                    await _send_capability_reply(
                        agent=agent,
                        thread_id=thread_id,
                        payload=payload,
                        websocket=websocket,
                        user_query_str=user_query_str,
                    )
                    continue
                
                # --- 🛡️ 【第一防御梯队：风控网关拦截】 ---
                is_vetoed = await RiskControlCache.check_veto(user_query_str)
                if is_vetoed:
                    print(f"🛑 [绝对防御] 发现违规内容，已在入口点阻断: {user_query_str[:15]}")
                    veto_note_document = {
                        "document_meta": {"title": "🚫 触发系统安全保护", "active_archetype": "seeding", "scenarios": ["seeding"]},
                        "theme": {"page_theme": {}, "global_vars": {"--primary-vibe": "#ff2442"}},
                        "blocks": [
                            {
                                "id": "title_1",
                                "type": "TitleBlock",
                                "label": "标题",
                                "semantic_role": "heading",
                                "content_brief": "安全提示",
                                "props": {"type": "TitleBlock", "title": "🚫 触发系统安全保护"},
                                "style": {},
                                "asset_refs": [],
                                "fact_bindings": [],
                                "editable_targets": ["title"],
                                "asset_support": "none",
                                "fact_binding_support": False,
                                "order": 0,
                            },
                            {
                                "id": "text_1",
                                "type": "StoryText",
                                "label": "正文",
                                "semantic_role": "narrative_text",
                                "content_brief": "安全说明",
                                "props": {
                                    "type": "StoryText",
                                    "paragraphs": [
                                        "您探讨的话题涉及敏感、暴力或高危领域，已被拦截。",
                                        "XHS-Forge 致力于提供健康创作环境。✨",
                                    ],
                                },
                                "style": {},
                                "asset_refs": [],
                                "fact_bindings": [],
                                "editable_targets": ["paragraphs"],
                                "asset_support": "none",
                                "fact_binding_support": False,
                                "order": 1,
                            },
                        ],
                        "assets": [],
                        "fact_bindings": [],
                        "provenance": {"fact_sources": [], "fact_conflicts": [], "confirmed_facts": {}, "fact_review_status": "clear"},
                        "ui_state": {"selected_element_id": None, "active_panel": payload.panel, "patch_tracks": {}},
                        "planner": {},
                    }
                    await websocket.send_json({"event": "token", "node": "risk_gateway", "data": "\n🛡️ 系统检测到高危/敏感内容，风控拦截已生效！"})
                    await websocket.send_json({
                        "event": "turn_end",
                        "data": _build_turn_end_payload(
                            payload.parent_checkpoint_id or "veto_hit",
                            oss_url=None,
                            image_assets=payload.current_assets or [],
                            source_code="",
                            note_document=veto_note_document,
                        ),
                    })
                    continue

                # --- 2. 【第二阶段：极速嗅探】去 Redis 查缓存 ---
                selected_el = payload.selected_element_id or "无 (全局修改)"
                candidate_topic = normalize_entity_name(user_query_str)
                if (
                    candidate_topic
                    and len(candidate_topic) <= 40
                    and payload_requests_create(
                        content=user_query_str,
                        panel=payload.panel,
                        selected_element_id=selected_el,
                    )
                ):
                    profile = infer_trend_profile(candidate_topic)
                    from app.services.cache_service import cache_service
                    await cache_service.update_trend_rank(
                        candidate_topic,
                        score_increment=1.0,
                        scenario_hint=profile["scenario_hint"],
                        source="user_query",
                    )
                
                cached_result = await get_trend_cache(user_query_str, selected_el)
                if cached_result and _can_use_trend_cache_fast_path(payload) and not awaiting_user_facts:
                    print(f"🚀 [语义缓存] 命中热点: {user_query_str[:15]}")
                    await websocket.send_json({"event": "token", "node": "cache", "data": "\n🚀 [语义缓存] 命中高相似度热点，大模型已旁路！"})
                    await websocket.send_json({
                        "event": "turn_end",
                        "data": _build_turn_end_payload(
                            payload.parent_checkpoint_id or "cache_hit",
                            oss_url=None,
                            image_assets=payload.current_assets or [],
                            source_code="",
                            note_document=build_note_document_from_state({"note_document": cached_result}),
                        ),
                    })
                    continue
                else:
                    if cached_result and not _can_use_trend_cache_fast_path(payload):
                        print("🧩 [语义缓存] 当前请求带有素材或父 checkpoint，跳过整页缓存旁路，改走实时生成链。")
                    # 如果缓存未命中，且是全新生成，挂载异步收录任务
                    if payload_requests_create(
                        content=user_query_str,
                        panel=payload.panel,
                        selected_element_id=selected_el,
                    ):
                        print(f"🔄 [任务挂载] 未命中缓存，已将「{user_query_str[:15]}...」加入后台热点收录队列")
                        asyncio.create_task(process_new_trend_background(candidate_topic or user_query_str, websocket=websocket))

                # 3. 准备执行输入
                if pending_urls:
                    message_content = [{"type": "text", "text": payload.content}]
                    for u in pending_urls: message_content.append({"type": "image_url", "image_url": {"url": u}})
                    new_msg = HumanMessage(content=message_content)
                else:
                    new_msg = HumanMessage(content=payload.content)

                msg_key = f"{payload.panel}_messages"
                inputs = {
                    msg_key: [new_msg],
                    "active_panel": payload.panel,
                    "selected_element_id": payload.selected_element_id or "无 (全局修改)",
                    "creator_persona": payload.creator_persona or "硬核数码博主",
                    "image_assets": _build_runtime_image_assets(payload),
                    "pending_images": pending_urls,
                }
                if awaiting_user_facts:
                    inputs["user_provided_facts"] = {
                        "raw_text": user_query_str,
                        "source": "chat_followup",
                        "requested_by": "truth_mode_checkpoint",
                    }
                    inputs["checkpoint_progress"] = {
                        "truth_mode": {
                            "awaiting_user_facts": False,
                            "resolved": True,
                            "query": str(truth_mode_progress.get("query") or ""),
                            "selected": "provide_user_facts",
                        }
                    }
                
                config = {"configurable": {"thread_id": thread_id, "vector_store": websocket.app.state.vector_store}}
                if payload.parent_checkpoint_id: config["configurable"]["checkpoint_id"] = payload.parent_checkpoint_id

                # 执行图循环
                before_state = await agent.aget_state(config)
                await _run_graph_loop(
                    agent,
                    inputs,
                    config,
                    websocket,
                    turn_context={
                        "user_query": user_query_str,
                        "selected_element_id": payload.selected_element_id or "无 (全局修改)",
                        "panel": payload.panel,
                        "message_kind": payload.message_kind or "user_prompt",
                        "before_values": before_state.values or {},
                    },
                )

            except WebSocketDisconnect:
                raise  # 交给外层统一处理，避免当普通错误处理或向已断开连接写数据
            except Exception as e:
                print(f"❌ WebSocket 循环错误: {e}")
                if settings.XHS_FORGE_DEBUG: import traceback; traceback.print_exc()
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"event": "error", "data": str(e)})

    except WebSocketDisconnect as e:
        print(f"[WS] Client {thread_id} disconnected (code={getattr(e, 'code', '')}, reason={getattr(e, 'reason', '') or '(none)'}).")

async def _run_graph_loop(agent, inputs, config, websocket, turn_context=None):
    """【核心循环】带全量日志、自动续火与 HITL 拦截"""
    current_inputs = inputs
    resume_count = 0
    MAX_RESUME = 10
    last_next_signature = None
    repeated_next_count = 0
    pending_interrupt_payload: dict[str, Any] | None = None
    
    # 🌟 哨兵监控：实时捕获最后一公里产生的物理资产
    final_oss_url = None
    final_html = ""
    trace_timeline = []

    while resume_count < MAX_RESUME:
        if websocket.client_state != WebSocketState.CONNECTED:
            print("🛑 [自动熔断] 客户端已断开")
            return

        async for event in agent.astream_events(current_inputs, config=config, version="v2"):
            if websocket.client_state != WebSocketState.CONNECTED: return
            kind = event["event"]
            
            # 1. 物理资产捕获 (document_renderer 节点产出)
            if kind == "on_chain_end" and event["name"] == "document_renderer":
                output = event["data"].get("output", {})
                final_oss_url = output.get("final_oss_url")
                final_html = output.get("final_html", "")
                if settings.XHS_FORGE_DEBUG:
                    message = f"📺 [渲染监控] 成功捕获最终 OSS 链接: {final_oss_url[:50] if final_oss_url else None}..."
                    print(message)
                    append_latest_console_log(message)

            # --- DEBUG 日志输出 ---
            if settings.XHS_FORGE_DEBUG:
                if kind == "on_chain_start" and event["name"] != "LangGraph":
                    message = f"▶️  [NODE START]: {event['name']}"
                    print(f"\033[1;36m{message}\033[0m")
                    append_latest_console_log(message)
                    trace_timeline.append({"event": "node_start", "node": event["name"]})
                elif kind == "on_chain_end" and event["name"] != "LangGraph":
                    output = event["data"].get("output", {})
                    out_str = summarize_node_output(event['name'], output)
                    message = f"✅ [NODE END]: {event['name']} -> {out_str}"
                    print(f"\033[1;32m{message}\033[0m")
                    append_latest_console_log(message)
                    trace_timeline.append({"event": "node_end", "node": event["name"]})

            # 1. 思维链下发
            if kind == "on_chain_end":
                node_name = event["name"]
                output = event["data"].get("output")
                thought = _extract_thought(output)
                if thought:
                    await websocket.send_json({"event": "thought_process", "data": {"node": node_name, "content": thought}})

            # 2. Token 流式输出
            if kind == "on_chat_model_stream":
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node") or metadata.get("node") or ""
                chunk = event["data"]["chunk"]
                content = chunk.content or ""
                if chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks: content += (tc.get("args") or "")
                if content:
                    await websocket.send_json({"event": "token", "data": content, "node": node_name})

            if kind == "on_chain_stream" and event.get("name") == "LangGraph":
                chunk = event.get("data", {}).get("chunk") or {}
                interrupts = list(chunk.get("__interrupt__") or [])
                if interrupts:
                    first_interrupt = interrupts[0]
                    pending_interrupt_payload = _normalize_checkpoint_action_payload(
                        getattr(first_interrupt, "value", None)
                    )

            # 3. 状态文案提示
            elif kind == "on_chain_start":
                node_name = event["name"]
                if node_name in NODE_THOUGHT_MAP:
                    await websocket.send_json({"event": "thought", "data": NODE_THOUGHT_MAP[node_name]})
            elif kind == "on_tool_start":
                tool_name = event["name"]
                thought = TOOL_THOUGHT_MAP.get(tool_name, f"🔧 正在执行工具: {tool_name}...")
                trace_timeline.append({"event": "tool_start", "node": tool_name})
                append_latest_console_log(f"🔧 [TOOL START]: {tool_name}")
                await websocket.send_json({"event": "thought", "data": thought})

        if pending_interrupt_payload:
            await websocket.send_json({"event": "action_required", "data": pending_interrupt_payload})
            return

        # 检查快照。注意：如果这轮是从旧 checkpoint 分叉出来的，收尾必须回到“线程最新”状态，
        # 不能继续拿带 checkpoint_id 的 config 读旧快照，否则前端会收到父版本页面。
        snapshot = await agent.aget_state(config)
        latest_config = _latest_thread_config(config)
        if not snapshot.next:
            latest_snapshot = await agent.aget_state(latest_config)
            turn_trace = _build_turn_trace(
                turn_context=turn_context or {},
                before_values=(turn_context or {}).get("before_values") or {},
                after_values=latest_snapshot.values or {},
                timeline=trace_timeline,
            )
            try:
                trace_patch = {"turn_trace": turn_trace}
                trace_patch.update(
                    _build_turn_anchor_patch(
                        latest_snapshot.values or {},
                        panel=(turn_context or {}).get("panel") or "main",
                        checkpoint_id=latest_snapshot.config["configurable"]["checkpoint_id"],
                    )
                )
                await _aupdate_state_compat(agent, latest_config, trace_patch, as_node=TRACE_STATE_NODE)
                latest_snapshot = await agent.aget_state(latest_config)
            except Exception:
                pass
            append_log_divider('TURN END')
            append_latest_console_log(f"🏁 [TURN END]: {summarize_turn_completion(turn_trace, latest_snapshot.values or {})}")
            await websocket.send_json({
                "event": "turn_end",
                "data": _build_turn_end_payload(
                    latest_snapshot.config["configurable"]["checkpoint_id"],
                    oss_url=final_oss_url or latest_snapshot.values.get("final_oss_url"),
                    image_assets=latest_snapshot.values.get("image_assets", []),
                    source_code=final_html or latest_snapshot.values.get("final_html", ""),
                    node_prompts=latest_snapshot.values.get("node_prompts"),
                    note_document=latest_snapshot.values.get("note_document"),
                    planner_output=latest_snapshot.values.get("planner_output"),
                    planner_policy=latest_snapshot.values.get("planner_policy"),
                    turn_trace=turn_trace,
                    agent_backends=latest_snapshot.values.get("agent_backends"),
                ),
            })
            return

        next_signature = tuple(snapshot.next)
        if current_inputs is None and next_signature == last_next_signature:
            repeated_next_count += 1
        else:
            repeated_next_count = 0
        last_next_signature = next_signature

        if repeated_next_count >= 2:
            message = f"⚠️ [AUTO RESUME GUARD] 检测到重复续火 {next_signature}，提前下发当前快照避免前端卡死。"
            print(message)
            append_latest_console_log(message)
            turn_trace = _build_turn_trace(
                turn_context=turn_context or {},
                before_values=(turn_context or {}).get("before_values") or {},
                after_values=snapshot.values or {},
                timeline=trace_timeline,
            )
            turn_trace["warnings"] = list((turn_trace.get("warnings") or [])) + ["auto_resume_guard"]
            append_log_divider('TURN END')
            append_latest_console_log(f"🏁 [TURN END]: {summarize_turn_completion(turn_trace, snapshot.values or {})}")
            try:
                trace_patch = {"turn_trace": turn_trace}
                trace_patch.update(
                    _build_turn_anchor_patch(
                        snapshot.values or {},
                        panel=(turn_context or {}).get("panel") or "main",
                        checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
                    )
                )
                await _aupdate_state_compat(agent, latest_config, trace_patch, as_node=TRACE_STATE_NODE)
                snapshot = await agent.aget_state(latest_config)
            except Exception:
                pass
            await websocket.send_json({
                "event": "turn_end",
                "data": _build_turn_end_payload(
                    snapshot.config["configurable"]["checkpoint_id"],
                    oss_url=final_oss_url or snapshot.values.get("final_oss_url"),
                    image_assets=snapshot.values.get("image_assets", []),
                    source_code=final_html or snapshot.values.get("final_html", ""),
                    node_prompts=snapshot.values.get("node_prompts"),
                    note_document=snapshot.values.get("note_document"),
                    planner_output=snapshot.values.get("planner_output"),
                    planner_policy=snapshot.values.get("planner_policy"),
                    turn_trace=turn_trace,
                    agent_backends=snapshot.values.get("agent_backends"),
                ),
            })
            return

        # HITL 检查
        if "controversy_sniffer" in snapshot.next and snapshot.values.get("needs_disambiguation"):
            await websocket.send_json({"event": "action_required", "data": {"action": "entity_disambiguation", "message": "发现消歧项", "options": snapshot.values.get("disambiguation_options", [])}})
            return
        if "note_editor" in snapshot.next and snapshot.values.get("has_controversy") and not snapshot.values.get("user_stance"):
            await websocket.send_json({"event": "action_required", "data": {"action": "stance_decision", "message": "发现争议", "options": [{"label": "🔴 黑榜", "value": "negative_stance"}, {"label": "🟢 红榜", "value": "positive_stance"}]}})
            return

        # 自动续火
        if settings.XHS_FORGE_DEBUG:
            message = f"🔥 [AUTO RESUME] 命中中断点 {snapshot.next}，正在自动唤醒..."
            print(f"\033[90m{message}\033[0m")
            append_latest_console_log(message)
        current_inputs = None
        resume_count += 1

    latest_config = _latest_thread_config(config)
    snapshot = await agent.aget_state(latest_config)
    message = f"⚠️ [AUTO RESUME GUARD] 超过最大自动续火次数，强制回传当前快照: {snapshot.next}"
    print(message)
    append_latest_console_log(message)
    turn_trace = _build_turn_trace(
        turn_context=turn_context or {},
        before_values=(turn_context or {}).get("before_values") or {},
        after_values=snapshot.values or {},
        timeline=trace_timeline,
    )
    turn_trace["warnings"] = list((turn_trace.get("warnings") or [])) + ["max_auto_resume_exceeded"]
    append_log_divider('TURN END')
    append_latest_console_log(f"🏁 [TURN END]: {summarize_turn_completion(turn_trace, snapshot.values or {})}")
    try:
        trace_patch = {"turn_trace": turn_trace}
        trace_patch.update(
            _build_turn_anchor_patch(
                snapshot.values or {},
                panel=(turn_context or {}).get("panel") or "main",
                checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
            )
        )
        await _aupdate_state_compat(agent, latest_config, trace_patch, as_node=TRACE_STATE_NODE)
        snapshot = await agent.aget_state(latest_config)
    except Exception:
        pass
    await websocket.send_json({
        "event": "turn_end",
        "data": _build_turn_end_payload(
            snapshot.config["configurable"]["checkpoint_id"],
            oss_url=final_oss_url or snapshot.values.get("final_oss_url"),
            image_assets=snapshot.values.get("image_assets", []),
            source_code=final_html or snapshot.values.get("final_html", ""),
            node_prompts=snapshot.values.get("node_prompts"),
            note_document=snapshot.values.get("note_document"),
            planner_output=snapshot.values.get("planner_output"),
            planner_policy=snapshot.values.get("planner_policy"),
            turn_trace=turn_trace,
            agent_backends=snapshot.values.get("agent_backends"),
        ),
    })
    return

def _extract_thought(output):
    if not isinstance(output, dict): return None
    top_level = output.get("thought_process")
    if top_level:
        return top_level
    for key in ["structure_result", "style_result", "content_result"]:
        res_obj = output.get(key)
        if res_obj is not None:
            return getattr(res_obj, "thought_process", None)
    return None
