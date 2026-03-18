import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from langchain_core.messages import AIMessage

# --- 🚀 文案大脑 5.7：变量加固版 ---

class ContentOutput(BaseModel):
    thought_process: str = Field(description="创作思路")
    storyline: str = Field(description="核心故事线")
    tone_vibe: str = Field(description="情感定调")
    key_golden_phrases: List[str] = Field(description="金句池")

async def content_agent(state: UIProjectState) -> dict:
    know = state.get("retrieved_knowledge", {})
    main_msgs = state.get("main_messages", [])
    user_query = str(main_msgs[-1].content) if main_msgs else ""
    
    # ✨ 核心修复：安全提取 domain_category
    domain = know.get("domain_category", "通用领域")
    audience = state.get("intent_result", {}).get("target_audience", "泛人群") if isinstance(state.get("intent_result"), dict) else "泛人群"

    llm = create_llm(
        model=settings.LLM_BRAIN_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0.7 
    )
    structured_llm = llm.with_structured_output(ContentOutput, method="function_calling")

    system_prompt = f"""你是一个顶级的【{domain}】领域内容导演。
    你的任务是为这篇笔记设定灵魂导引。
    
    【核心事实依据】：
    {json.dumps(know, ensure_ascii=False)}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "【🎯 目标受众】：{audience}\n【用户原始指令】：{query}\n请设定故事线和情感风格。")
    ])

    try:
        chain = prompt | structured_llm
        # ✨ 核心修复：输入变量名必须与 prompt 占位符严格对应
        result: ContentOutput = await chain.ainvoke({
            "audience": audience, 
            "query": user_query
        })
        
        vibe_content = f"【动线】：{result.storyline}\n【风格】：{result.tone_vibe}\n【金句】：{' | '.join(result.key_golden_phrases)}"
        human_reply = AIMessage(content=f"✨ 导演定调完毕：{result.storyline}")

        return {
            "content_result": result,
            "content_messages": [AIMessage(content=vibe_content)],
            "main_messages": [human_reply]
        }
    except Exception as e:
        print(f"❌ Content Agent 失败: {e}")
        return {}
