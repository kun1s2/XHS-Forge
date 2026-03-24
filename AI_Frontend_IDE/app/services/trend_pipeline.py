import asyncio
from typing import List, Dict, Any
from app.services.cache_service import cache_service
from app.services.rag_ingestion import ingest_retrieved_knowledge
from app.services.trend_intelligence import infer_trend_profile, normalize_trend_keyword
from app.agents.services.research_service import research_service
from langchain_core.messages import HumanMessage

RuntimeState = dict[str, Any]

# --- 🚀 面试亮点：多线程/异步后台热点预热流水线 ---

class TrendPipeline:
    """
    【预热流水线】：模拟社交平台热点发现与异步 RAG 注入。
    """
    def __init__(self):
        self._is_running = False
        self._inflight_topics: set[str] = set()

    async def start_background_task(self):
        """
        后台启动预热守护进程。
        """
        if self._is_running: return
        self._is_running = True
        print("🛡️ [Sentinel Pipeline] 启动热点预热守护进程...")
        asyncio.create_task(self._trend_loop())

    async def _trend_loop(self):
        """
        核心循环：动态从 Redis 提取 Top 热词并执行深度异步调研。
        """
        while self._is_running:
            try:
                # 1. ✨ 面试亮点：不再使用死列表，而是从 Redis ZSet 提取真实热词
                dynamic_trends = await cache_service.get_top_trends(limit=5)

                for topic in dynamic_trends:
                    print(f"📡 [哨兵追踪] 正在对动态热词「{topic}」执行长效监测...")

                    # 2. 模拟深度挖掘：不仅仅是查参数，还要查最新的舆情争议点
                    await self._pre_research_topic(topic, deep_scan=True)

            except Exception as e:
                print(f"❌ [Sentinel Pipeline] 预热失败: {e}")

            # 社交平台热点更新快，我们每 5 分钟扫描一轮
            await asyncio.sleep(300)

    async def _pre_research_topic(self, topic: str, deep_scan: bool = False):
        """
        调用 Agent 进行调研。如果开启 deep_scan，会增加舆情探测权重。
        """
        normalized_topic = normalize_trend_keyword(topic)
        if not normalized_topic:
            return
        profile = infer_trend_profile(normalized_topic)
        prompt = f"请调研 {topic} 的最新评价和参数。"
        if deep_scan:
            prompt = f"请针对「{topic}」进行深度舆情分析，找出现在社交平台上大家争议最大的 3 个点，并提取高保真图片。"

        # 构造调研状态
        mock_state: RuntimeState = {
            "main_messages": [HumanMessage(content=prompt)],
            "scenarios": [profile["scenario_hint"]] if profile["scenario_hint"] != "general" else ["seeding"],
            "active_archetype": "seeding",
            "intent_decision": {
                "task_type": "create",
                "operation_type": "generate",
                "scope": "global_canvas",
                "needs_research": True,
                "needs_assets": True,
                "confidence": 0.9,
                "fallback_required": False,
                "risk_flags": [],
            },
        }

        
        try:
            # ✨ 面试槽点：此处可引申为异步分布式 Worker 的一部分
            result = await research_service(mock_state)
            knowledge = result.get("retrieved_knowledge")
            if knowledge:
                # 调研成功，写入 Redis 供所有用户共享
                ingest_result = await ingest_retrieved_knowledge(
                    entity_name=topic,
                    scenario=profile["scenario_hint"] if profile["scenario_hint"] != "general" else "seeding",
                    ingest_mode="system_preload",
                    knowledge=knowledge,
                )
                knowledge["retrieval_summary"] = {
                    **dict(knowledge.get("retrieval_summary") or {}),
                    "policy_name": (knowledge.get("retrieval_summary") or {}).get("policy_name") or "cache_then_live_grounded",
                    "policy_path": (knowledge.get("retrieval_summary") or {}).get("policy_path") or "cache_first_then_live_search",
                    "ingest_mode": "system_preload",
                    "record_count": ingest_result["kb_snapshot"].get("record_count") or 0,
                    "fresh_record_count": ingest_result["kb_snapshot"].get("fresh_record_count") or 0,
                    "stale_record_count": ingest_result["kb_snapshot"].get("stale_record_count") or 0,
                    "freshness": ingest_result["kb_snapshot"].get("freshness") or "fresh",
                    "rerank_applied": bool((knowledge.get("retrieval_summary") or {}).get("rerank_applied")),
                }
                knowledge["retrieval_eval"] = ingest_result["retrieval_eval"]
                knowledge["knowledge_records"] = ingest_result["records"]
                ttl_seconds = max(
                    [int(record.get("ttl_seconds") or 0) for record in (ingest_result["records"] or [])] or [6 * 3600]
                )
                await cache_service.set_hot_knowledge(normalized_topic, knowledge, ttl=ttl_seconds)
                await cache_service.update_trend_rank(
                    normalized_topic,
                    score_increment=5.0 if deep_scan else 2.0,
                    scenario_hint=profile["scenario_hint"],
                    source="system_preload",
                    record_count=ingest_result["kb_snapshot"].get("record_count") or 0,
                    freshness=ingest_result["kb_snapshot"].get("freshness") or "fresh",
                )
        except Exception as e:
            print(f"⚠️ [预热工兵] 调研失败 ({topic}): {e}")

# 单例模式
trend_pipeline = TrendPipeline()

async def process_new_trend_background(query_str: str, websocket=None):
    """
    【主动式热点发现】：用户提问时如果未命中缓存，异步启动该话题的收录。
    这展示了“由点及面”的流量聚合能力。
    """
    topic = normalize_trend_keyword(query_str)
    if not topic:
        return
    profile = infer_trend_profile(topic)
    hot_snapshot = await cache_service.get_hot_knowledge_snapshot(topic)
    if hot_snapshot.get("cache_hit") and hot_snapshot.get("cache_freshness") == "fresh":
        return
    if topic in trend_pipeline._inflight_topics:
        return

    print(f"🔄 [任务分发] 针对新用户话题「{topic[:15]}...」启动后台热点收录任务")
    trend_pipeline._inflight_topics.add(topic)
    try:
        await cache_service.update_trend_rank(
            topic,
            score_increment=2.0,
            scenario_hint=profile["scenario_hint"],
            source="task_triggered_ingest",
            freshness="unknown",
        )
        await trend_pipeline._pre_research_topic(topic, deep_scan=True)
    finally:
        trend_pipeline._inflight_topics.discard(topic)
