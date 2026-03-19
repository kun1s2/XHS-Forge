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
    knowledge = state.get("retrieved_knowledge", {}) if isinstance(state.get("retrieved_knowledge", {}), dict) else {}
    has_controversy = state.get("has_controversy", False)
    battle_report = knowledge.get("battle_report")
    
    # 获取用户真实指令，这是大纲排版的最核心依据！
    main_msgs = state.get("main_messages", [])
    if main_msgs:
        raw_content = getattr(main_msgs[-1], "content", "")
        if isinstance(raw_content, list):
            user_query = "".join(
                str(part.get("text"))
                for part in raw_content
                if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
            ).strip() or "自由排版"
        else:
            user_query = str(raw_content)
    else:
        user_query = "自由排版"

    # 3. 构造 ReAct 提示词
    # 强制告知大模型：必须使用工具来操作画布
    system_prompt = f"""你是一个具备 ReAct 思考能力的顶级排版导演。
你的终极任务是使用【画布工具】将内容转化为高交互的一维区块流。

【🎯 用户原始要求 (最高优先级)】:
>> {user_query} <<
你必须仔细阅读用户的要求。如果用户指定了某个积木（如雷达图、投票），你必须选用对应的积木。

{dashboard}

【⚙️ 可用物理组件库 (字典级白名单)】:
你【只能】使用以下这些被系统支持的积木，绝对严禁捏造任何其他名称（如 ImageBlock, AdvantageBlock 等）！
- TitleBlock: 页面标题
- StoryText: 叙事文本
- VersusCard: 深度对比（红黑对撞）
- ProductSpecCard: 核心参数网格
- RadarChartBlock: 多维性能雷达图
- CoverSwiper: 大图轮播 (仅限图片数>0使用)
- WeatherPolaroid: 时态氛围拍立得 (仅限图片数>0使用)
- PollBlock: 互动投票卡
- LocationBlock: 地理位置打卡

【🛠️ 你的行动指南】：
1. 观察：阅读上述仪表盘，了解当前页面进度、资产余量以及【RAG 知识库存】。
2. 思考 (Thought)：分析当前叙事阶段需要什么积木。如果你不知道怎么用某个积木，调用 search_block_manual 查询。
3. 行动 (Action)：你【每轮只能调用一个】工具！
   - 如果你想加积木，调用 append_block。
   - 如果你发现加错了，可以调用 remove_block 修改。

【🚨 排版审计铁律 (禁止过早完工)】:
- 知识转化：你必须审视仪表盘中的‘事实库存’。如果还有未转化的【优势点】或【槽点】，你【严禁】结束排版！你必须继续添加积木（如 RadarChartBlock 或 ProductSpecCard）来消耗这些知识。
- 积木限额：全篇积木数（不含标题）必须达到 5-7 个，以确保页面内容的极致丰满度和专业感。
- 只有满足上述两点，你才能调用 finish_layout 工具来结束工作。

【🔥 对冲内容优先级】：
- 如果系统已提供 battle_report，你必须至少加入一个 VersusCard 来承接正反观点。
- 如果 has_controversy = true，优先考虑加入 PollBlock 强化互动站队。

【⚠️ 绝对铁律】：
- 严禁直接输出 JSON 结构！所有动作必须通过工具完成。
"""

    if battle_report:
        system_prompt += f"\n【battle_report 已就绪】:\n{json.dumps(battle_report, ensure_ascii=False)}\n"
    if has_controversy:
        system_prompt += "\n【当前内容存在争议信号】has_controversy = true\n"

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
