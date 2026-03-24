"""Skill registry for the digital purchase agent workbench.

Skills are file-backed task recipes. They do not replace tool
implementations or LangGraph orchestration; they only make the agent's
tool-usage rules explicit, inspectable, and traceable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
SKILLS_SNAPSHOT_PATH = SKILLS_ROOT / "SKILLS_SNAPSHOT.md"


@dataclass(frozen=True)
class SkillSpec:
    name: str
    path: Path
    summary: str
    role_targets: tuple[str, ...]
    tool_hints: tuple[str, ...]
    fallback: str


SKILL_SPECS: dict[str, SkillSpec] = {
    "product-search": SkillSpec(
        name="product-search",
        path=SKILLS_ROOT / "product-search" / "SKILL.md",
        summary="查询数码产品参数、价格、竞品证据，优先结构化知识，再补混合检索。",
        role_targets=("retrieval_worker",),
        tool_hints=("query_structured_knowledge", "retrieve_knowledge_hits", "network_search"),
        fallback="如果结构化命中不足，就补混合检索并把结果写成候选知识；仍不足时要求用户补资料。",
    ),
    "product-images": SkillSpec(
        name="product-images",
        path=SKILLS_ROOT / "product-images" / "SKILL.md",
        summary="判断当前档案是否缺图，补搜图片并回填图片区块或资产。",
        role_targets=("retrieval_worker", "composition_worker"),
        tool_hints=("inspect_note_state", "google_images", "update_note_block"),
        fallback="如果搜图失败，明确说明未补图成功，并建议上传资料或继续搜图。",
    ),
    "spec-sheet-ingest": SkillSpec(
        name="spec-sheet-ingest",
        path=SKILLS_ROOT / "spec-sheet-ingest" / "SKILL.md",
        summary="导入参数表/产品资料包，切块、抽候选知识并送入会话审查流。",
        role_targets=("retrieval_worker",),
        tool_hints=("ingest_user_material", "index_chunks", "extract_candidate_records"),
        fallback="如果解析失败，返回可见失败原因和建议的替代输入格式。",
    ),
    "decision-note-compose": SkillSpec(
        name="decision-note-compose",
        path=SKILLS_ROOT / "decision-note-compose" / "SKILL.md",
        summary="把已审知识组织成数码购买决策档案：结论、事实、对比、风险和图片。",
        role_targets=("composition_worker", "critique_worker"),
        tool_hints=("inspect_note_state", "inspect_component_state", "composition_service"),
        fallback="如果这轮没有实际改动，返回显式失败反馈并指出缺少的知识或块级目标。",
    ),
}


def list_skill_specs() -> list[SkillSpec]:
    return list(SKILL_SPECS.values())


def load_skills_snapshot() -> str:
    if not SKILLS_SNAPSHOT_PATH.exists():
        return ""
    return SKILLS_SNAPSHOT_PATH.read_text(encoding="utf-8").strip()


def load_skill_markdown(name: str) -> str:
    spec = SKILL_SPECS.get(str(name or "").strip())
    if not spec or not spec.path.exists():
        return ""
    return spec.path.read_text(encoding="utf-8").strip()


def _normalize_intent(intent_decision: dict[str, Any] | None) -> dict[str, Any]:
    return intent_decision if isinstance(intent_decision, dict) else {}


def recommend_skills_for_knowledge_plan(
    *,
    intent_decision: dict[str, Any] | None,
    knowledge_plan: dict[str, Any] | None,
) -> list[str]:
    intent = _normalize_intent(intent_decision)
    plan = knowledge_plan if isinstance(knowledge_plan, dict) else {}
    task_type = str(intent.get("task_type") or "").lower()
    operation_type = str(intent.get("operation_type") or "").lower()
    needs_assets = bool(intent.get("needs_assets"))
    required_fields = [str(item) for item in (plan.get("required_fields") or []) if str(item).strip()]

    selected: list[str] = []
    if operation_type == "kb_import" or task_type == "ingest":
        selected.append("spec-sheet-ingest")
    if needs_assets or operation_type == "asset_edit":
        selected.append("product-images")
    if required_fields or task_type in {"create", "edit", "review"}:
        selected.append("product-search")
    if task_type in {"create", "edit"} or operation_type in {"text_edit", "layout_edit", "generate"}:
        selected.append("decision-note-compose")
    if not selected:
        selected.append("product-search")
    return _dedupe_preserve_order(selected)


def recommend_skills_for_role(
    *,
    role: str,
    intent_decision: dict[str, Any] | None,
    knowledge_plan: dict[str, Any] | None,
) -> list[str]:
    recommended = recommend_skills_for_knowledge_plan(
        intent_decision=intent_decision,
        knowledge_plan=knowledge_plan,
    )
    role_name = str(role or "").strip()
    if not role_name:
        return recommended
    selected = [
        name
        for name in recommended
        if role_name in (SKILL_SPECS.get(name).role_targets if SKILL_SPECS.get(name) else ())
    ]
    if role_name == "critique_worker" and "decision-note-compose" not in selected:
        selected.append("decision-note-compose")
    if role_name == "retrieval_worker" and not selected:
        selected.append("product-search")
    if role_name == "supervisor_agent" and not selected:
        return recommended
    return _dedupe_preserve_order(selected)


def build_skill_context(
    *,
    role: str,
    intent_decision: dict[str, Any] | None,
    knowledge_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    selected_skills = recommend_skills_for_role(
        role=role,
        intent_decision=intent_decision,
        knowledge_plan=knowledge_plan,
    )
    selected_docs = {name: load_skill_markdown(name) for name in selected_skills}
    tool_plan = [
        {
            "skill": name,
            "summary": SKILL_SPECS[name].summary,
            "tool_hints": list(SKILL_SPECS[name].tool_hints),
            "fallback": SKILL_SPECS[name].fallback,
        }
        for name in selected_skills
        if name in SKILL_SPECS
    ]
    return {
        "snapshot": load_skills_snapshot(),
        "selected_skills": selected_skills,
        "skill_documents": selected_docs,
        "tool_plan": tool_plan,
    }


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
