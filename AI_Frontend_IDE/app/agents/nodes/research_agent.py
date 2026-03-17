import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.agents.tools_registry import RESEARCH_TOOLS
from app.agents.memory_utils import get_trimmed_messages

# ✨ 2026 级增强：定义实体消歧评价模型
class DisambiguationEval(BaseModel):
    selected_meaning: str = Field(description="最终选定的实体含义")
    confidence_score: float = Field(description="置信度评分 (0.0-1.0)")
    reason: str = Field(description="打分理由，需结合上下文和场景原型")
    suggested_options: List[Dict[str, str]] = Field(
        default_factory=list, 
        description="备选释义列表，每项包含 label 和 value"
    )

# 初始化支持 Tool Calling 的 LLM
# 🧠 哨兵三轨制：调研专家切换为最强的 BRAIN 模型
llm = create_llm(
    model=settings.LLM_BRAIN_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    temperature=0.2
).bind_tools(RESEARCH_TOOLS)

async def research_agent(state: UIProjectState) -> dict:
    """
    【最新技术栈：自适应实体消歧调研大脑】
    """
    print("🧠 [Research Agent] 开始动态调研与实体消歧...")
    
    # 1. 提取动态上下文（拔除硬编码）
    active_archetype = state.get("active_archetype", "general")
    image_assets = state.get("image_assets", [])
    image_desc = ", ".join([a.get("desc", "") for a in image_assets]) if image_assets else "无"
    
    active_panel = state.get("active_panel", "main")
    messages = state.get(f"{active_panel}_messages", [])
    
    # 2. 记忆截断
    trimmed_messages = get_trimmed_messages(messages, max_tokens=3000)
    
    # 3. 注入“状态驱动”的系统指令（含实时时钟）
    from datetime import datetime
    current_time = datetime.now().strftime("%Y-%m-%d %A")
    
    system_instruction = f"""你是一个专业的互联网调研专家。
【当前时间】: {current_time}
【当前创作场景原型】: {active_archetype}
【用户提供的视觉线索】: {image_desc}

请结合以上背景，自主决定调用工具进行深度调研。
如果你识别到用户指令中包含“最新”、“最近”、“新款”等时效性词汇，请务必在生成搜索 query 时结合当前年份 {current_time[:4]} 进行精准检索。
如果搜索结果存在多义性，请务必结合当前场景和线索进行逻辑推理。
请确保输出符合工具调用的 JSON 格式规范。
"""
    
    # 构造请求消息
    full_messages = [("system", system_instruction)] + trimmed_messages
    
    # 4. 调用 LLM
    response = await llm.ainvoke(full_messages)
    
    # 5. ✨ 核心重构：置信度评估与自适应 HITL 判定
    needs_disambiguation = False
    options = []
    retrieved_knowledge = ""
    
    if not response.tool_calls and response.content:
        # 🛡️ 评估模型也切换为 LOGIC 模型，确保打分公正
        eval_llm = create_llm(
            model=settings.LLM_LOGIC_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0
        ).with_structured_output(DisambiguationEval, method="function_calling")
        
        eval_prompt = f"""请评估以下调研结论的准确性，并以 JSON 格式输出评估结果。
场景: {active_archetype}
线索: {image_desc}
结论: {response.content}

如果结论中涉及的实体存在明显歧义且无法从线索中排除，请降低置信度并给出选项。"""
        
        try:
            eval_result = await eval_llm.ainvoke(eval_prompt)
            print(f"📊 [置信度评价] 得分: {eval_result.confidence_score} | 理由: {eval_result.reason}")
            
            if eval_result.confidence_score < 0.6:
                print("⚠️ [自适应 HITL] 置信度过低，触发人类消歧机制！")
                needs_disambiguation = True
                options = eval_result.suggested_options or [
                    {"label": "含义 A", "value": "meaning_a"},
                    {"label": "含义 B", "value": "meaning_b"}
                ]
            else:
                retrieved_knowledge = response.content
        except Exception as e:
            print(f"⚠️ [置信度评价] 出错: {e}")
            retrieved_knowledge = response.content

    return {
        "messages": [response],
        "retrieved_knowledge": retrieved_knowledge,
        "needs_disambiguation": needs_disambiguation,
        "disambiguation_options": options
    }

def should_continue_research(state: UIProjectState) -> str:
    """条件边：判断是去执行工具，还是调研完毕进入下一步"""
    # 如果触发了消歧，强行中断，走向会触发 interrupt_before 的节点
    if state.get("needs_disambiguation"):
        return "controversy_sniffer"
        
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        print(f"🔧 [Research Agent] 决定调用工具: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tools"
    
    print("✅ [Research Agent] 调研完毕。")
    return "controversy_sniffer"