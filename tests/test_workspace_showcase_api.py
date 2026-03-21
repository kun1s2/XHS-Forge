import asyncio

from app.api.workspace import get_showcase_profiles


def test_workspace_showcase_profiles_endpoint_returns_curated_tracks():
    payload = asyncio.run(get_showcase_profiles())
    profiles = payload["profiles"]

    assert [profile["id"] for profile in profiles] == ["digital_review", "travel_explore", "daily_share"]
    assert profiles[0]["scenario_id"] == "seeding"
    assert profiles[0]["persona"] == "硬核数码博主"
    assert profiles[0]["demo_script"][0]["action"] == "start"
    assert len(profiles[1]["talking_points"]) == 3
    assert profiles[2]["scenario_id"] == "daily_share"
