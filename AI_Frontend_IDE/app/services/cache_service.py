import json
import time
import asyncio
import datetime
from typing import Optional, Any, Dict, List
from app.core.config import settings
from app.services.rag_knowledge import dedupe_knowledge_records, split_records_by_freshness, summarize_record_freshness

# --- 🚀 面试亮点：Redis 语义缓存与热点排行服务 ---

class CacheService:
    """
    【哨兵缓存层】：封装 Redis 逻辑，支持热词排行与知识快照缓存。
    """
    def __init__(self):
        # 实际开发中会使用 redis.asyncio.Redis()
        # 此处模拟 Redis 连接，优先保证功能闭环
        self._mock_redis: Dict[str, str] = {}
        self._mock_redis_expiry: Dict[str, float] = {}
        self._mock_zset: Dict[str, float] = {} # 模拟 Redis ZSet 排行榜
        self._trend_labels: Dict[str, str] = {}
        self._mock_kb: Dict[str, List[Dict[str, Any]]] = {}
        self._mock_hot_knowledge: Dict[str, Dict[str, Any]] = {}

    def _now_ts(self) -> float:
        return time.time()

    def _normalize_cache_key(self, keyword: str) -> str:
        return " ".join(str(keyword or "").strip().lower().split())

    def _hot_knowledge_key(self, keyword: str) -> str:
        return self._normalize_cache_key(keyword)

    def _purge_if_expired(self, key: str) -> bool:
        expires_at = self._mock_redis_expiry.get(key)
        if expires_at is not None and expires_at <= self._now_ts():
            self._mock_redis.pop(key, None)
            self._mock_redis_expiry.pop(key, None)
            return True
        return False

    def _get_live_hot_entry(self, keyword: str) -> Optional[Dict[str, Any]]:
        cache_key = self._hot_knowledge_key(keyword)
        entry = self._mock_hot_knowledge.get(cache_key)
        if not entry:
            return None
        expires_at_ts = float(entry.get("expires_at_ts") or 0)
        if expires_at_ts and expires_at_ts <= self._now_ts():
            self._mock_hot_knowledge.pop(cache_key, None)
            return None
        return entry

    def _build_hot_entry_meta(self, keyword: str, entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not entry:
            return {
                "cache_key": self._hot_knowledge_key(keyword),
                "cache_hit": False,
                "cache_freshness": "miss",
                "ttl_seconds": 0,
                "age_seconds": 0,
                "remaining_ttl_seconds": 0,
            }
        now = self._now_ts()
        cached_at_ts = float(entry.get("cached_at_ts") or now)
        expires_at_ts = float(entry.get("expires_at_ts") or now)
        ttl_seconds = int(entry.get("ttl_seconds") or max(0, int(expires_at_ts - cached_at_ts)))
        age_seconds = max(0, int(now - cached_at_ts))
        remaining_ttl_seconds = max(0, int(expires_at_ts - now))
        return {
            "cache_key": str(entry.get("cache_key") or self._hot_knowledge_key(keyword)),
            "cache_hit": True,
            "cache_freshness": "fresh" if remaining_ttl_seconds > 0 else "expired",
            "ttl_seconds": ttl_seconds,
            "age_seconds": age_seconds,
            "remaining_ttl_seconds": remaining_ttl_seconds,
            "cached_at": entry.get("cached_at"),
            "expires_at": entry.get("expires_at"),
            "keyword": entry.get("keyword") or keyword,
        }

    async def get_hot_knowledge(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        尝试从缓存中提取预热好的结构化知识。
        """
        entry = self._get_live_hot_entry(keyword)
        if entry:
            print(f"🚀 [Redis Hit] 命中热词缓存: {entry.get('keyword') or keyword}")
            return json.loads(json.dumps(entry.get("payload") or {}, ensure_ascii=False))
        return None

    async def get_hot_knowledge_snapshot(self, keyword: str) -> Dict[str, Any]:
        return self._build_hot_entry_meta(keyword, self._get_live_hot_entry(keyword))

    async def set_hot_knowledge(self, keyword: str, data: Dict[str, Any], ttl: int = 3600):
        """
        将 Agent 预调研的结果存入缓存，设置过期时间防止内存溢出。
        """
        cache_key = self._hot_knowledge_key(keyword)
        now = self._now_ts()
        ttl_seconds = max(1, int(ttl))
        expires_at_ts = now + ttl_seconds
        self._mock_hot_knowledge[cache_key] = {
            "cache_key": cache_key,
            "keyword": str(keyword or "").strip() or cache_key,
            "payload": json.loads(json.dumps(data or {}, ensure_ascii=False)),
            "cached_at_ts": now,
            "expires_at_ts": expires_at_ts,
            "ttl_seconds": ttl_seconds,
            "cached_at": datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc).isoformat(),
            "expires_at": datetime.datetime.fromtimestamp(expires_at_ts, tz=datetime.timezone.utc).isoformat(),
        }
        print(f"📦 [Redis Set] 已缓存热点知识包: {keyword} | key={cache_key} | TTL: {ttl_seconds}s")

    async def upsert_knowledge_records(
        self,
        entity_name: str,
        records: List[Dict[str, Any]],
        *,
        ingest_mode: str,
    ) -> Dict[str, Any]:
        """
        将知识记录写入轻量 KB 存储。
        """
        key = (entity_name or "").strip()
        if not key:
            return {"record_count": 0, "fresh_record_count": 0, "stale_record_count": 0, "freshness": "unknown", "ingest_mode": ingest_mode}
        merged = dedupe_knowledge_records([*(self._mock_kb.get(key) or []), *(records or [])])
        self._mock_kb[key] = merged
        summary = summarize_record_freshness(merged)
        summary["ingest_mode"] = ingest_mode
        print(f"📚 [KB UPSERT] entity={key} | records={summary['record_count']} | fresh={summary['fresh_record_count']} | mode={ingest_mode}")
        return summary

    async def get_knowledge_records(self, entity_name: str, *, include_stale: bool = True) -> List[Dict[str, Any]]:
        key = (entity_name or "").strip()
        records = list(self._mock_kb.get(key, []))
        if include_stale:
            return records
        fresh, _stale = split_records_by_freshness(records)
        return fresh

    async def get_knowledge_snapshot(self, entity_name: str) -> Dict[str, Any]:
        records = await self.get_knowledge_records(entity_name, include_stale=True)
        summary = summarize_record_freshness(records)
        summary["records"] = records
        return summary

    async def get_trend_result(self, query: str, selected_element_id: str) -> Optional[Dict[str, Any]]:
        key = f"trend:result:{selected_element_id}:{query}"
        self._purge_if_expired(key)
        data = self._mock_redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_trend_result(self, query: str, selected_element_id: str, page_dsl: Dict[str, Any], ttl: int = 3600) -> None:
        key = f"trend:result:{selected_element_id}:{query}"
        self._mock_redis[key] = json.dumps(page_dsl, ensure_ascii=False)
        self._mock_redis_expiry[key] = self._now_ts() + max(1, int(ttl))
        print(f"📦 [Redis Set] 已缓存趋势结果: el={selected_element_id} | TTL: {ttl}s")

    async def update_trend_rank(self, keyword: str, score_increment: float = 1.0):
        """
        更新热词排行榜。
        """
        # 面试槽点：利用 Redis ZSet 自动排序特性，获取 Top 10 热点仅需 O(logN)
        normalized = self._normalize_cache_key(keyword)
        current_score = self._mock_zset.get(normalized, 0.0)
        self._mock_zset[normalized] = current_score + score_increment
        if keyword and keyword.strip():
            self._trend_labels[normalized] = keyword.strip()

    async def get_top_trends(self, limit: int = 10) -> list:
        """
        获取当前最热的搜索词。
        """
        sorted_trends = sorted(self._mock_zset.items(), key=lambda x: x[1], reverse=True)
        return [self._trend_labels.get(item[0], item[0]) for item in sorted_trends[:limit]]

    async def match_trends_in_text(self, text: str) -> list:
        """
        在一段文本中匹配已存在的热词，并按热度从高到低返回。

        说明：真实线上通常会用更高效的 AC 自动机或倒排索引；
        这里用 mock zset 的 key 做一次线性扫描，确保功能可用。
        """
        if not text:
            return []

        text_normalized = self._normalize_cache_key(text)
        found: list[tuple[str, float]] = []
        for normalized_key, score in self._mock_zset.items():
            display = self._trend_labels.get(normalized_key, normalized_key)
            if normalized_key and (normalized_key in text_normalized or display in text):
                found.append((display, score))
        found.sort(key=lambda item: item[1], reverse=True)
        return [item[0] for item in found]

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
