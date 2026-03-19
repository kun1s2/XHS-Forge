from scripts.ws_probe import _find_block_count, _find_story_block, _find_target_block, _list_component_types


def test_find_target_block_prefers_requested_component_type():
    page = {
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock"},
            {"id": "poll_1", "component_type": "PollBlock"},
            {"id": "story_1", "component_type": "StoryText"},
        ]
    }

    assert _find_target_block(page, "PollBlock") == "poll_1"
    assert _find_target_block(page, "StoryText") == "story_1"


def test_find_story_block_returns_story_text_block():
    page = {
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock"},
            {"id": "story_1", "component_type": "StoryText"},
        ]
    }

    assert _find_story_block(page) == "story_1"


def test_find_block_count_returns_number_of_blocks():
    page = {
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock"},
            {"id": "story_1", "component_type": "StoryText"},
        ]
    }

    assert _find_block_count(page) == 2


def test_list_component_types_returns_component_order():
    page = {
        "blocks": [
            {"id": "title_1", "component_type": "TitleBlock"},
            {"id": "poll_1", "component_type": "PollBlock"},
        ]
    }

    assert _list_component_types(page) == ["TitleBlock", "PollBlock"]
