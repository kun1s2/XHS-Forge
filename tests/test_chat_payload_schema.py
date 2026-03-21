from app.schemas.requests import ChatWSPayload


def test_chat_ws_payload_accepts_structured_current_assets():
    payload = ChatWSPayload.model_validate(
        {
            "content": "帮我继续编辑",
            "panel": "main",
            "current_assets": [
                {
                    "url": "https://example.com/a.jpg",
                    "desc": "封面图",
                    "role": "cover",
                    "locked": False,
                    "used_by_blocks": ["cover_1"],
                    "selection_state": "selected",
                },
                {
                    "url": "https://example.com/b.jpg",
                    "desc": "补充图",
                    "used_by_blocks": [],
                    "locked": False,
                },
            ],
        }
    )

    assert payload.current_assets is not None
    assert payload.current_assets[0]["locked"] is False
    assert payload.current_assets[0]["used_by_blocks"] == ["cover_1"]
