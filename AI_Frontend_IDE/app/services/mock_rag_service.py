# app/services/mock_rag_service.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 🗄️ 【X-Forge 热缓存数据库】：存储高价值、高时效性的行业事实
MOCK_KNOWLEDGE_DB = {
    "小米17 Ultra": """
    【3C数码 - 小米 17 Ultra (2026款)】
    - 处理器：高通骁龙 8 Gen 5 (定制版)
    - 屏幕：6.73英寸 3K 双层 OLED 屏，局部峰值亮度 4500nit
    - 影像：徕卡全焦段四摄，主摄采用 1.5英寸超大底传感器，支持全像素对焦
    - 亮点：首发小米自研卫星通话 2.0，支持无信号双向即时通讯；钛金属 3.0 机身
    - 缺点：机身重量约 235g 较沉；起售价上涨至 6999 元
    """,
    "海蓝之谜面霜": """
    【美妆个护 - La Mer 海蓝之谜精华面霜】
    - 核心成分：神奇活性精萃 Miracle Broth™、酸橙茶精华
    - 功效：极致修护、舒缓抗敏、强韧屏障
    - 质地：丰盈绸缎质地，需掌心乳化至透明状
    - 亮点：修护力天花板，尤其适合换季过敏或术后修护
    - 缺点：价格昂贵，性价比低；油皮使用需谨慎，可能闷痘
    """,
    "安福路探店": """
    【线下探店 - 上海安福路网红街区】
    - 推荐店铺：Sunflour (阳光粮品)、RAC Bar、BADMARKET
    - 特色：极具“多巴胺”气息的街道，上海街拍鼻祖，法式梧桐氛围感
    - 人均：120元 - 300元
    - 亮点：出片率 100%，适合复古、废土或老钱风穿搭
    - 缺点：周末人流极大，热门餐厅需等位 2小时以上；街道较窄易拥堵
    """
}

async def retrieve_from_mock_db(query: str) -> Optional[str]:
    """
    【双引擎 RAG 第一层：Cache Hit 层】
    根据用户 Query 匹配本地热缓存。
    TODO: 若此处 Cache Miss，应触发 Web Search 并双写回 PGVector 向量库。
    """
    query_clean = query.strip()
    
    # 简单的关键词命中逻辑
    for key, content in MOCK_KNOWLEDGE_DB.items():
        if key.lower() in query_clean.lower():
            logger.info(f"🎯 [RAG Cache Hit]: 命中关键词 「{key}」")
            return content
            
    logger.warning(f"⚠️ [RAG Cache Miss]: 关键词 「{query_clean}」未命中本地热缓存")
    return None
