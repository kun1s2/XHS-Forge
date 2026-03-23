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
from app.core.component_manifest import resolve_component_for_block_intent
from app.core.request_semantics import latest_user_text_from_messages, state_requests_create
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
            }
        )
    return cleaned


def _make_block_intent(
    intent_type: str,
    priority: int,
    *,
    required: bool = False,
    preferred_component: str | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    return {
        "intent_type": intent_type,
        "priority": priority,
        "goal": goal or intent_type.replace("_", " "),
        "preferred_component": preferred_component,
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
    active = str(state.get("active_archetype") or "general")
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
            intents.append(
                _make_block_intent(
                    intent_type,
                    len(intents),
                    required=intent_type in {"heading", "narrative_text"},
                    preferred_component=component,
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
                    _make_block_intent("score_overview", 3, preferred_component="RadarChartBlock", goal="多维评分"),
                    _make_block_intent("comparison", 4, preferred_component="VersusCard", goal="正反对比"),
                    _make_block_intent("interactive_opinion", 5, preferred_component="PollBlock", goal="互动收口"),
                ]),
            },
            {
                "label": "更像参数测评",
                "value": "seeding_specs",
                "description": "参数和购买判断更靠前，适合参数党和做决策的人看。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("evidence_summary", 2, preferred_component="ProductSpecCard", goal="参数重点"),
                    _make_block_intent("score_overview", 3, preferred_component="RadarChartBlock", goal="评分依据"),
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
                    _make_block_intent("ambience_snapshot", 3, preferred_component="WeatherPolaroid", goal="氛围补充"),
                    _make_block_intent("comparison", 4, preferred_component="VersusCard", goal="站队分流"),
                    _make_block_intent("interactive_opinion", 5, preferred_component="PollBlock", goal="互动收口"),
                ]),
            },
        ]

    if active == "travel":
        return [
            {
                "label": "更像路线攻略",
                "value": "travel_route",
                "description": "路线和地点信息更靠前，适合实用型出行阅读。",
                "recommended": True,
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("location_info", 2, preferred_component="LocationBlock", goal="地点信息"),
                    _make_block_intent("timeline", 3, preferred_component="TimelineBlock", goal="行程顺序"),
                    _make_block_intent("narrative_text", 4, required=True, preferred_component="StoryText", goal="路线说明"),
                ]),
            },
            {
                "label": "更像生活方式旅行笔记",
                "value": "travel_lifestyle",
                "description": "更强调氛围、故事和现场感，适合做生活方式表达。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="旅行故事"),
                    _make_block_intent("ambience_snapshot", 3, preferred_component="WeatherPolaroid", goal="氛围画面"),
                    _make_block_intent("location_info", 4, preferred_component="LocationBlock", goal="地点说明"),
                ]),
            },
        ]

    if active in {"gourmet", "food"}:
        return [
            {
                "label": "更像实用探店",
                "value": "store_practical",
                "description": "地址、人均和招牌更明确，适合快速决策。",
                "recommended": True,
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("location_info", 2, preferred_component="LocationBlock", goal="店铺信息"),
                    _make_block_intent("evidence_summary", 3, preferred_component="ProductSpecCard", goal="关键信息"),
                    _make_block_intent("narrative_text", 4, required=True, preferred_component="StoryText", goal="探店结论"),
                ]),
            },
            {
                "label": "更像氛围分享",
                "value": "store_ambient",
                "description": "更像生活方式表达，强调现场感和主观体验。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="探店感受"),
                    _make_block_intent("ambience_snapshot", 3, preferred_component="WeatherPolaroid", goal="氛围画面"),
                    _make_block_intent("interactive_opinion", 4, preferred_component="PollBlock", goal="互动问题"),
                ]),
            },
        ]

    if active == "daily_share":
        return [
            {
                "label": "更像生活叙事",
                "value": "daily_story",
                "description": "先保留生活感和叙事节奏，不强塞太多硬信息。",
                "recommended": True,
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="生活故事"),
                    _make_block_intent("ambience_snapshot", 3, preferred_component="WeatherPolaroid", goal="氛围补充"),
                    _make_block_intent("interactive_opinion", 4, preferred_component="PollBlock", goal="轻互动"),
                ]),
            },
            {
                "label": "更像轻 grounded 分享",
                "value": "daily_grounded",
                "description": "保留生活感，但会更强调有依据的小结论。",
                "block_intents": _compose([
                    _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                    _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="生活故事"),
                    _make_block_intent("evidence_summary", 3, preferred_component="QuoteBlock", goal="引用依据"),
                    _make_block_intent("interactive_opinion", 4, preferred_component="PollBlock", goal="轻互动"),
                ]),
            },
        ]

    return [
        {
            "label": "更像结构化笔记",
            "value": "general_structured",
            "description": "先把结论和重点讲清楚，适合信息密度高一点的内容。",
            "recommended": True,
            "block_intents": _compose([
                _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="正文"),
                _make_block_intent("evidence_summary", 3, preferred_component="ProductSpecCard", goal="重点信息"),
            ]),
        },
        {
            "label": "更像观点分享",
            "value": "general_opinion",
            "description": "更适合先表达立场，再补一点证据和互动。",
            "block_intents": _compose([
                _make_block_intent("heading", 1, required=True, preferred_component="TitleBlock", goal="标题"),
                _make_block_intent("narrative_text", 2, required=True, preferred_component="StoryText", goal="观点表达"),
                _make_block_intent("interactive_opinion", 3, preferred_component="PollBlock", goal="互动问题"),
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
    active = str(state.get("active_archetype") or "general")
    return {
        "action_type": "structure_checkpoint",
        "checkpoint_id": f"structure::{active}",
        "title": "这页先按哪种方向搭骨架？",
        "summary": "我先给出推荐结构。你选定方向后，我再继续补事实、安排素材并搭完整页面。",
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
    return {
        "planner_output": planner_output,
        "planner_policy": planner_policy,
        "turn_trace": {
            "conversation_checkpoints": {
                "structure": {
                    "resolved": True,
                    "selected": str(selected.get("value") or ""),
                    "label": str(selected.get("label") or ""),
                }
            }
        },
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


def build_fact_gap_checkpoint(state: UIProjectState) -> dict[str, Any] | None:
    critical_keys, retrieval_profile, slot_labels = _critical_missing_slot_keys(state)
    if not critical_keys:
        return None
    missing_labels = [slot_labels.get(key, key) for key in critical_keys]
    profile_name = str(retrieval_profile.get("profile_name") or "general_grounded")
    return {
        "action_type": "fact_gap_checkpoint",
        "checkpoint_id": f"fact-gap::{profile_name}",
        "title": "我还缺几条关键事实，先和你确认一下",
        "summary": f"当前还缺这些会明显影响页面质量的信息：{' / '.join(missing_labels)}。",
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


def apply_cautious_fact_strategy(state: UIProjectState) -> dict[str, Any]:
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
        "turn_trace": {
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "cautious_generate"}
            }
        },
    }


def apply_confirmed_only_strategy(state: UIProjectState) -> dict[str, Any]:
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
        "turn_trace": {
            "conversation_checkpoints": {
                "fact_gap": {"resolved": True, "selected": "confirmed_only"}
            }
        },
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
            "recommended_option": "continue_without_images",
            "blocking": True,
            "options": _safe_options(
                [
                    {
                        "label": "继续无图生成",
                        "value": "continue_without_images",
                        "description": "我会保留页面结构，但不再强行上封面图。",
                        "recommended": True,
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
            "turn_trace": {
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "use_recommended_bundle"}
                }
            },
        }

    if decision_value.startswith("set_cover::"):
        cover_url = decision_value.split("::", 1)[1]
        return {
            "image_assets": [{"__replace__": True}, *_mark_assets(cover_url=cover_url or None)],
            "turn_trace": {
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "set_cover", "cover_url": cover_url}
                }
            },
        }

    if decision_value.startswith("exclude::"):
        excluded_url = decision_value.split("::", 1)[1]
        return {
            "image_assets": [{"__replace__": True}, *_mark_assets(excluded_urls={excluded_url})],
            "turn_trace": {
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": "exclude", "excluded_url": excluded_url}
                }
            },
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
            "turn_trace": {
                "conversation_checkpoints": {
                    "asset": {"resolved": True, "selected": decision_value}
                }
            },
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
        "recommended_option": "keep_cautious",
        "blocking": True,
        "options": _safe_options(options),
    }


def apply_fact_conflict_checkpoint_decision(state: UIProjectState, decision: dict[str, Any] | str | None) -> dict[str, Any]:
    knowledge = deepcopy(state.get("retrieved_knowledge") or {})
    decision_value = str(decision.get("decision") or decision.get("value") or "") if isinstance(decision, dict) else str(decision or "")
    if decision_value == "keep_cautious":
        return {
            "retrieved_knowledge": apply_confirmed_facts_to_knowledge(knowledge),
            "turn_trace": {
                "conversation_checkpoints": {
                    "fact_conflict": {"resolved": True, "selected": "keep_cautious"}
                }
            },
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
            "turn_trace": {
                "conversation_checkpoints": {
                    "fact_conflict": {"resolved": True, "selected": field, "value": value}
                }
            },
        }
    return {}
