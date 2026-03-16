import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocketState
from pydantic import ValidationError
from app.schemas.requests import ChatWSPayload
from langchain_core.messages import HumanMessage
from app.services.cache_service import get_trend_cache, set_trend_cache, RiskControlCache
from app.services.trend_pipeline import process_new_trend_background
from app.core.config import settings

router = APIRouter()

# 定义思考状态映射表 (全局，供所有路由逻辑共用)
NODE_THOUGHT_MAP = {
    "intent_agent": "🔍 正在深度解析您的创作意图...",
    "research_agent": "🧠 正在为您搜寻最硬核的专业背景资料...",
    "tools": "🔧 正在调用专业工具执行任务...",
    "controversy_sniffer": "🛡️ 正在进行内容合规与舆情审计...",
    "content_node": "✍️ 正在为您撰写爆款文案...",
    "outline_node": "🗺️ 正在为您勾勒页面大纲...",
    "component_builder": "👷 工兵正在全力搭建组件...",
    "enrichment_node": "🚀 正在执行事实补全与地理位置打卡...",
    "style_node": "🎨 正在为您生成高定版页面样式...",
    "render": "📺 正在进行云端打包渲染..."
}

TOOL_THOUGHT_MAP = {
    "retrieve_private_knowledge": "📚 正在访问企业私域机密知识库...",
    "search_public_internet": "🌐 正在触发全网搜索获取最新资讯...",
    "analyze_uploaded_images": "👁️ 正在利用视觉模型深度解析图片...",
    "enrich_product_tool": "📊 正在核实商品参数与最新定价...",
    "enrich_location_tool": "📍 正在通过高德地图精准定位坐标...",
    "generate_images_tool": "🎨 正在调用 CogView 绘制视觉素材..."
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
                if settings.XHS_FORGE_DEBUG:
                    print(f"\n\033[95m[DEBUG] 收到前端消息: {data[:200]}...\033[0m")

                # 1. 解析 Payload
                payload_dict = json.loads(data)
                
                # --- HITL 唤醒处理逻辑 (Stance/Disambiguation) ---
                if payload_dict.get("type") in ["submit_stance", "submit_disambiguation"]:
                    print(f"📥 [HITL 唤醒] 收到决策: {payload_dict.get('type')}")
                    config = {"configurable": {"thread_id": thread_id}}
                    
                    if payload_dict.get("type") == "submit_stance":
                        await agent.aupdate_state(config, {"user_stance": payload_dict.get("stance")})
                    else:
                        await agent.aupdate_state(config, {
                            "retrieved_knowledge": f"【指挥官校准结论】：{payload_dict.get('choice')}",
                            "needs_disambiguation": False
                        })
                    
                    # 续火执行
                    await _run_graph_loop(agent, None, config, websocket)
                    continue

                # 2. 正常消息解析
                try:
                    payload = ChatWSPayload.model_validate_json(data)
                except ValidationError as ve:
                    await websocket.send_json({"event": "error", "data": f"请求格式错误: {ve}"})
                    continue

                user_query_str = payload.content
                
                # --- 🛡️ 【第一防御梯队：风控网关拦截】 ---
                is_vetoed = await RiskControlCache.check_veto(user_query_str)
                if is_vetoed:
                    print(f"🛑 [绝对防御] 发现违规内容，已在入口点阻断: {user_query_str[:15]}")
                    veto_dsl = {
                        "page_order": ["title_1", "text_1"],
                        "title_1": {"type": "TitleBlock", "title": "🚫 触发系统安全保护"},
                        "text_1": {
                            "type": "StoryText", 
                            "paragraphs": ["您探讨的话题涉及敏感、暴力或高危领域，已被拦截。", "XHS-Forge 致力于提供健康创作环境。✨"]
                        }
                    }
                    await websocket.send_json({"event": "token", "node": "risk_gateway", "data": "\n🛡️ 系统检测到高危/敏感内容，风控拦截已生效！"})
                    await websocket.send_json({
                        "event": "turn_end",
                        "data": {
                            "checkpoint_id": payload.parent_checkpoint_id or "veto_hit",
                            "oss_url": None,
                            "image_assets": payload.current_assets or [],
                            "page_data": veto_dsl,
                            "style_data": {"global_vars": {"--primary-vibe": "#ff2442"}},
                            "source_code": ""
                        }
                    })
                    continue

                # --- 2. 【第二阶段：极速嗅探】去 Redis 查缓存 ---
                selected_el = payload.selected_element_id or "无 (全局修改)"
                pending_urls = payload.image_urls or []
                
                cached_result = await get_trend_cache(user_query_str, selected_el)
                if cached_result and not pending_urls:
                    print(f"🚀 [语义缓存] 命中热点: {user_query_str[:15]}")
                    await websocket.send_json({"event": "token", "node": "cache", "data": "\n🚀 [语义缓存] 命中高相似度热点，大模型已旁路！"})
                    await websocket.send_json({
                        "event": "turn_end",
                        "data": {
                            "checkpoint_id": payload.parent_checkpoint_id or "cache_hit",
                            "oss_url": None,
                            "image_assets": payload.current_assets or [],
                            "page_data": cached_result,
                            "style_data": {},
                            "source_code": ""
                        }
                    })
                    continue
                else:
                    # 如果缓存未命中，且是全新生成，挂载异步收录任务
                    if selected_el in ["无 (全局修改)", "none", None]:
                        print(f"🔄 [任务挂载] 未命中缓存，已将「{user_query_str[:15]}...」加入后台热点收录队列")
                        asyncio.create_task(process_new_trend_background(user_query_str, websocket=websocket))

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
                    "pending_images": pending_urls,
                }
                
                config = {"configurable": {"thread_id": thread_id, "vector_store": websocket.app.state.vector_store}}
                if payload.parent_checkpoint_id: config["configurable"]["checkpoint_id"] = payload.parent_checkpoint_id

                # 执行图循环
                await _run_graph_loop(agent, inputs, config, websocket)

            except Exception as e:
                print(f"❌ WebSocket 循环错误: {e}")
                if settings.XHS_FORGE_DEBUG: import traceback; traceback.print_exc()
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"event": "error", "data": str(e)})

    except WebSocketDisconnect:
        print(f"[WS] Client {thread_id} disconnected.")

