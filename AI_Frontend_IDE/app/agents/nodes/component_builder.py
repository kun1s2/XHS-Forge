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

# 🐝 蜂群限制器
_github_limiter = asyncio.Semaphore(10)

_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_WORKER_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点 5.8】：纯文本注入版 (杜绝 jinja2 错误)。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "填充内容")
    user_query = state.get("user_query", "")
    
    # 1. 提取 RAG 知识
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    battle_report = None
    
    fact_str = "无外部参考资料"
    if isinstance(retrieved_knowledge, dict):
        battle_report = retrieved_knowledge.get("battle_report")
        if retrieved_knowledge.get("entity_name"):
            fact_context = {
                "entity": retrieved_knowledge.get('entity_name'),
                "attributes": retrieved_knowledge.get('core_attributes', {}),
                "images": state.get("image_assets", []) 
            }
            fact_str = json.dumps(fact_context, ensure_ascii=False, indent=2)

    # 2. 提取导引文案
    content_msgs = state.get("content_messages", [])
    global_guide = "未提供全局定调"
    if content_msgs:
        for msg in reversed(content_msgs):
            if hasattr(msg, "content") and msg.content:
                global_guide = str(msg.content)
                break

    async with _github_limiter:
        await asyncio.sleep(random.uniform(0.1, 0.2))
        print(f"👷 [并发工兵] 构建中: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput)
        
        # 3. 构造指令 (纯 f-string 拼接，最安全)
        system_prompt = f"""你是一个顶级组件设计师。当前构建 ID: [{comp_id}], 类型: "{comp_type}"。

【⚠️ 本组件专项简报】: >> {content_brief} <<

【📖 全局定调背景】:
{global_guide}

【📊 结构化事实库】:
{fact_str}

【通用铁律】：
1. 职责锁定：仅针对简报指派的细节创作。
2. 严禁复读：严禁照抄全局背景原句。
3. 📸 零幻觉图像：若事实库无图，image_url 设为 null。
"""

        if comp_type == "VersusCard" and battle_report:
            system_prompt += f"\n【🚨 强制对冲数据】:\n{json.dumps(battle_report, ensure_ascii=False)}"

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据指令完成组件数据构建。用户指令：{query}")
        ])
        
        try:
            chain = prompt | structured_llm
            result: ComponentBuilderOutput = await chain.ainvoke({"query": user_query})
            
            res_data = {}
            if result.data:
                res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type 
            
            # VersusCard 深度纠偏
            if comp_type == "VersusCard" and battle_report:
                res_data["title"] = battle_report.get('title')
                res_data["proText"] = battle_report.get('pros', {}).get('details')
                res_data["conText"] = battle_report.get('cons', {}).get('details')
            
            style_data = {"css_classes": "", "inline_styles": {}}
            if result.style:
                style_data = result.style.model_dump(exclude_none=True)

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_data}
            }
        except Exception as e:
            print(f"🩹 [工兵自愈] {comp_id} 失败: {e}")
            
            # 最后的挣扎：如果是 VersusCard 且有报告，直接硬填
            if comp_type == "VersusCard" and battle_report:
                 return {
                    "data_dsl": {comp_id: {
                        "type": "VersusCard",
                        "title": battle_report.get('title'),
                        "proText": battle_report.get('pros', {}).get('details'),
                        "conText": battle_report.get('cons', {}).get('details')
                    }},
                    "style_dsl": {comp_id: {"css_classes": "opacity-90"}}
                }
            
            return {"data_dsl": {comp_id: {"type": comp_type, "title": "内容生成异常"}}}
