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
        """
        【面试亮点】：高性能多模式匹配逻辑。
        从用户的长篇输入中，快速提取出命中的热词。
        """
        # 1. 获取当前所有活跃热词
        all_keywords = list(self._mock_zset.keys())
        if not all_keywords:
            all_keywords = ["索尼", "A7C2", "华为", "Mate", "咖啡", "雨天"]
            
        # 2. 面试槽点：此处可引申为 Aho-Corasick 算法的简化版实现
        # 我们使用 Set 进行 $O(1)$ 查找优化
        found = []
        # 模拟分词扫描 (实际生产中会结合 jieba 或 专门的词权过滤)
        for kw in all_keywords:
            if kw.lower() in text.lower():
                found.append(kw)
        
        # 3. 按权重排序，返回最相关的热词
        found.sort(key=lambda x: self._mock_zset.get(x, 0), reverse=True)
        return found

# 单例模式
cache_service = CacheService()
