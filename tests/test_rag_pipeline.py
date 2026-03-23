import pytest
import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError
# 引入核心业务组件
from app.core.schema import FocusedKnowledge
from app.services.mock_rag_service import retrieve_from_mock_db
from app.services.cache_service import CacheService
from app.agents.nodes.research_agent import research_agent
from app.agents.state import UIProjectState
from app.api.workspace import inspect_agent_state

# --- 🧪 Test Suite 1: 测试 Mock 库与 Schema 强校验 ---

@pytest.mark.asyncio
async def test_mock_db_retrieval():
    """验证本地热缓存能否正确命中"""
    # 命中测试
    content = await retrieve_from_mock_db("帮我看看小米17 Ultra")
    assert content is not None
    assert "骁龙 8 Gen 5" in content
    
    # 错过测试
    missing = await retrieve_from_mock_db("不存在的神秘产品")
    assert missing is None

def test_focused_knowledge_schema():
    """验证 Pydantic 契约的严谨性"""
    valid_data = {
        "domain_category": "3C数码测评",
        "entity_name": "小米 17 Ultra",
        "core_attributes": {"处理器": "骁龙8 Gen 5"},
        "key_selling_points": ["卫星通话"],
        "known_issues": ["重"],
        "summary": "测试总结"
    }
    
    # 1. 实例化测试
    knowledge = FocusedKnowledge(**valid_data)
    assert knowledge.domain_category == "3C数码测评"
    
    # 2. 越界测试：传入非法领域
    invalid_data = valid_data.copy()
    invalid_data["domain_category"] = "非法领域 (如金融)"
    with pytest.raises(ValidationError):
        FocusedKnowledge(**invalid_data)

# --- 🧪 Test Suite 2: 测试主线阻塞与时序流转 ---

@pytest.mark.asyncio
@patch.dict(
    "app.agents.nodes.research_agent.TOOL_POOL",
    {
        "network_search": MagicMock(
            ainvoke=AsyncMock(side_effect=[
                "小米 17 Ultra 参数: CPU=Snapdragon 8 Gen 5, 价格=6999",
                "用户评价: 影像强，但价格偏高"
            ])
        )
    },
)
@patch("app.agents.nodes.research_agent.search_network_structured_async", new_callable=AsyncMock)
@patch("app.agents.nodes.research_agent.search_google_images", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.get_hot_knowledge", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.match_trends_in_text", new_callable=AsyncMock)
async def test_research_node_blocking_flow(mock_match_trends, mock_get_hot_knowledge, mock_search_google_images, mock_structured_search):
    """【核心战役】：验证 research_node 必须阻塞并正确填充 State"""

    mock_match_trends.return_value = []
    mock_get_hot_knowledge.return_value = None
    mock_search_google_images.return_value = []
    mock_structured_search.side_effect = [
        [{"title": "华为官网 Mate 60", "link": "https://example.com/official", "snippet": "价格 6999"}],
        [{"title": "用户评价合集", "link": "https://example.com/review", "snippet": "影像强"}],
    ]
    
    # 2. 构造初始状态
    from langchain_core.messages import HumanMessage
    state: UIProjectState = {
        "main_messages": [HumanMessage(content="我想写小米17 Ultra")],
        "active_panel": "main",
        "retrieved_knowledge": None,
        "intent_result_v2": {"needs_assets": "none"},
    }
    
    # 3. 触发节点（执行必须是阻塞的）
    result = await research_agent(state)
    
    # 4. 生死断言：检查状态机是否被同步更新
    assert result["retrieved_knowledge"] is not None
    assert result["retrieved_knowledge"]["entity_name"] == "小米17 Ultra"
    assert result["retrieved_knowledge"]["is_fact_ready"] is True
    assert "Snapdragon 8 Gen 5" in result["retrieved_knowledge"]["text_facts"]
    assert result["retrieved_knowledge"]["retrieval_summary"]["strategy"] == "live_search_with_citations"
    assert result["retrieved_knowledge"]["retrieval_summary"]["policy_name"] == "cache_then_live_grounded"
    assert result["retrieved_knowledge"]["retrieval_summary"]["policy_path"] == "cache_first_then_live_search"
    assert result["retrieved_knowledge"]["retrieval_summary"]["ingest_mode"] == "task_triggered_ingest"
    assert result["retrieved_knowledge"]["retrieval_summary"]["rerank_applied"] is True
    assert result["retrieved_knowledge"]["retrieval_summary"]["citation_count"] == 2
    assert result["retrieved_knowledge"]["retrieval_summary"]["record_count"] == 2
    assert len(result["retrieved_knowledge"]["fact_sources"]) == 2
    assert len(result["retrieved_knowledge"]["knowledge_records"]) == 2
    assert result["retrieved_knowledge"]["retrieval_eval"]["citation_count"] == 2
    assert result["retrieved_knowledge"]["retrieval_eval"]["citation_coverage"] >= 0.5
    assert result["retrieved_knowledge"]["retrieval_eval"]["source_quality"] == "medium"
    assert result["retrieved_knowledge"]["retrieval_eval"]["recommendation"]
    assert "missing_fields_before_followup" in result["retrieved_knowledge"]["retrieval_summary"]
    assert "followup_search_used" in result["retrieved_knowledge"]["retrieval_summary"]
    assert result["image_assets"] == []
    assert result["agent_backends"]["research_agent"] == "deterministic_tool_orchestrator"
    print("\n✅ [时序校验通过]: research_node 已阻塞完成并成功回填 State。")


