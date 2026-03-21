import json
import asyncio
import re
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import apply_confirmed_facts_to_knowledge
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.schema import FocusedKnowledge
from app.services.cache_service import cache_service
from langchain_core.messages import ToolMessage, AIMessage, RemoveMessage


SOURCE_CARD_LIMIT = 6
CONFLICT_PATTERNS = {
    "battery_capacity": [
        re.compile(r"(?:电池|电池容量)[^0-9]{0,8}(\d{4,5})\s*mAh", re.IGNORECASE),
        re.compile(r"(\d{4,5})\s*mAh", re.IGNORECASE),
    ],
    "price": [
        re.compile(r"(?:售价|价格|起售价|官方价)[^0-9]{0,8}([0-9]{3,6})\s*元", re.IGNORECASE),
        re.compile(r"￥\s*([0-9]{3,6})"),
    ],
}


def _extract_structured_sources(raw_content: str) -> list[dict[str, Any]]:
    if not raw_content:
        return []

    pattern = re.compile(r"\[(\d+)\]\s*(.*?)\n链接:\s*(.*?)\n(.*?)(?=\n\[\d+\]\s|\Z)", re.S)
    sources: list[dict[str, Any]] = []
    for order, title, link, snippet in pattern.findall(raw_content):
        clean_title = str(title).strip()
        clean_link = str(link).strip()
        clean_snippet = " ".join(str(snippet).split())[:220]
        if not clean_title and not clean_link:
            continue
        source_type = "official" if any(token in clean_title.lower() or token in clean_link.lower() for token in ["official", "huawei.com", "apple.com", "mi.com", "oppo.com"]) else "web"
        sources.append({
            "order": int(order),
            "title": clean_title,
            "url": clean_link,
            "snippet": clean_snippet,
            "source_type": source_type,
        })
        if len(sources) >= SOURCE_CARD_LIMIT:
            break
    return sources


def _extract_conflicts(raw_content: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw_content:
        return []

    conflicts: list[dict[str, Any]] = []
    lowered = raw_content.lower()
    for field_name, patterns in CONFLICT_PATTERNS.items():
        values: dict[str, set[str]] = {}
        for source in sources or [{"title": "raw", "snippet": raw_content, "url": ""}]:
            text = f"{source.get('title', '')}\n{source.get('snippet', '')}"
            for pattern in patterns:
                for match in pattern.findall(text):
                    if isinstance(match, tuple):
                        value = next((str(item) for item in match if item), "")
                    else:
                        value = str(match)
                    value = value.strip()
                    if not value:
                        continue
                    values.setdefault(value, set()).add(source.get("title") or source.get("url") or "未知来源")

        if len(values) > 1:
            conflicts.append({
                "field": field_name,
                "values": [
                    {
                        "value": fact_value,
                        "sources": sorted(list(origin_sources))[:3],
                    }
                    for fact_value, origin_sources in sorted(values.items(), key=lambda item: item[0])
                ],
                "status": "needs_confirmation",
            })

    return conflicts


def _infer_fact_confidence(sources: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> str:
    if conflicts:
        return "low"
    official_count = sum(1 for source in sources if source.get("source_type") == "official")
    if official_count >= 1 and len(sources) >= 2:
        return "high"
    if len(sources) >= 2:
        return "medium"
    return "low"

async def distill_node(state: UIProjectState) -> dict:
    """
    【事实提纯器 6.0】：从总线中提取所有工具返回的结果并结构化。
    """
    all_msgs = state.get("messages", [])
    existing_knowledge = state.get("retrieved_knowledge", {})
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

    # research_agent 已经可能直接把文本事实塞进 retrieved_knowledge，这里做兜底承接
    if isinstance(existing_knowledge, dict):
        if existing_knowledge.get("text_facts"):
            raw_content += str(existing_knowledge["text_facts"]).strip()
        for asset in state.get("image_assets", []):
            url = asset.get("url")
            if url:
                image_links.append(url)

    if not raw_content and not image_links:
        if isinstance(existing_knowledge, dict) and existing_knowledge:
            return {"retrieved_knowledge": existing_knowledge}
        return {"retrieved_knowledge": {"is_fact_ready": False}}

    # 2. 文本事实提纯
    llm = create_llm(
        model=settings.LLM_MODEL, 
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
        # 重试回路
        max_retries = 2
        attempt = 0
        knowledge = None
        while attempt < max_retries:
            try:
                knowledge: FocusedKnowledge = await runnable.ainvoke(prompt)
                break
            except Exception as loop_e:
                attempt += 1
                print(f"⚠️ [Distill Node] 内部调用出错 (尝试 {attempt}/{max_retries}): {loop_e}")
                if attempt >= max_retries:
                    raise loop_e
                await asyncio.sleep(1)

        fact_sources = _extract_structured_sources(raw_content)
        fact_conflicts = _extract_conflicts(raw_content, fact_sources)
        fact_confidence = _infer_fact_confidence(fact_sources, fact_conflicts)

        k_dict = knowledge.model_dump()
        k_dict["is_fact_ready"] = True
        k_dict["fact_sources"] = fact_sources
        k_dict["fact_conflicts"] = fact_conflicts
        k_dict["fact_confidence"] = fact_confidence
        k_dict["needs_fact_confirmation"] = bool(fact_conflicts)
        k_dict["fact_review_status"] = "pending" if fact_conflicts else "clear"
        if isinstance(existing_knowledge, dict):
            normalized_entity = normalize_entity_name(existing_knowledge.get("entity_name", ""))
            if normalized_entity:
                k_dict["entity_name"] = normalized_entity
            for carry_key in ("text_facts", "battle_report", "clash_report", "fact_sources", "fact_conflicts", "confirmed_facts", "fact_confidence", "needs_fact_confirmation", "fact_review_status"):
                if existing_knowledge.get(carry_key) is not None and k_dict.get(carry_key) in (None, "", [], {}):
                    k_dict[carry_key] = existing_knowledge[carry_key]

        k_dict = apply_confirmed_facts_to_knowledge(k_dict)
        
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
        if isinstance(existing_knowledge, dict) and existing_knowledge:
            fallback_knowledge = dict(existing_knowledge)
            fallback_knowledge["is_fact_ready"] = bool(existing_knowledge.get("text_facts") or existing_knowledge.get("core_attributes"))
            return {
                "retrieved_knowledge": fallback_knowledge,
                "messages": messages_to_remove
            }
        return {
            "retrieved_knowledge": {"is_fact_ready": False},
            "messages": messages_to_remove
        }
