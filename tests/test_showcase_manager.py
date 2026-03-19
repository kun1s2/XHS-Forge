from app.services.showcase_manager import showcase_manager


def test_showcase_profiles_cover_three_job_story_tracks():
    profiles = showcase_manager.list_profiles()
    ids = [profile["id"] for profile in profiles]
    scenario_ids = [profile["scenario_id"] for profile in profiles]
    personas = [profile["persona"] for profile in profiles]

    assert ids == ["digital_review", "travel_explore", "daily_share"]
    assert scenario_ids == ["seeding", "travel", "daily_share"]
    assert personas == ["硬核数码博主", "温柔探店达人", "深夜感性诗人"]
    assert all(profile["starter_prompt"] for profile in profiles)
    assert all(profile["talking_points"] for profile in profiles)
    assert all(len(profile["demo_script"]) == 4 for profile in profiles)
    assert all(profile["demo_script"][0]["action"] == "start" for profile in profiles)