@pytest.mark.asyncio
@patch.dict(
    "app.agents.nodes.research_agent.TOOL_POOL",
    {
        "network_search": MagicMock(
            ainvoke=AsyncMock(side_effect=[
                "Mate 60 官方参数",
                "Mate 60 用户评价"
            ])
        )
    },
)
@patch("app.agents.nodes.research_agent.search_network_structured_async", new_callable=AsyncMock)
@patch("app.agents.nodes.research_agent.search_google_images", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.get_hot_knowledge", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.match_trends_in_text", new_callable=AsyncMock)
async def test_research_node_can_infer_asset_search_from_query_without_legacy_intent(mock_match_trends, mock_get_hot_knowledge, mock_search_google_images, mock_structured_search):
    mock_match_trends.return_value = []
    mock_get_hot_knowledge.return_value = None
    mock_search_google_images.return_value = ["https://img.example/mate60.jpg"]
    mock_structured_search.side_effect = [
        [{"title": "Mate 60 官方图文", "link": "https://example.com/official", "snippet": "核心参数"}],
        [{"title": "Mate 60 使用反馈", "link": "https://example.com/review", "snippet": "真实体验"}],
    ]

    from langchain_core.messages import HumanMessage
    result = await research_agent({
        "main_messages": [HumanMessage(content="帮我搜几张 Mate 60 实拍图")],
        "active_panel": "main",
        "retrieved_knowledge": None,
    })

    assert result["image_assets"] == [{"url": "https://img.example/mate60.jpg", "desc": "Mate 60 实拍图"}]
    assert result["retrieved_knowledge"]["retrieval_summary"]["image_count"] == 1
    assert result["retrieved_knowledge"]["retrieval_summary"]["asset_mode"] == "search"
    assert result["agent_backends"]["research_agent"] == "deterministic_tool_orchestrator"


@pytest.mark.asyncio
@patch.dict(
    "app.agents.nodes.research_agent.TOOL_POOL",
    {
        "network_search": MagicMock(
            ainvoke=AsyncMock(side_effect=[
                "Mate 60 官方参数：麒麟芯片，价格 5999",
                "Mate 60 用户体验：影像风格强，续航稳定"
            ])
        )
    },
)
@patch("app.agents.nodes.research_agent.search_network_structured_async", new_callable=AsyncMock)
@patch("app.agents.nodes.research_agent.search_google_images", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.get_hot_knowledge", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.match_trends_in_text", new_callable=AsyncMock)
async def test_research_node_uses_digital_retrieval_profile_for_seeding(
    mock_match_trends,
    mock_get_hot_knowledge,
    mock_search_google_images,
    mock_structured_search,
):
    mock_match_trends.return_value = []
    mock_get_hot_knowledge.return_value = None
    mock_search_google_images.return_value = []
    mock_structured_search.side_effect = [
        [{"title": "Mate 60 官方参数", "link": "https://consumer.huawei.com/mate60", "snippet": "价格 5999，影像升级"}],
        [{"title": "Mate 60 用户体验", "link": "https://example.com/review", "snippet": "续航稳定，影像风格强"}],
        [{"title": "Mate 60 芯片参数", "link": "https://consumer.huawei.com/mate60-chip", "snippet": "处理器为麒麟芯片"}],
        [{"title": "Mate 60 电池续航", "link": "https://consumer.huawei.com/mate60-battery", "snippet": "电池容量和续航表现稳定"}],
        [{"title": "Mate 60 屏幕参数", "link": "https://consumer.huawei.com/mate60-display", "snippet": "屏幕亮度与分辨率升级"}],
        [{"title": "Mate 60 相机参数", "link": "https://consumer.huawei.com/mate60-camera", "snippet": "影像系统升级"}],
        [{"title": "Mate 60 价格版本", "link": "https://consumer.huawei.com/mate60-price", "snippet": "官方售价 5999 起"}],
        [{"title": "Mate 60 充电参数", "link": "https://consumer.huawei.com/mate60-charge", "snippet": "支持 66W 快充"}],
    ]

    from langchain_core.messages import HumanMessage
    result = await research_agent({
        "main_messages": [HumanMessage(content="帮我做一篇华为 Mate 60 的数码测评")],
        "active_panel": "main",
        "active_archetype": "seeding",
        "retrieved_knowledge": None,
        "intent_result_v2": {"needs_assets": "none"},
    })

    summary = result["retrieved_knowledge"]["retrieval_summary"]
    assert summary["retrieval_profile"] == "digital_review"
    assert summary["retrieval_domain"] == "digital_review"
    assert len(summary["query_variants"]) == 7
    assert isinstance(summary["missing_fields"], list)
    assert summary["followup_search_used"] is True
    assert "fact_slots" in result["retrieved_knowledge"]
    assert "chipset" in result["retrieved_knowledge"]["fact_slots"]
    assert "battery" in result["retrieved_knowledge"]["fact_slots"]
    assert "price" in result["retrieved_knowledge"]["fact_slots"]
    assert "charging" in result["retrieved_knowledge"]["fact_slots"]


