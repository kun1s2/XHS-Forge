import json
import re
import random
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import SurgicalPatchOutput
from app.agents.tools_registry import google_image_search_tool
from tenacity import retry, stop_after_attempt, wait_exponential

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_patch_llm():
    global _llm_instance
    if _llm_instance is None:
        # ✨ 哨兵性能优化：手术刀节点切换为极速小模型
        _llm_instance = create_llm(
            model=settings.LLM_SMALL_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Patch Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), before_sleep=log_retry)
async def invoke_patch_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def surgical_patch_agent(state: UIProjectState) -> dict:
    """
    【手术刀节点】：只针对选中的单个组件进行极速数据微调。
    支持 SerpApi 搜图增强。
    """
    llm = get_patch_llm()
    # ✨ 恢复为更精准的 function_calling 模式
    structured_llm = llm.with_structured_output(SurgicalPatchOutput, method="function_calling")
    
    # 1. 锁定修改目标
    selected_id = state.get("selected_element_id")
    data_dsl = state.get("data_dsl", {})
    
    if not selected_id or selected_id not in data_dsl:
        print(f"⚠️ [Patch Node] 未找到选中的组件 {selected_id}，退回 structure_node")
        return {"intent_route": "structure_node"}

    target_component = data_dsl[selected_id]
    
    # 2. 提取用户指令
    main_msgs = state.get("main_messages", [])
    user_query = main_msgs[-1].content if main_msgs else ""
    if isinstance(user_query, list):
        user_query = " ".join([item["text"] for item in user_query if item.get("type") == "text"])

    # --- ⚔️ 视觉狙击逻辑：如果意图涉及“换图/配图” ---
    # 我们简单的通过关键词嗅探意图，如果包含“图片”、“换图”、“配图”等
    if any(kw in user_query for kw in ["图片", "换图", "配图", "图", "照"]):
        print(f"📸 [视觉狙击] 检测到换图指令，正在启动 SerpApi...")
        # 让 AI 帮我们总结一个搜图关键词
        # 🌟 优化：强制搜索“真实产品”素材，严禁 UI 设计稿
        search_prompt = (
            f"针对组件 {selected_id} ({target_component.get('type')})，根据用户指令「{user_query}」，"
            f"生成一个精准的 Google 图片搜索关键词（英文）。"
            f"要求：必须针对“真实产品”或“真实场景照片”（如 Sony A7C2 real photo），严禁包含 'UI', 'design', 'layout' 等设计稿相关的关键词。"
        )
        search_kw_msg = await llm.ainvoke(search_prompt)
        search_kw = search_kw_msg.content.strip().strip('"')
        
        # 调用 SerpApi
        image_links_str = await google_image_search_tool.ainvoke(search_kw)
        image_links = image_links_str.split("\n")
        
        if image_links and image_links[0].startswith("http"):
            target_url = image_links[0]
            print(f"🎯 [视觉狙击] 捕获到真实直链: {target_url}")
        else:
            # 兜底：使用 Picsum 随机图
            random_id = random.randint(1, 1000)
            target_url = f"https://picsum.photos/seed/{random_id}/800/600"
            print(f"🩹 [视觉兜底] SerpApi 未果，使用 Picsum 占位图: {target_url}")
        
        # 强制将新图注入用户指令，辅助 AI 完成最终 JSON 构建
        user_query += f" | 请务必将该组件的图片 URL 设为: {target_url}"

    # 3. 加载提示词
    prompt_path = Path(__file__).parents[2] / "prompts" / "patch_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "用户的最新修改指令：\n<user_input>\n{{ query }}\n</user_input>\n(请通过调用工具输出 JSON 格式结果)")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        # 🌟 修复：补回 target_id 变量，并确保与 prompt 模板一致
        inputs = {
            "selected_element": selected_id,
            "target_id": selected_id,
            "target_component_json": json.dumps(target_component, ensure_ascii=False),
            "query": user_query
        }
        
        # 记录快照
        rendered_messages = prompt.format_messages(**inputs)
        prompt_snapshot = [{"role": m.type, "content": m.content} for m in rendered_messages]

        result: SurgicalPatchOutput = await invoke_patch_retry(chain, inputs)
        
        # 🛡️ 鲁棒性硬核检查
        if result is None:
            raise ValueError("大模型未返回有效的结构化修改建议 (SurgicalPatchOutput is None)")

        print(f"💉 [手术刀修改成功] 目标: {selected_id} | 理由: {result.reason}")
        
        # 4. 构建补丁包（保留 None 作为“墓碑标志”，配合 merge_dsl 进行删除）
        updated_data = result.updated_component.model_dump(exclude_unset=True)
        dsl_patch = {
            selected_id: updated_data
        }
        
        # ✨ 核心新增：记录组件级生长档案
        from datetime import datetime
        track_entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": user_query,
            "data_snapshot": updated_data,
            "agent_thought": result.thought_process
        }

        # ✨ 补齐局部记忆：将本次成功修改写入内容通道，便于后续上下文理解
        ai_memory_msg = AIMessage(
            content=f"已成功对组件 {selected_id} 进行局部修改。理由：{result.reason}。思考过程：{result.thought_process}"
        )
        
        return {
            "data_dsl": dsl_patch,
            "patch_tracks": {selected_id: [track_entry]},
            "node_prompts": {"patch_node": prompt_snapshot},
            "content_messages": [ai_memory_msg],
        }
        
    except Exception as e:
        print(f"❌ Patch Agent 最终失败: {e}")
        return {}
