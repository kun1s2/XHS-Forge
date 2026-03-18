import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from langchain_core.messages import AIMessage

# --- 🚀 文案大脑 5.0：情感与逻辑定调输出 (去中心化版) ---

class ContentOutput(BaseModel):
    """不再输出正文，只输出灵魂导引"""
    thought_process: str = Field(description="创作思路")
    storyline: str = Field(description="一句话描述本篇笔记的情绪起伏和逻辑动线。")
    tone_vibe: str = Field(description="情感定调：如‘毒舌避雷’、‘温馨治愈’、‘专业硬核’。")
    key_golden_phrases: List[str] = Field(description="为工兵准备的金句池（3-5句），工兵可以选择性使用。")

async def content_agent(state: UIProjectState) -> dict:
    """
    【文案大脑 5.0】：定调者。
    为后续积木工兵提供灵魂（故事线），而非肉体（具体文字）。
    """
    # 1. 状态提取
    know = state.get("retrieved_knowledge", {})
    main_msgs = state.get("main_messages", [])
    user_query = str(main_msgs[-1].content) if main_msgs else ""
    creator_persona = state.get("creator_persona", "专业博主")
    
    # 提取六维信号
    intent_res = state.get("intent_result")
    audience = getattr(intent_res, "target_audience", "泛人群") if intent_res else "泛人群"

    # 2. 准备提示词
    llm = create_llm(
        model=settings.LLM_BRAIN_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0.7 
    )
    structured_llm = llm.with_structured_output(ContentOutput, method="function_calling")

    system_prompt = f"""你是一个顶级的自媒体内容导演。
    你的任务不是写出一整篇笔记，而是为这篇笔记设定【灵魂导引】。
    
    【导演准则】：
    1. 设定动线：给出一句有冲击力的故事线（如：‘从深夜的焦虑到看到这一刻美景的释怀’）。
    2. 提炼金句：写出几句符合【{creator_persona}】人设的黄金短句。
    3. 拒绝执行：严禁输出任何长段落，你的输出将作为下游 5 个工兵的创作背景。

    【核心事实依据】：
    {json.dumps(know, ensure_ascii=False)}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "【🎯 目标受众】：{audience}\n【用户原始指令】：{query}\n请设定本篇笔记的灵魂导引。")
    ])

    try:
        # ✨ 修复：构建完整的链 (Chain)，否则 ainvoke 传 dict 会因缺少 Prompt 而报错
        chain = prompt | structured_llm
        result: ContentOutput = await chain.ainvoke({"audience": audience, "query": user_query})
        
        # 封装导引包
        vibe_content = f"【本篇创作动线】：{result.storyline}\n【情感风格】：{result.tone_vibe}\n【可用金句】：{' | '.join(result.key_golden_phrases)}"
        
        # 拟人化反馈
        human_reply = AIMessage(content=f"✨ 导演已就位！本次创作定调为「{result.tone_vibe}」，故事线：{result.storyline}")

        return {
            "content_result": result,
            "content_messages": [AIMessage(content=vibe_content)],
            "main_messages": [human_reply]
        }
    except Exception as e:
        print(f"❌ Content Agent 失败: {e}")
        # 物理兜底：提供基础情感包，防止下游节点崩盘或复读
        fallback_result = ContentOutput(
            thought_process="系统兜底逻辑",
            storyline="通过真实的参数和直观的视觉感受，向用户全方位展示产品的核心魅力。",
            tone_vibe="客观专业",
            key_golden_phrases=["硬核测评，不吹不黑", "参数只是起点，体验才是终点", "入手不亏的真香选择"]
        )
        return {
            "content_result": fallback_result,
            "content_messages": [AIMessage(content="【兜底模式】导演暂时离线，切换至标准专业模板。")],
            "main_messages": [AIMessage(content="✨ 导演因网络波动暂退，已由副导演接管定调。")]
        }
