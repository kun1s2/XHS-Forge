# app/services/search_enricher.py
import logging
import json
import re
import asyncio
from typing import List, Dict, Any
from app.tools.network_search import search_network_structured_async
from langchain_openai import ChatOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# ✨ 性能优化：复用极速清洗模型
_cleaner_llm = None
def get_cleaner_llm():
    global _cleaner_llm
    if _cleaner_llm is None:
        _cleaner_llm = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0
        )
    return _cleaner_llm

async def enrich_product_data(data_dsl: dict, archetype: str = "general") -> dict:
    """
    【全领域事实增强引擎 3.0】：领域感知 + 极速 LLM 蒸馏。
    无论用户搜的是相机、护肤品还是餐厅，都能输出专家级参数。
    """
    enriched_dsl = data_dsl.copy()
    llm = get_cleaner_llm()
    
    # 1. 确定领域画像与提取目标
    DOMAIN_MAP = {
        "seeding": "核心参数、规格、主要成分、功能特性、官方售价",
        "gourmet": "招牌菜品、人均消费、营业时间、详细地址、评分总结",
        "travel": "门票价格、开放时间、游玩耗时、最佳月份、交通建议",
        "general": "关键信息、核心特点、参考价格、基本属性"
    }
    target_info = DOMAIN_MAP.get(archetype, DOMAIN_MAP["general"])

    # 2. 嗅探页面全局主体
    page_title = data_dsl.get("page_title", "")
    title_block = next((v.get("title") for v in data_dsl.values() if isinstance(v, dict) and v.get("type") == "TitleBlock"), "")
    global_subject = title_block or page_title

    for comp_id, comp_data in enriched_dsl.items():
        if not isinstance(comp_data, dict): continue
            
        comp_type = comp_data.get("type")
        # 只要是需要“事实”的卡片，都启动增强
        if comp_type in ["ProductCard", "ProductSpecCard", "LocationBlock"]:
            local_title = comp_data.get("title", "")
            query_subject = local_title if local_title and len(local_title) > 2 else global_subject
            
            print(f"🔍 [事实增强] 正在为「{query_subject}」寻找互联网真实数据 (领域: {archetype})...")
            
            try:
                # 执行搜索
                results = await search_network_structured_async(query_subject + " " + target_info, num=4)
                if not results: continue
                
                snippets = "\n".join([f"- {r.get('title')}: {r.get('snippet')}" for r in results])
                
                # 3. ✨ 核心进化：使用极速 LLM 进行“专业蒸馏”
                # 这种方式彻底解决了硬编码关键词的局限性！
                distill_prompt = f"""你是一个专业的数据蒸馏助手。
请根据以下搜索结果，提取「{query_subject}」的「{target_info}」。

【搜索结果】:
{snippets}

【输出要求】:
1. 提取 5 条最硬核、最准确的信息。
2. 严禁包含营销话术、过时新闻（如发布会时间）或无关干扰。
3. 必须输出为 JSON 格式：{{"refined_name": "简洁的官方名称", "price": "参考价格", "features": ["参数1", "参数2", ...]}}
不要有任何多余文字。"""

                response = await llm.ainvoke(distill_prompt)
                # 清洗 JSON
                clean_json = re.sub(r"```json\n?|```", "", response.content).strip()
                distilled_data = json.loads(clean_json)
                
                # 4. 回填 DSL：数据闭环
                # 修正商品/地点名字
                if distilled_data.get("refined_name"):
                    enriched_dsl[comp_id]["title"] = distilled_data["refined_name"]
                
                # 修正价格
                if distilled_data.get("price") and distilled_data.get("price") != "暂无":
                    enriched_dsl[comp_id]["price"] = distilled_data["price"]
                
                # 修正参数
                if distilled_data.get("features"):
                    enriched_dsl[comp_id]["core_features"] = distilled_data["features"][:5]
                
                print(f"✅ [事实增强] 「{query_subject}」数据已由 LLM 完成领域级蒸馏")
                        
            except Exception as e:
                logger.error(f"事实增强蒸馏失败: {e}")
                
    return enriched_dsl