@pytest.mark.asyncio
@patch("app.services.trend_pipeline.research_agent", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.set_hot_knowledge", new_callable=AsyncMock)
async def test_trend_pipeline_preload_persists_retrieval_eval_and_records(mock_set_hot_knowledge, mock_research_agent):
    from app.services.trend_pipeline import TrendPipeline

    pipeline = TrendPipeline()
    mock_research_agent.return_value = {
        "retrieved_knowledge": {
            "entity_name": "Mate 60",
            "fact_sources": [
                {
                    "title": "华为官网 Mate 60",
                    "url": "https://consumer.huawei.com/cn/phones/mate-60/",
                    "snippet": "价格 6999",
                    "source_scope": "official",
                    "query": "Mate 60 核心参数 价格 官方",
                },
                {
                    "title": "用户评价合集",
                    "url": "https://www.bilibili.com/video/BV1xx",
                    "snippet": "影像强",
                    "source_scope": "review",
                    "query": "Mate 60 用户评价 真实体验",
                },
            ],
            "retrieval_hits": [
                {"scope": "official", "query": "Mate 60 核心参数 价格 官方", "count": 1, "titles": ["华为官网 Mate 60"]},
                {"scope": "review", "query": "Mate 60 用户评价 真实体验", "count": 1, "titles": ["用户评价合集"]},
            ],
            "retrieval_summary": {
                "strategy": "live_search_with_citations",
                "query": "Mate 60",
                "citation_count": 2,
                "freshness": "live",
                "grounding_status": "grounded",
            },
        }
    }

    await pipeline._pre_research_topic("Mate 60", deep_scan=True)

    mock_set_hot_knowledge.assert_awaited_once()
    payload = mock_set_hot_knowledge.await_args.args[1]
    assert payload["retrieval_summary"]["ingest_mode"] == "system_preload"
    assert payload["retrieval_summary"]["policy_name"] == "cache_then_live_grounded"
    assert payload["retrieval_summary"]["record_count"] == 2
    assert payload["retrieval_eval"]["citation_count"] == 2
    assert payload["retrieval_eval"]["source_quality"] in {"high", "medium"}
    assert len(payload["knowledge_records"]) == 2

# --- 🧪 Test Suite 3: 测试白盒探针 API ---

def test_glassbox_inspect_api():
    """验证前端能否顺利偷窥 Agent 脑电图"""
    test_thread_id = "test_case_001"
    mock_values = {
        "intent_route": "research_agent",
        "creator_persona": "硬核数码博主",
        "retrieved_knowledge": {"entity_name": "小米 17 Ultra", "summary": "热缓存命中"}
    }
    mock_snapshot = MagicMock()
    mock_snapshot.values = mock_values

    mock_agent = MagicMock()
    mock_agent.aget_state = AsyncMock(return_value=mock_snapshot)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(agent=mock_agent)))

    data = asyncio.run(inspect_agent_state(test_thread_id, request))

    assert data["status"] == "success"
    assert data["data"]["intent_route"] == "research_agent"
    assert data["data"]["creator_persona"] == "硬核数码博主"
    assert data["data"]["retrieved_knowledge"]["entity_name"] == "小米 17 Ultra"
    print("\n✅ [白盒探针通过]: FastAPI 成功透传 Agent 决策元数据。")


@pytest.mark.asyncio
async def test_cache_service_hot_knowledge_snapshot_tracks_ttl_and_expiry():
    cache = CacheService()
    await cache.set_hot_knowledge(" Mate 60 ", {"entity_name": "Mate 60"}, ttl=2)

    cached = await cache.get_hot_knowledge("mate 60")
    snapshot = await cache.get_hot_knowledge_snapshot("mate 60")

    assert cached["entity_name"] == "Mate 60"
    assert snapshot["cache_hit"] is True
    assert snapshot["cache_key"] == "mate 60"
    assert snapshot["ttl_seconds"] == 2
    assert snapshot["remaining_ttl_seconds"] <= 2

    cache._mock_hot_knowledge["mate 60"]["expires_at_ts"] = time.time() - 1
    expired = await cache.get_hot_knowledge("mate 60")
    expired_snapshot = await cache.get_hot_knowledge_snapshot("mate 60")

    assert expired is None
    assert expired_snapshot["cache_hit"] is False
    assert expired_snapshot["cache_freshness"] == "miss"

if __name__ == "__main__":
    # 方便直接运行
    asyncio.run(test_mock_db_retrieval())
    test_focused_knowledge_schema()
    print("Suite 1: OK")
