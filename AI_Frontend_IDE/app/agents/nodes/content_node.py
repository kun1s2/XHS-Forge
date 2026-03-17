import json
from pathlib import Path
from pydantic import BaseModel, Field
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.agents.memory_utils import get_trimmed_messages

class ContentOutput(BaseModel):
    """文案创作大脑输出结构"""
    thought_process: str = Field(description="文案创作思路与钩子设计推理")
    final_content: str = Field(description="最终生成的小红书文案主体")

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_content_llm():
    global _llm_instance
    if _llm_instance is None:
        # 🧠 哨兵三轨制：创作大脑切换为最强的 BRAIN 模型
        _llm_instance = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.7
        )
    return _llm_instance

async def content_agent(state: UIProjectState) -> dict:
    llm = get_content_llm()
    
    # 提取用户指令
    main_msgs = state.get("main_messages", [])
    trimmed_messages = get_trimmed_messages(main_msgs, max_tokens=4000)
    raw_query = trimmed_messages[-1].content if trimmed_messages else "请构思一段文案。"
    user_query = str([item["text"] for item in raw_query if item.get("type") == "text"]) if isinstance(raw_query, list) else str(raw_query)
        
    current_data_dsl = state.get("data_dsl", {})
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    is_update = bool(current_data_dsl and current_data_dsl.get("page_order"))
    
    scenarios = state.get("scenarios", [])
    retrieved_knowledge = state.get("retrieved_knowledge", "")
    user_stance = state.get("user_stance", "")
    creator_persona = state.get("creator_persona", "硬核数码博主")
    
    target_text = "全局修改"
    if selected_element != "无 (全局修改)" and selected_element in current_data_dsl:
        target_comp = current_data_dsl[selected_element]
        target_text = json.dumps({k: v for k, v in target_comp.items() if k in ["title", "subtitle", "heading", "paragraphs", "desc", "caption"]}, ensure_ascii=False)

    prompt_path = Path(__file__).parents[2] / "prompts" / "content_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    # ✨ 使用 Jinja2 模板直接处理所有动态变量，避免 Python f-string 拼接
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "【当前创作者人设】：{{ creator_persona }}\n{% if user_stance %}【⚠️ 创作立场要求】：指挥官已定夺本次创作立场为：「{{ user_stance }}」。请务必严格遵守此立场！\n{% endif %}用户的最新指令：\n<user_input>\n{{ query }}\n</user_input>\n请在创作文案的同时，规划创作思路并以 JSON 格式输出。")
    ], template_format="jinja2")

    structured_llm = llm.with_structured_output(ContentOutput, method="function_calling")
    
    # ✨ 哨兵三轨制：创作大脑切换为最强的 BRAIN 模型
    # 并强制适配结构化 RAG 数据
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    
    fact_details = ""
    if isinstance(retrieved_knowledge, dict) and retrieved_knowledge.get("entity_name"):
        fact_details = f"""
【核心事实依据 (结构化 JSON)】：
- 实体名称: {retrieved_knowledge.get('entity_name')}
- 核心参数: {json.dumps(retrieved_knowledge.get('core_attributes'), ensure_ascii=False)}
- 核心卖点: {retrieved_knowledge.get('key_selling_points')}
- 避雷点: {retrieved_knowledge.get('known_issues')}
- 结论摘要: {retrieved_knowledge.get('summary')}

【⚠️ 绝对服从令】：
1. 你必须 100% 依据上述 JSON 中的参数进行创作。
2. 严禁捏造任何不在上述列表中的新型号、价格或黑科技。
3. 如果 core_attributes 为空，请基于 entity_name 进行通用创作，但依然严禁捏造具体数值。
"""
    
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d")
    
    fact_constraint = f"""
{fact_details}
(今日日期: {current_time})
"""

    try:
        inputs = {
            "fact_constraint": fact_constraint, # ✨ 强制注入
            "is_update": is_update,
            "current_data": json.dumps(current_data_dsl, ensure_ascii=False) if current_data_dsl else "空",
            "selected_element": selected_element,
            "target_text": target_text,
            "creator_persona": creator_persona,
            "user_stance": user_stance,
            "query": user_query,
            "scenarios": scenarios,
            "retrieved_knowledge": retrieved_knowledge
        }
        
        rendered_messages = prompt.format_messages(**inputs)
        prompt_data = [{"role": m.type, "content": m.content} for m in rendered_messages]
        
        # ✨ 修复：使用管道模式调用，让 LangChain 自动处理变量注入
        chain = prompt | structured_llm
        result = await chain.ainvoke(inputs)
        
        new_content = result.final_content
        thought = result.thought_process
    except Exception as e:
        print(f"❌ Content Agent 失败: {e}")
        if settings.DEBUG_MODE:
            raise e
        new_content = "文案生成失败，请重试。"
        thought = "思考过程中断"
        prompt_data = []
        result = None

    content_msgs = state.get("content_messages", [])
    main_msgs = state.get("main_messages", [])
    from langchain_core.messages import SystemMessage, AIMessage
    content_msgs.append(SystemMessage(content=new_content))
    
    # ✨ 拟人化回音：向主对话流追加一条干净的 AIMessage
    hummanized_reply = AIMessage(content=f"✨ 文案工坊已出炉：\n\n{new_content}")
    
    return {
        "content_result": result, # ✨ 供 WebSocket 截获思维链
        "content_messages": content_msgs,
        "main_messages": [hummanized_reply], # ✨ LangGraph 会自动根据 Reducer 追加
        "node_prompts": {"content_node": prompt_data},
        "has_controversy": False,
        "user_stance": "" 
    }
