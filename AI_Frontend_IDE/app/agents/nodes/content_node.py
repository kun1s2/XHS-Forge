import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.agents.state import UIProjectState
from app.core.config import settings
from app.agents.memory_utils import get_trimmed_messages # ✨ 引入记忆截断器

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_content_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.6
        )
    return _llm_instance

async def content_agent(state: UIProjectState) -> dict:
    llm = get_content_llm()
    
    # 提取用户指令
    main_msgs = state.get("main_messages", [])
    
    # ✨ 核心优化：在生成文案之前执行记忆截断，确保上下文不超限
    # 文案生成可能需要较多历史，给 4000 token
    trimmed_messages = get_trimmed_messages(main_msgs, max_tokens=4000)
    
    raw_query = trimmed_messages[-1].content if trimmed_messages else "请构思一段文案。"
    # ✨ 修正：这里同样改回 raw_query，防止 NameError
    user_query = str([item["text"] for item in raw_query if item.get("type") == "text"]) if isinstance(raw_query, list) else str(raw_query)
        
    current_data_dsl = state.get("data_dsl", {})
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    is_update = bool(current_data_dsl and current_data_dsl.get("page_order"))
    
    # ✨ 提取通过 intent_node 识别出的业务场景标签
    scenarios = state.get("scenarios", [])
    retrieved_knowledge = state.get("retrieved_knowledge", "")
    user_stance = state.get("user_stance", "") # ✨ HITL 决策立场
    creator_persona = state.get("creator_persona", "硬核数码博主") # ✨ 创作者人设
    
    target_text = "全局修改"
    if selected_element != "无 (全局修改)" and selected_element in current_data_dsl:
        target_comp = current_data_dsl[selected_element]
        target_text = json.dumps({k: v for k, v in target_comp.items() if k in ["title", "subtitle", "heading", "paragraphs", "desc", "caption"]}, ensure_ascii=False)

    # ====== ✨ 现代化：从外部 XML 加载系统提示词 ======
    from pathlib import Path
    prompt_path = Path(__file__).parents[2] / "prompts" / "content_system.xml"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_template = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"未找到提示词文件：{prompt_path}")

    # ====== ✨ 现代化：ChatPromptTemplate (支持 Jinja2 语法) ======
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "用户的最新指令: {{ query }}")
    ], template_format="jinja2")

    # ====== ✨ 现代化：LCEL 管道操作符 `|` 与 StrOutputParser ======
    chain = prompt | llm | StrOutputParser()
    
    try:
        # ✨ 提示词增强：注入人类立场决策
        stance_instruction = ""
        if user_stance:
            stance_instruction = f"\n\n【⚠️ 创作立场要求】：指挥官已定夺本次创作立场为：「{user_stance}」。请务必严格遵守此立场，在文案中表现出鲜明的情感倾向，严禁模棱两可！"

        # ✨ 提示词增强：要求 AI 在文案创作的同时，预估该内容的社交热度
        query_with_social = f"【当前创作者人设】：{creator_persona}\n\n{user_query}{stance_instruction}\n\n请在创作文案的同时，根据内容的质量和爆款潜力，构思一组合理的社交互动数据（点赞、收藏、评论数）。"
        
        inputs = {
            "is_update": is_update,
            "current_data": json.dumps(current_data_dsl, ensure_ascii=False) if current_data_dsl else "空",
            "selected_element": selected_element,
            "target_text": target_text,
            "query": query_with_social,
            "scenarios": scenarios,
            "retrieved_knowledge": retrieved_knowledge # ✨ 传递给 Jinja2 模板
        }
        
        # ✨ 新增：捕获渲染后的结构化提示词
        rendered_messages = prompt.format_messages(**inputs)
        prompt_data = [{"role": m.type, "content": m.content} for m in rendered_messages]
        
        # 直接 ainvoke 字典变量，告别 f-string 拼接！
        new_content = await chain.ainvoke(inputs)
    except Exception as e:
        print(f"❌ Content Agent 失败: {e}")
        new_content = "文案生成失败，请重试。"
        prompt_data = []

    content_msgs = state.get("content_messages", [])
    # 将纯文本转为系统消息存入状态机
    from langchain_core.messages import SystemMessage
    content_msgs.append(SystemMessage(content=new_content))
    
    return {
        "content_messages": content_msgs,
        "node_prompts": {"content_node": prompt_data}, # ✨ 保存结构化提示词
        # ✨ 代码净化：HITL 状态“用完即焚”，防止污染下一轮对话
        "has_controversy": False,
        "user_stance": "" 
    }