async def _run_graph_loop(agent, inputs, config, websocket):
    """【核心循环】带全量日志、自动续火与 HITL 拦截"""
    current_inputs = inputs
    resume_count = 0
    MAX_RESUME = 10

    while resume_count < MAX_RESUME:
        if websocket.client_state != WebSocketState.CONNECTED:
            print("🛑 [自动熔断] 客户端已断开")
            return

        async for event in agent.astream_events(current_inputs, config=config, version="v2"):
            if websocket.client_state != WebSocketState.CONNECTED: return
            kind = event["event"]
            
            # --- DEBUG 日志输出 ---
            if settings.XHS_FORGE_DEBUG:
                if kind == "on_chain_start" and event["name"] != "LangGraph":
                    print(f"\033[1;36m▶️  [NODE START]: {event['name']}\033[0m")
                elif kind == "on_chain_end" and event["name"] != "LangGraph":
                    output = event["data"].get("output", {})
                    out_str = str(output)[:300] + "..." if len(str(output)) > 300 else str(output)
                    print(f"\033[1;32m✅ [NODE END]: {event['name']} -> Output: {out_str}\033[0m")

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

            # 3. 状态文案提示
            elif kind == "on_chain_start":
                node_name = event["name"]
                if node_name in NODE_THOUGHT_MAP:
                    await websocket.send_json({"event": "thought", "data": NODE_THOUGHT_MAP[node_name]})
            elif kind == "on_tool_start":
                tool_name = event["name"]
                thought = TOOL_THOUGHT_MAP.get(tool_name, f"🔧 正在执行工具: {tool_name}...")
                await websocket.send_json({"event": "thought", "data": thought})

        # 检查快照
        snapshot = await agent.aget_state(config)
        if not snapshot.next:
            # 运行结束，下发最终结果
            await websocket.send_json({
                "event": "turn_end",
                "data": {
                    "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
                    "oss_url": snapshot.values.get("final_oss_url"),
                    "image_assets": snapshot.values.get("image_assets", []),
                    "page_data": snapshot.values.get("data_dsl", {}),
                    "style_data": snapshot.values.get("style_dsl", {}),
                    "source_code": snapshot.values.get("final_html", ""),
                }
            })
            return

        # HITL 检查
        if "controversy_sniffer" in snapshot.next and snapshot.values.get("needs_disambiguation"):
            await websocket.send_json({"event": "action_required", "data": {"action": "entity_disambiguation", "message": "发现消歧项", "options": snapshot.values.get("disambiguation_options", [])}})
            return
        if "content_node" in snapshot.next and snapshot.values.get("has_controversy") and not snapshot.values.get("user_stance"):
            await websocket.send_json({"event": "action_required", "data": {"action": "stance_decision", "message": "发现争议", "options": [{"label": "🔴 黑榜", "value": "negative_stance"}, {"label": "🟢 红榜", "value": "positive_stance"}]}})
            return

        # 自动续火
        if settings.XHS_FORGE_DEBUG: print(f"\033[90m🔥 [AUTO RESUME] 命中中断点 {snapshot.next}，正在自动唤醒...\033[0m")
        current_inputs = None
        resume_count += 1

def _extract_thought(output):
    if not isinstance(output, dict): return None
    for key in ["intent_result", "structure_result", "style_result", "content_result"]:
        if key in output: return getattr(output[key], "thought_process", None)
    return output.get("thought_process")
