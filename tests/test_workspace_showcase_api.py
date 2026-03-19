from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.workspace import router as workspace_router


def test_workspace_showcase_profiles_endpoint_returns_curated_tracks():
    app = FastAPI()
    app.include_router(workspace_router)

    with TestClient(app) as client:
        response = client.get("/workspace/showcase/profiles")

    assert response.status_code == 200
    payload = response.json()
    profiles = payload["profiles"]

    assert [profile["id"] for profile in profiles] == ["digital_review", "travel_explore", "daily_share"]
    assert profiles[0]["scenario_id"] == "seeding"
    assert profiles[0]["persona"] == "硬核数码博主"
    assert profiles[0]["demo_script"][0]["action"] == "start"
    assert len(profiles[1]["talking_points"]) == 3
    assert profiles[2]["scenario_id"] == "daily_share"
