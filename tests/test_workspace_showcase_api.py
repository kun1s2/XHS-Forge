import asyncio

from app.api.workspace import get_showcase_profiles


def test_workspace_showcase_profiles_endpoint_returns_curated_tracks():
    payload = asyncio.run(get_showcase_profiles())
    profiles = payload["profiles"]

    assert [profile["id"] for profile in profiles] == ["digital_purchase_decision"]
    assert profiles[0]["scenario_id"] == "seeding"
    assert profiles[0]["persona"] == "硬核数码决策顾问"
    assert profiles[0]["demo_script"][0]["action"] == "start"
    assert len(profiles[0]["talking_points"]) == 3
