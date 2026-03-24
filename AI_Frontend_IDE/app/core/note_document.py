"""正式的 NoteDocument 桥接层。

这个文件是运行时状态折叠成 `NoteDocument` 的唯一入口。主链节点如果需要
正式文档协议、紧凑编辑视图、布局投影或文档级 patch，都应该优先复用这里
的函数，而不是在各自文件里重新拼装。
"""

from copy import deepcopy
import re
from typing import Any

from app.core.component_manifest import get_asset_support, get_component_entry, get_editable_targets, normalize_component_type
from app.agents.utils.fact_utils import FACT_FIELD_LABELS
from app.core.truth_safety import has_user_provided_facts, normalize_user_provided_facts


def _label_fact_fields(fields: list[str]) -> list[str]:
    """把事实字段名转换成人类可读标签。"""
    labels: list[str] = []
    for field in fields:
        field_key = str(field).strip()
        if not field_key:
            continue
        labels.append(FACT_FIELD_LABELS.get(field_key, field_key))
    return labels


def _extract_asset_urls(payload: dict[str, Any]) -> list[str]:
    """从组件 payload 中提取直接引用的图片 URL。"""
    urls: list[str] = []
    if not isinstance(payload, dict):
        return urls
    image_url = payload.get("image_url")
    if isinstance(image_url, str) and image_url.strip() and "example.com" not in image_url and "picsum.photos" not in image_url and "placeholder" not in image_url:
        urls.append(image_url.strip())
    for item in payload.get("image_urls") or []:
        if isinstance(item, str) and item.strip() and "example.com" not in item and "picsum.photos" not in item and "placeholder" not in item:
            urls.append(item.strip())
    return urls


def _is_placeholder_image_url(value: Any) -> bool:
    """过滤运行时遗留的假图链接。"""
    url = str(value or "").strip().lower()
    if not url:
        return False
    return any(token in url for token in ("example.com", "picsum.photos", "placeholder"))


def _sanitize_block_media_props(props: dict[str, Any] | None) -> dict[str, Any]:
    """统一清洗区块 props 里的图片字段。"""
    cleaned = deepcopy(props or {})
    if not isinstance(cleaned, dict):
        return {}
    if isinstance(cleaned.get("image_urls"), list):
        cleaned["image_urls"] = [
            str(item).strip()
            for item in (cleaned.get("image_urls") or [])
            if str(item or "").strip() and not _is_placeholder_image_url(item)
        ]
    if _is_placeholder_image_url(cleaned.get("image_url")):
        cleaned.pop("image_url", None)
    return cleaned


def _looks_precise_timestamp(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if "T" in text:
        return True
    return any(token in text for token in ("-", "/", ":", "年", "月", "日"))


def _timeline_period_label(index: int) -> str:
    labels = ["上午", "中午", "下午", "傍晚", "收尾"]
    return labels[min(index, len(labels) - 1)]


_PRECISE_TIME_PATTERNS = (
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"(?:凌晨|清晨|早上|上午|中午|下午|傍晚|晚上)?\s*\d{1,2}\s*(?:点|时)(?:\s*\d{1,2}\s*分|\s*半)?"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?\b"),
)


def _soften_precise_time_text(text: Any, fallback_label: str) -> str:
    raw_text = str(text or "").strip()
    if not raw_text:
        return ""
    softened = raw_text
    for pattern in _PRECISE_TIME_PATTERNS:
        softened = pattern.sub(fallback_label, softened)
    softened = re.sub(rf"(?:{fallback_label})[\s，,、]*(?:{fallback_label})+", fallback_label, softened)
    softened = re.sub(r"\s+", " ", softened).strip()
    return softened


def _extract_location_context_tokens(props: dict[str, Any]) -> list[str]:
    location_text = str(props.get("location") or "").strip()
    poi_text = str(props.get("poi_name") or "").strip()
    text = location_text or poi_text
    if not text:
        return []
    geo_tokens = re.findall(r"[\u4e00-\u9fff]{2,}?(?:市|区|县|镇|乡|街道|路|湾|湖|岛|山|海岸)", text)
    plain_tokens = [token for token in re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text) if token not in {"地点", "位置", "景点", "旅游"}]
    tokens: list[str] = []
    for token in [*geo_tokens, *plain_tokens]:
        cleaned = str(token).strip()
        if not cleaned or cleaned in tokens:
            continue
        tokens.append(cleaned)
        for suffix in ("市", "区", "县", "镇", "乡", "街道", "路", "湾", "湖", "岛", "山", "海岸"):
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
                short = cleaned[: -len(suffix)].strip()
                if len(short) >= 2 and short not in tokens:
                    tokens.append(short)
    return tokens


