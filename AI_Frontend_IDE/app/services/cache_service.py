import json
import time
import asyncio
import datetime
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

    async def get_trend_result(self, query: str, selected_element_id: str) -> Optional[Dict[str, Any]]:
        key = f"trend:result:{selected_element_id}:{query}"
        data = self._mock_redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_trend_result(self, query: str, selected_element_id: str, page_dsl: Dict[str, Any], ttl: int = 3600) -> None:
        key = f"trend:result:{selected_element_id}:{query}"
        self._mock_redis[key] = json.dumps(page_dsl, ensure_ascii=False)
        print(f"📦 [Redis Set] 已缓存趋势结果: el={selected_element_id} | TTL: {ttl}s")

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
        在一段文本中匹配已存在的热词，并按热度从高到低返回。

        说明：真实线上通常会用更高效的 AC 自动机或倒排索引；
        这里用 mock zset 的 key 做一次线性扫描，确保功能可用。
        """
        if not text:
            return []

        found = [kw for kw in self._mock_zset.keys() if kw and kw in text]
        found.sort(key=lambda x: self._mock_zset.get(x, 0.0), reverse=True)
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

async def get_trend_cache(query: str, selected_element_id: str) -> Optional[Dict[str, Any]]:
    return await cache_service.get_trend_result(query, selected_element_id)


async def set_trend_cache(query: str, selected_element_id: str, page_dsl: Dict[str, Any], ttl: int = 3600) -> None:
    await cache_service.set_trend_result(query, selected_element_id, page_dsl, ttl=ttl)


class RiskControlCache:
    """
    为 API 层提供稳定的风控入口（兼容旧导入）。
    """

    @staticmethod
    async def check_veto(text: str) -> bool:
        hit = await cache_service.check_risk_words(text or "")
        return bool(hit)


async def sync_risk_words_from_cloud() -> None:
    """
    从云端同步最新风控词库。

    说明：当前仓库使用 mock 缓存实现，为了保证系统可启动，这里提供一个安全的占位实现。
    若后续接入真实 Redis / OSS / HTTP 接口，可在此处替换为真实拉取逻辑，并写入 cache_service。
    """
    # 预留：settings 中可能存在词库地址/鉴权信息；当前不强依赖，避免启动失败
    print("🛡️ [风控同步] (mock) 已触发云端词库同步。")


async def scheduled_risk_sync_task() -> None:
    """
    定时同步守护协程：每天凌晨 02:00 触发一次 sync_risk_words_from_cloud。
    该协程会长期运行，支持被 Cancel。
    """
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target + datetime.timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()

        try:
            await asyncio.sleep(sleep_seconds)
            await sync_risk_words_from_cloud()
        except asyncio.CancelledError:
            # 允许应用 shutdown 时优雅退出
            raise
