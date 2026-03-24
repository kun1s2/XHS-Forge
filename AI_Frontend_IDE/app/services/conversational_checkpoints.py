"""聊天流内的高频协作 checkpoint 辅助模块。

这里集中管理 agent 主动向用户发起的结构化协作卡：
- 结构协商
- 事实缺口
- 素材决策
- 事实冲突

这些卡片只负责“该问什么”和“用户选了以后怎么落状态”，
真正的图中断/恢复由节点里的 `interrupt()` 负责。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agents.state import UIProjectState
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import (
    apply_confirmed_facts_to_knowledge,
    merge_confirmed_fact_selection,
    normalize_confirmed_facts,
)
from app.core.component_manifest import (
    resolve_component_candidates_for_block_intent,
    resolve_component_for_block_intent,
)
from app.core.request_semantics import latest_user_text_from_messages, state_requests_create
from app.core.truth_safety import (
    has_user_provided_facts,
    normalize_user_provided_facts,
    query_requests_truth_mode,
)
from app.services.knowledge_hub import (
    apply_knowledge_review_decision,
    group_records,
)
from app.services.retrieval_profiles import (
    compute_missing_slot_keys,
    infer_retrieval_profile,
)


def _user_query(state: UIProjectState) -> str:
    return latest_user_text_from_messages(state.get("main_messages", []) or [])


def _entity_name(state: UIProjectState) -> str:
    knowledge = state.get("retrieved_knowledge") or {}
    return normalize_entity_name((knowledge or {}).get("entity_name") or _user_query(state))


def _safe_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """剔除前端不该直接看到的内部字段。"""
    cleaned: list[dict[str, Any]] = []
    for item in options:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "label": str(item.get("label") or ""),
                "value": str(item.get("value") or ""),
                "description": str(item.get("description") or ""),
                "recommended": bool(item.get("recommended")),
                "asset_url": str(item.get("asset_url") or "") or None,
                "selected_asset_ids": list(item.get("selected_asset_ids") or []),
                "selected_fact_value": str(item.get("selected_fact_value") or "") or None,
                "metadata": deepcopy(item.get("metadata") or {}),
            }
        )
    return cleaned


def _append_custom_note(trace_payload: dict[str, Any], *, note: str | None) -> dict[str, Any]:
    normalized_note = str(note or "").strip()
    if not normalized_note:
        return trace_payload
    next_payload = deepcopy(trace_payload)
    checkpoints = next_payload.setdefault("conversation_checkpoints", {})
    if isinstance(checkpoints, dict):
        for value in checkpoints.values():
            if isinstance(value, dict):
                value["custom_note"] = normalized_note
    return next_payload


def _truth_mode_query_signature(state: UIProjectState) -> str:
    return _user_query(state).strip()


def _truth_mode_progress(state: UIProjectState) -> dict[str, Any]:
    progress = state.get("checkpoint_progress") or {}
    if not isinstance(progress, dict):
        return {}
    return dict(progress.get("truth_mode") or {})


def _truth_mode_kind(state: UIProjectState) -> str:
    query = _user_query(state)
    if any(token in query for token in ["原话", "我的原话", "引用"]):
        return "quote_capture"
    if any(token in query for token in ["几点几分", "几点到", "几分到", "精确时间"]):
        return "precise_schedule"
    if any(token in query for token in ["打卡", "现场记录"]):
        return "real_checkin"
    return "generic_truth"


def _truth_mode_title(kind: str) -> str:
    if kind == "quote_capture":
        return "这类表达像真实原话，我先和你确认一下"
    if kind == "precise_schedule":
        return "你要写到具体时间，我先确认你手里有没有这些信息"
    if kind == "real_checkin":
        return "这类内容会像真实打卡记录，我先和你对齐一下"
    return "这类表达更像真实记录，我先和你确认一下"


def _truth_mode_summary(kind: str) -> str:
    if kind == "quote_capture":
        return "如果你想保留真实原话或说话人口吻，请先补关键上下文；否则我会默认写成摘要版，避免看起来像伪造引用。"
    if kind == "precise_schedule":
        return "如果你想写到几点几分，请先补真实时间节点；否则我会默认按推荐顺序或时间段来写。"
    if kind == "real_checkin":
        return "如果你想写成真实打卡，请先补地点、时间和真实感受；否则我会按推荐打卡版来写。"
    return "如果你想写成真实经历/原话/精确时间，请先补关键事实；否则我会默认按推荐版或已确认事实来写，避免看起来像编造。"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = str(item or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _truth_location_candidates(state: UIProjectState) -> list[dict[str, Any]]:
    query = _user_query(state)
    entity = _entity_name(state)
    candidates = [entity]
    for token in ["沙滩", "海边", "餐厅", "酒店", "景区", "码头", "咖啡店", "商场", "夜市", "观景台"]:
        if token in query:
            candidates.append(token)
    options = _dedupe_preserve_order(candidates)[:5]
    return [{"label": item, "value": item, "recommended": idx == 0} for idx, item in enumerate(options) if item]


def _truth_focus_options(kind: str, active: str) -> list[dict[str, Any]]:
    if kind == "real_checkin":
        labels = ["开箱场景", "使用环境", "连续体验", "对比对象", "购买动机", "真实感受"]
    elif kind == "quote_capture":
        labels = ["保留原话语气", "只保留原意", "允许轻微润色", "强调情绪感"]
    elif kind == "precise_schedule":
        labels = ["出发时间", "到达时间", "中间节点", "用餐时间", "返程时间"]
    else:
        labels = ["关键时间", "关键地点", "真实经过", "一句原话"]
    return [{"label": label, "value": label} for label in labels]


def _truth_form_fields(state: UIProjectState, kind: str) -> list[dict[str, Any]]:
    active = str(state.get("active_archetype") or "seeding")
    if kind == "quote_capture":
        return [
            {
                "id": "speaker_role",
                "label": "这句原话是谁说的",
                "type": "single_select",
                "options": [
                    {"label": "我自己", "value": "我自己", "recommended": True},
                    {"label": "同行的人", "value": "同行的人"},
                    {"label": "工作人员", "value": "工作人员"},
                    {"label": "其他", "value": "其他"},
                ],
                "allow_custom": True,
                "custom_placeholder": "如果不是上面这些，可以补充具体是谁",
            },
            {
                "id": "quote_style",
                "label": "这句原话你想怎么保留",
                "type": "single_select",
                "options": [
                    {"label": "尽量原样保留", "value": "原样保留", "recommended": True},
                    {"label": "允许轻微润色", "value": "轻微润色"},
                    {"label": "只保留意思", "value": "只保留意思"},
                ],
            },
            {
                "id": "quote_context",
                "label": "原话内容",
                "placeholder": "例如：我当时说“风大但特别舒服”",
                "type": "textarea",
            },
            {
                "id": "event_context",
                "label": "发生在什么场景",
                "placeholder": "例如：在海边散步时、刚到酒店时、点完菜后",
                "type": "textarea",
            },
        ]

    if kind == "precise_schedule":
        return [
            {
                "id": "time_precision",
                "label": "你能提供到什么粒度",
                "type": "single_select",
                "options": [
                    {"label": "只到上午/中午/下午", "value": "时间段", "recommended": True},
                    {"label": "大概几点", "value": "大概时间"},
                    {"label": "具体到几点几分", "value": "精确分钟"},
                ],
            },
            {
                "id": "schedule_slots",
                "label": "你手里有哪几个时间节点",
                "type": "multi_select",
                "options": _truth_focus_options(kind, active),
                "allow_custom": True,
                "custom_placeholder": "如果还有别的时间节点，可以补充",
            },
            {
                "id": "time_context",
                "label": "时间信息",
                "placeholder": "例如：上午看参数，中午去线下店摸机，晚上决定是否下单",
                "type": "textarea",
            },
            {
                "id": "location_context",
                "label": "关键场景顺序",
                "placeholder": "例如：先看参数，再对比竞品，最后结合预算做决定",
                "type": "textarea",
            },
        ]

    if kind == "real_checkin":
        return [
            {
                "id": "time_precision",
                "label": "这次更适合写成哪种时间粒度",
                "type": "single_select",
                "options": [
                    {"label": "只写时间段，更自然", "value": "时间段", "recommended": True},
                    {"label": "我能提供大概时间", "value": "大概时间"},
                    {"label": "我能提供具体时间", "value": "精确时间"},
                ],
            },
            {
                "id": "visited_spots",
                "label": "你真实体验过哪些场景",
                "type": "multi_select",
                "options": _truth_location_candidates(state),
                "allow_custom": True,
                "custom_placeholder": "如果候选里没有，补充真实使用或体验场景",
            },
            {
                "id": "focus_points",
                "label": "这次更想突出哪些内容",
                "type": "multi_select",
                "options": _truth_focus_options(kind, active),
                "allow_custom": True,
                "custom_placeholder": "如果还有别的重点，可以补充",
            },
            {
                "id": "event_context",
                "label": "真实经过",
                "placeholder": kind == "real_checkin" and "例如：先在海边拍照，后来去吃饭，傍晚看日落"
                  or "例如：上午先去沙滩散步，中午吃饭，下午去了观景台",
                "type": "textarea",
            },
            {
                "id": "quote_context",
                "label": "原话或瞬间感受",
                "placeholder": "例如：我当时觉得“风很大但特别舒服”",
                "type": "textarea",
            },
        ]

    return [
        {
            "id": "fact_focuses",
            "label": "你现在手里有哪些真实信息",
            "type": "multi_select",
            "options": _truth_focus_options(kind, active),
            "allow_custom": True,
            "custom_placeholder": "如果还有别的真实信息，可以补充",
        },
        {
            "id": "time_context",
            "label": "时间",
            "placeholder": "例如：上午9点到，下午3点离开",
            "type": "textarea",
        },
        {
            "id": "location_context",
            "label": "地点",
            "placeholder": "例如：先去主景点，再去餐厅",
            "type": "textarea",
        },
        {
            "id": "event_context",
            "label": "真实经过",
            "placeholder": "例如：发生了什么、你最想保留什么",
            "type": "textarea",
        },
    ]


def build_truth_mode_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    if not state_requests_create(state):
        return None
    query = _truth_mode_query_signature(state)
    if not query_requests_truth_mode(query):
        return None
    progress = _truth_mode_progress(state)
    if progress.get("resolved") and str(progress.get("query") or "") == query:
        return None
    if has_user_provided_facts(state.get("user_provided_facts")):
        return None
    kind = _truth_mode_kind(state)
    active = str(state.get("active_archetype") or "seeding")
    helper_text = {
        "quote_capture": "先选清楚你想保留的是原话、语气，还是只保留意思；不确定的项可以留空。",
        "precise_schedule": "先勾你手里真的有的时间节点；如果没有具体分钟，也可以只选时间段。",
        "real_checkin": "先勾真实去过的点位和重点，再补几句真实经过；没有的项可以留空。",
    }.get(kind, "先勾你手里真正有把握的信息，再补充文字；不确定的项可以留空。")
    provide_label = {
        "quote_capture": "我来补原话和场景",
        "precise_schedule": "我来补真实时间",
        "real_checkin": "我来补真实打卡信息",
    }.get(kind, "我来补关键信息")
    provide_description = {
        "quote_capture": "你补说话人、原话和场景，我再按真实引用或摘要整理。",
        "precise_schedule": "你补真实时间节点和地点顺序，我再按更真实的行程来整理。",
        "real_checkin": "你补地点、时间和真实感受，我再按真实打卡版整理。",
    }.get(kind, "你补真实时间、地点、经过或原话，我再按真实经历来整理。")
    return {
        "action_type": "truth_mode_checkpoint",
        "checkpoint_id": "truth-mode::representation",
        "title": _truth_mode_title(kind),
        "summary": _truth_mode_summary(kind),
        "proposal_summary": "我建议先确认你想要的是推荐版、已确认事实版，还是基于你自己的真实经历来写。",
        "recommended_reason": "这类表达很容易被读成真实记录，我先把写法边界和你的可用信息对齐，能明显降低误解风险。",
        "other_allowed": True,
        "other_placeholder": "如果你想补充别的约束或说明，可以写在这里",
        "input_schema": {
            "submit_label": "按这些真实信息继续",
            "helper_text": helper_text,
            "fields": _truth_form_fields(state, kind),
        },
        "recommended_option": "recommended",
        "blocking": True,
        "options": _safe_options(
            [
                {
                    "label": provide_label,
                    "value": "provide_user_facts",
                    "description": provide_description,
                    "metadata": {"truth_mode_kind": kind, "active_archetype": active},
                },
                {
                    "label": "按推荐版本写",
                    "value": "recommended",
                    "description": "默认写成推荐路线/摘要版本，不伪装成真实日志。",
                    "recommended": True,
                    "metadata": {"truth_mode_kind": kind, "active_archetype": active},
                },
                {
                    "label": "只按已确认事实写",
                    "value": "confirmed_only",
                    "description": "只沿用已确认事实，宁可保守，也不扩写成像真实记录。",
                    "metadata": {"truth_mode_kind": kind, "active_archetype": active},
                },
            ]
        ),
    }


def apply_truth_mode_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    query = _truth_mode_query_signature(state)
    user_provided_payload = normalize_user_provided_facts((decision or {}).get("user_provided_facts")) if isinstance(decision, dict) else {}
    has_inline_user_facts = has_user_provided_facts(user_provided_payload)
    custom_note = str((decision or {}).get("custom_note") or "").strip() if isinstance(decision, dict) else ""
    representation_preferences = deepcopy(state.get("representation_preferences") or {})
    checkpoint_progress = deepcopy(state.get("checkpoint_progress") or {})
    truth_mode_progress = dict(checkpoint_progress.get("truth_mode") or {})
    truth_mode_progress["query"] = query
    truth_mode_progress["resolved"] = True
    truth_mode_progress["selected"] = decision_value or "recommended"
    truth_mode_progress["awaiting_user_facts"] = decision_value == "provide_user_facts" and not has_inline_user_facts
    checkpoint_progress["truth_mode"] = truth_mode_progress

    if decision_value == "provide_user_facts" and not has_inline_user_facts:
        return {
            "checkpoint_progress": checkpoint_progress,
            "representation_preferences": representation_preferences,
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "truth_mode": {"resolved": True, "selected": "provide_user_facts"}
                }
            }, note=custom_note),
        }

    representation_preferences.update(
        {
            "timeline": "user_provided" if has_inline_user_facts else ("confirmed" if decision_value == "confirmed_only" else "recommended"),
            "location": "user_provided" if has_inline_user_facts else ("confirmed" if decision_value == "confirmed_only" else "recommended"),
            "snapshot": "user_provided" if has_inline_user_facts else ("confirmed_snapshot" if decision_value == "confirmed_only" else "ambience"),
            "quote": "user_quote" if has_inline_user_facts else ("source_quote" if decision_value == "confirmed_only" else "summary"),
            "spec_card": (
                "purchase_judgment"
                if str(state.get("active_archetype") or "") == "seeding"
                else "neutral_facts"
            ),
            "radar": "judgment_summary",
        }
    )
    result = {
        "checkpoint_progress": checkpoint_progress,
        "representation_preferences": representation_preferences,
        "turn_trace": _append_custom_note({
            "conversation_checkpoints": {
                "truth_mode": {
                    "resolved": True,
                    "selected": decision_value or "recommended",
                    "used_inline_user_facts": has_inline_user_facts,
                }
            }
        }, note=custom_note),
    }
    if has_inline_user_facts:
        result["user_provided_facts"] = user_provided_payload
    if decision_value == "confirmed_only":
        confirmed_result = apply_confirmed_only_strategy(state)
        if confirmed_result.get("retrieved_knowledge") is not None:
            result["retrieved_knowledge"] = confirmed_result["retrieved_knowledge"]
        if confirmed_result.get("planner_policy") is not None:
            result["planner_policy"] = confirmed_result["planner_policy"]
        result["turn_trace"] = _append_custom_note({
            "conversation_checkpoints": {
                "truth_mode": {"resolved": True, "selected": "confirmed_only"}
            }
        }, note=custom_note)
    return result


def _make_block_intent(
    intent_type: str,
    priority: int,
    *,
    required: bool = False,
    preferred_component: str | None = None,
    candidate_components: list[str] | None = None,
    selection_mode: str | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    return {
        "intent_type": intent_type,
        "priority": priority,
        "goal": goal or intent_type.replace("_", " "),
        "preferred_component": preferred_component,
        "candidate_components": list(candidate_components or []),
        "selection_mode": selection_mode or "anchored",
        "required": required,
    }


def _has_visual_lead(state: UIProjectState) -> bool:
    planner_output = state.get("planner_output") or {}
    user_query = _user_query(state)
    block_intents = list(planner_output.get("block_intents") or [])
    return any(str(item.get("intent_type") or "") == "hero_media" for item in block_intents) or any(
        token in user_query for token in ["封面", "首图", "头图", "配图", "图片", "图文"]
    )


def _recommended_structure_options(state: UIProjectState) -> list[dict[str, Any]]:
    """根据当前场景生成 2~3 个页面骨架候选。"""
    planner_output = state.get("planner_output") or {}
    scenario_scores = planner_output.get("scenario_scores") or {}
    active = str(state.get("active_archetype") or "seeding")
    has_images = bool(state.get("image_assets"))
    wants_visual = _has_visual_lead(state) or has_images

    def _expand(raw_intents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        intents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(raw_intents):
            intent_type = str(item.get("intent_type") or "").strip()
            if not intent_type or intent_type in seen:
                continue
            seen.add(intent_type)
            preferred_component = item.get("preferred_component")
            component = preferred_component or resolve_component_for_block_intent(
                intent_type,
                has_images=has_images,
                scenario_scores=scenario_scores,
            )
            candidate_components = resolve_component_candidates_for_block_intent(
                intent_type,
                has_images=has_images,
                scenario_scores=scenario_scores,
                user_query=_user_query(state),
                active_archetype=active,
                retrieved_knowledge=state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {},
                preferred_component=component,
            )
            intents.append(
                _make_block_intent(
                    intent_type,
                    len(intents),
                    required=intent_type in {"heading", "narrative_text"},
                    preferred_component=component,
                    candidate_components=candidate_components,
                    selection_mode="flexible" if candidate_components and candidate_components[0] != component else "anchored",
                    goal=str(item.get("goal") or intent_type.replace("_", " ")),
                )
            )
        return intents

    base_prefix = [
        _make_block_intent("hero_media", 0, preferred_component="CoverSwiper", goal="首屏封面")
    ] if wants_visual else []

    def _compose(defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _expand([*base_prefix, *defs])

    if active == "seeding":
        return [
            {
                "label": "更像对比测评",
                "value": "seeding_compare",
                "description": "先讲结论，再给参数和对比，适合做购买分流。",
                "recommended": True,
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="开场结论"),
                    _make_block_intent("decision_summary", 3, preferred_component="RadarChartBlock", goal="判断重点"),
                    _make_block_intent("comparison", 4, preferred_component="VersusCard", goal="正反对比"),
                    _make_block_intent("interactive_opinion", 5, preferred_component="PollBlock", goal="互动收口"),
                ]),
            },
            {
                "label": "更像参数测评",
                "value": "seeding_specs",
                "description": "参数和判断依据更靠前，适合想快速比较重点的人看。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("fact_list", 2, preferred_component="ProductSpecCard", goal="参数重点"),
                    _make_block_intent("decision_summary", 3, preferred_component="RadarChartBlock", goal="维度说明"),
                    _make_block_intent("narrative_text", 4, required=True, preferred_component="StoryText", goal="购买建议"),
                    _make_block_intent("comparison", 5, preferred_component="VersusCard", goal="对比结论"),
                ]),
            },
            {
                "label": "更像体验分享",
                "value": "seeding_experience",
                "description": "更重手感、真实体验和站队表达，不那么参数堆砌。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="真实体验"),
                    _make_block_intent("quote_or_voice", 3, preferred_component="QuoteBlock", goal="体验强调"),
                    _make_block_intent("comparison", 4, preferred_component="VersusCard", goal="站队分流"),
                    _make_block_intent("interactive_opinion", 5, preferred_component="PollBlock", goal="互动收口"),
                ]),
            },
        ]

    return [
        {
            "label": "更像判断型评测",
            "value": "seeding_structured",
            "description": "先把结论、关键参数和判断边界讲清楚。",
            "recommended": True,
            "block_intents": _compose([
                _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="正文"),
                _make_block_intent("fact_list", 3, preferred_component="ProductSpecCard", goal="重点信息"),
                _make_block_intent("decision_summary", 4, preferred_component="RadarChartBlock", goal="判断收束"),
            ]),
        },
        {
            "label": "更像体验型评测",
            "value": "seeding_opinion",
            "description": "先讲真实体验，再补对比和互动，更像一篇完整评测笔记。",
            "block_intents": _compose([
                _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="观点表达"),
                _make_block_intent("comparison", 3, preferred_component="VersusCard", goal="对比判断"),
                _make_block_intent("interactive_opinion", 4, preferred_component="PollBlock", goal="互动问题"),
            ]),
        },
    ]


def build_structure_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    if not state_requests_create(state):
        return None
    options = _recommended_structure_options(state)
    if not options:
        return None
    recommended = next((item.get("value") for item in options if item.get("recommended")), options[0].get("value"))
    active = str(state.get("active_archetype") or "seeding")
    return {
        "action_type": "structure_checkpoint",
        "checkpoint_id": f"structure::{active}",
        "title": "这页先按哪种方向搭骨架？",
        "summary": "我先给出推荐结构。你选定方向后，我再继续补事实、安排素材并搭完整页面。",
        "proposal_summary": "我已经先按当前主题想好了几种骨架，其中有一套更适合作为这页的主方向。",
        "recommended_reason": "推荐方案会优先把当前场景最该先讲清楚的内容放在前面，后面再补事实和素材，不会一开始就把页面写散。",
        "other_allowed": True,
        "other_placeholder": "如果你想强调别的结构重点，也可以补一句",
        "recommended_option": str(recommended or ""),
        "blocking": True,
        "options": _safe_options(options),
    }


def apply_structure_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    planner_output = deepcopy(state.get("planner_output") or {})
    planner_policy = deepcopy(state.get("planner_policy") or {})
    options = _recommended_structure_options(state)
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    selected = next((item for item in options if str(item.get("value") or "") == decision_value), None)
    if not selected:
        selected = next((item for item in options if item.get("recommended")), options[0] if options else None)
    if not selected:
        return {}

    block_intents = deepcopy(selected.get("block_intents") or [])
    planner_output["block_intents"] = block_intents
    planner_output["reason"] = f"已按用户确认的结构方向继续搭建：{selected.get('label')}"
    layout_policy = dict(planner_policy.get("layout_policy") or {})
    layout_policy["preferred_block_intents"] = [str(item.get("intent_type") or "") for item in block_intents]
    layout_policy["confirmed_structure_mode"] = str(selected.get("value") or "")
    planner_policy["layout_policy"] = layout_policy
    custom_note = str((decision or {}).get("custom_note") or "").strip() if isinstance(decision, dict) else ""
    return {
        "planner_output": planner_output,
        "planner_policy": planner_policy,
        "turn_trace": _append_custom_note({
            "conversation_checkpoints": {
                "structure": {
                    "resolved": True,
                    "selected": str(selected.get("value") or ""),
                    "label": str(selected.get("label") or ""),
                }
            }
        }, note=custom_note),
    }


def _critical_missing_slot_keys(state: UIProjectState) -> tuple[list[str], dict[str, Any], dict[str, str]]:
    knowledge = state.get("retrieved_knowledge") or {}
    retrieval_profile = infer_retrieval_profile(
        user_query=_user_query(state),
        entity_name=_entity_name(state),
        active_archetype=str(state.get("active_archetype") or ""),
    )
    slot_labels = {
        str(key): str(value)
        for key, value in (retrieval_profile.get("slot_labels") or {}).items()
    }
    fact_slots = knowledge.get("fact_slots") if isinstance(knowledge.get("fact_slots"), dict) else {}
    missing_keys = compute_missing_slot_keys(slot_labels=slot_labels, fact_slots=fact_slots)
    critical_keys = [
        str(key)
        for key in (retrieval_profile.get("critical_slot_keys") or [])
        if str(key) in missing_keys
    ]
    return critical_keys, retrieval_profile, slot_labels


def _pending_candidate_groups(state: UIProjectState) -> list[dict[str, Any]]:
    knowledge = state.get("retrieved_knowledge") or {}
    candidate_payload = (knowledge.get("candidate_session_kb") or {}) if isinstance(knowledge, dict) else {}
    groups = []
    for group in group_records(candidate_payload.get("records") or []):
        pending_records = [
            item for item in (group.get("records") or [])
            if isinstance(item, dict) and str(item.get("review_status") or "") == "pending_review"
        ]
        if not pending_records:
            continue
        groups.append({**group, "records": pending_records})
    return groups


def build_knowledge_review_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    if not state_requests_create(state):
        return None
    groups = _pending_candidate_groups(state)
    if not groups:
        return None
    knowledge = state.get("retrieved_knowledge") or {}
    plan = (knowledge.get("knowledge_plan") or {}) if isinstance(knowledge, dict) else {}
    display_groups = groups[:5]
    labels = [str(group.get("field_label") or group.get("field_or_topic") or "补充知识") for group in display_groups]
    candidate_lines = []
    for group in display_groups:
        best = next((item for item in (group.get("records") or []) if str(item.get("record_id") or "") == str(group.get("recommended_record_id") or "")), None)
        if not isinstance(best, dict):
            best = ((group.get("records") or [None])[0] if isinstance(group.get("records"), list) else None)
        if not isinstance(best, dict):
            continue
        candidate_lines.append(f"{group.get('field_label') or group.get('field_or_topic')}: {best.get('summary') or best.get('value') or ''}")
    remaining = max(0, len(groups) - len(display_groups))
    summary = "我先把这轮最关键的候选知识压缩出来给你看。"
    if labels:
        summary += f" 当前优先影响这些字段：{' / '.join(labels)}。"
    if remaining:
        summary += f" 另外还有 {remaining} 条候选会折叠到知识面板里。"
    field_labels = candidate_lines[:3]
    return {
        "action_type": "knowledge_review_checkpoint",
        "checkpoint_id": f"knowledge-review::{str(plan.get('retrieval_profile') or state.get('active_archetype') or 'general')}",
        "title": "我先把这轮候选知识压缩给你确认",
        "summary": summary,
        "proposal_summary": "这些候选知识会直接影响后面页面的判断、容器选择和表达强度。我建议先采用推荐项，再继续生成。",
        "recommended_reason": "先把候选知识过一遍，可以避免系统把缓存或公网搜到的弱信息直接写成确定结论。",
        "other_allowed": True,
        "other_placeholder": "如果你想说明采用原则，也可以补一句",
        "recommended_option": "approve_recommended",
        "blocking": True,
        "options": _safe_options(
            [
                {
                    "label": "采用推荐候选后继续",
                    "value": "approve_recommended",
                    "description": "我会先采用每组里最稳的一条候选知识，再继续搭页面。",
                    "recommended": True,
                    "metadata": {"candidate_preview": field_labels},
                },
                {
                    "label": "先按已有知识继续",
                    "value": "continue_with_existing",
                    "description": "我先不使用这些新候选，只沿用当前已确认的知识继续。",
                },
                {
                    "label": "这一轮先都暂不使用",
                    "value": "defer_all",
                    "description": "把这批候选先放回待审区，你稍后可以上传资料或再审。",
                },
            ]
        ),
    }


def apply_knowledge_review_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    custom_note = str((decision or {}).get("custom_note") or "").strip() if isinstance(decision, dict) else ""
    if decision_value == "approve_recommended":
        next_knowledge = apply_knowledge_review_decision(
            state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {},
            decision="approve_recommended",
        )
        return {
            "retrieved_knowledge": next_knowledge,
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "knowledge_review": {"resolved": True, "selected": "approve_recommended"}
                }
            }, note=custom_note),
        }
    if decision_value == "defer_all":
        next_knowledge = apply_knowledge_review_decision(
            state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {},
            decision="defer_all",
        )
        return {
            "retrieved_knowledge": next_knowledge,
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "knowledge_review": {"resolved": True, "selected": "defer_all"}
                }
            }, note=custom_note),
        }
    return {
        "turn_trace": _append_custom_note({
            "conversation_checkpoints": {
                "knowledge_review": {"resolved": True, "selected": "continue_with_existing"}
            }
        }, note=custom_note),
    }


def build_fact_gap_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    critical_keys, retrieval_profile, slot_labels = _critical_missing_slot_keys(state)
    if not critical_keys:
        return None
    missing_labels = [slot_labels.get(key, key) for key in critical_keys]
    profile_name = str(retrieval_profile.get("profile_name") or "digital_review")
    return {
        "action_type": "fact_gap_checkpoint",
        "checkpoint_id": f"fact-gap::{profile_name}",
        "title": "我还缺几条关键事实，先和你确认一下",
        "summary": f"当前还缺这些会明显影响页面质量的信息：{' / '.join(missing_labels)}。",
        "proposal_summary": "我建议先把这些缺口补齐，再继续写页面，这样后面的结论和结构会更稳。",
        "recommended_reason": "这些字段一旦缺失，页面很容易出现“结构看起来完整，但关键判断站不住”的问题。",
        "other_allowed": True,
        "other_placeholder": "如果你想指定补搜重点或保留策略，可以补一句",
        "recommended_option": "continue_research",
        "blocking": True,
        "options": _safe_options(
            [
                {
                    "label": "继续补搜关键事实",
                    "value": "continue_research",
                    "description": "我再补一轮定向搜索，把缺口尽量补齐后再继续。",
                    "recommended": True,
                },
                {
                    "label": "先生成保守版",
                    "value": "cautious_generate",
                    "description": "先出一版保守表达，不把缺失字段写成确定结论。",
                },
                {
                    "label": "只用已确认事实",
                    "value": "confirmed_only",
                    "description": "只沿用已经确认的事实，宁可更克制，也不扩写不稳信息。",
                },
            ]
        ),
    }


def apply_cautious_fact_strategy(state: UIProjectState, *, custom_note: str | None = None) -> dict[str, Any]:
    knowledge = deepcopy(state.get("retrieved_knowledge") or {})
    retrieval_summary = dict(knowledge.get("retrieval_summary") or {})
    retrieval_summary["weak_result_mode"] = "cautious_generate"
    knowledge["retrieval_summary"] = retrieval_summary
    planner_policy = deepcopy(state.get("planner_policy") or {})
    fact_policy = dict(planner_policy.get("fact_policy") or {})
    fact_policy["prefer_confirmed_facts"] = True
    fact_policy["fallback_to_cautious_copy"] = True
    planner_policy["fact_policy"] = fact_policy
    return {
        "retrieved_knowledge": knowledge,
        "planner_policy": planner_policy,
        "turn_trace": _append_custom_note({
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "cautious_generate"}
            }
        }, note=custom_note),
    }


def apply_confirmed_only_strategy(state: UIProjectState, *, custom_note: str | None = None) -> dict[str, Any]:
    knowledge = apply_confirmed_facts_to_knowledge(deepcopy(state.get("retrieved_knowledge") or {}))
    confirmed_facts = normalize_confirmed_facts(knowledge.get("confirmed_facts"))
    confirmed_attrs = {}
    for field, payload in confirmed_facts.items():
        value = str(payload.get("value") or "").strip()
        if value:
            confirmed_attrs[str(payload.get("field_label") or field)] = value
    knowledge["core_attributes"] = confirmed_attrs
    retrieval_summary = dict(knowledge.get("retrieval_summary") or {})
    retrieval_summary["weak_result_mode"] = "confirmed_only"
    knowledge["retrieval_summary"] = retrieval_summary
    planner_policy = deepcopy(state.get("planner_policy") or {})
    fact_policy = dict(planner_policy.get("fact_policy") or {})
    fact_policy["prefer_confirmed_facts"] = True
    fact_policy["confirmed_only"] = True
    planner_policy["fact_policy"] = fact_policy
    return {
        "retrieved_knowledge": knowledge,
        "planner_policy": planner_policy,
        "turn_trace": _append_custom_note({
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "confirmed_only"}
            }
        }, note=custom_note),
    }


def build_asset_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    planner_output = state.get("planner_output") or {}
    wants_hero_media = any(
        str(item.get("intent_type") or "") == "hero_media"
        for item in (planner_output.get("block_intents") or [])
        if isinstance(item, dict)
    )
    raw_assets = [
        asset for asset in (state.get("image_assets") or [])
        if isinstance(asset, dict) and str(asset.get("url") or "").strip()
    ]
    assets: list[dict[str, Any]] = []
    seen_asset_urls: set[str] = set()
    for asset in raw_assets:
        asset_url = str(asset.get("url") or "").strip()
        if not asset_url or asset_url in seen_asset_urls:
            continue
        seen_asset_urls.add(asset_url)
        assets.append(asset)

    def _asset_checkpoint_label(asset: dict[str, Any], position: int) -> str:
        desc = str(asset.get("desc") or "").strip()
        if desc:
            return f"第{position}张「{desc[:14]}」"
        return f"第{position}张图片"

    if len(assets) >= 2:
        recommended_cover = next(
            (asset for asset in assets if str(asset.get("role") or "").strip().lower() == "cover"),
            assets[0],
        )
        options: list[dict[str, Any]] = [
            {
                "label": "采用 Agent 推荐图组",
                "value": "use_recommended_bundle",
                "description": f"我建议用「{_asset_checkpoint_label(recommended_cover, assets.index(recommended_cover) + 1)}」做封面，其余保留为正文补图。",
                "recommended": True,
                "asset_url": str(recommended_cover.get("url") or ""),
                "selected_asset_ids": [str(asset.get("url") or "") for asset in assets[:3] if str(asset.get("url") or "")],
            }
        ]
        for idx, asset in enumerate(assets[:3], start=1):
            asset_url = str(asset.get("url") or "")
            asset_label = _asset_checkpoint_label(asset, idx)
            options.append(
                {
                    "label": f"改用「{asset_label}」做封面",
                    "value": f"set_cover::{asset_url}",
                    "description": "保留其它图做正文补图。",
                    "asset_url": asset_url,
                }
            )
        for idx, asset in enumerate(assets[:2], start=1):
            asset_url = str(asset.get("url") or "")
            asset_label = _asset_checkpoint_label(asset, idx)
            options.append(
                {
                    "label": f"不要用「{asset_label}」",
                    "value": f"exclude::{asset_url}",
                    "description": "把它从本轮素材候选里排除。",
                    "asset_url": asset_url,
                }
            )
        options.append(
            {
                "label": "继续无图生成",
                "value": "continue_without_images",
                "description": "本轮先不使用这些图，改走无图版页面。",
            }
        )
        return {
            "action_type": "asset_checkpoint",
            "checkpoint_id": "asset::selection",
            "title": "我看到了多张素材，先一起定下怎么用",
            "summary": "我可以直接按推荐方案落图，也可以由你指定封面或排除某张素材。",
            "proposal_summary": "我已经先给出了一套封面图 + 正文补图的推荐组合，默认会先按这套推进。",
            "recommended_reason": f"推荐方案会优先用「{_asset_checkpoint_label(recommended_cover, assets.index(recommended_cover) + 1)}」做封面，因为它最适合承担首屏第一印象，其余图片更适合补正文画面。",
            "other_allowed": True,
            "other_placeholder": "如果你有别的图组想法，也可以补一句说明",
            "recommended_option": "use_recommended_bundle",
            "blocking": True,
            "options": _safe_options(options),
        }
    if wants_hero_media and not assets:
        return {
            "action_type": "asset_checkpoint",
            "checkpoint_id": "asset::missing",
            "title": "这页本来适合有首图，但我现在没有可用图片",
            "summary": "你可以让我继续做无图版，或者把这轮改成纯文字开场。",
            "proposal_summary": "如果你愿意，我建议先补一轮更贴主题的图片，再继续当前页面生成；如果你不想补图，我也可以立刻切成更稳的无图版。",
            "recommended_reason": "这页的开场会因为图片是否贴题而差很多，先补图通常能比硬上无图首屏更完整。",
            "other_allowed": True,
            "other_placeholder": "如果你想指定搜图方向或直接说明不要图，也可以补一句",
            "recommended_option": "continue_without_images",
            "blocking": True,
            "options": _safe_options(
                [
                    {
                        "label": "先帮我搜图补封面",
                        "value": "search_images_for_cover",
                        "description": "我会先去搜一轮更贴主题的图片，再继续当前页面生成。",
                        "recommended": True,
                    },
                    {
                        "label": "继续无图生成",
                        "value": "continue_without_images",
                        "description": "我会保留页面结构，但不再强行上封面图。",
                    },
                    {
                        "label": "改成纯文字开场",
                        "value": "remove_hero_media",
                        "description": "我会把首屏切成无图结构，让页面更干净。",
                    },
                ]
            ),
        }
    return None


def apply_asset_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    selected_asset_ids = list(decision.get("selected_asset_ids") or []) if isinstance(decision, dict) else []
    custom_note = str((decision or {}).get("custom_note") or "").strip() if isinstance(decision, dict) else ""
    assets = deepcopy(state.get("image_assets") or [])
    planner_output = deepcopy(state.get("planner_output") or {})

    def _mark_assets(*, cover_url: str | None = None, excluded_urls: set[str] | None = None) -> list[dict[str, Any]]:
        excluded_urls = excluded_urls or set()
        next_assets: list[dict[str, Any]] = []
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            url = str(asset.get("url") or "").strip()
            if not url:
                continue
            role = str(asset.get("role") or "supporting")
            selection_state = "available"
            if url in excluded_urls:
                selection_state = "excluded"
            elif cover_url and url == cover_url:
                role = "cover"
                selection_state = "selected"
            elif selected_asset_ids and url in selected_asset_ids:
                role = "supporting"
                selection_state = "selected"
            elif cover_url:
                role = "supporting"
            next_assets.append(
                {
                    **asset,
                    "role": role,
                    "selection_state": selection_state,
                    "source_reason": asset.get("source_reason") or asset.get("desc") or f"素材图 {index + 1}",
                }
            )
        return next_assets

    if decision_value == "use_recommended_bundle":
        cover_url = str(decision.get("asset_url") or "") if isinstance(decision, dict) else ""
        return {
            "image_assets": [{"__replace__": True}, *_mark_assets(cover_url=cover_url or None)],
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "use_recommended_bundle"}
                }
            }, note=custom_note),
        }

    if decision_value.startswith("set_cover::"):
        cover_url = decision_value.split("::", 1)[1]
        return {
            "image_assets": [{"__replace__": True}, *_mark_assets(cover_url=cover_url or None)],
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "set_cover", "cover_url": cover_url}
                }
            }, note=custom_note),
        }

    if decision_value.startswith("exclude::"):
        excluded_url = decision_value.split("::", 1)[1]
        return {
            "image_assets": [{"__replace__": True}, *_mark_assets(excluded_urls={excluded_url})],
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "exclude", "excluded_url": excluded_url}
                }
            }, note=custom_note),
        }

    if decision_value in {"continue_without_images", "remove_hero_media"}:
        planner_output["block_intents"] = [
            item
            for item in (planner_output.get("block_intents") or [])
            if str(item.get("intent_type") or "") != "hero_media"
        ]
        planner_policy = deepcopy(state.get("planner_policy") or {})
        layout_policy = dict(planner_policy.get("layout_policy") or {})
        layout_policy["preferred_block_intents"] = [
            item for item in list(layout_policy.get("preferred_block_intents") or [])
            if str(item) != "hero_media"
        ]
        planner_policy["layout_policy"] = layout_policy
        return {
            "planner_output": planner_output,
            "planner_policy": planner_policy,
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": decision_value}
                }
            }, note=custom_note),
        }

    return {}


def build_fact_conflict_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    knowledge = state.get("retrieved_knowledge") or {}
    conflicts = [item for item in (knowledge.get("fact_conflicts") or []) if isinstance(item, dict)]
    if not conflicts:
        return None
    conflict = conflicts[0]
    field = str(conflict.get("field") or "").strip()
    values = [item for item in (conflict.get("values") or []) if isinstance(item, dict)]
    if not field or len(values) < 2:
        return None
    options: list[dict[str, Any]] = []
    for item in values[:3]:
        candidate = str(item.get("value") or "").strip()
        source_titles = [str(source).strip() for source in (item.get("sources") or []) if str(source).strip()]
        if not candidate:
            continue
        options.append(
            {
                "label": candidate,
                "value": f"confirm::{field}::{candidate}",
                "description": " / ".join(source_titles[:2]) or "采用这个说法继续生成",
                "selected_fact_value": candidate,
            }
        )
    options.append(
        {
            "label": "保持保守表达",
            "value": "keep_cautious",
            "description": "不选定冲突值，继续使用保守写法。",
            "recommended": True,
        }
    )
    return {
        "action_type": "fact_conflict_checkpoint",
        "checkpoint_id": f"fact-conflict::{field}",
        "title": f"关于「{field}」我发现了冲突说法",
        "summary": "你可以直接选一个版本继续，或者让我保持保守表达。",
        "proposal_summary": "这条事实有多个来源给出了不同说法，我先把最关键的候选摆出来，避免系统替你擅自拍板。",
        "recommended_reason": "如果当前证据还不足以稳稳站住一个版本，我宁可先保持保守表达，也不把冲突信息写成确定结论。",
        "other_allowed": True,
        "other_placeholder": "如果你想补充采用原则，也可以写在这里",
        "recommended_option": "keep_cautious",
        "blocking": True,
        "options": _safe_options(options),
    }


def apply_fact_conflict_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    knowledge = deepcopy(state.get("retrieved_knowledge") or {})
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    custom_note = str((decision or {}).get("custom_note") or "").strip() if isinstance(decision, dict) else ""
    if decision_value == "keep_cautious":
        return {
            "retrieved_knowledge": apply_confirmed_facts_to_knowledge(knowledge),
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "fact_conflict": {"resolved": True, "selected": "keep_cautious"}
                }
            }, note=custom_note),
        }
    if decision_value.startswith("confirm::"):
        _, field, value = decision_value.split("::", 2)
        conflict = next(
            (item for item in (knowledge.get("fact_conflicts") or []) if str(item.get("field") or "") == field),
            {},
        )
        selected_sources = []
        for item in (conflict.get("values") or []):
            if str((item or {}).get("value") or "") == value:
                selected_sources = [str(source).strip() for source in ((item or {}).get("sources") or []) if str(source).strip()]
                break
        next_knowledge = merge_confirmed_fact_selection(
            knowledge,
            field=field,
            value=value,
            sources=selected_sources,
        )
        return {
            "retrieved_knowledge": next_knowledge,
            "turn_trace": _append_custom_note({
                "conversation_checkpoints": {
                    "fact_conflict": {"resolved": True, "selected": field, "value": value}
                }
            }, note=custom_note),
        }
    return {}
