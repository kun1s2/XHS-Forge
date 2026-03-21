import asyncio
import json
import random
from typing import List, Dict, Any
from app.services.cache_service import cache_service
from app.agents.nodes.research_agent import research_agent
from app.agents.state import UIProjectState
from langchain_core.messages import HumanMessage

# --- 🚀 面试亮点：多线程/异步后台热点预热流水线 ---

class TrendPipeline:
    """
    【预热流水线】：模拟社交平台热点发现与异步 RAG 注入。
    """
    def __init__(self):
        self._is_running = False
        self._hot_topics = ["索尼 A7C2", "华为 Mate 60", "赛博朋克风测评", "理想 L9 避雷", "春天第一杯咖啡"]

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
        prompt = f"请调研 {topic} 的最新评价和参数。"
        if deep_scan:
            prompt = f"请针对「{topic}」进行深度舆情分析，找出现在社交平台上大家争议最大的 3 个点，并提取高保真图片。"

        # 构造调研状态
        mock_state: UIProjectState = {
            "main_messages": [HumanMessage(content=prompt)],
            "scenarios": ["seeding"],
            "active_archetype": "general",
            "intent_result_v2": {
                "task_type": "create",
                "edit_scope": "none",
                "needs_research": True,
                "needs_assets": "search",
                "scenario_scores": {"seeding": 1.0},
                "risk_flags": [],
            },
        }

        
        try:
            # ✨ 面试槽点：此处可引申为异步分布式 Worker 的一部分
            result = await research_agent(mock_state)
            knowledge = result.get("retrieved_knowledge")
            if knowledge:
                # 调研成功，写入 Redis 供所有用户共享
                await cache_service.set_hot_knowledge(topic, knowledge)
        except Exception as e:
            print(f"⚠️ [预热工兵] 调研失败 ({topic}): {e}")

# 单例模式
trend_pipeline = TrendPipeline()

async def process_new_trend_background(query_str: str, websocket=None):
    """
    【主动式热点发现】：用户提问时如果未命中缓存，异步启动该话题的收录。
    这展示了“由点及面”的流量聚合能力。
    """
    print(f"🔄 [任务分发] 针对新用户话题「{query_str[:15]}...」启动后台热点收录任务")
    # 此处可发送到消息队列 (RabbitMQ/Kafka) 进行削峰处理
    pass
