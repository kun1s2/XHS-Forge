import re


_QUOTED_PATTERNS = (
    r"「([^」]+)」",
    r"“([^”]+)”",
    r'"([^"]+)"',
)

_PRODUCT_ENTITY_PATTERNS = (
    r"((?:华为|Huawei)\s*(?:Mate|Pura|nova|MateBook)\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:荣耀|Honor)\s*(?:Magic|GT|X|Play)\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:小米|Xiaomi)\s*(?:\d+|Mix\s*\d+|Civi\s*\d+|Pad\s*\d+)[A-Za-z0-9 +\-]*)",
    r"((?:红米|Redmi)\s*(?:K|Note|Turbo)\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:OPPO)\s*(?:Find|Reno|Ace)\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:vivo|iQOO)\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:一加|OnePlus)\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:三星|Samsung)\s*Galaxy\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:苹果|Apple)\s*iPhone\s*\d+[A-Za-z0-9 +\-]*)",
    r"((?:Mate|Pura|nova)\s*\d+[A-Za-z0-9 +\-]*)",
    r"(iPhone\s*\d+[A-Za-z0-9 +\-]*)",
    r"(Find\s*X\d+[A-Za-z0-9 +\-]*)",
    r"(Reno\s*\d+[A-Za-z0-9 +\-]*)",
    r"(Magic\s*[A-Za-z]*\s*\d+[A-Za-z0-9 +\-]*)",
    r"(K\d+[A-Za-z0-9 +\-]*\s*(?:至尊版|Ultra|Pro|标准版)?)",
)

_GENERIC_ENTITY_CUES = (
    "买一台",
    "买个",
    "预算",
    "左右的手机",
    "左右的平板",
    "左右的耳机",
    "左右的笔记本",
    "主要看重",
    "值不值得买",
    "持续笔记",
    "这篇笔记",
    "当前主题",
)

_GENERIC_ENTITY_EXACT = {
    "手机",
    "平板",
    "耳机",
    "笔记本",
    "笔记主题",
    "这篇笔记",
    "当前主题",
    "持续笔记协作档案",
}


def _clean_candidate(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip("：:，。,.!！?？;；「」“”\"' ")
    cleaned = re.sub(r"\s+(Pro Max|Pro|Plus|Ultra|Max|Mini|FE|SE)\b", r" \1", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def extract_entity_candidates(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    matches: list[tuple[int, int, str]] = []
    for pattern in _PRODUCT_ENTITY_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = _clean_candidate(match.group(1))
            if candidate:
                matches.append((match.start(), -len(candidate), candidate))

    matches.sort(key=lambda item: (item[0], item[1]))
    deduped: list[str] = []
    seen: set[str] = set()
    for _, _, candidate in matches:
        normalized = candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return deduped


def is_generic_entity_name(raw: str) -> bool:
    text = _clean_candidate(raw)
    if not text:
        return True
    if extract_entity_candidates(text):
        return False
    lowered = text.lower()
    if lowered in {item.lower() for item in _GENERIC_ENTITY_EXACT}:
        return True
    return any(cue in text for cue in _GENERIC_ENTITY_CUES)


def mentions_other_specific_entity(text: str, target_entity: str) -> bool:
    target = normalize_entity_name(target_entity)
    if not target or is_generic_entity_name(target):
        return False
    candidates = extract_entity_candidates(text)
    if not candidates:
        return False
    normalized_target = target.lower()
    saw_target = False
    for item in candidates:
        normalized_candidate = normalize_entity_name(item).lower()
        if not normalized_candidate:
            continue
        if normalized_candidate in normalized_target or normalized_target in normalized_candidate:
            saw_target = True
            continue
        return True
    return False if saw_target else True


def normalize_entity_name(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    explicit_candidates = extract_entity_candidates(text)
    if explicit_candidates:
        return explicit_candidates[0]

    for pattern in _QUOTED_PATTERNS:
        match = re.search(pattern, text)
        if match and match.group(1).strip():
            quoted = _clean_candidate(match.group(1))
            if quoted:
                return quoted

    text = re.sub(r"^(帮我|请|麻烦你|给我|我想|想让你|想请你)", "", text).strip()
    text = re.sub(r"^(针对|围绕|关于)", "", text).strip()
    text = re.sub(r"^(写|做|生成|整理|分析|测评|评测|出一篇|出一个)", "", text).strip()
    text = re.sub(
        r"(做一个|做一篇|写一个|写一篇|生成一个|生成一篇|出一个|出一篇|整理一个|来一个|来一篇).*$",
        "",
        text,
    ).strip()
    text = re.sub(r"(深度种草笔记|种草笔记|深度测评|测评|评测|分析|攻略|介绍).*$", "", text).strip()
    text = re.sub(r"[，。,.!！?？:].*$", "", text).strip()
    text = _clean_candidate(text)

    return text or _clean_candidate(raw)


def resolve_state_entity_name(state: dict | None, fallback_query: str = "") -> str:
    state = state or {}
    note_document = state.get("note_document") if isinstance(state.get("note_document"), dict) else {}
    document_meta = note_document.get("document_meta") if isinstance(note_document.get("document_meta"), dict) else {}
    artifact = state.get("artifact") if isinstance(state.get("artifact"), dict) else {}
    retrieved_knowledge = state.get("retrieved_knowledge") if isinstance(state.get("retrieved_knowledge"), dict) else {}

    candidates = [
        str(retrieved_knowledge.get("entity_name") or "").strip(),
        str(fallback_query or "").strip(),
        str(document_meta.get("title") or "").strip(),
        str(artifact.get("title") or "").strip(),
    ]
    for candidate in candidates:
        normalized = normalize_entity_name(candidate)
        if normalized and not is_generic_entity_name(normalized):
            return normalized
    return normalize_entity_name(fallback_query)

