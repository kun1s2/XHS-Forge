from app.agents.state import UIProjectState
from app.services.rag_service import retrieve_brand_knowledge

async def rag_node(state: UIProjectState) -> dict:
    """
    【RAG 检索节点】：在生成文案前，先去向量库捞一把私域知识。
    """
    active_panel = state.get("active_panel", "main")
    messages = state.get(f"{active_panel}_messages", [])
    
    if not messages:
        return {"retrieved_knowledge": ""}
        
    # 获取用户最后一条指令
    last_msg = messages[-1].content
    user_query = ""
    if isinstance(last_msg, list):
        user_query = " ".join([item["text"] for item in last_msg if item.get("type") == "text"])
    else:
        user_query = str(last_msg)
        
    # 执行 RAG 检索
    knowledge = await retrieve_brand_knowledge(user_query)
    
    # 将知识写入 state，供后续正式页面生成链消费
    return {
        "retrieved_knowledge": knowledge
    }
