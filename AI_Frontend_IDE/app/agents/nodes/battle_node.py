import asyncio
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from pydantic import BaseModel, Field

class SideOpinion(BaseModel):
    summary: str = Field(description="核心观点提炼，字数需精简")
    details: str = Field(description="详细的论据支撑")

async def battle_node(state: UIProjectState) -> dict:
    """
    【对冲生成引擎】：并发驱动红黑双方 Agent 进行逻辑对撞。
    面试亮点：异步 IO 并发，模拟多线程生产消费模型。
    """
    knowledge = state.get("retrieved_knowledge", {})
    clash_report = knowledge.get("clash_report")
    
    # ====== ✨ 核心重构：无事实，不对冲 ======
    if not clash_report or not knowledge.get("is_fact_ready"):
        print("🛑 [对冲引擎停火] 缺乏真实论据支撑，严禁脑补对撞文案。")
        return {}

    llm = create_llm(
        model=settings.LLM_WORKER_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0.7
    )
    structured_llm = llm.with_structured_output(SideOpinion)

    async def generate_side(role: str, focus: str):
        """内部闭包：单个极性的 Agent 工兵"""
        prompt = f"""你现在是【{role}】Agent。
        针对该话题，请根据以下指令进行深度扩写：
        >> {focus} <<
        
        要求：话术必须极具感染力，符合小红书‘红黑榜’或‘避雷/真香’的调性。
        参考资料：{knowledge.get('summary', '')}
        """
        return await structured_llm.ainvoke(prompt)

    print(f"⚔️ [对冲引擎] 启动并发线程，正在合成对峙观点...")

    # ====== ✨ 核心亮点：asyncio.gather 异步并发执行 ======
    # 面试时可宣称：为了提高生成效率，我将红黑双方的思考过程进行了解耦并发处理
    pros_task = generate_side("红榜正方", clash_report["pros_focus"])
    cons_task = generate_side("黑榜反方", clash_report["cons_focus"])
    
    pros_res, cons_task_res = await asyncio.gather(pros_task, cons_task)

    # 封装为对撞包
    battle_report = {
        "title": clash_report["clash_title"],
        "pros": pros_res.model_dump(),
        "cons": cons_task_res.model_dump()
    }

    print(f"🏁 [对冲引擎] 合成完毕：{battle_report['title']}")

    return {
        "retrieved_knowledge": {
            **knowledge,
            "battle_report": battle_report
        }
    }
