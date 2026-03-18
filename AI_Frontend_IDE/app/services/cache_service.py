import json
import time
from typing import Optional, Any, Dict
from app.core.config import settings

# --- 🚀 面试亮点：Redis 语义缓存与热点排行服务 ---

class CacheService:
    """
    【哨兵缓存层】：封装 Redis 逻辑，支持热词排行与知识快照缓存。
    """
    def __init__(self):
        # 实际开发中会使用 redis.asyncio.Redis()
        # 此处模拟 Redis 连接，优先保证功能闭环
        self._mock_redis: Dict[str, str] = {}
        self._mock_zset: Dict[str, float] = {} # 模拟 Redis ZSet 排行榜

    async def get_hot_knowledge(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        尝试从缓存中提取预热好的结构化知识。
        """
        # 面试槽点：使用 Redis GET 操作，复杂度 O(1)
        data = self._mock_redis.get(f"trend:knowledge:{keyword}")
        if data:
            print(f"🚀 [Redis Hit] 命中热词缓存: {keyword}")
            return json.loads(data)
        return None

    async def set_hot_knowledge(self, keyword: str, data: Dict[str, Any], ttl: int = 3600):
        """
        将 Agent 预调研的结果存入缓存，设置过期时间防止内存溢出。
        """
        # 面试槽点：设置 TTL 保证热点时效性，通常热点生命周期为 1-4 小时
        self._mock_redis[f"trend:knowledge:{keyword}"] = json.dumps(data)
        print(f"📦 [Redis Set] 已缓存热点知识包: {keyword} | TTL: {ttl}s")

    async def update_trend_rank(self, keyword: str, score_increment: float = 1.0):
        """
        更新热词排行榜。
        """
        # 面试槽点：利用 Redis ZSet 自动排序特性，获取 Top 10 热点仅需 O(logN)
        current_score = self._mock_zset.get(keyword, 0.0)
        self._mock_zset[keyword] = current_score + score_increment

    async def get_top_trends(self, limit: int = 10) -> list:
        """
        获取当前最热的搜索词。
        """
        sorted_trends = sorted(self._mock_zset.items(), key=lambda x: x[1], reverse=True)
        return [item[0] for item in sorted_trends[:limit]]

    async def match_trends_in_text(self, text: str) -> list:
...
        found.sort(key=lambda x: self._mock_zset.get(x, 0), reverse=True)
        return found

    # --- 🛡️ 面试亮点：风控安全服务 ---
    
    async def check_risk_words(self, text: str) -> Optional[str]:
        """
        【第一道防线】：基于关键词的极速风控审计。
        """
        # 实际场景下会从 Redis 加载 500+ 违禁词
        risk_words = ["色情", "暴力", "毒品", "反动", "博彩", "刷单"]
        
        for word in risk_words:
            if word in text:
                print(f"🚨 [风控拦截] 发现违禁词: {word}")
                return word
        return None

# 单例模式
cache_service = CacheService()
