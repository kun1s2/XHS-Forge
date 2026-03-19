import re


def normalize_entity_name(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    for pattern in (
        r"「([^」]+)」",
        r"“([^”]+)”",
        r'"([^"]+)"',
    ):
        match = re.search(pattern, text)
        if match and match.group(1).strip():
            return match.group(1).strip()

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
    text = text.strip("：:「」“”\"' ")

    return text or str(raw or "").strip()
