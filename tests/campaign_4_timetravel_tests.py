# 🧪 战役四：时空穿梭与幽灵数据防御 (Time-Travel & Ghost Data Tests)
import pytest
from AI_Frontend_IDE.app.agents.state import (
    merge_dsl,
    merge_patch_tracks,
    restore_component_version,
)


def test_patch_tracks_increment_on_new_field():
    """增量修改与快照生成：为 product_1 新增 tag 后，patch_tracks['product_1'] 长度 +1。"""
    state = {
        "data_dsl": {"product_1": {"type": "ProductCard", "title": "相机"}},
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
    """毒药补丁回滚：restore 返回的补丁含 tag: None，merge 后 data_dsl 中 tag 被物理删除，其他组件不受影响。"""
    # 当前状态：product_1 有 tag，text_1 有独立修改
    state = {
        "data_dsl": {
            "product_1": {"type": "ProductCard", "title": "相机", "tag": "2024 年度理财产品"},
            "text_1": {"type": "StoryText", "paragraphs": ["最新正文"]},
        },
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
    assert "data_dsl" in patch_result
    assert "product_1" in patch_result["data_dsl"]
    rollback = patch_result["data_dsl"]["product_1"]
    # 毒药补丁：当前有而快照没有的 key 应为 None
    assert rollback.get("tag") is None

    # 合并后全局 data_dsl
    merged_dsl = merge_dsl(state["data_dsl"], patch_result["data_dsl"])
    assert "tag" not in merged_dsl["product_1"]
    assert merged_dsl["product_1"]["title"] == "相机"
    # 其他组件不受影响
    assert merged_dsl["text_1"]["paragraphs"] == ["最新正文"]
