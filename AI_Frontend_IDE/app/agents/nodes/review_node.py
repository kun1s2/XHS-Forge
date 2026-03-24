from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from pydantic import BaseModel, Field

class ClashPoints(BaseModel):
    is_controversial: bool = Field(description="是否存在明显的极性冲突")
    clash_title: str = Field(description="为这次取舍判断拟定一个清楚的对比标题")
    pros_focus: str = Field(description="正方应重点展开的优势方向")
    cons_focus: str = Field(description="反方应重点展开的代价或提醒方向")
    reason: str = Field(description="判定理由")

async def controversy_sniffer_node(state: UIProjectState) -> dict:
    """
    识别资料中是否存在需要正反并置讲清楚的关键取舍。
    """
    knowledge = state.get("retrieved_knowledge", {})
    if not knowledge:
        return {"has_controversy": False}

    llm = create_llm(
        model=settings.LLM_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    structured_llm = llm.with_structured_output(ClashPoints)

    # ✨ 核心加固：识别极性冲突
    prompt = f"""你是一个内容工作台里的争议判断助手。
    请针对以下调研资料，提取该产品的【关键取舍】与【容易分歧的判断点】。
    
    【强制判定准则】：
    1. 竞品对比：如果资料中出现了两个及以上竞争品牌（如华为 vs 苹果），必须判定为 is_controversial = true。
    2. 情感烈度：如果用户语气强烈，烈度 >= 0.7，必须判定为 true。
    
    你的任务是提取两侧都站得住的重点，为后续并发判断提供材料。

【资料内容】:
{knowledge}
"""

    try:
        result: ClashPoints = await structured_llm.ainvoke(prompt)
        print(f"🧐 [取舍判断] 结果: {result.is_controversial} | 标题: {result.clash_title}")
        
        # 将对峙点存入状态，供后续并发节点提取
        return {
            "has_controversy": result.is_controversial,
            "retrieved_knowledge": {
                **knowledge,
                "clash_report": result.model_dump() if result.is_controversial else None
            }
        }
    except Exception as e:
        print(f"⚠️ [取舍判断] 失败: {e}")
        return {"has_controversy": False}
