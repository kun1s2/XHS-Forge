from app.agents.state import UIProjectState
from langchain_core.messages import AIMessage

async def refusal_node(state: UIProjectState) -> dict:
    """
    【风控隔离区】：针对非法或风险指令的礼貌拒绝节点。
    """
    intent_res = state.get("intent_result")
    risk_reason = "内容违反安全策略"
    if intent_res:
        risk_reason = getattr(intent_res, "thought_process", "检测到潜在风险")

    print(f"🛡️ [Refusal Node] 拦截生效: {risk_reason}")
    
    reply = AIMessage(content="报告长官：您的请求由于涉及敏感内容或不合规操作，已被系统风控网关拦截。XHS-Forge 致力于打造健康、绿色的创作环境，请调整您的指令后重试。")
    
    return {
        "main_messages": [reply]
    }
