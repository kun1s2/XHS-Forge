# 🧪 战役四：时空穿梭与幽灵数据防御 (Time-Travel & Ghost Data Tests)
import pytest
from AI_Frontend_IDE.app.agents.state import (
    merge_state_patch,
    merge_patch_tracks,
    restore_component_version,
)
from AI_Frontend_IDE.app.core.note_document import build_note_document


def test_patch_tracks_increment_on_new_field():
    """增量修改与快照生成：为 product_1 新增 tag 后，patch_tracks['product_1'] 长度 +1。"""
    state = {
        "document_view": {"product_1": {"type": "ProductCard", "title": "相机"}},
        "patch_tracks": {"product_1": []},
    }
    new_track = {
        "timestamp": "2024-01-01T12:00:00",
        "prompt": "加 tag",
        "data_snapshot": {"type": "ProductCard", "title": "相机", "tag": "2024 年度理财产品"},
        "agent_thought": "已添加 tag",
    }
    updated = merge_patch_tracks(state["patch_tracks"], {"product_1": [new_track]})
    assert len(updated["product_1"]) == 1
    assert updated["product_1"][0]["data_snapshot"].get("tag") == "2024 年度理财产品"


def test_restore_component_version_tombstone_and_ghost_removal():
    """毒药补丁回滚：restore 返回 note_document 补丁，回滚后目标块恢复历史快照且不污染其他块。"""
    # 当前状态：product_1 有 tag，text_1 有独立修改
    state = {
        "note_document": build_note_document(
            document_view={
                "blocks": [
                    {"id": "product_1", "component_type": "ProductCard", "content_brief": ""},
                    {"id": "text_1", "component_type": "StoryText", "content_brief": ""},
                ],
                "product_1": {"type": "ProductCard", "title": "相机", "tag": "2024 年度理财产品"},
                "text_1": {"type": "StoryText", "paragraphs": ["最新正文"]},
            },
            block_style_map={},
        ),
        "patch_tracks": {
            "product_1": [
                {
                    "timestamp": "2024-01-01T11:00:00",
                    "data_snapshot": {"type": "ProductCard", "title": "相机"},
                    "agent_thought": "旧版本无 tag",
                }
            ],
        },
    }

    patch_result = restore_component_version(state, "product_1", 0)
    assert "note_document" in patch_result

    merged_document = merge_state_patch(state["note_document"], patch_result["note_document"])
    product_block = next(block for block in merged_document["blocks"] if block["id"] == "product_1")
    text_block = next(block for block in merged_document["blocks"] if block["id"] == "text_1")
    assert "tag" not in product_block["props"]
    assert product_block["props"]["title"] == "相机"
    assert text_block["props"]["paragraphs"] == ["最新正文"]
