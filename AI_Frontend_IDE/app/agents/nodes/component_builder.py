"""Contract-first component builder.

This node keeps one worker-style generation path, but the surrounding contract
layer owns normalization, required/optional prop filtering, capability hints,
and fallback enforcement so the worker only fills a narrow, structured brief.
"""

import json
import asyncio
import random
from typing import Any, List
from app.core.llm_factory import create_llm
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import (
    build_conflict_safe_notes,
    build_fact_grounding_context,
    summarize_confirmed_attributes,
)
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.context_engineering import (
    build_asset_summary,
    build_fact_summary,
    build_policy_summary,
    build_retrieval_evidence_slice,
    count_fact_summary_entries,
)
from app.core.schema import ComponentBuilderOutput
from app.core.component_manifest import (
    filter_payload_for_component,
    get_asset_support,
    get_component_label,
    get_component_semantic_role,
    get_editable_targets,
    get_optional_props,
    get_quick_actions,
    get_required_props,
    get_theme_slots,
    normalize_component_type,
    supports_fact_binding,
)
from app.core.note_document import append_note_document_block, build_note_document_from_state, update_note_document_block
from app.core.prompt_engineering import build_prompt_snapshot, render_string_prompt

# Limit concurrent worker-style generation tasks.
_github_limiter = asyncio.Semaphore(10)

_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance


VERIFIED_FEATURE_PREFIX = "__verified__"


def build_component_contract_snapshot(comp_type: str) -> dict[str, Any]:
    normalized_type = normalize_component_type(comp_type) or comp_type
    return {
        "type": normalized_type,
        "label": get_component_label(normalized_type) or str(normalized_type),
        "semantic_role": get_component_semantic_role(normalized_type) or "content",
        "required_props": get_required_props(normalized_type),
        "optional_props": get_optional_props(normalized_type),
        "editable_targets": get_editable_targets(normalized_type),
        "asset_support": get_asset_support(normalized_type) or "none",
        "fact_binding_support": supports_fact_binding(normalized_type),
        "theme_slots": get_theme_slots(normalized_type),
        "quick_actions": get_quick_actions(normalized_type),
    }


