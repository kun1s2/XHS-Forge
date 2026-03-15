import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocketState
from pydantic import ValidationError
from app.schemas.requests import ChatWSPayload
from langchain_core.messages import HumanMessage
from app.services.cache_service import get_trend_cache, set_trend_cache, RiskControlCache
from app.services.trend_pipeline import process_new_trend_background

router = APIRouter()

@router.websocket("/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    agent = websocket.app.state.agent
    if not agent:
        await websocket.send_json({"type": "error", "message": "AI 引擎未就绪"})
        await websocket.close()
        return

    try:
        while True:
            try:
                data = await websocket.receive_text()
                
                # 1. 解析 Payload
                try:
                    payload_dict = json.loads(data)
                    
                    # ✨ HITL 唤醒逻辑：处理人类提交的立场决策
                    if payload_dict.get("type") == "submit_stance":
                        stance = payload_dict.get("stance")
                        print(f"📥 [HITL 唤醒] 收到人类决策立场: {stance}")
                        
                        config = {"configurable": {"thread_id": thread_id}}
                        # 1. 将人类的偏见注入 State
                        await agent.aupdate_state(config, {"user_stance": stance})
                        
                        # 2. 唤醒图引擎：传入 None 告诉 LangGraph 从中断点继续
                        async for event in agent.astream_events(None, config=config, version="v2"):
                            kind = event["event"]
                            if kind == "on_chat_model_stream":
                                metadata = event.get("metadata", {})
                                node_name = metadata.get("langgraph_node") or metadata.get("node") or ""
                                chunk = event["data"]["chunk"]
                                content = chunk.content or ""
                                if chunk.tool_call_chunks:
                                    for tc in chunk.tool_call_chunks:
                                        if tc.get("args"): content += tc["args"]
                                if content:
                                    await websocket.send_json({
                                        "event": "token", 
                                        "data": content,
                                        "node": node_name
                                    })
                            elif kind == "on_chain_start":
                                node_name = event["name"]
                                if node_name in NODE_THOUGHT_MAP:
                                    await websocket.send_json({
                                        "event": "thought",
                                        "data": NODE_THOUGHT_MAP[node_name]
                                    })
                            elif kind == "on_tool_start":
                                tool_name = event["name"]
                                thought = TOOL_THOUGHT_MAP.get(tool_name, f"🔧 正在执行工具: {tool_name}...")
                                await websocket.send_json({
                                    "event": "thought",
                                    "data": thought
                                })

                        # 3. 运行结束，下发最终状态
                        final_state = await agent.aget_state(config)
                        await websocket.send_json({
                            "event": "turn_end",
                            "data": {
                                "checkpoint_id": final_state.config["configurable"]["checkpoint_id"],
                                "oss_url": final_state.values.get("final_oss_url"),
                                "page_data": final_state.values.get("data_dsl", {}),
                                "style_data": final_state.values.get("style_dsl", {}),
                                "node_prompts": final_state.values.get("node_prompts", {}),
                                "source_code": final_state.values.get("final_html", ""),
                            }
                        })
                        continue

                    # ✨ HITL 唤醒逻辑：处理人类提交的消歧决策
                    if payload_dict.get("type") == "submit_disambiguation":
                        choice = payload_dict.get("choice")
                        print(f"📥 [HITL 唤醒] 收到实体消歧决策: {choice}")
                        
                        config = {"configurable": {"thread_id": thread_id}}
                        # 注入选择并清除标志位
                        await agent.aupdate_state(config, {
                            "retrieved_knowledge": f"【指挥官校准结论】：{choice}",
                            "needs_disambiguation": False
                        })
                        
                        # 唤醒图引擎
                        async for event in agent.astream_events(None, config=config, version="v2"):
                            kind = event["event"]
                            if kind == "on_chat_model_stream":
                                metadata = event.get("metadata", {})
                                node_name = metadata.get("langgraph_node") or metadata.get("node") or ""
                                chunk = event["data"]["chunk"]
                                content = chunk.content or ""
                                if chunk.tool_call_chunks:
                                    for tc in chunk.tool_call_chunks:
                                        if tc.get("args"): content += tc["args"]
                                if content:
                                    await websocket.send_json({"event": "token", "data": content, "node": node_name})
                            elif kind == "on_chain_start":
                                node_name = event["name"]
                                if node_name in NODE_THOUGHT_MAP:
                                    await websocket.send_json({"event": "thought", "data": NODE_THOUGHT_MAP[node_name]})
                            elif kind == "on_tool_start":
                                tool_name = event["name"]
                                thought = TOOL_THOUGHT_MAP.get(tool_name, f"🔧 正在执行工具: {tool_name}...")
                                await websocket.send_json({"event": "thought", "data": thought})

                        # 运行结束，下发最终状态
                        final_state = await agent.aget_state(config)
                        await websocket.send_json({
                            "event": "turn_end",
                            "data": {
                                "checkpoint_id": final_state.config["configurable"]["checkpoint_id"],
                                "oss_url": final_state.values.get("final_oss_url"),
                                "image_assets": final_state.values.get("image_assets", []),
                                "page_data": final_state.values.get("data_dsl", {}),
                                "style_data": final_state.values.get("style_dsl", {}),
                                "node_prompts": final_state.values.get("node_prompts", {}),
                                "source_code": final_state.values.get("final_html", ""),
                            }
                        })
                        continue

                    payload = ChatWSPayload.model_validate_json(data)
                except ValidationError as ve:
                    await websocket.send_json({"type": "error", "message": f"请求格式错误: {ve}"})
                    continue
                
                # ✨ 极速嗅探：去 Redis 查有没有人问过一模一样的问题
                user_query_str = payload.content
                selected_el = payload.selected_element_id or "无 (全局修改)"
                pending_urls = payload.image_urls or []
                
                # 🛡️ 前置风控网关：双栈否决检查
                is_vetoed = await RiskControlCache.check_veto(user_query_str)
                if is_vetoed:
                    print(f"🛑 [风控拦截] 拒绝为高危/争议话题提供生成服务: {user_query_str[:15]}")
                    
                    # 构建优雅的兜底 DSL
                    veto_dsl = {
                        "page_order": ["title_1", "text_1"],
                        "title_1": {
                            "type": "TitleBlock",
                            "title": "🚫 触发系统保护机制"
                        },
                        "text_1": {
                            "type": "StoryText",
                            "paragraphs": [
                                "您探讨的话题涉及敏感或高危领域，系统风控保护已开启。",
                                "我们倡导健康绿色的网络环境，请换个话题试试吧~ ✨"
                            ]
                        }
                    }
                    
                    await websocket.send_json({
                        "type": "token",
                        "node": "risk_gateway",
                        "content": "\n🛡️ 系统检测到高危内容，已触发风控拦截..."
                    })
                    
                    await websocket.send_json({
                        "type": "turn_end",
                        "checkpoint_id": payload.parent_checkpoint_id or "veto_hit",
                        "oss_url": None,
                        "image_assets": payload.current_assets or [],
                        "page_data": veto_dsl,
                        "style_data": {
                            "global_vars": {
                                "--primary-vibe": "#ff2442",
                                "--primary-vibe-light": "rgba(255,36,66,0.1)",
                                "--accent-vibe": "#333333"
                            }
                        },
                        "node_prompts": {"risk_gateway": [{"role": "system", "content": "风控系统触发，生成被阻断。"}]},
                        "source_code": ""
                    })
                    continue # 结束本轮请求
                
                # 仅当没有新上传图片时，才使用缓存
                if not pending_urls:
                    cached_result = await get_trend_cache(user_query_str, selected_el)
                    if cached_result:
                        await websocket.send_json({
                            "type": "token",
                            "node": "cache_interceptor",
                            "content": "\n🚀 [语义缓存] 命中高相似度热点，大模型已旁路！"
                        })
                        await websocket.send_json({"type": "middleware", "node": "cache_interceptor", "status": "running"})
                        
                        await websocket.send_json({
                            "type": "turn_end",
                            "checkpoint_id": payload.parent_checkpoint_id or "cache_hit",
                            "oss_url": None,
                            "image_assets": payload.current_assets or [],
                            "page_data": cached_result,
                            "style_data": {}, # 简化版，实际中最好也把样式缓存下来
                            "node_prompts": {"cache": [{"role": "system", "content": "命中 Redis 缓存"}]},
                            "source_code": ""
                        })
                        continue # 直接进入下一次接收循环
                    else:
                        # ✨ 核心动作：如果缓存未命中，说明是一个全新的热点，将其挂载到后台进行异步收录
                        if selected_el in ["无 (全局修改)", "none", None]:
                            print(f"🔄 [任务挂载] 未命中缓存，已将「{user_query_str[:15]}...」加入后台热点收录队列")
                            asyncio.create_task(process_new_trend_background(user_query_str))

                # ✨ 核心重构：处理图片资产，打通多模态
                # 我们不再直接同步整个 current_assets 数组到 inputs，因为这会触发 operator.add 导致重复。
                # 相反，我们只处理本轮真正“新”出现的图片 (image_urls)。
                
                pending_urls = payload.image_urls or []
                
                # 组装多模态 HumanMessage
                if pending_urls:
                    message_content = [{"type": "text", "text": payload.content}]
                    for u in pending_urls:
                        message_content.append({"type": "image_url", "image_url": {"url": u}})
                    new_msg = HumanMessage(content=message_content)
                else:
                    new_msg = HumanMessage(content=payload.content)

                msg_key = f"{payload.panel}_messages"
                
                # 准备执行输入
                inputs = {
                    msg_key: [new_msg],
                    "active_panel": payload.panel,
                    "selected_element_id": payload.selected_element_id or "无 (全局修改)",
                    "creator_persona": payload.creator_persona or "硬核数码博主", # ✨ 注入创作者人设
                    "pending_images": pending_urls, # 触发 asset_node 处理
                }
                
                # ✨ 如果这是第一轮（没有 parent_checkpoint），且前端带了资产，我们需要初始化图库
                # 但由于 StateGraph 的 operator.add 限制，我们依赖 asset_node 去根据 URL 去重追加。
                # 现在的逻辑是：pending_images 传进去 -> asset_node 对比现有的 image_assets -> 仅追加新发现的 URL。
                
                config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "vector_store": websocket.app.state.vector_store 
                    }
                }
                if payload.parent_checkpoint_id:
                    config["configurable"]["checkpoint_id"] = payload.parent_checkpoint_id
                
                # 2. 运行 LangGraph 事件流
                # 定义思考状态映射表
                NODE_THOUGHT_MAP = {
                    "intent_agent": "🔍 正在深度解析您的创作意图...",
                    "research_agent": "🧠 正在为您搜寻最硬核的专业背景资料...",
                    "tools": "🔧 正在调用专业工具执行任务...",
                    "controversy_sniffer": "🛡️ 正在进行内容合规与舆情审计...",
                    "content_node": "✍️ 正在为您撰写爆款文案...",
                    "structure_node": "📐 正在为您规划最合理的视觉构图...",
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

                async for event in agent.astream_events(inputs, config=config, version="v2"):
                    kind = event["event"]
                    
                    # === 【核心修复：过滤流式输出，只播报特定节点】 ===
                    if kind == "on_chat_model_stream":
                        # 获取当前正在执行的节点名称 (优先从 metadata 取，这是 LangGraph 的标准位置)
                        metadata = event.get("metadata", {})
                        node_name = metadata.get("langgraph_node") or metadata.get("node") or ""
                        
                        chunk = event["data"]["chunk"]
                        # 既捕获普通文本内容，也捕获工具调用（structured_output 往往走这里）
                        content = ""
                        if chunk.content:
                            content = chunk.content
                        elif chunk.tool_call_chunks:
                            # 将工具调用的参数片段也流式传给前端预览
                            for tc in chunk.tool_call_chunks:
                                if tc.get("args"):
                                    content += tc["args"]

                        if content:
                            await websocket.send_json({
                                "event": "token", 
                                "data": content,
                                "node": node_name
                            })
                    # ===============================================

                    elif kind == "on_chain_start":
                        node_name = event["name"]
                        if node_name in NODE_THOUGHT_MAP:
                            print(f"🟢 [后端引擎] 正在执行节点: {node_name}...") 
                            await websocket.send_json({
                                "event": "thought",
                                "data": NODE_THOUGHT_MAP[node_name]
                            })
                            
                    elif kind == "on_tool_start":
                        tool_name = event["name"]
                        thought = TOOL_THOUGHT_MAP.get(tool_name, f"🔧 正在执行工具: {tool_name}...")
                        await websocket.send_json({
                            "event": "thought",
                            "data": thought
                        })
                        
                    elif kind == "on_chain_end":
                        if event["name"] == "LangGraph":
                            # 这里原本是 turn_end，但我们需要先检查是否被中断
                            pass

                # 3. ✨ HITL 检查：检查图是否被挂起（即进入了中断点）
                current_state = await agent.aget_state(config)
                
                # 情况 A：暂停在争议嗅探前（通常是因为消歧）
                if current_state.next and "controversy_sniffer" in current_state.next:
                    if current_state.values.get("needs_disambiguation"):
                        print(f"🚨 [HITL 中断] 发现实体歧义，等待人类选择...")
                        await websocket.send_json({
                            "event": "action_required",
                            "data": {
                                "action": "entity_disambiguation",
                                "message": "搜索到多个可能的结果，请问您指的是哪一个？",
                                "options": current_state.values.get("disambiguation_options", [])
                            }
                        })
                        continue

                # 情况 B：暂停在内容生成前（通常是因为舆情争议）
                if current_state.next and "content_node" in current_state.next:
                    # 只有在发现争议时才触发中断信令
                    if current_state.values.get("has_controversy") and not current_state.values.get("user_stance"):
                        print(f"🚨 [HITL 中断] 发现争议热点，等待人类立场决策...")
                        await websocket.send_json({
                            "event": "action_required",
                            "data": {
                                "action": "stance_decision",
                                "message": "发现该话题存在严重争议，请指挥官定夺本次创作立场！",
                                "options": [
                                    {"label": "🔴 黑榜避雷揭秘", "value": "negative_stance"},
                                    {"label": "🟢 红榜强力种草", "value": "positive_stance"}
                                ]
                            }
                        })
                        continue # 暂停本次循环，等待前端发回 submit_stance

                # 4. 如果没有被中断，正常下发 turn_end
                await websocket.send_json({
                    "event": "turn_end",
                    "data": {
                        "checkpoint_id": current_state.config["configurable"]["checkpoint_id"],
                        "oss_url": current_state.values.get("final_oss_url"),
                        "image_assets": current_state.values.get("image_assets", []),
                        "page_data": current_state.values.get("data_dsl", {}),
                        "style_data": current_state.values.get("style_dsl", {}),
                        "node_prompts": current_state.values.get("node_prompts", {}),
                        "source_code": current_state.values.get("final_html", ""),
                    }
                })

            except ValidationError as e:
                await websocket.send_json({"type": "error", "message": f"请求格式错误: {e}"})
            except Exception as inner_e:
                # 如果是正常关闭的信号 (1000/1001)，直接跳出，不再当作错误打印
                if "1000" in str(inner_e) or "1001" in str(inner_e):
                    print("[WS] 客户端主动断开连接 (1000/1001)，安全退出当前轮次。")
                    break
                
                print(f"[WS] 轮次执行错误: {inner_e}")
                    
                # 确保客户端没掉线才发报错信息
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({"type": "error", "message": f"执行出错: {str(inner_e)}"})
                    except Exception as send_err:
                        print(f"[WS] 尝试发送错误信息失败: {send_err}")
                else:
                    print("[WS] 客户端已断开，放弃发送错误通知。")
                    break

    except WebSocketDisconnect:
        print(f"[WS] Client {thread_id} disconnected normally.")
    except Exception as fatal_e:
        print(f"[WS] 致命错误导致连接崩溃: {fatal_e}")