from app.agents.nodes.component_builder import build_component_fallback


def test_xiaomi_latest_phone_regression_uses_grounded_future_fact_without_old_models():
    """
    当前架构下的防幻觉回归：当 research/distill 已明确提供未来机型事实时，
    fallback 生成不应回退到旧型号记忆。
    """

    payload = build_component_fallback(
        comp_type="StoryText",
        comp_id="story_1",
        content_brief="小米 17 Ultra 相机总结",
        user_query="写一篇最新的小米手机测评，重点说说相机",
        retrieved_knowledge={
            "entity_name": "小米 17 Ultra",
            "summary": "小米 17 Ultra 正式发布，核心卖点是 1.5 英寸超大底主摄。",
            "key_selling_points": ["1.5 英寸超大底主摄", "4K 四等深微曲屏", "6500mAh 金沙江电池"],
            "known_issues": [],
            "text_facts": "小米 17 Ultra / 1.5 英寸超大底主摄 / 6500mAh 金沙江电池",
        },
        image_assets=[],
    )

    final_content = "\n".join(payload.get("paragraphs") or [])

    assert "17 Ultra" in final_content
    assert "1.5" in final_content
    for old_model in ["12 Pro", "13 Pro", "14 Pro"]:
        assert old_model not in final_content
