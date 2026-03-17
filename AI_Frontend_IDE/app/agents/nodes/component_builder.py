import json
import asyncio
import random
from pydantic import BaseModel, Field, field_validator
from typing import Any, Union, List, Dict
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentData, ComponentStyle, ComponentBuilderOutput
from tenacity import retry, stop_after_attempt, wait_exponential

# 🛡️ 【哨兵性能加固】：在三轨制架构下，扩容工兵并发数，平衡吞吐与稳定性
_github_limiter = asyncio.Semaphore(8)

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        # 🐝 哨兵三轨制：并发工兵切换为极速 WORKER 模型
        _llm_instance = create_llm(
            model=settings.LLM_WORKER_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.4
        )
    return _llm_instance

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点】：具备全局上下文感知的组件构建引擎。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    user_query = state.get("user_query", "")
    
    # ✨ 补全丢失的全局记忆
    knowledge = state.get("retrieved_knowledge", "无")
    archetype = state.get("active_archetype", "general")
    persona = state.get("creator_persona", "专业博主")
    
    # 提取文案节点刚刚生成的全局内容（核心上下文）
    content_msgs = state.get("content_messages", [])
    # 过滤掉非 AIMessage 的干扰（虽然 state 里定义了 BaseMessage 列表，此处取最后一条有效内容）
    global_content = "未提供全局文案"
    if content_msgs:
        last_msg = content_msgs[-1]
        global_content = getattr(last_msg, "content", str(last_msg))

    async with _github_limiter:
        # ✨ 哨兵提速：压缩随机抖动，实现极速响应
        jitter = random.uniform(0.1, 0.5)
        await asyncio.sleep(jitter)
        
        print(f"👷 [并发工兵] 开始构建组件: {comp_id} ({comp_type})...")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # ✨ 重新丰满系统提示词，让特种兵拥有大局观
        system_prompt = f"""你是一个严谨的前端组件数据构建专家。当前正在构建 ID 为 [{comp_id}]，类型为 "{comp_type}" 的组件。

【全局上下文】：
- 业务场景原型: {archetype}
- 创作者人设: {persona}
- 外部知识背景: {knowledge}
- 全局文案基调: {global_content}

【你的任务】：
请从上述“全局文案基调”和“知识背景”中，精准提取并转化出属于组件 [{comp_id}] 的数据。
1. 必须确保该组件的文案风格与全局基调 100% 保持一致。
2. 如果是 ProductCard，必须引用知识库中的真实价格和参数。
3. 如果是 StoryText，必须承接全局文案中的具体段落。
4. 如果是 InteractionsBar，请脑补极其逼真的点赞(likes)、收藏(collects)、评论(comments)数据（如：1.2w, 856）。
5. 必须输出 JSON 格式，包含 thought_process, data 和 style 字段。"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据用户指令构建组件数据并以 JSON 格式输出：\n{query}")
        ])
        
        try:
            # 执行 LCEL 管道
            result: ComponentBuilderOutput = await (prompt | structured_llm).ainvoke({"query": user_query})
            
            # 数据加工
            res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type # 物理强制锁定
            
            # 样式加工
            style_patch = result.style.model_dump(exclude_none=True)
            
            if settings.XHS_FORGE_DEBUG:
                print(f"✅ [DEBUG Output] 组件 {comp_id} 构建完毕，思维链: {result.thought_process[:100]}...")

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_patch}
            }
        except Exception as e:
            print(f"❌ [并发工兵] 组件 {comp_id} 构建失败: {e}")
            return {
                "data_dsl": {comp_id: {"type": comp_type, "title": "内容填充失败"}},
                "style_dsl": {comp_id: {"css_classes": "opacity-50"}}
            }
