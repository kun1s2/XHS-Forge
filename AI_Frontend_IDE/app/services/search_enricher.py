"""显式 enrich 流的补充检索器。

这条链不再承担主运行时的事实主入口，默认只在显式 enrich 场景下工作，
并且优先“补空槽位”，避免覆盖 research 已经落好的 grounded facts。
"""

import logging
import json
import re
from copy import deepcopy
from typing import Any
from app.tools.network_search import search_network_structured_async
from app.core.llm_factory import create_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

# ✨ 性能优化：复用极速清洗模型
_cleaner_llm = None
def get_cleaner_llm():
    global _cleaner_llm
    if _cleaner_llm is None:
        _cleaner_llm = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0
        )
    return _cleaner_llm


_PRICE_PATTERNS = (
    r"[¥￥]\s?\d[\d,]*(?:\.\d+)?",
    r"\d[\d,]*(?:\.\d+)?\s?元",
    r"\d+(?:\.\d+)?\s?[wW万]",
)


def _normalize_feature_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -:：，,。；;")
    return text


def _extract_price_from_results(results: list[dict[str, Any]]) -> str:
    for item in results or []:
        haystack = " ".join([
            str(item.get("title") or ""),
            str(item.get("snippet") or ""),
        ])
        for pattern in _PRICE_PATTERNS:
            matched = re.search(pattern, haystack)
            if matched:
                return matched.group(0).replace(" ", "")
    return ""


def _extract_feature_candidates(results: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for item in results or []:
        snippet = str(item.get("snippet") or "").strip()
        title = str(item.get("title") or "").strip()
        text = "；".join(part for part in [title, snippet] if part)
        for chunk in re.split(r"[；;。.!！?？\n]+", text):
            normalized = _normalize_feature_text(chunk)
            if not normalized:
                continue
            if len(normalized) < 6:
                continue
            if any(token in normalized for token in ["点击", "打开", "立即", "购买", "广告", "下载"]):
                continue
            candidates.append(normalized)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:5]


def _safe_parse_distilled_json(raw_text: str) -> dict[str, Any]:
    text = re.sub(r"```json\n?|```", "", str(raw_text or "")).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}

async def enrich_product_document(note_document: dict, archetype: str = "general") -> dict:
    """Distill product/location facts directly into NoteDocument blocks."""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    llm = get_cleaner_llm()
    
    # 1. 确定领域画像与提取目标
    DOMAIN_MAP = {
        "seeding": "核心参数、规格、主要成分、功能特性、官方售价",
        "gourmet": "招牌菜品、人均消费、营业时间、详细地址、评分总结",
        "travel": "门票价格、开放时间、游玩耗时、最佳月份、交通建议",
        "daily_share": "天气氛围、地点背景、时间线线索、可引用的生活细节",
        "general": "关键信息、核心特点、参考价格、基本属性"
    }
    target_info = DOMAIN_MAP.get(archetype, DOMAIN_MAP["general"])

    # 2. 嗅探页面全局主体
    page_title = ((document.get("document_meta") or {}).get("title") or "").strip()
    title_block = next(
        (
            str((block.get("props") or {}).get("title") or "").strip()
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "TitleBlock"
        ),
        "",
    )
    global_subject = title_block or page_title

    for block in blocks:
        if not isinstance(block, dict):
            continue
        comp_type = str(block.get("type") or "")
        props = deepcopy(block.get("props") or {})
        if comp_type in ["ProductCard", "ProductSpecCard", "LocationBlock"]:
            local_title = str(props.get("title") or "").strip()
            query_subject = local_title if local_title and len(local_title) > 2 else global_subject

            # 已有 grounded 数据时，不再重复改写，只补空字段。
            has_existing_sources = bool(props.get("sources"))
            has_existing_core_features = bool(props.get("core_features"))
            has_existing_price = bool(str(props.get("price") or "").strip())
            if has_existing_sources and has_existing_core_features and has_existing_price:
                continue
            
            print(f"🔍 [事实增强] 正在为「{query_subject}」寻找互联网真实数据 (领域: {archetype})...")
            
            try:
                # 执行搜索
                query = f"{query_subject} {target_info} 官方 真实体验 参数 价格"
                results = await search_network_structured_async(query, num=6)
                if not results: continue
                
                snippets = "\n".join([f"- {r.get('title')}: {r.get('snippet')}" for r in results])
                fallback_price = _extract_price_from_results(results)
                fallback_features = _extract_feature_candidates(results)
                
                # 3. ✨ 核心进化：使用极速 LLM 进行“专业蒸馏”
                # 这种方式彻底解决了硬编码关键词的局限性！
                distill_prompt = f"""你是一个专业的数据蒸馏助手。
请根据以下搜索结果，提取「{query_subject}」的「{target_info}」。

【搜索结果】:
{snippets}

【任务要求】:
1. 提取 5 条最硬核、最准确的信息。
2. 关于【价格】: 必须给出一个具体数字或区间（如 ￥11,390 或 1.1w-1.3w）。如果搜索结果存在多个价格（如官方价与溢价），请优先保留官方价并标注（如 ￥11,390 起）。严禁输出“未提及”或“暂无”。
3. 必须输出为严格的 JSON 格式：{{"refined_name": "简洁的官方名称", "price": "￥具体数值", "features": ["参数1", "参数2", ...]}}
不要有任何多余文字。"""

                response = await llm.ainvoke(distill_prompt)
                distilled_data = _safe_parse_distilled_json(response.content)
                if not distilled_data:
                    distilled_data = {}
                
                # 4. 回填 DSL：数据闭环
                # 修正商品/地点名字
                if (not local_title) and distilled_data.get("refined_name") and "未提及" not in distilled_data["refined_name"]:
                    props["title"] = distilled_data["refined_name"]
                
                # 修正价格
                price_val = distilled_data.get("price")
                if (not has_existing_price) and price_val and "未提及" not in str(price_val):
                    props["price"] = str(price_val)
                elif (not has_existing_price) and fallback_price:
                    props["price"] = fallback_price
                elif not has_existing_price:
                    props["price"] = "￥价格请以官方为准"

                
                # 修正参数
                if (not has_existing_core_features) and distilled_data.get("features"):
                    props["core_features"] = [
                        _normalize_feature_text(item)
                        for item in distilled_data["features"][:5]
                        if _normalize_feature_text(item)
                    ]
                elif (not has_existing_core_features) and fallback_features:
                    props["core_features"] = fallback_features

                if results and not has_existing_sources:
                    props["sources"] = [
                        {
                            "title": str(item.get("title") or "未命名来源").strip(),
                            "url": str(item.get("link") or "").strip(),
                            "snippet": str(item.get("snippet") or "").strip(),
                        }
                        for item in results[:3]
                        if str(item.get("title") or item.get("link") or item.get("snippet") or "").strip()
                    ]

                block["props"] = props
                
                print(f"✅ [事实增强] 「{query_subject}」数据已由 LLM 完成领域级蒸馏")
                        
            except Exception as e:
                logger.error(f"事实增强蒸馏失败: {e}")
                
    document["blocks"] = blocks
    return document