def _clip_text(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _pick_document_guide_summary(content_msgs: list[Any]) -> str:
    for msg in reversed(content_msgs or []):
        content = getattr(msg, "content", None)
        summary = _clip_text(content, 240)
        if summary:
            return summary
    return "未提供额外导引"


def _nonempty_keys(payload: dict[str, Any] | None) -> list[str]:
    return [
        str(key)
        for key, value in (payload or {}).items()
        if value not in (None, "", [], {})
    ]


def apply_component_contract_with_trace(comp_type: str, payload: dict[str, Any] | None, fallback_data: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_type = normalize_component_type(comp_type) or comp_type
    required_props = get_required_props(normalized_type)
    optional_props = get_optional_props(normalized_type)
    filtered_payload = filter_payload_for_component(normalized_type, payload or {})
    filtered_fallback = filter_payload_for_component(normalized_type, fallback_data or {})
    payload_keys = set(_nonempty_keys(payload))
    fallback_keys = set(_nonempty_keys(fallback_data))
    filtered_payload_keys = set(_nonempty_keys(filtered_payload))
    filtered_fallback_keys = set(_nonempty_keys(filtered_fallback))
    merged = enforce_component_contract(normalized_type, filtered_payload, filtered_fallback)
    final_payload = filter_payload_for_component(normalized_type, merged)
    precheck_missing_required = [
        field
        for field in required_props
        if filtered_payload.get(field) in (None, "", [], {})
    ]
    final_missing_required = [
        field
        for field in required_props
        if final_payload.get(field) in (None, "", [], {})
    ]
    contract_trace = {
        "normalized_type": normalized_type,
        "required_prop_count": len(required_props),
        "optional_prop_count": len(optional_props),
        "payload_field_count": len(payload_keys),
        "fallback_field_count": len(fallback_keys),
        "dropped_payload_fields": sorted(payload_keys - filtered_payload_keys),
        "dropped_fallback_fields": sorted(fallback_keys - filtered_fallback_keys),
        "contract_filter_count": len(payload_keys - filtered_payload_keys) + len(fallback_keys - filtered_fallback_keys),
        "precheck_warnings": [f"missing_required_before_merge:{field}" for field in precheck_missing_required],
        "precheck_warning_count": len(precheck_missing_required),
        "final_missing_required": final_missing_required,
    }
    return final_payload, contract_trace


def apply_component_contract_layer(comp_type: str, payload: dict[str, Any] | None, fallback_data: dict[str, Any] | None) -> dict[str, Any]:
    final_payload, _ = apply_component_contract_with_trace(comp_type, payload, fallback_data)
    return final_payload

def build_component_fallback(
    comp_type: str,
    comp_id: str,
    content_brief: str,
    user_query: str,
    retrieved_knowledge: Any,
    image_assets: list[dict[str, Any]],
) -> dict:
    knowledge = retrieved_knowledge if isinstance(retrieved_knowledge, dict) else {}
    entity_name = normalize_entity_name(knowledge.get("entity_name") or user_query)
    attrs = knowledge.get("core_attributes") or {}
    selling_points = knowledge.get("key_selling_points") or []
    known_issues = knowledge.get("known_issues") or []
    summary = knowledge.get("summary") or content_brief or user_query
    confirmed_summaries = summarize_confirmed_attributes(knowledge)
    conflict_safe_notes = build_conflict_safe_notes(knowledge)
    image_urls = [asset.get("url") for asset in image_assets if asset.get("url")]
    verified_feature_items = [f"{VERIFIED_FEATURE_PREFIX}{item}" for item in confirmed_summaries]

    if comp_type == "TitleBlock":
        return {"type": comp_type, "title": content_brief or entity_name}
    if comp_type == "StoryText":
        paragraphs = []
        paragraph_meta = []
        if summary:
            paragraphs.append(summary)
            paragraph_meta.append({"kind": "default", "sources": [], "hint": "页面摘要"})
        if confirmed_summaries:
            paragraphs.append("已确认参数：" + " / ".join(confirmed_summaries[:3]))
            confirmed_sources = []
            for payload in (knowledge.get("confirmed_facts") or {}).values():
                for source in (payload.get("sources") or []):
                    source_text = str(source).strip()
                    if source_text and source_text not in confirmed_sources:
                        confirmed_sources.append(source_text)
            paragraph_meta.append({
                "kind": "verified",
                "sources": confirmed_sources[:4],
                "hint": "该段采用已确认事实",
                "fields": list((knowledge.get("confirmed_facts") or {}).keys()),
            })
        if conflict_safe_notes:
            paragraphs.append("参数提示：" + " / ".join(conflict_safe_notes[:2]))
            caution_sources = []
            for conflict in (knowledge.get("fact_conflicts") or []):
                for value in (conflict.get("values") or []):
                    for source in (value.get("sources") or []):
                        source_text = str(source).strip()
                        if source_text and source_text not in caution_sources:
                            caution_sources.append(source_text)
            paragraph_meta.append({
                "kind": "caution",
                "sources": caution_sources[:4],
                "hint": "该段因参数冲突而采用保守表达",
                "fields": [str(conflict.get("field") or "") for conflict in (knowledge.get("fact_conflicts") or []) if str(conflict.get("field") or "")],
            })
        if selling_points:
            paragraphs.append("亮点: " + " / ".join(selling_points[:3]))
            paragraph_meta.append({"kind": "default", "sources": [], "hint": "卖点提炼"})
        if not paragraphs:
            paragraphs.append(content_brief or "内容整理中")
            paragraph_meta.append({"kind": "default", "sources": [], "hint": "基础内容占位"})
        return {"type": comp_type, "paragraphs": paragraphs, "paragraph_meta": paragraph_meta}
    if comp_type == "ProductSpecCard":
        feature_meta = []
        features = []
        confirmed_facts = knowledge.get("confirmed_facts") or {}
        for item in confirmed_summaries[:4]:
            features.append(f"{VERIFIED_FEATURE_PREFIX}{item}")
            matched_sources = []
            for payload in confirmed_facts.values():
                label = str(payload.get("field_label") or "")
                value = str(payload.get("value") or "")
                if label and value and item == f"{label}: {value}":
                    matched_sources = [str(source) for source in (payload.get("sources") or [])]
                    break
            feature_meta.append({"kind": "verified", "sources": matched_sources, "hint": "该参数已由用户人工确认", "field": next((field for field, payload in confirmed_facts.items() if f"{payload.get('field_label')}: {payload.get('value')}" == item), None)})

        for attr_text in [f"{k}: {v}" for k, v in list(attrs.items())[:6] if f"{k}: {v}" not in confirmed_summaries]:
            features.append(attr_text)
            feature_meta.append({"kind": "default", "sources": [], "hint": "当前结构化事实库参数", "field": attr_text.split(":", 1)[0] if ":" in attr_text else None})

        conflict_map = {str(item.get("field") or ""): item for item in (knowledge.get("fact_conflicts") or []) if isinstance(item, dict)}
        for note in conflict_safe_notes[:2]:
            if note not in features:
                features.append(note)
                matched_sources = []
                for field_name, conflict in conflict_map.items():
                    label = str(field_name)
                    if note.startswith("电池容量") and field_name == "battery_capacity":
                        matched_sources = sorted({str(src) for value in (conflict.get("values") or []) for src in (value.get("sources") or [])})[:4]
                        break
                    if note.startswith("价格") and field_name == "price":
                        matched_sources = sorted({str(src) for value in (conflict.get("values") or []) for src in (value.get("sources") or [])})[:4]
                        break
                feature_meta.append({"kind": "caution", "sources": matched_sources, "hint": "该参数存在冲突，已自动采用保守表达", "field": "battery_capacity" if note.startswith("电池容量") else ("price" if note.startswith("价格") else None)})

        if not features:
            features = selling_points[:4] or [content_brief or "核心参数整理中"]
            feature_meta = [{"kind": "default", "sources": [], "hint": "基础参数摘要"} for _ in features]
        return {"type": comp_type, "core_features": features, "feature_meta": feature_meta}
    if comp_type == "CoverSwiper":
        return {"type": comp_type, "image_urls": image_urls[:5]}
    if comp_type == "RadarChartBlock":
        dimensions = ["性能", "影像", "续航", "设计", "体验"]
        score_seed = min(95, 60 + len(selling_points) * 5)
        scores = [score_seed, score_seed - 4, score_seed - 8, score_seed - 2, score_seed - 6]
        return {"type": comp_type, "dimensions": dimensions, "scores": scores}
    if comp_type == "PollBlock":
        return {
            "type": comp_type,
            "question": f"{entity_name} 最打动你的是哪一点？",
            "option_a": selling_points[0] if selling_points else "影像表现",
            "option_b": known_issues[0] if known_issues else "价格门槛",
        }
    if comp_type == "VersusCard":
        battle_report = knowledge.get("battle_report") or {}
        return {
            "type": comp_type,
            "title": battle_report.get("title") or "优缺点速览",
            "proText": battle_report.get("pros", {}).get("details") or (selling_points[0] if selling_points else "优势整理中"),
            "conText": battle_report.get("cons", {}).get("details") or (known_issues[0] if known_issues else "短板整理中"),
        }
    if comp_type == "LocationBlock":
        return {"type": comp_type, "poi_name": entity_name, "location": summary}
    if comp_type == "WeatherPolaroid":
        return {
            "type": comp_type,
            "image_url": image_urls[0] if image_urls else None,
            "weather": "晴",
            "temperature": "24C",
            "time": "今日",
            "desc": summary,
        }
    return {"type": comp_type, "title": content_brief or "内容整理中"}


def enforce_component_contract(comp_type: str, result_data: dict, fallback_data: dict) -> dict:
    merged = dict(result_data or {})
    required_fields_map = {
        "TitleBlock": ["title"],
        "StoryText": ["paragraphs"],
        "ProductSpecCard": ["core_features"],
        "RadarChartBlock": ["dimensions", "scores"],
        "PollBlock": ["question", "option_a", "option_b"],
        "VersusCard": ["title", "proText", "conText"],
        "CoverSwiper": ["image_urls"],
        "LocationBlock": ["poi_name", "location"],
        "WeatherPolaroid": ["desc"],
    }

    for field in required_fields_map.get(comp_type, []):
        value = merged.get(field)
        if value in (None, "", [], {}):
            fallback_value = fallback_data.get(field)
            if fallback_value not in (None, "", [], {}):
                merged[field] = fallback_value

    if "type" not in merged:
        merged["type"] = comp_type
    return merged

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点 5.8】：纯文本注入版 (杜绝 jinja2 错误)。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "填充内容")
    user_query = state.get("user_query", "")
    planner_policy = state.get("planner_policy", {}) if isinstance(state.get("planner_policy", {}), dict) else {}
    contract_snapshot = build_component_contract_snapshot(comp_type)
    
    # 1. 提取 RAG/Planner 摘要（保持 contract-first，但压缩 prompt 噪音）
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    battle_report = None
    image_assets = state.get("image_assets", [])
    fact_summary = {"entity": "", "key_selling_points": [], "known_issues": [], "core_attributes": {}, "confirmed_facts": {}, "conflict_count": 0, "image_count": 0}
    if isinstance(retrieved_knowledge, dict):
        battle_report = retrieved_knowledge.get("battle_report")
        fact_summary = build_fact_summary(retrieved_knowledge, image_assets)
        fact_grounding = build_fact_grounding_context(retrieved_knowledge)
    else:
        fact_grounding = ""

    # 2. 提取导引文案
    content_msgs = state.get("content_messages", [])
    document_guide_summary = _pick_document_guide_summary(content_msgs)
    policy_summary = build_policy_summary(planner_policy)
    asset_summary = build_asset_summary(image_assets, limit=3)
    evidence_slice = build_retrieval_evidence_slice(retrieved_knowledge, semantic_role=contract_snapshot.get("semantic_role"), limit=3)
    fact_summary_count = count_fact_summary_entries(fact_summary)
    asset_count = len([asset for asset in image_assets if asset.get("url")])

    async with _github_limiter:
        await asyncio.sleep(random.uniform(0.1, 0.2))
        print(f"👷 [并发工兵] 构建中: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # 3. 构造指令 (contract-first + compact prompt)
        system_prompt = render_string_prompt(
            "component_builder_system.xml",
            comp_id=comp_id,
            comp_type=comp_type,
            contract_snapshot=json.dumps(contract_snapshot, ensure_ascii=False, indent=2),
            content_brief=content_brief,
            global_guide=document_guide_summary,
            fact_summary=json.dumps(fact_summary, ensure_ascii=False, indent=2),
            asset_summary=json.dumps(asset_summary, ensure_ascii=False, indent=2),
            planner_policy_summary=json.dumps(policy_summary, ensure_ascii=False, indent=2),
            fact_grounding=(
                (fact_grounding or "暂无已确认事实；若存在冲突，不要编造绝对参数。")
                + f"\n\n【🔎 Evidence Slice】\n{json.dumps(evidence_slice, ensure_ascii=False, indent=2)}"
            ),
            battle_report=json.dumps(battle_report, ensure_ascii=False, indent=2) if (comp_type == "VersusCard" and battle_report) else "",
        )
        prompt_snapshot = build_prompt_snapshot(
            "component_builder",
            system_prompt=system_prompt,
            user_prompt=f"请根据指令完成组件数据构建。用户指令：{user_query}",
        )

        try:
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
            )
            result: ComponentBuilderOutput = await structured_llm.ainvoke([
                ("system", system_prompt),
                ("human", f"请根据指令完成组件数据构建。用户指令：{user_query}")
            ])
            
            res_data = {}
            if result.data:
                res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type
            res_data, contract_trace = apply_component_contract_with_trace(comp_type, res_data, fallback_data)
            
            # VersusCard 深度纠偏
            if comp_type == "VersusCard" and battle_report:
                res_data["title"] = battle_report.get('title')
                res_data["proText"] = battle_report.get('pros', {}).get('details')
                res_data["conText"] = battle_report.get('cons', {}).get('details')
            
            style_data = {"css_classes": "", "inline_styles": {}}
            if result.style:
                style_data = result.style.model_dump(exclude_none=True)

            updated_document = build_note_document_from_state(state)
            if not any(block.get("id") == comp_id for block in (updated_document.get("blocks") or [])):
                updated_document = append_note_document_block(
                    updated_document,
                    {"id": comp_id, "component_type": comp_type, "content_brief": content_brief},
                )
            updated_document = update_note_document_block(updated_document, comp_id, props=res_data, style=style_data)

            return {
                "note_document": updated_document,
                "node_prompts": prompt_snapshot,
                "turn_trace": {
                    "component_builder": {
                        comp_id: {
                            "component_type": comp_type,
                            "semantic_role": contract_snapshot.get("semantic_role"),
                            "required_props": contract_snapshot.get("required_props", []),
                            "editable_targets": contract_snapshot.get("editable_targets", []),
                            "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                            "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                            "precheck_warnings": contract_trace.get("precheck_warnings", []),
                            "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                            "prompt_mode": "compact_contract_first",
                            "fact_summary_count": fact_summary_count,
                            "asset_count": asset_count,
                            "fallback_used": False,
                            "contract_first": True,
                        }
                    }
                },
                "agent_backends": {"component_builder": "contract_first_worker"},
            }
        except Exception as e:
            print(f"🩹 [工兵自愈] {comp_id} 失败: {e}")
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
            )
            
            # 最后的挣扎：如果是 VersusCard 且有报告，直接硬填
            if comp_type == "VersusCard" and battle_report:
                 merged_data, contract_trace = apply_component_contract_with_trace("VersusCard", {
                        "type": "VersusCard",
                        "title": battle_report.get('title'),
                        "proText": battle_report.get('pros', {}).get('details'),
                        "conText": battle_report.get('cons', {}).get('details')
                    }, fallback_data)
                 updated_document = build_note_document_from_state(state)
                 if not any(block.get("id") == comp_id for block in (updated_document.get("blocks") or [])):
                    updated_document = append_note_document_block(
                        updated_document,
                        {"id": comp_id, "component_type": comp_type, "content_brief": content_brief},
                    )
                 updated_document = update_note_document_block(
                    updated_document,
                    comp_id,
                    props=merged_data,
                    style={"css_classes": "opacity-90", "inline_styles": {}},
                 )
                 return {
                     "note_document": updated_document,
                     "node_prompts": prompt_snapshot,
                     "turn_trace": {
                        "component_builder": {
                            comp_id: {
                                "component_type": comp_type,
                                "semantic_role": contract_snapshot.get("semantic_role"),
                                "required_props": contract_snapshot.get("required_props", []),
                                "editable_targets": contract_snapshot.get("editable_targets", []),
                                "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                                "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                                "precheck_warnings": contract_trace.get("precheck_warnings", []),
                                "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                                "prompt_mode": "compact_contract_first",
                                "fact_summary_count": fact_summary_count,
                                "asset_count": asset_count,
                                "fallback_used": True,
                                "fallback_reason": str(e),
                                "contract_first": True,
                            }
                        }
                    },
                    "agent_backends": {"component_builder": "contract_first_worker"},
                }
            
            merged_data, contract_trace = apply_component_contract_with_trace(comp_type, {}, fallback_data)
            updated_document = build_note_document_from_state(state)
            if not any(block.get("id") == comp_id for block in (updated_document.get("blocks") or [])):
                updated_document = append_note_document_block(
                    updated_document,
                    {"id": comp_id, "component_type": comp_type, "content_brief": content_brief},
                )
            updated_document = update_note_document_block(
                updated_document,
                comp_id,
                props=merged_data,
                style={"css_classes": "", "inline_styles": {}},
            )
            return {
                "note_document": updated_document,
                "node_prompts": prompt_snapshot,
                "turn_trace": {
                    "component_builder": {
                        comp_id: {
                            "component_type": comp_type,
                            "semantic_role": contract_snapshot.get("semantic_role"),
                            "required_props": contract_snapshot.get("required_props", []),
                            "editable_targets": contract_snapshot.get("editable_targets", []),
                            "contract_filter_count": contract_trace.get("contract_filter_count", 0),
                            "dropped_payload_fields": contract_trace.get("dropped_payload_fields", []),
                            "precheck_warnings": contract_trace.get("precheck_warnings", []),
                            "precheck_warning_count": contract_trace.get("precheck_warning_count", 0),
                            "prompt_mode": "compact_contract_first",
                            "fact_summary_count": fact_summary_count,
                            "asset_count": asset_count,
                            "fallback_used": True,
                            "fallback_reason": str(e),
                            "contract_first": True,
                        }
                    }
                },
                "agent_backends": {"component_builder": "contract_first_worker"},
            }
