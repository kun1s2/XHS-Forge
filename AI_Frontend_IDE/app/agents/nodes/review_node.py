from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from pydantic import BaseModel, Field

class ControversyOutput(BaseModel):
    is_controversial: bool = Field(description="是否存在明显的争议或情感极性冲突")
    reason: str = Field(description="简述理由")

async def controversy_sniffer_node(state: UIProjectState) -> dict:
    """
    【争议嗅探节点】：分析检索到的知识，判断是否需要人类介入定调。
    """
    knowledge = state.get("retrieved_knowledge", "")
    if not knowledge:
        return {"has_controversy": False}

    llm = create_llm(
        model=settings.LLM_SMALL_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    structured_llm = llm.with_structured_output(ControversyOutput, method="function_calling")

    # ✨ 哨兵加固：引入更具深度的舆情嗅探指令
    prompt = f"""你是一个资深的小红书趋势分析专家。
    请快速审计以下背景资料，识别该话题背后的【心智博弈】：
    1. 利益冲突：是否存在“溢价严重” vs “为爱发电”的争论？
    2. 审美冲突：是否存在“复古美学” vs “智商税”的博弈？
    3. 事实冲突：是否存在“避雷吐槽” vs “红榜安利”的极性？

    你的目标是识别这些“热评冲突点”，为后续文案生成提供“情绪锚点”。

【资料内容】:
{knowledge}

输出必须包含布尔值 is_controversial。"""

    try:
        result = await structured_llm.ainvoke(prompt)
        print(f"🧐 [争议嗅探] 结果: {result.is_controversial} | 理由: {result.reason}")
        return {"has_controversy": result.is_controversial}
    except Exception as e:
        print(f"⚠️ [争议嗅探] 失败: {e}")
        return {"has_controversy": False}
