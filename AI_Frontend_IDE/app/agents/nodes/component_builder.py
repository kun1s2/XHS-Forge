import json
import asyncio
import random
from pydantic import BaseModel, Field, field_validator
from typing import Any, Union, List, Dict
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentBuilderOutput

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
    content_brief = state.get("content_brief", "请根据全局文案填充数据")
    user_query = state.get("user_query", "")
    
    # ✨ 补全丢失的全局记忆
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    knowledge_str = "无外部参考资料"
    
    if isinstance(retrieved_knowledge, dict) and retrieved_knowledge.get("entity_name"):
        knowledge_str = f"""
【结构化参考资料】：
- 目标主体: {retrieved_knowledge.get('entity_name')}
- 核心参数列表: {json.dumps(retrieved_knowledge.get('core_attributes'), ensure_ascii=False)}
- 核心卖点: {', '.join(retrieved_knowledge.get('key_selling_points', []))}
- 避雷建议: {', '.join(retrieved_knowledge.get('known_issues', []))}
- 搜集到的真实图片: {retrieved_knowledge.get('image_urls', [])}
"""

    archetype = state.get("active_archetype", "general")
    persona = state.get("creator_persona", "专业博主")
    
    # 提取文案节点生成的全局内容
    content_msgs = state.get("content_messages", [])
    global_content = "未提供全局文案"
    if content_msgs:
        last_msg = content_msgs[-1]
        global_content = getattr(last_msg, "content", str(last_msg))

    async with _github_limiter:
        jitter = random.uniform(0.1, 0.5)
        await asyncio.sleep(jitter)
        
        print(f"👷 [并发工兵] 开始构建组件: {comp_id} ({comp_type})...")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # ✨ 4.0 核心指令：执行【人机协同】图像策略
        system_prompt = f"""你是一个严谨的前端组件数据构建专家。当前正在构建 ID 为 [{comp_id}]，类型为 "{comp_type}" 的组件。

【⚠️ 本组件专项任务简报 (最高优先级)】: 
>> {content_brief} <<

{knowledge_str}

【你的任务】：
请从上述“结构化参考资料”中，精准提取并转化出属于组件 [{comp_id}] 的数据。

1. ⚠️ 图像触发机制 (生死时速):
   - 如果“搜集到的真实图片”列表不为空: 必须从中提取 URL 填入 image_url 或 image_urls。
   - 如果列表为空: 禁止使用任何 placeholder！你必须将 image_url 设为 null，并在 desc 或 title 中填入引导语：“长官，文案已就绪，请点击此处上传您的实拍图✨”。

2. ⚠️ 边界意识：你只负责简报中指派的内容，严禁提及简报之外的参数（防止内容重叠）。
3. ⚠️ 字段完整性：在 data 对象中，必须包含 "type": "{comp_type}"。
4. ⚠️ 绝对服从：你必须 100% 依据资料中的“核心参数列表”填充组件。
5. 动态列表渲染：如果构建 ProductSpecCard，请将 core_attributes 中的键值对转化为 features 列表。
6. 输出必须为 JSON 格式。"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据用户指令构建组件数据并以 JSON 格式输出：\n{{ query }}")
        ], template_format="jinja2")
        
        try:
            result: ComponentBuilderOutput = await (prompt | structured_llm).ainvoke({"query": user_query})
            
            res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type 
            
            style_patch = result.style.model_dump(exclude_none=True)
            
            if settings.XHS_FORGE_DEBUG:
                print(f"✅ [DEBUG Output] 组件 {comp_id} 构建完毕")

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_patch}
            }
        except Exception as e:
            print(f"❌ [并发工兵] 组件 {comp_id} 最终校验失败: {e}")
            return {
                "data_dsl": {comp_id: {"type": comp_type, "title": "数据解析失败，请点重试"}},
                "style_dsl": {comp_id: {"css_classes": "opacity-50"}}
            }
