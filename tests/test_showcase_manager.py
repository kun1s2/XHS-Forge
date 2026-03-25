from app.services.showcase_manager import showcase_manager


def test_showcase_profiles_cover_two_formal_story_tracks():
    profiles = showcase_manager.list_profiles()
    ids = [profile["id"] for profile in profiles]
    scenario_ids = [profile["scenario_id"] for profile in profiles]
    personas = [profile["persona"] for profile in profiles]

    assert ids == ["persistent_notes_workspace"]
    assert scenario_ids == ["notes"]
    assert personas == ["笔记共创搭档"]
    assert all(profile["starter_prompt"] for profile in profiles)
    assert all(profile["talking_points"] for profile in profiles)
    assert all(len(profile["demo_script"]) == 4 for profile in profiles)
    assert all(profile["demo_script"][0]["action"] == "start" for profile in profiles)

