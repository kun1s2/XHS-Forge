import json
import asyncio
import re
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.cache_service import cache_service
from langchain_core.messages import ToolMessage, AIMessage, RemoveMessage

async def distill_node(state: UIProjectState) -> dict:
    """
    【事实提纯器 6.0】：从总线中提取所有工具返回的结果并结构化。
    """
    all_msgs = state.get("messages", [])
    raw_content = ""
    image_links = []
    messages_to_remove = []
    
    # 1. 遍历总线，搜集所有证据
    for msg in all_msgs:
        if msg.id: messages_to_remove.append(RemoveMessage(id=msg.id))
        
        if isinstance(msg, ToolMessage):
            # 获取工具名称（支持不同版本的映射）
            tool_name = getattr(msg, "name", "").lower()
            content = str(msg.content)
            
            # 如果是文本搜索结果
            if "network_search" in tool_name:
                raw_content += content + "\n"
            # 如果是搜图结果（宽容匹配 google_images 或 images）
            if "images" in tool_name or "google_images" in tool_name:
                # 提取其中的链接
                urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)', content)
                image_links.extend(urls)
                # 同时也把内容喂给文本提纯，防止图片描述中有文字干货
                raw_content += content + "\n"

    if not raw_content and not image_links:
        return {"retrieved_knowledge": {"is_fact_ready": False}}

    # 2. 文本事实提纯
    llm = create_llm(
        model=settings.LLM_BRAIN_MODEL, 
        api_key=settings.LLM_API_KEY, 
        base_url=settings.LLM_BASE_URL,
        temperature=0
    )
    runnable = llm.with_structured_output(FocusedKnowledge, method="function_calling")
    
    prompt = f"""你是一个极其严谨的数据提纯专家。
    请将以下【资料】提炼为结构化事实。
    
    【资料内容】:
    {raw_content}
    """

    try:
        knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        
        # 合并搜图抓到的直链
        # 物理过滤掉占位符
        final_images = []
        for url in list(set(image_links)):
            u_l = url.lower()
            if any(ghost in u_l for ghost in ["example.com", "picsum.photos", "placeholder"]): continue
            final_images.append(url)
        
        # 这里的 image_urls 字段已从 FocusedKnowledge 移除（根据之前的指令）
        # 但我们仍然可以将图片存入全局 image_assets
        new_assets = [{"url": u, "desc": f"{knowledge.entity_name} 真实搜证图片"} for u in final_images[:5]]

        print(f"✅ [提纯完毕] 主体: {knowledge.entity_name} | 捕获图片: {len(new_assets)}")

        return {
            "retrieved_knowledge": k_dict,
            "image_assets": new_assets,
            "messages": messages_to_remove + [AIMessage(content=f"已完成对「{knowledge.entity_name}」的搜证。")]
        }
    except Exception as e:
        print(f"❌ [蒸馏失败]: {e}")
        return {
            "retrieved_knowledge": {"is_fact_ready": False},
            "messages": messages_to_remove
        }
