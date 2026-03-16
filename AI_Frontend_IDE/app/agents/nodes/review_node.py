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

    prompt = f"""你是一个舆情分析专家。请快速阅读以下背景资料，判断该话题是否存在明显的争议、极性冲突或多方博弈（例如：一半人疯狂安利，一半人避雷吐槽）。

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
