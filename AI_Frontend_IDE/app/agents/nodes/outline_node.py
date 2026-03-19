import json
from pathlib import Path
from typing import Dict, Any, List
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import OutlineOutput 
from app.agents.tools_registry import OUTLINE_TOOLS
from app.agents.utils.observation_dashboard import generate_observation_dashboard
from langchain_core.messages import AIMessage, HumanMessage

# ✨ 性能优化：全局复用支持工具调用的 LLM 实例
_llm_instance = None

def get_outline_agent_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.7 
        ).bind_tools(OUTLINE_TOOLS) # ✨ 绑定积木检索工具
    return _llm_instance

async def outline_agent(state: UIProjectState) -> dict:
    """
    【X-Forge 7.0 真·ReAct 大纲节点】：
    不再是一次性生成，而是在循环中利用工具检索积木说明书，边观察边排版。
    """
    # 1. 环境观测：生成实时仪表盘
    dashboard = generate_observation_dashboard(state)
    
    # 2. 状态提取
    intent_res = state.get("intent_result")
    mode = getattr(intent_res, "narrative_mode", "spatial") if not isinstance(intent_res, dict) else intent_res.get("narrative_mode", "spatial")
    
    # 3. 构造 ReAct 提示词
    # 强制告知大模型：必须使用工具来操作画布
    system_prompt = f"""你是一个具备 ReAct 思考能力的顶级排版导演。
你的终极任务是使用【画布工具】将内容转化为高交互的一维区块流。

{dashboard}

【🛠️ 你的行动指南】：
1. 观察：阅读上述仪表盘，了解当前页面进度和资产余量。
2. 思考 (Thought)：分析当前叙事阶段需要什么积木。如果你不知道怎么用某个积木，调用 search_block_manual 查询。
3. 行动 (Action)：你【必须】调用 append_block 工具将积木逐个添加到画布上。如果你发现加错了，可以调用 remove_block 或 update_block_brief 修改。
4. 收尾：当你认为画布积木数（4-6个）已经足够且排版完美时，你【必须】调用 finish_layout 工具来结束工作。

【⚠️ 绝对铁律】：
- 严禁直接输出 JSON 结构！你所有的排版动作都必须通过调用 append_block 等工具来完成。
- 无图时严禁追加 CoverSwiper, WeatherPolaroid 等图片积木。
"""

    llm = get_outline_agent_llm()
    
    # 我们将之前的对话历史也带上，方便 ReAct 循环记忆之前的 Thought
    # 如果是循环的第一轮，我们注入初始指令
    messages = state.get("messages", [])
    if not messages:
        messages = [
            ("system", system_prompt),
            ("human", f"请开始排版。当前叙事模式: {mode}")
        ]
    else:
        # 如果是循环的中途，我们只更新 System 信息（仪表盘）
        # 这里为了保持简洁，我们每次都重新注入最新的仪表盘
        messages = [("system", system_prompt)] + [m for m in messages if not isinstance(m, tuple) or m[0] != "system"]

    print(f"🧠 [ReAct 导演] 正在思考下一步行动...")
    res = await llm.ainvoke(messages)
    
    return {"messages": [res]}

def should_continue_outlining(state: UIProjectState) -> str:
    """
    【大纲路由守卫】：判断 Agent 是想查手册，还是已经交卷。
    """
    msgs = state.get("messages", [])
    if not msgs: return "END"
    
    last_msg = msgs[-1]
    # 如果有工具调用（search_block_manual）
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "outline_tools"
    
    # 否则，尝试将输出内容解析为 JSON 提纯
    return "outline_synthesizer"
