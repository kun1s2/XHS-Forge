import pytest
from unittest.mock import AsyncMock, patch

from app.services.trend_pipeline import TrendPipeline
from app.services.cache_service import CacheService


@pytest.mark.asyncio
async def test_trend_pipeline_primes_research_with_intent_decision():
    pipeline = TrendPipeline()

    with patch("app.services.trend_pipeline.research_service", new_callable=AsyncMock) as mock_research:
        mock_research.return_value = {"retrieved_knowledge": {"entity_name": "Mate 60"}}
        with patch("app.services.cache_service.cache_service.set_hot_knowledge", new_callable=AsyncMock) as mock_set:
            await pipeline._pre_research_topic("Mate 60", deep_scan=True)

    mock_research.assert_awaited_once()
    state = mock_research.await_args.args[0]
    assert state["intent_decision"]["needs_assets"] is True
    assert state["intent_decision"]["needs_research"] is True
    assert state["active_archetype"] == "seeding"
    assert state["scenarios"] == ["seeding"]
    mock_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_cache_service_returns_structured_trend_items_without_hardcoded_fallback():
    cache = CacheService()
    cache._get_redis = AsyncMock(return_value=None)
    items = await cache.get_top_trend_items(limit=5)
    assert items == []

    await cache.update_trend_rank("华为 Mate 60", score_increment=3.0, scenario_hint="seeding", source="user_query")
    items = await cache.get_top_trend_items(limit=5)

    assert len(items) == 1
    assert items[0]["keyword"] == "华为 Mate 60"
    assert items[0]["scenario_hint"] == "seeding"
    assert items[0]["recommended_prompt"]
