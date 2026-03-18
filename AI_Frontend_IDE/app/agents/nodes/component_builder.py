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

_github_limiter = asyncio.Semaphore(10)

_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_WORKER_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3 # 降低随机性，减少幻觉
        )
    return _llm_instance

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点 5.6】：职责隔离与去重增强版。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "填充内容")
    user_query = state.get("user_query", "")
    
    # 1. 提取 RAG 知识
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    knowledge_str = "无外部参考资料"
    battle_report = None
    
    if isinstance(retrieved_knowledge, dict):
        battle_report = retrieved_knowledge.get("battle_report")
        if retrieved_knowledge.get("entity_name"):
            knowledge_str = f"""
【结构化事实库】：
- 目标主体: {retrieved_knowledge.get('entity_name')}
- 核心参数: {json.dumps(retrieved_knowledge.get('core_attributes', {}), ensure_ascii=False)}
- 真实图片: {json.dumps(retrieved_knowledge.get('image_urls', []), ensure_ascii=False)}
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
        await asyncio.sleep(random.uniform(0.1, 0.3))
        print(f"👷 [并发工兵] 正在生产: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # 针对不同组件类型，动态调整指令权重
        type_specific_instruction = ""
        if comp_type == "VersusCard" and battle_report:
            type_specific_instruction = f"""
【🚨 红色通缉令】：这是一个 VersusCard！
你必须【严格且仅能】使用下述对冲报告进行填充，绝对禁止使用全局文案！
- 标题: {battle_report.get('title')}
- 正方(PROS): {battle_report.get('pros', {}).get('details')}
- 反方(CONS): {battle_report.get('cons', {}).get('details')}
"""
        elif comp_type == "StoryText":
            type_specific_instruction = f"""
【🚨 职责隔离令】：
你的任务简报是: >> {content_brief} <<
你必须【仅针对简报内容】进行扩写。绝对禁止直接复制粘贴全局文案！
如果全局文案包含多个段落，你只能提取并深度加工与你简报相关的那个段落。
"""

        system_prompt = f"""你是一个顶级组件设计师。当前构建 ID: [{comp_id}], 类型: "{comp_type}"。

{type_specific_instruction}

【📖 全局参考背景】:
{global_content}

{knowledge_str}

【通用铁律】：
1. 严禁复读：禁止直接照抄全局参考背景。你必须根据【任务简报】进行个性化创作。
2. 真实性：100% 依据事实库。
3. 图像：若图片库为空，image_url 设为 null。
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据简报完成组件数据构建。")
        ], template_format="jinja2")
        
        try:
            result: ComponentBuilderOutput = await (prompt | structured_llm).ainvoke({"query": user_query})
            res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type 
            
            # 针对 VersusCard 强制修正映射
            if comp_type == "VersusCard" and battle_report:
                res_data["title"] = battle_report.get('title')
                res_data["pros"] = battle_report.get('pros')
                res_data["cons"] = battle_report.get('cons')

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: result.style.model_dump(exclude_none=True)}
            }
        except Exception as e:
            print(f"🩹 [自愈] {comp_id} 失败: {e}")
            return {"data_dsl": {comp_id: {"type": comp_type, "title": "内容加载中..."}}}
