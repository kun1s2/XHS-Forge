import json
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
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
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
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
        ("human", "【当前创作者人设】：{{ creator_persona }}\n{% if user_stance %}【⚠️ 创作立场要求】：指挥官已定夺本次创作立场为：「{{ user_stance }}」。请务必严格遵守此立场！\n{% endif %}用户的最新指令：\n<user_input>\n{{ query }}\n</user_input>\n请在创作文案的同时，规划创作思路。")
    ], template_format="jinja2")

    structured_llm = llm.with_structured_output(ContentOutput)
    
    try:
        inputs = {
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
        
        result = await structured_llm.ainvoke(inputs)
        new_content = result.final_content
        thought = result.thought_process
    except Exception as e:
        print(f"❌ Content Agent 失败: {e}")
        new_content = "文案生成失败，请重试。"
        thought = "思考过程中断"
        prompt_data = []
        result = None

    content_msgs = state.get("content_messages", [])
    from langchain_core.messages import SystemMessage
    content_msgs.append(SystemMessage(content=new_content))
    
    return {
        "content_result": result, # ✨ 供 WebSocket 截获思维链
        "content_messages": content_msgs,
        "node_prompts": {"content_node": prompt_data},
        "has_controversy": False,
        "user_stance": "" 
    }
