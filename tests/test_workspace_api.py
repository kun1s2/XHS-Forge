from datetime import datetime

from app.schemas.responses import WorkspaceDataResponse
from langchain_core.messages import HumanMessage

from app.api.workspace import _extract_session_title, _format_checkpoint_timestamp, _pick_row_value, dedupe_assets, format_messages


def test_format_checkpoint_timestamp_accepts_datetime():
    value = datetime(2026, 3, 19, 18, 0, 0)
    assert _format_checkpoint_timestamp(value) == "2026-03-19T18:00:00"


def test_format_checkpoint_timestamp_accepts_string():
    value = "2026-03-19T18:00:00+08:00"
    assert _format_checkpoint_timestamp(value) == value


def test_workspace_data_response_accepts_structured_messages_and_prompts():
    response = WorkspaceDataResponse(
        is_new=False,
        messages={
            "main": [
                {"role": "user", "content": "帮我生成一篇 Mate 60 笔记"},
                {"role": "assistant", "content": "已完成页面更新"},
            ]
        },
        active_panel="main",
        selected_element_id=None,
        data_dsl={"page_title": "Mate 60 页面", "blocks": []},
        style_dsl={"global_vars": {"--bg-color": "#fff"}},
        image_assets=[{"url": "https://img.example/1.jpg", "desc": "封面图", "source_type": "search"}],
        node_prompts={"intent_agent": [{"role": "system", "content": "prompt"}]},
        oss_url=None,
        source_code="<html></html>",
        checkpoints=[],
    )

    assert response.messages["main"][0]["role"] == "user"
    assert response.node_prompts["intent_agent"][0]["role"] == "system"
    assert response.image_assets[0]["source_type"] == "search"


def test_format_messages_flattens_multimodal_human_message():
    formatted = format_messages([
        HumanMessage(content=[
            {"type": "text", "text": "帮我生成一篇 Mate 60 笔记"},
            {"type": "image_url", "image_url": {"url": "https://img.example/1.jpg"}},
        ])
    ])

    assert formatted[0]["role"] == "user"
    assert formatted[0]["content"] == "帮我生成一篇 Mate 60 笔记"
    assert formatted[0]["imageUrls"] == ["https://img.example/1.jpg"]


def test_dedupe_assets_merges_same_url_entries():
    deduped = dedupe_assets([
        {"url": "https://img.example/1.jpg", "desc": "A", "source_type": "search"},
        {"url": "https://img.example/1.jpg", "query": "Mate 60"},
    ])

    assert len(deduped) == 1
    assert deduped[0]["desc"] == "A"
    assert deduped[0]["query"] == "Mate 60"


def test_extract_session_title_prefers_first_human_message():
    title = _extract_session_title(
        {
            "main_messages": [
                HumanMessage(content="帮我生成一篇关于华为 Mate 60 的对比种草笔记"),
            ]
        },
        "thread_12345678",
    )

    assert title.startswith("帮我生成一篇关于华为 Mate 60")


def test_extract_session_title_falls_back_to_page_title():
    title = _extract_session_title(
        {
            "data_dsl": {
                "page_title": "华为 Mate 60 高能种草页"
            }
        },
        "thread_12345678",
    )

    assert title == "华为 Mate 60 高能种草页"


def test_pick_row_value_supports_dict_row():
    row = {"thread_id": "thread_abc"}
    assert _pick_row_value(row, "thread_id", 0) == "thread_abc"
