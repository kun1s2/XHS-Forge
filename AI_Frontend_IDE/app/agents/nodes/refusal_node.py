from app.agents.state import UIProjectState
from langchain_core.messages import AIMessage

async def refusal_node(state: UIProjectState) -> dict:
    """
    【风控隔离区】：针对非法或风险指令的礼貌拒绝节点。
    """
    risk_reason = "内容违反安全策略"
    if state.get("thought_process"):
        risk_reason = str(state.get("thought_process") or risk_reason)

    print(f"🛡️ [Refusal Node] 拦截生效: {risk_reason}")
    
    reply = AIMessage(content="报告长官：您的请求由于涉及敏感内容或不合规操作，已被系统风控网关拦截。XHS-Forge 致力于打造健康、绿色的创作环境，请调整您的指令后重试。")
    
    return {
        "main_messages": [reply]
    }
