import json
import asyncio
import random
from pydantic import BaseModel, Field
from typing import Any, Union, List, Dict
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentBuilderOutput

# 🛡️ 【哨兵性能加固】：在三轨制架构下，扩容工兵并发数
_github_limiter = asyncio.Semaphore(10)

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_WORKER_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.4
        )
    return _llm_instance

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点 5.0】：源头治水架构下的数据填充引擎。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "请根据全局文案填充数据")
    user_query = state.get("user_query", "")
    
    # 1. 提取 RAG 知识
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    knowledge_str = "无外部参考资料"
    
    if isinstance(retrieved_knowledge, dict) and retrieved_knowledge.get("entity_name"):
        battle_info = ""
        report = retrieved_knowledge.get("battle_report")
        if report:
            battle_info = f"""
【⚠️ 舆情对冲报告】：
- 对峙标题: {report.get('title')}
- 红榜观点 (PROS): {report.get('pros', {}).get('details')}
- 黑榜槽点 (CONS): {report.get('cons', {}).get('details')}
(如果是 VersusCard，必须 100% 使用上述对冲报告数据进行填充！)
"""
        
        knowledge_str = f"""
【结构化参考资料】：
- 目标主体: {retrieved_knowledge.get('entity_name')}
{battle_info}
- 核心参数列表: {json.dumps(retrieved_knowledge.get('core_attributes', {}), ensure_ascii=False)}
- 核心卖点: {json.dumps(retrieved_knowledge.get('key_selling_points', []), ensure_ascii=False)}
- 真实图片库: {json.dumps(retrieved_knowledge.get('image_urls', []), ensure_ascii=False)}
"""

    # 2. 提取全局文案
    content_msgs = state.get("content_messages", [])
    global_content = "未提供全局文案"
    if content_msgs:
        for msg in reversed(content_msgs):
            if hasattr(msg, "content") and msg.content:
                global_content = str(msg.content)
                break

    async with _github_limiter:
        jitter = random.uniform(0.1, 0.3)
        await asyncio.sleep(jitter)
        
        print(f"👷 [并发工兵] 正在填充: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        system_prompt = f"""你是一个严谨的前端组件数据构建专家。当前正在构建 ID 为 [{comp_id}]，类型为 "{comp_type}" 的组件。

【⚠️ 本组件专项任务简报】: 
>> {content_brief} <<

【📖 全局文案背景】:
{global_content}

{knowledge_str}

【任务要求】：
1. 真实性：100% 依据参考资料填充。若资料缺失，根据博主语气合理撰写，严禁输出占位符。
2. 图像：若图片库不为空，必须提取有效 URL。
3. 完整性：必须包含 "type": "{comp_type}"。
4. 格式：严格输出 JSON。
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据用户指令构建组件数据并以 JSON 格式输出：\n{{ query }}")
        ], template_format="jinja2")
        
        try:
            result: ComponentBuilderOutput = await (prompt | structured_llm).ainvoke({"query": user_query})
            
            res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type 
            style_patch = result.style.model_dump(exclude_none=True)
            
            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_patch}
            }
        except Exception as e:
            print(f"🩹 [工兵自愈] 组件 {comp_id} 填充失败: {e}")
            return {
                "data_dsl": {comp_id: {"type": comp_type, "title": "内容打磨中..."}},
                "style_dsl": {comp_id: {"css_classes": "opacity-80 animate-pulse"}}
            }
