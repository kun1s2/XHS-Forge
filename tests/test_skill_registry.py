from app.services.knowledge_hub import build_knowledge_plan
from app.services.skill_registry import (
    build_skill_context,
    load_skill_markdown,
    load_skills_snapshot,
    recommend_skills_for_knowledge_plan,
    recommend_skills_for_role,
)


def test_skill_files_are_present_and_snapshot_is_readable():
    snapshot = load_skills_snapshot()
    assert "product-search" in snapshot
    assert "decision-note-compose" in snapshot
    assert "数码购买决策 Agent" in snapshot

    assert "product-search" in load_skill_markdown("product-search")
    assert "product-images" in load_skill_markdown("product-images")


def test_build_knowledge_plan_contains_recommended_skills_for_digital_purchase():
    state = {
        "main_messages": [{"content": "写一篇华为 Mate 60 值不值得买的测评，顺便补几张图片"}],
        "active_archetype": "seeding",
        "intent_decision": {
            "task_type": "create",
            "operation_type": "generate",
            "scope": "global_canvas",
            "needs_research": True,
            "needs_assets": True,
            "confidence": 0.92,
            "fallback_required": False,
        },
    }
    plan = build_knowledge_plan(state)

    assert plan["recommended_skills"]
    assert "product-search" in plan["recommended_skills"]
    assert "product-images" in plan["recommended_skills"]
    assert "decision-note-compose" in plan["recommended_skills"]


def test_recommend_skills_for_role_splits_retrieval_and_composition():
    intent = {
        "task_type": "edit",
        "operation_type": "asset_edit",
        "scope": "global_canvas",
        "needs_research": True,
        "needs_assets": True,
        "confidence": 0.95,
        "fallback_required": False,
    }
    knowledge_plan = {
        "required_fields": ["price", "battery", "camera"],
    }

    retrieval_skills = recommend_skills_for_role(
        role="retrieval_worker",
        intent_decision=intent,
        knowledge_plan=knowledge_plan,
    )
    composition_skills = recommend_skills_for_role(
        role="composition_worker",
        intent_decision=intent,
        knowledge_plan=knowledge_plan,
    )
    critique_skills = recommend_skills_for_role(
        role="critique_worker",
        intent_decision=intent,
        knowledge_plan=knowledge_plan,
    )

    assert "product-search" in retrieval_skills
    assert "product-images" in retrieval_skills
    assert "decision-note-compose" in composition_skills
    assert "product-images" in composition_skills
    assert critique_skills == ["decision-note-compose"]


def test_build_skill_context_returns_tool_plan_and_selected_skills():
    bundle = build_skill_context(
        role="retrieval_worker",
        intent_decision={
            "task_type": "ingest",
            "operation_type": "kb_import",
            "needs_assets": False,
        },
        knowledge_plan={"required_fields": ["price"]},
    )

    assert "spec-sheet-ingest" in bundle["selected_skills"]
    assert bundle["tool_plan"]
    assert any(item["skill"] == "spec-sheet-ingest" for item in bundle["tool_plan"])


def test_recommend_skills_for_knowledge_plan_defaults_to_product_search():
    selected = recommend_skills_for_knowledge_plan(intent_decision={}, knowledge_plan={})
    assert selected == ["product-search"]