def _filter_location_binding_sources(props: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    context_tokens = _extract_location_context_tokens(props)
    if not context_tokens:
        return binding

    def _matches(item_text: str) -> bool:
        return any(token in item_text for token in context_tokens)

    next_binding = deepcopy(binding)
    source_items = [item for item in (binding.get("source_items") or []) if isinstance(item, dict)]
    filtered_source_items = []
    for item in source_items:
        haystack = " ".join(
            part
            for part in (
                str(item.get("label") or "").strip(),
                str(item.get("url") or "").strip(),
            )
            if part
        )
        if haystack and _matches(haystack):
            filtered_source_items.append(item)
    if filtered_source_items:
        next_binding["source_items"] = filtered_source_items
        next_binding["sources"] = [str(item.get("label") or "").strip() for item in filtered_source_items if str(item.get("label") or "").strip()]
    return next_binding


def _binding_count(block: dict[str, Any]) -> int:
    return len([item for item in (block.get("fact_bindings") or []) if isinstance(item, dict)])


def _has_location_confirmation(props: dict[str, Any], block: dict[str, Any]) -> bool:
    if props.get("lat") is not None and props.get("lng") is not None:
        return True
    return _binding_count(block) > 0


def _has_strong_radar_support(props: dict[str, Any], block: dict[str, Any]) -> bool:
    metrics = [item for item in (props.get("metrics") or []) if isinstance(item, dict)]
    if len(metrics) < 3:
        return False
    evidence_count = len([item for item in metrics if str(item.get("evidence") or "").strip()])
    return evidence_count >= 3 and _binding_count(block) > 0


def _representation_mode_for_block(
    *,
    block_type: str,
    props: dict[str, Any],
    block: dict[str, Any],
    active_archetype: str,
    representation_preferences: dict[str, Any],
    user_provided_facts: dict[str, Any],
) -> str:
    if block_type == "TimelineBlock":
        preferred = str(representation_preferences.get("timeline") or props.get("mode") or "recommended")
        if has_user_provided_facts(user_provided_facts) and preferred in {"user_journal", "user_provided"}:
            return "user_journal"
        if preferred == "confirmed" and _binding_count(block) > 0:
            return "confirmed"
        return "recommended"
    if block_type == "LocationBlock":
        preferred = str(representation_preferences.get("location") or props.get("mode") or "recommended")
        if preferred == "confirmed" and _has_location_confirmation(props, block):
            return "confirmed"
        return "recommended"
    if block_type == "WeatherPolaroid":
        preferred = str(representation_preferences.get("snapshot") or props.get("mode") or "ambience")
        if has_user_provided_facts(user_provided_facts) and preferred in {"confirmed_snapshot", "user_provided"}:
            return "confirmed_snapshot"
        if preferred == "confirmed_snapshot" and _binding_count(block) > 0:
            return "confirmed_snapshot"
        return "ambience"
    if block_type == "QuoteBlock":
        preferred = str(representation_preferences.get("quote") or props.get("mode") or "summary")
        if has_user_provided_facts(user_provided_facts) and preferred in {"user_quote", "user_provided"}:
            return "user_quote"
        if preferred == "source_quote" and _binding_count(block) > 0:
            return "source_quote"
        return "summary"
    if block_type == "ProductSpecCard":
        preferred = str(representation_preferences.get("spec_card") or props.get("mode") or "")
        if preferred:
            return preferred
        if active_archetype == "seeding":
            return "purchase_judgment"
        if active_archetype in {"gourmet", "food"}:
            return "store_facts"
        return "neutral_facts"
    if block_type == "RadarChartBlock":
        preferred = str(representation_preferences.get("radar") or props.get("mode") or "")
        if preferred == "scored_evidence" and _has_strong_radar_support(props, block):
            return "scored_evidence"
        return "judgment_summary"
    return str(props.get("mode") or "")


def _apply_representation_safety_to_block(
    block: dict[str, Any],
    *,
    active_archetype: str,
    representation_preferences: dict[str, Any],
    user_provided_facts: dict[str, Any],
) -> dict[str, Any]:
    next_block = deepcopy(block)
    props = _sanitize_block_media_props(next_block.get("props") or {})
    block_type = str(next_block.get("type") or "")
    mode = _representation_mode_for_block(
        block_type=block_type,
        props=props,
        block=next_block,
        active_archetype=active_archetype,
        representation_preferences=representation_preferences,
        user_provided_facts=user_provided_facts,
    )

    if block_type == "TimelineBlock":
        normalized_events: list[dict[str, Any]] = []
        for idx, raw_event in enumerate(props.get("events") or []):
            if not isinstance(raw_event, dict):
                continue
            timestamp = str(raw_event.get("timestamp") or "").strip()
            title = str(raw_event.get("title") or "").strip() or f"第{idx + 1}站"
            if mode == "recommended":
                time_label = timestamp if timestamp and not _looks_precise_timestamp(timestamp) else _timeline_period_label(idx)
                description = _soften_precise_time_text(raw_event.get("description"), time_label)
            else:
                time_label = timestamp or _timeline_period_label(idx)
                description = str(raw_event.get("description") or "").strip()
            normalized_events.append(
                {
                    "timestamp": time_label,
                    "title": title,
                    "description": description,
                }
            )
        props["events"] = normalized_events
        props["mode"] = mode
    elif block_type == "LocationBlock":
        props["mode"] = mode
        next_block["fact_bindings"] = [
            _filter_location_binding_sources(props, item) if isinstance(item, dict) else item
            for item in (next_block.get("fact_bindings") or [])
        ]
    elif block_type == "WeatherPolaroid":
        if mode != "confirmed_snapshot":
            props.pop("weather", None)
            props.pop("temperature", None)
            props.pop("time", None)
        props["mode"] = mode
    elif block_type == "QuoteBlock":
        props["mode"] = mode
    elif block_type == "ProductSpecCard":
        props["mode"] = mode
    elif block_type == "RadarChartBlock":
        props["mode"] = mode
    next_block["props"] = props
    return next_block


def _normalize_document_assets(
    image_assets: list[dict[str, Any]] | None,
    blocks: list[dict[str, Any]] | None,
    *,
    preferred_cover_url: str | None = None,
    existing_assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """把运行时素材列表归一化成文档级资产结构。"""
    normalized_assets = []
    normalized_blocks = [block for block in (blocks or []) if isinstance(block, dict)]
    existing_by_url = {
        str(asset.get("url") or ""): deepcopy(asset)
        for asset in (existing_assets or [])
        if isinstance(asset, dict) and asset.get("url")
    }
    for asset in deepcopy(image_assets or []):
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        asset_url = str(asset["url"])
        used_by_blocks = []
        for block in normalized_blocks:
            asset_refs = list(block.get("asset_refs") or [])
            props = block.get("props") or {}
            if not asset_refs:
                asset_refs = _extract_asset_urls(props)
            if asset_url in asset_refs:
                used_by_blocks.append(str(block.get("id") or ""))
        previous_asset = existing_by_url.get(asset_url, {})
        previous_role = str(previous_asset.get("role") or asset.get("role") or "supporting")
        if preferred_cover_url and asset_url == preferred_cover_url:
            normalized_role = "cover"
        elif previous_role == "cover":
            normalized_role = "supporting"
        else:
            normalized_role = previous_role
        normalized_assets.append({
            "id": asset.get("id") or previous_asset.get("id") or asset_url,
            "url": asset_url,
            "desc": asset.get("desc") or previous_asset.get("desc", ""),
            "source_type": asset.get("source_type") or previous_asset.get("source_type", "unknown"),
            "query": asset.get("query") or previous_asset.get("query"),
            "role": normalized_role,
            "locked": bool(asset.get("locked", previous_asset.get("locked", False))),
            "selection_state": asset.get("selection_state") or previous_asset.get("selection_state", "available"),
            "source_reason": asset.get("source_reason") or previous_asset.get("source_reason") or asset.get("desc", ""),
            "used_by_blocks": [block_id for block_id in used_by_blocks if block_id],
        })
    return normalized_assets


def _normalize_cover_asset_roles(
    assets: list[dict[str, Any]] | None,
    preferred_cover_url: str | None,
) -> list[dict[str, Any]]:
    """根据封面偏好统一资产角色，避免“选封面”等于提前生成封面块。"""
    normalized_assets: list[dict[str, Any]] = []
    for asset in deepcopy(assets or []):
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        next_asset = deepcopy(asset)
        if preferred_cover_url and str(next_asset.get("url") or "") == preferred_cover_url:
            next_asset["role"] = "cover"
        elif str(next_asset.get("role") or "") == "cover":
            next_asset["role"] = "supporting"
        normalized_assets.append(next_asset)
    return normalized_assets


def _pick_grounding_source_items(
    knowledge: dict[str, Any],
    preferred_scope: str | None = None,
    limit: int = 3,
) -> list[dict[str, str]]:
    """按来源范围挑选最适合展示的 grounding 引用，并保留标题与链接。"""
    sources = [item for item in (knowledge.get("fact_sources") or []) if isinstance(item, dict)]
    picked: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _collect(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
        collected: list[dict[str, str]] = []
        for item in rows:
            label = str(item.get("title") or item.get("url") or "").strip()
            url = str(item.get("url") or "").strip()
            if not label:
                continue
            key = (label, url)
            if key in seen:
                continue
            seen.add(key)
            collected.append({
                "label": label,
                "url": url,
                "source_scope": str(item.get("source_scope") or "").strip(),
            })
            if len(collected) >= limit:
                break
        return collected

    if preferred_scope:
        scoped_rows = [
            item for item in sources
            if str(item.get("source_scope") or "").strip() == preferred_scope
        ]
        picked = _collect(scoped_rows)
        if picked:
            return picked[:limit]

    return _collect(sources)[:limit]


def _pick_grounding_sources(knowledge: dict[str, Any], preferred_scope: str | None = None, limit: int = 3) -> list[str]:
    """按来源范围挑选最适合展示的 grounding 引用。"""
    return [item["label"] for item in _pick_grounding_source_items(knowledge, preferred_scope=preferred_scope, limit=limit)]


def _merge_binding_into_meta(meta: dict[str, Any] | None, binding: dict[str, Any] | None) -> dict[str, Any]:
    """把块级或字段级 binding 投影回 props 元数据。"""
    next_meta = deepcopy(meta or {})
    safe_binding = binding if isinstance(binding, dict) else {}

    sources = list(next_meta.get("sources") or [])
    for source in safe_binding.get("sources") or []:
        source_text = str(source or "").strip()
        if source_text and source_text not in sources:
            sources.append(source_text)
    if sources:
        next_meta["sources"] = sources

    source_items = [
        item
        for item in (next_meta.get("source_items") or [])
        if isinstance(item, dict) and str(item.get("label") or "").strip()
    ]
    seen_source_items = {
        f'{str(item.get("label") or "").strip()}::{str(item.get("url") or "").strip()}'
        for item in source_items
    }
    for item in safe_binding.get("source_items") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if not label:
            continue
        key = f"{label}::{url}"
        if key in seen_source_items:
            continue
        seen_source_items.add(key)
        source_items.append(
            {
                "label": label,
                "url": url,
                "source_scope": str(item.get("source_scope") or "").strip(),
            }
        )
    if source_items:
        next_meta["source_items"] = source_items

    if safe_binding.get("confidence"):
        next_meta["confidence"] = safe_binding.get("confidence")
    if safe_binding.get("hint") and not next_meta.get("hint"):
        next_meta["hint"] = safe_binding.get("hint")
    if safe_binding.get("kind") and not next_meta.get("kind"):
        next_meta["kind"] = safe_binding.get("kind")
    if safe_binding.get("fact_fields"):
        next_meta["fields"] = [str(field) for field in (safe_binding.get("fact_fields") or []) if str(field).strip()]
    return next_meta


def _project_fact_bindings_into_props(
    *,
    block_type: str,
    props: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    """把绑定信息继续投影到 props 的段落/字段元数据，供前端按项展示来源。"""
    next_props = deepcopy(props or {})
    if not bindings:
        return next_props

    if block_type == "StoryText":
        paragraph_meta = list(next_props.get("paragraph_meta") or [])
        paragraphs = list(next_props.get("paragraphs") or [])
        while len(paragraph_meta) < len(paragraphs):
            paragraph_meta.append({})

        sections = list(next_props.get("sections") or [])
        for binding in bindings:
            field = str(binding.get("field") or "")
            if field.startswith("paragraphs[") and field.endswith("]"):
                try:
                    paragraph_index = int(field[len("paragraphs[") : -1])
                except ValueError:
                    continue
                if 0 <= paragraph_index < len(paragraph_meta):
                    paragraph_meta[paragraph_index] = _merge_binding_into_meta(paragraph_meta[paragraph_index], binding)
                if 0 <= paragraph_index < len(sections):
                    sections[paragraph_index] = _merge_binding_into_meta(sections[paragraph_index], binding)

        if paragraph_meta:
            next_props["paragraph_meta"] = paragraph_meta
        if sections:
            next_props["sections"] = sections
        return next_props

    if block_type == "ProductSpecCard":
        feature_meta = list(next_props.get("feature_meta") or [])
        core_features = list(next_props.get("core_features") or [])
        while len(feature_meta) < len(core_features):
            feature_meta.append({})

        spec_items = list(next_props.get("spec_items") or [])
        for binding in bindings:
            field = str(binding.get("field") or "")
            if field.startswith("core_features[") and field.endswith("]"):
                try:
                    feature_index = int(field[len("core_features[") : -1])
                except ValueError:
                    continue
                if 0 <= feature_index < len(feature_meta):
                    feature_meta[feature_index] = _merge_binding_into_meta(feature_meta[feature_index], binding)
                if 0 <= feature_index < len(spec_items) and isinstance(spec_items[feature_index], dict):
                    spec_items[feature_index] = _merge_binding_into_meta(spec_items[feature_index], binding)

        if feature_meta:
            next_props["feature_meta"] = feature_meta
        if spec_items:
            next_props["spec_items"] = spec_items
        return next_props

    if block_type == "RadarChartBlock":
        metrics = list(next_props.get("metrics") or [])
        score_binding = next((item for item in bindings if str(item.get("field") or "") == "scores"), None)
        if score_binding and metrics:
            next_props["metrics"] = [
                _merge_binding_into_meta(metric if isinstance(metric, dict) else {}, score_binding)
                for metric in metrics
            ]
        return next_props

    return next_props


def _build_retrieval_fact_bindings(
    *,
    block_type: str,
    props: dict[str, Any],
    knowledge: dict[str, Any],
) -> list[dict[str, Any]]:
    """按组件类型生成 block 级 retrieval grounding 绑定。"""
    if not isinstance(knowledge, dict) or not (knowledge.get("fact_sources") or knowledge.get("confirmed_facts")):
        return []

    bindings: list[dict[str, Any]] = []
    if block_type == "ProductSpecCard" and props.get("core_features"):
        bindings.append({
            "field": "core_features",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "confidence": str(knowledge.get("fact_confidence") or "medium"),
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "source_items": _pick_grounding_source_items(knowledge, preferred_scope="official"),
            "hint": "该参数卡引用了本轮检索到的官方/高可信资料",
        })
    elif block_type == "StoryText" and props.get("paragraphs"):
        bindings.append({
            "field": "paragraphs[0]",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "confidence": str(knowledge.get("fact_confidence") or "medium"),
            "sources": _pick_grounding_sources(knowledge, preferred_scope="review"),
            "source_items": _pick_grounding_source_items(knowledge, preferred_scope="review"),
            "hint": "该段正文引用了本轮检索证据或已确认事实",
        })
    elif block_type == "LocationBlock":
        bindings.append({
            "field": "poi_name",
            "fact_fields": [],
            "fact_field_labels": [],
            "kind": "retrieval_grounded",
            "confidence": str(knowledge.get("fact_confidence") or "medium"),
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "source_items": _pick_grounding_source_items(knowledge, preferred_scope="official"),
            "hint": "该地点信息引用了本轮检索资料",
        })
    elif block_type == "RadarChartBlock" and props.get("scores"):
        bindings.append({
            "field": "scores",
            "fact_fields": [str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()],
            "fact_field_labels": _label_fact_fields([str(field) for field in (knowledge.get("confirmed_facts") or {}).keys()]),
            "kind": "retrieval_grounded",
            "confidence": str(knowledge.get("fact_confidence") or "medium"),
            "sources": _pick_grounding_sources(knowledge, preferred_scope="official"),
            "source_items": _pick_grounding_source_items(knowledge, preferred_scope="official"),
            "hint": "该评分概览由本轮检索证据支撑",
        })
    elif block_type == "VersusCard" and (props.get("pros") or props.get("cons") or props.get("proText") or props.get("conText")):
        bindings.append({
            "field": "comparison_copy",
            "fact_fields": [],
            "fact_field_labels": [],
            "kind": "retrieval_grounded",
            "confidence": str(knowledge.get("fact_confidence") or "medium"),
            "sources": _pick_grounding_sources(knowledge, preferred_scope="review"),
            "source_items": _pick_grounding_source_items(knowledge, preferred_scope="review"),
            "hint": "该对比结论综合了本轮检索到的口碑/评价来源",
        })
    return [item for item in bindings if item.get("sources")]


def _apply_retrieval_grounding_to_document(note_document: dict[str, Any] | None, knowledge: dict[str, Any] | None) -> dict[str, Any]:
    """把检索到的 grounding 绑定应用到整份文档。"""
    document = deepcopy(note_document or {})
    safe_knowledge = knowledge if isinstance(knowledge, dict) else {}
    if not safe_knowledge:
        return document

    blocks = []
    top_level_fact_bindings = []
    for block in document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        next_block = deepcopy(block)
        existing_bindings = [item for item in (next_block.get("fact_bindings") or []) if isinstance(item, dict)]
        derived_bindings = _build_retrieval_fact_bindings(
            block_type=str(next_block.get("type") or ""),
            props=deepcopy(next_block.get("props") or {}),
            knowledge=safe_knowledge,
        )
        merged_bindings = existing_bindings[:]
        existing_fields = {str(item.get("field") or "") for item in existing_bindings}
        for item in derived_bindings:
            if str(item.get("field") or "") not in existing_fields:
                merged_bindings.append(item)
        next_block["props"] = _project_fact_bindings_into_props(
            block_type=str(next_block.get("type") or ""),
            props=deepcopy(next_block.get("props") or {}),
            bindings=merged_bindings,
        )
        next_block["fact_bindings"] = merged_bindings
        blocks.append(next_block)
        if merged_bindings:
            top_level_fact_bindings.append({"block_id": str(next_block.get("id") or ""), "bindings": merged_bindings})

    document["blocks"] = blocks
    document["fact_bindings"] = top_level_fact_bindings
    return document


def _apply_representation_safety_to_document(
    note_document: dict[str, Any] | None,
    *,
    representation_preferences: dict[str, Any] | None = None,
    user_provided_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = deepcopy(note_document or {})
    active_archetype = str(((document.get("document_meta") or {}).get("active_archetype")) or "seeding")
    safe_preferences = deepcopy(representation_preferences or {})
    safe_user_facts = normalize_user_provided_facts(user_provided_facts or {})
    blocks = []
    for block in document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        blocks.append(
            _apply_representation_safety_to_block(
                block,
                active_archetype=active_archetype,
                representation_preferences=safe_preferences,
                user_provided_facts=safe_user_facts,
            )
        )
    document["blocks"] = blocks
    return document


def build_note_document(
    *,
    document_view: dict[str, Any] | None = None,
    block_style_map: dict[str, Any] | None = None,
    image_assets: list[dict[str, Any]] | None = None,
    patch_tracks: dict[str, Any] | None = None,
    selected_element_id: str | None = None,
    active_panel: str | None = None,
    scenarios: list[str] | None = None,
    active_archetype: str | None = None,
    retrieved_knowledge: dict[str, Any] | None = None,
    planner_output: dict[str, Any] | None = None,
    representation_preferences: dict[str, Any] | None = None,
    user_provided_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从 document_view / style / assets 等运行态材料构造正式 NoteDocument。"""
    data = deepcopy(document_view or {})
    styles = deepcopy(block_style_map or {})
    assets = deepcopy(image_assets or [])
    tracks = deepcopy(patch_tracks or {})
    knowledge = deepcopy(retrieved_knowledge or {})
    blocks = []
    top_level_fact_bindings = []

    block_list = list(data.get("blocks") or [])
    for index, block in enumerate(block_list):
        block_id = str(block.get("id") or f"block_{index}")
        component_type = normalize_component_type(block.get("component_type")) or str(block.get("component_type") or "")
        props = _sanitize_block_media_props(data.get(block_id, {}) or {})
        block_style = deepcopy(styles.get(block_id, {}) or {})
        asset_refs = _extract_asset_urls(props)
        block_fact_bindings = []
        component_entry = get_component_entry(component_type) or {}
        editable_targets = get_editable_targets(component_type)

        paragraph_meta = props.get("paragraph_meta") or []
        for paragraph_index, meta in enumerate(paragraph_meta):
            if isinstance(meta, dict) and (meta.get("sources") or meta.get("hint")):
                fact_fields = [str(item) for item in (meta.get("fields") or []) if str(item).strip()]
                block_fact_bindings.append({
                    "field": f"paragraphs[{paragraph_index}]",
                    "fact_fields": fact_fields,
                    "fact_field_labels": _label_fact_fields(fact_fields),
                    "kind": meta.get("kind") or "default",
                    "confidence": meta.get("confidence") or ("high" if (meta.get("kind") or "default") == "verified" else ("low" if (meta.get("kind") or "default") == "caution" else "medium")),
                    "sources": list(meta.get("sources") or []),
                    "source_items": deepcopy(meta.get("source_items") or []),
                    "hint": meta.get("hint"),
                })

        feature_meta = props.get("feature_meta") or []
        for feature_index, meta in enumerate(feature_meta):
            if isinstance(meta, dict) and (meta.get("sources") or meta.get("hint")):
                fact_fields = []
                if meta.get("field"):
                    fact_fields.append(str(meta.get("field")))
                for field_name in meta.get("fields") or []:
                    field_text = str(field_name).strip()
                    if field_text and field_text not in fact_fields:
                        fact_fields.append(field_text)
                block_fact_bindings.append({
                    "field": f"core_features[{feature_index}]",
                    "fact_fields": fact_fields,
                    "fact_field_labels": _label_fact_fields(fact_fields),
                    "kind": meta.get("kind") or "default",
                    "confidence": meta.get("confidence") or ("high" if (meta.get("kind") or "default") == "verified" else ("low" if (meta.get("kind") or "default") == "caution" else "medium")),
                    "sources": list(meta.get("sources") or []),
                    "source_items": deepcopy(meta.get("source_items") or []),
                    "hint": meta.get("hint"),
                })

        blocks.append({
            "id": block_id,
            "type": component_type,
            "label": component_entry.get("label") or component_type,
            "semantic_role": component_entry.get("semantic_role") or "content",
            "content_brief": block.get("content_brief", ""),
            "props": props,
            "style": block_style,
            "asset_refs": asset_refs,
            "fact_bindings": block_fact_bindings,
            "editable_targets": editable_targets,
            "asset_support": get_asset_support(component_type),
            "fact_binding_support": bool(component_entry.get("fact_binding_support")),
            "order": index,
        })
        if block_fact_bindings:
            top_level_fact_bindings.append({"block_id": block_id, "bindings": block_fact_bindings})

    cover_asset_url = str(
        next(
            (
                item.get("url")
                for item in (assets or [])
                if isinstance(item, dict) and str(item.get("role") or "") == "cover" and str(item.get("url") or "").strip()
            ),
            "",
        )
    ).strip() or None
    normalized_assets = _normalize_document_assets(assets, blocks, preferred_cover_url=cover_asset_url)

    document = {
        "document_meta": {
            "title": data.get("page_title") or "XHS-Forge Note",
            "active_archetype": active_archetype or "seeding",
            "scenarios": list(scenarios or [active_archetype or "seeding"]),
        },
        "theme": {
            "page_theme": deepcopy(data.get("page_theme") or {}),
            "global_vars": deepcopy(styles.get("global_vars") or {}),
        },
        "blocks": blocks,
        "assets": normalized_assets,
        "fact_bindings": top_level_fact_bindings,
        "provenance": {
            "fact_sources": deepcopy(knowledge.get("fact_sources") or []),
            "fact_conflicts": deepcopy(knowledge.get("fact_conflicts") or []),
            "confirmed_facts": deepcopy(knowledge.get("confirmed_facts") or {}),
            "fact_review_status": knowledge.get("fact_review_status") or "clear",
        },
        "ui_state": {
            "selected_element_id": selected_element_id,
            "active_panel": active_panel or "main",
            "patch_tracks": tracks,
            "cover_asset_url": cover_asset_url,
            "representation_preferences": deepcopy(representation_preferences or {}),
        },
        "planner": deepcopy(planner_output or {}),
    }
    return _apply_representation_safety_to_document(
        _apply_retrieval_grounding_to_document(document, knowledge),
        representation_preferences=representation_preferences,
        user_provided_facts=user_provided_facts,
    )


def note_document_to_document_view(note_document: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """把正式 NoteDocument 投影回紧凑 document_view + style_map + assets。"""
    note_document = deepcopy(note_document or {})
    document_view: dict[str, Any] = {
        "page_title": ((note_document.get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "page_theme": deepcopy(((note_document.get("theme") or {}).get("page_theme") or {})),
        "blocks": [],
    }
    block_style_map: dict[str, Any] = {
        "global_vars": deepcopy(((note_document.get("theme") or {}).get("global_vars") or {})),
    }

    for block in note_document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        component_type = normalize_component_type(block.get("type")) or str(block.get("type") or "")
        if not block_id or not component_type:
            continue
        document_view["blocks"].append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": block.get("content_brief", ""),
        })
        document_view[block_id] = deepcopy(block.get("props") or {})
        block_style_map[block_id] = deepcopy(block.get("style") or {})

    image_assets = []
    for asset in note_document.get("assets") or []:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        image_assets.append({
            "url": asset.get("url"),
            "desc": asset.get("desc", ""),
            "source_type": asset.get("source_type"),
            "query": asset.get("query"),
            "locked": asset.get("locked", False),
            "selection_state": asset.get("selection_state"),
            "source_reason": asset.get("source_reason"),
        })
    return document_view, block_style_map, image_assets


def build_note_document_layout(note_document: dict[str, Any] | None) -> dict[str, Any]:
    """生成只读布局视图，供渲染器和分发逻辑快速消费。"""
    note_document = deepcopy(note_document or {})
    blocks: list[dict[str, Any]] = []
    for index, block in enumerate(note_document.get("blocks") or []):
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or f"block_{index}")
        component_type = normalize_component_type(block.get("type")) or str(block.get("type") or "")
        if not component_type:
            continue
        blocks.append({
            "id": block_id,
            "component_type": component_type,
            "content_brief": block.get("content_brief", ""),
            "props": _sanitize_block_media_props(block.get("props") or {}),
            "style": deepcopy(block.get("style") or {}),
            "semantic_role": block.get("semantic_role") or "content",
            "editable_targets": deepcopy(block.get("editable_targets") or []),
            "asset_support": block.get("asset_support") or get_asset_support(component_type),
            "fact_binding_support": bool(block.get("fact_binding_support")),
        })

    return {
        "page_title": ((note_document.get("document_meta") or {}).get("title") or "XHS-Forge Note"),
        "page_theme": deepcopy(((note_document.get("theme") or {}).get("page_theme") or {})),
        "global_vars": deepcopy(((note_document.get("theme") or {}).get("global_vars") or {})),
        "blocks": blocks,
        "assets": deepcopy(note_document.get("assets") or []),
    }


def build_note_document_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """从运行时 state 折叠出当前的正式 NoteDocument。"""
    state = state or {}
    existing = deepcopy(state.get("note_document") or {})
    if isinstance(existing, dict) and existing.get("blocks") is not None:
        document_meta = existing.setdefault("document_meta", {})
        ui_state = existing.setdefault("ui_state", {})
        provenance = existing.setdefault("provenance", {})
        planner = existing.setdefault("planner", {})
        cleaned_blocks: list[dict[str, Any]] = []
        for block in existing.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            next_block = deepcopy(block)
            next_block["props"] = _sanitize_block_media_props(next_block.get("props") or {})
            next_block["asset_refs"] = [
                ref for ref in (next_block.get("asset_refs") or [])
                if str(ref or "").strip() and not _is_placeholder_image_url(ref)
            ]
            cleaned_blocks.append(next_block)
        existing["blocks"] = cleaned_blocks

        if state.get("active_archetype"):
            document_meta["active_archetype"] = state.get("active_archetype")
        if state.get("scenarios"):
            document_meta["scenarios"] = list(state.get("scenarios") or [])
        if state.get("selected_element_id") is not None:
            ui_state["selected_element_id"] = state.get("selected_element_id")
        if state.get("active_panel"):
            ui_state["active_panel"] = state.get("active_panel")
        if state.get("patch_tracks") is not None:
            ui_state["patch_tracks"] = deepcopy(state.get("patch_tracks") or {})
        if state.get("representation_preferences") is not None:
            ui_state["representation_preferences"] = deepcopy(state.get("representation_preferences") or {})
        if isinstance(state.get("retrieved_knowledge"), dict):
            knowledge = state.get("retrieved_knowledge") or {}
            provenance["fact_sources"] = deepcopy(knowledge.get("fact_sources") or provenance.get("fact_sources") or [])
            provenance["fact_conflicts"] = deepcopy(knowledge.get("fact_conflicts") or provenance.get("fact_conflicts") or [])
            provenance["confirmed_facts"] = deepcopy(knowledge.get("confirmed_facts") or provenance.get("confirmed_facts") or {})
            provenance["fact_review_status"] = knowledge.get("fact_review_status") or provenance.get("fact_review_status") or "clear"
        if state.get("planner_output") is not None:
            existing["planner"] = deepcopy(state.get("planner_output") or {})
        if state.get("image_assets") is not None:
            existing["assets"] = _normalize_document_assets(
                state.get("image_assets") or [],
                existing.get("blocks") or [],
                preferred_cover_url=str(ui_state.get("cover_asset_url") or "").strip() or None,
                existing_assets=existing.get("assets") or [],
            )
        return _apply_representation_safety_to_document(
            _apply_retrieval_grounding_to_document(existing, state.get("retrieved_knowledge") or {}),
            representation_preferences=ui_state.get("representation_preferences") or state.get("representation_preferences") or {},
            user_provided_facts=state.get("user_provided_facts") or {},
        )

    document = {
        "document_meta": {
            "title": "XHS-Forge Note",
            "active_archetype": state.get("active_archetype") or "seeding",
            "scenarios": list(state.get("scenarios") or [state.get("active_archetype") or "seeding"]),
        },
        "theme": {
            "page_theme": {},
            "global_vars": {},
        },
        "blocks": [],
        "assets": _normalize_document_assets(state.get("image_assets") or [], []),
        "fact_bindings": [],
        "provenance": {
            "fact_sources": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_sources") or []),
            "fact_conflicts": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_conflicts") or []),
            "confirmed_facts": deepcopy(((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("confirmed_facts") or {}),
            "fact_review_status": (((state.get("retrieved_knowledge") or {}) if isinstance(state.get("retrieved_knowledge"), dict) else {}).get("fact_review_status") or "clear"),
        },
        "ui_state": {
            "selected_element_id": state.get("selected_element_id"),
            "active_panel": state.get("active_panel") or "main",
            "patch_tracks": deepcopy(state.get("patch_tracks") or {}),
            "cover_asset_url": None,
            "representation_preferences": deepcopy(state.get("representation_preferences") or {}),
        },
        "planner": deepcopy(state.get("planner_output") or {}),
    }
    return _apply_representation_safety_to_document(
        _apply_retrieval_grounding_to_document(document, state.get("retrieved_knowledge") or {}),
        representation_preferences=state.get("representation_preferences") or {},
        user_provided_facts=state.get("user_provided_facts") or {},
    )


def build_note_document_layout_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """把运行时 state 直接投影成标准化布局视图。"""
    return build_note_document_layout(build_note_document_from_state(state))


def build_note_document_editing_context(
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """构造编辑器所需的紧凑上下文：文档、视图、样式映射和素材列表。"""
    note_document = build_note_document_from_state(state)
    document_view, block_style_map, image_assets = note_document_to_document_view(note_document)
    return note_document, document_view, block_style_map, image_assets


def build_document_view_from_note_document(note_document: dict[str, Any] | None) -> dict[str, Any]:
    """测试兼容包装：从 NoteDocument 生成 document_view。"""
    return build_note_document_layout(note_document)


def build_document_view_from_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """测试兼容包装：从 state 生成 document_view。"""
    return build_note_document_layout_from_state(state)


def build_document_editing_context_from_state(
    state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """测试兼容包装：从 state 生成编辑上下文。"""
    return build_note_document_editing_context(state)


def update_note_document_block(
    note_document: dict[str, Any] | None,
    block_id: str,
    *,
    props: dict[str, Any] | None = None,
    style: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """更新单个区块的 props / style / 元数据。"""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    for block in blocks:
        if str(block.get("id") or "") != str(block_id):
            continue
        if props is not None:
            block["props"] = deepcopy(props)
        if style is not None:
            block["style"] = deepcopy(style)
        if metadata:
            for key, value in metadata.items():
                block[key] = deepcopy(value)
        break
    document["blocks"] = blocks
    return document


def update_note_document_theme(
    note_document: dict[str, Any] | None,
    *,
    page_theme: dict[str, Any] | None = None,
    global_vars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """更新文档级主题信息。"""
    document = deepcopy(note_document or {})
    theme = document.setdefault("theme", {})
    if page_theme is not None:
        theme["page_theme"] = deepcopy(page_theme)
    if global_vars is not None:
        theme["global_vars"] = deepcopy(global_vars)
    return document


def update_note_document_title(note_document: dict[str, Any] | None, title: str) -> dict[str, Any]:
    """更新文档标题。"""
    document = deepcopy(note_document or {})
    meta = document.setdefault("document_meta", {})
    meta["title"] = title
    return document


def update_note_document_cover_preference(
    note_document: dict[str, Any] | None,
    cover_asset_url: str | None,
) -> dict[str, Any]:
    """只记录封面素材偏好，不提前物化封面区块。"""
    document = deepcopy(note_document or {})
    ui_state = document.setdefault("ui_state", {})
    normalized_cover_url = str(cover_asset_url or "").strip() or None
    ui_state["cover_asset_url"] = normalized_cover_url
    document["assets"] = _normalize_cover_asset_roles(document.get("assets") or [], normalized_cover_url)
    return document


def update_note_document_asset_preferences(
    note_document: dict[str, Any] | None,
    asset_url: str,
    *,
    role: str | None = None,
    locked: bool | None = None,
    selection_state: str | None = None,
) -> dict[str, Any]:
    """更新单个文档资产的使用偏好，并同步封面偏好。"""
    document = deepcopy(note_document or {})
    normalized_url = str(asset_url or "").strip()
    if not normalized_url:
        return document

    ui_state = document.setdefault("ui_state", {})
    normalized_role = str(role or "").strip() or None
    normalized_selection_state = str(selection_state or "").strip() or None

    updated_assets: list[dict[str, Any]] = []
    asset_exists = False
    for asset in document.get("assets") or []:
        if not isinstance(asset, dict) or not asset.get("url"):
            continue
        next_asset = deepcopy(asset)
        if str(next_asset.get("url") or "") == normalized_url:
            asset_exists = True
            if normalized_role is not None:
                next_asset["role"] = normalized_role
            if locked is not None:
                next_asset["locked"] = bool(locked)
            if normalized_selection_state is not None:
                next_asset["selection_state"] = normalized_selection_state
                if normalized_selection_state == "excluded":
                    next_asset["locked"] = False
                    if str(next_asset.get("role") or "") == "cover":
                        next_asset["role"] = "supporting"
            if normalized_role == "cover":
                next_asset["selection_state"] = "available"
        updated_assets.append(next_asset)

    if not asset_exists:
        updated_assets.append({
            "id": normalized_url,
            "url": normalized_url,
            "desc": "",
            "source_type": "unknown",
            "query": None,
            "role": normalized_role or "supporting",
            "locked": bool(locked),
            "selection_state": normalized_selection_state or "available",
            "source_reason": "",
            "used_by_blocks": [],
        })

    if normalized_role == "cover":
        ui_state["cover_asset_url"] = normalized_url
        document["assets"] = _normalize_cover_asset_roles(updated_assets, normalized_url)
    else:
        current_cover_url = str(ui_state.get("cover_asset_url") or "").strip()
        if current_cover_url == normalized_url and (
            normalized_selection_state == "excluded" or normalized_role in {"inline", "supporting"}
        ):
            ui_state["cover_asset_url"] = None
        document["assets"] = _normalize_cover_asset_roles(updated_assets, str(ui_state.get("cover_asset_url") or "").strip() or None)
    return document


def remove_note_document_asset(
    note_document: dict[str, Any] | None,
    asset_url: str,
) -> dict[str, Any]:
    """删除文档资产，并同步清理封面偏好与区块中的直接图片引用。"""
    document = deepcopy(note_document or {})
    normalized_url = str(asset_url or "").strip()
    if not normalized_url:
        return document

    document["assets"] = [
        deepcopy(asset)
        for asset in (document.get("assets") or [])
        if isinstance(asset, dict) and str(asset.get("url") or "") != normalized_url
    ]

    ui_state = document.setdefault("ui_state", {})
    if str(ui_state.get("cover_asset_url") or "") == normalized_url:
        ui_state["cover_asset_url"] = None

    cleaned_blocks: list[dict[str, Any]] = []
    for block in document.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        next_block = deepcopy(block)
        next_block["asset_refs"] = [
            ref for ref in (next_block.get("asset_refs") or [])
            if str(ref or "") != normalized_url
        ]
        props = deepcopy(next_block.get("props") or {})
        if isinstance(props.get("image_urls"), list):
            props["image_urls"] = [
                item for item in props.get("image_urls") or []
                if str(item or "") != normalized_url and not _is_placeholder_image_url(item)
            ]
        if str(props.get("image_url") or "") == normalized_url or _is_placeholder_image_url(props.get("image_url")):
            props.pop("image_url", None)
        next_block["props"] = props
        cleaned_blocks.append(next_block)

    document["blocks"] = cleaned_blocks
    return document


def replace_note_document_blocks(note_document: dict[str, Any] | None, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """整批替换文档区块列表。"""
    document = deepcopy(note_document or {})
    document["blocks"] = deepcopy(blocks)
    return document


def append_note_document_block(
    note_document: dict[str, Any] | None,
    block: dict[str, Any],
    *,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在文档尾部追加一个区块，并补齐 block 能力元数据。"""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    component_type = normalize_component_type(block.get("component_type")) or str(block.get("type") or block.get("component_type") or "")
    block_id = str(block.get("id") or "")
    component_entry = get_component_entry(component_type) or {}
    if not block_id or not component_type:
        return document
    blocks.append({
        "id": block_id,
        "type": component_type,
        "label": component_entry.get("label") or component_type,
        "semantic_role": component_entry.get("semantic_role") or "content",
        "content_brief": block.get("content_brief", ""),
        "props": deepcopy(props or {}),
        "style": {},
        "asset_refs": [],
        "fact_bindings": [],
        "editable_targets": get_editable_targets(component_type),
        "asset_support": get_asset_support(component_type),
        "fact_binding_support": bool(component_entry.get("fact_binding_support")),
        "order": len(blocks),
    })
    for index, item in enumerate(blocks):
        item["order"] = index
    document["blocks"] = blocks
    return document


def insert_note_document_block(
    note_document: dict[str, Any] | None,
    block: dict[str, Any],
    index: int,
    *,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在指定位置插入一个区块，并补齐 block 能力元数据。"""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    component_type = normalize_component_type(block.get("component_type")) or str(block.get("type") or block.get("component_type") or "")
    block_id = str(block.get("id") or "")
    component_entry = get_component_entry(component_type) or {}
    if not block_id or not component_type:
        return document
    safe_index = min(max(0, index), len(blocks))
    blocks.insert(safe_index, {
        "id": block_id,
        "type": component_type,
        "label": component_entry.get("label") or component_type,
        "semantic_role": component_entry.get("semantic_role") or "content",
        "content_brief": block.get("content_brief", ""),
        "props": deepcopy(props or {}),
        "style": {},
        "asset_refs": [],
        "fact_bindings": [],
        "editable_targets": get_editable_targets(component_type),
        "asset_support": get_asset_support(component_type),
        "fact_binding_support": bool(component_entry.get("fact_binding_support")),
        "order": safe_index,
    })
    for new_index, item in enumerate(blocks):
        item["order"] = new_index
    document["blocks"] = blocks
    return document


def remove_note_document_block(note_document: dict[str, Any] | None, block_id: str) -> dict[str, Any]:
    """按 block_id 删除一个区块。"""
    document = deepcopy(note_document or {})
    blocks = [block for block in (document.get("blocks") or []) if str(block.get("id") or "") != str(block_id)]
    for index, block in enumerate(blocks):
        block["order"] = index
    document["blocks"] = blocks
    return document


def build_note_document_from_structure_patch(
    note_document: dict[str, Any] | None,
    *,
    page_title: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    component_payloads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """基于结构化补丁更新标题和区块骨架。"""
    document = deepcopy(note_document or {})
    current_blocks = list(document.get("blocks") or [])
    current_by_id = {
        str(block.get("id") or ""): deepcopy(block)
        for block in current_blocks
        if isinstance(block, dict) and block.get("id")
    }
    component_payloads = deepcopy(component_payloads or {})

    next_blocks: list[dict[str, Any]] = []
    for order, block in enumerate(blocks or []):
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "")
        component_type = normalize_component_type(block.get("component_type")) or str(block.get("component_type") or "")
        if not block_id or not component_type:
            continue
        current_block = current_by_id.get(block_id, {})
        component_entry = get_component_entry(component_type) or {}
        next_blocks.append({
            "id": block_id,
            "type": component_type,
            "label": component_entry.get("label") or component_type,
            "semantic_role": component_entry.get("semantic_role") or current_block.get("semantic_role") or "content",
            "content_brief": block.get("content_brief", ""),
            "props": deepcopy(component_payloads.get(block_id) or current_block.get("props") or {}),
            "style": deepcopy(current_block.get("style") or {}),
            "asset_refs": deepcopy(current_block.get("asset_refs") or []),
            "fact_bindings": deepcopy(current_block.get("fact_bindings") or []),
            "editable_targets": deepcopy(current_block.get("editable_targets") or get_editable_targets(component_type)),
            "asset_support": current_block.get("asset_support") or get_asset_support(component_type),
            "fact_binding_support": bool(
                current_block.get("fact_binding_support")
                if current_block.get("fact_binding_support") is not None
                else component_entry.get("fact_binding_support")
            ),
            "order": order,
        })

    document["blocks"] = next_blocks
    if page_title is not None:
        meta = document.setdefault("document_meta", {})
        meta["title"] = page_title or "XHS-Forge Note"
    return document
