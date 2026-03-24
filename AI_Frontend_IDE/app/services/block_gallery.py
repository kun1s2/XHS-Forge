"""积木大全固定样例。

这里提供两类数据：
1. 单积木真实样例：让每个积木都能在“像真实内容”的状态下被查看。
2. 场景整页样例：让积木放回真实页面里观察比例、层次和主题一致性。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import quote


def _svg_data_uri(*, title: str, subtitle: str, start: str, end: str) -> str:
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 900">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="{start}" />
          <stop offset="100%" stop-color="{end}" />
        </linearGradient>
      </defs>
      <rect width="1200" height="900" fill="url(#bg)" rx="48" />
      <circle cx="220" cy="190" r="170" fill="rgba(255,255,255,0.16)" />
      <circle cx="1000" cy="130" r="120" fill="rgba(255,255,255,0.12)" />
      <circle cx="940" cy="760" r="190" fill="rgba(15,23,42,0.12)" />
      <rect x="88" y="612" width="1024" height="176" rx="36" fill="rgba(255,255,255,0.14)" />
      <text x="92" y="694" font-family="Arial, Helvetica, sans-serif" font-size="76" font-weight="800" fill="white">{title}</text>
      <text x="96" y="748" font-family="Arial, Helvetica, sans-serif" font-size="28" fill="rgba(255,255,255,0.86)">{subtitle}</text>
    </svg>
    """
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def _build_theme(primary: str, accent: str, bg: str = "#fff8f7") -> dict[str, Any]:
    return {
        "page_theme": {
            "--bg-color": bg,
            "--bg-gradient": f"linear-gradient(180deg, {bg} 0%, color-mix(in srgb, {accent} 8%, white 92%) 100%)",
            "--card-bg": "rgba(255,255,255,0.95)",
            "--card-bg-soft": "rgba(255,255,255,0.82)",
            "--card-border": "rgba(244,114,182,0.14)",
            "--card-shadow": "0 18px 42px rgba(15,23,42,0.08)",
            "--text-color": "#1f2937",
            "--text-muted": "#6b7280",
            "--primary-vibe": primary,
            "--primary-vibe-light": f"color-mix(in srgb, {primary} 20%, white 80%)",
            "--pro-color": primary,
            "--con-color": "#0f172a",
        },
        "global_vars": {},
    }


MATE_HERO_A = "/demo-assets/mate-hero-a.jpg"
MATE_HERO_B = "/demo-assets/mate-hero-b.jpg"
PHONE_ALT_A = "/demo-assets/travel-hero-a.jpg"
PHONE_ALT_B = "/demo-assets/travel-hero-b.jpg"
LAPTOP_ALT = "/demo-assets/daily-hero.jpg"
EARBUD_ALT = "/demo-assets/daily-coffee.jpg"


def _component_note(block: dict[str, Any], *, title: str, scenarios: list[str], theme: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_meta": {"title": title, "scenarios": scenarios},
        "theme": deepcopy(theme),
        "blocks": [deepcopy(block)],
        "assets": [],
    }


COMPONENT_FIXTURES: list[dict[str, Any]] = [
    {
        "id": "component_title_block",
        "component_type": "TitleBlock",
        "label": "标题块",
        "semantic_role": "heading",
        "supported_scenarios": ["seeding"],
        "summary": "适合承接页面总判断，别把它写成无意义的大口号。",
        "fixture": {
            "id": "component_title_block",
            "title": "标题块真实样例",
            "description": "用于观察标题是否足够清楚、够像结论，而不是空泛 slogan。",
            "note_document": _component_note(
                {
                    "id": "title_1",
                    "type": "TitleBlock",
                    "semantic_role": "heading",
                    "props": {
                        "title": "华为 Mate 60：不是参数最猛，但整机体验依然很能打",
                        "subtitle": "标题应该先说判断，再说边界。",
                    },
                },
                title="标题块真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_story_text",
        "component_type": "StoryText",
        "label": "正文块",
        "semantic_role": "narrative_text",
        "supported_scenarios": ["seeding"],
        "summary": "更适合分成“开场判断 / 事实补充 / 边界提醒”，不要退化成长文墙。",
        "fixture": {
            "id": "component_story_text",
            "title": "正文块真实样例",
            "description": "正文要能让用户一眼看出每段在负责什么，而不是全挤成同一种大段文字。",
            "note_document": _component_note(
                {
                    "id": "story_1",
                    "type": "StoryText",
                    "semantic_role": "narrative_text",
                    "props": {
                        "paragraphs": [
                            "如果你想要的是一台“整机体验强于纸面参数”的手机，Mate 60 依然很能打。",
                            "真正拉开差距的不是某一个跑分，而是手感、系统反馈和影像调性组合出来的稳定体验。",
                            "如果你更在意生态协同和跨设备效率，这个结论就需要保守一点。",
                        ],
                        "sections": [
                            {"label": "开场判断", "role": "summary", "paragraph": "如果你想要的是一台“整机体验强于纸面参数”的手机，Mate 60 依然很能打。", "summary": "先给结论。"},
                            {"label": "为什么成立", "role": "selling_point", "paragraph": "真正拉开差距的不是某一个跑分，而是手感、系统反馈和影像调性组合出来的稳定体验。", "summary": "把理由拆开。"},
                            {"label": "边界提醒", "role": "caution", "paragraph": "如果你更在意生态协同和跨设备效率，这个结论就需要保守一点。", "summary": "别忘了边界。"},
                        ],
                    },
                },
                title="正文块真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_product_spec",
        "component_type": "ProductSpecCard",
        "label": "参数卡",
        "semantic_role": "evidence_summary",
        "supported_scenarios": ["seeding"],
        "summary": "参数卡更适合回答“为什么重要”，不适合只堆字符串。",
        "fixture": {
            "id": "component_product_spec",
            "title": "参数卡真实样例",
            "description": "让参数不只是一列列表，而是带判断价值的结构化证据。",
            "note_document": _component_note(
                {
                    "id": "spec_1",
                    "type": "ProductSpecCard",
                    "semantic_role": "evidence_summary",
                    "props": {
                        "spec_items": [
                            {"label": "影像风格", "value": "高动态范围更自然，夜景不过度抹平。", "status": "verified", "decision_impact": "更适合承接为什么它会让人第一眼喜欢。", "sources": ["样张实测"], "hint": "适合放进主推荐理由里。"},
                            {"label": "续航策略", "value": "中高强度一天够用，但重度拍摄仍需补电。", "status": "default", "decision_impact": "更适合解释“够不够用”，而不是写成绝对优势。", "sources": ["日常续航反馈"]},
                            {"label": "购买提醒", "value": "如果你更看重生态协同，结论需要更谨慎。", "status": "caution", "decision_impact": "更适合作为购买边界，而不是一票否决。", "sources": ["跨平台体验"], "hint": "这里要保守表达。"},
                        ],
                    },
                },
                title="参数卡真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_radar_chart",
        "component_type": "RadarChartBlock",
        "label": "雷达图",
        "semantic_role": "score_overview",
        "supported_scenarios": ["seeding"],
        "summary": "雷达图应该解释每个维度为什么高低，而不是只当装饰。",
        "fixture": {
            "id": "component_radar_chart",
            "title": "雷达图真实样例",
            "description": "让图表真正负责证据总结，而不是孤立炫技。",
            "note_document": _component_note(
                {
                    "id": "radar_1",
                    "type": "RadarChartBlock",
                    "semantic_role": "score_overview",
                    "props": {
                        "title": "五维体验雷达",
                        "dimensions": ["性能", "影像", "续航", "手感", "系统"],
                        "scores": [85, 90, 83, 88, 92],
                        "metrics": [
                            {"label": "性能", "value": 85, "reason": "重度使用下依然够稳，不会拖后腿。", "confidence": "medium", "evidence": "长时间切换与常用负载表现"},
                            {"label": "影像", "value": 90, "reason": "风格辨识度很强，属于容易让人记住的优势。", "confidence": "high", "evidence": "日景与夜景样张"},
                            {"label": "续航", "value": 83, "reason": "一天够用，但不是绝对无脑优势。", "confidence": "medium", "evidence": "中高强度续航反馈"},
                            {"label": "手感", "value": 88, "reason": "上手氛围和握持反馈都很完整。", "confidence": "medium", "evidence": "机身尺寸与重量平衡"},
                            {"label": "系统", "value": 92, "reason": "流畅度和整体一致性是它真正拉开差距的地方。", "confidence": "high", "evidence": "日常操作与反馈节奏"},
                        ],
                    },
                },
                title="雷达图真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_versus_card",
        "component_type": "VersusCard",
        "label": "对比卡",
        "semantic_role": "comparison",
        "supported_scenarios": ["seeding"],
        "summary": "更像购买分流卡，不该再退化成左右两坨长文。",
        "fixture": {
            "id": "component_versus_card",
            "title": "对比卡真实样例",
            "description": "每边都应该有摘要、要点和适合谁，而不是单纯长文对冲。",
            "note_document": _component_note(
                {
                    "id": "versus_1",
                    "type": "VersusCard",
                    "semantic_role": "comparison",
                    "props": {
                        "title": "华为 Mate 60 vs iPhone 17",
                        "pros": {
                            "summary": "更在意系统统一性、影像调性和上手氛围",
                            "points": ["上手好感更强", "影像风格更有辨识度", "整机气质更统一"],
                            "fit_for": "适合更看重整机氛围和第一眼好感的人。",
                        },
                        "cons": {
                            "summary": "更追求绝对稳定的生态协同和工作流",
                            "points": ["第三方适配更稳", "视频工作流更省心", "生态协同更成熟"],
                            "fit_for": "适合更看重长期稳定性和效率的人。",
                        },
                        "pros": {
                            "summary": "更像“整体验受宠”路线",
                            "details": "上手观感更完整。影像风格更有记忆点。系统反馈和日常手感更讨喜。",
                            "points": ["第一眼好感更强", "影像风格更有辨识度", "系统反馈更讨喜"],
                            "fit_for": "适合更在意整机氛围、影像调性和日常愉悦感的人。",
                        },
                        "cons": {
                            "summary": "更像“效率与生态”路线",
                            "details": "跨设备协同更成熟。第三方生态更稳。视频和工作流更容易无脑接入。",
                            "points": ["生态协同更成熟", "第三方适配更稳", "工作流接入更省心"],
                            "fit_for": "适合更在意效率、生态和长期无脑稳定的人。",
                        },
                        "decision_hint": "这不是单纯优缺点堆砌，而是“你到底更想要哪种使用路线”的分流。",
                        "risk_note": "如果两边都写成大段长文，这张卡就会失去“帮用户做决定”的价值。",
                    },
                },
                title="对比卡真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_poll_block",
        "component_type": "PollBlock",
        "label": "投票卡",
        "semantic_role": "interactive_opinion",
        "supported_scenarios": ["seeding"],
        "summary": "投票卡应该承接表达和分流，而不是伪装真实平台票仓。",
        "fixture": {
            "id": "component_poll_block",
            "title": "投票卡真实样例",
            "description": "每个选项都要说清“这边代表什么”，而不是只给两个词。",
            "note_document": _component_note(
                {
                    "id": "poll_1",
                    "type": "PollBlock",
                    "semantic_role": "interactive_opinion",
                    "props": {
                        "question": "华为 Mate 60 的对比里你更站哪边？",
                        "option_a": "看整机氛围感，我更站 Mate 60",
                        "option_b": "看生态和效率，我还是选 iPhone",
                        "explanation": "这张卡只负责承接偏好表达，不假装自己是平台真票仓。",
                        "option_cards": [
                            {"label": "看整机氛围感，我更站 Mate 60", "stance": "主推理由", "vote_hint": "如果你最在意“拿起来就喜欢”的整机体验，会更容易站这边。", "why_it_matters": "它更适合承接第一购买理由和情绪驱动力。"},
                            {"label": "看生态和效率，我还是选 iPhone", "stance": "现实代价", "vote_hint": "如果你更看重无脑稳定和工作流效率，会更容易站这边。", "why_it_matters": "它更适合承接长期使用里的现实妥协点。"},
                        ],
                    },
                },
                title="投票卡真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_cover_swiper",
        "component_type": "CoverSwiper",
        "label": "封面轮播",
        "semantic_role": "hero_media",
        "supported_scenarios": ["seeding"],
        "summary": "封面块要负责定调，不应该只有空壳或跑题图。",
        "fixture": {
            "id": "component_cover_swiper",
            "title": "封面轮播真实样例",
            "description": "适合观察首屏氛围、比例和图片是否真的贴题。",
            "note_document": _component_note(
                {
                    "id": "cover_1",
                    "type": "CoverSwiper",
                    "semantic_role": "hero_media",
                    "props": {"image_urls": [MATE_HERO_A, MATE_HERO_B]},
                },
                title="封面轮播真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#ff5b7f", "#ffd7de"),
            ),
        },
    },
    {
        "id": "component_location_block",
        "component_type": "LocationBlock",
        "label": "地点卡",
        "semantic_role": "location_info",
        "supported_scenarios": ["seeding"],
        "summary": "地点卡在正式产品里只作为线下看机或购买地点补充，不作为主内容承载。",
        "fixture": {
            "id": "component_location_block",
            "title": "地点卡真实样例",
            "description": "适合观察线下看机或购买渠道信息是否能自然补充进决策页。",
            "note_document": _component_note(
                {
                    "id": "location_1",
                    "type": "LocationBlock",
                    "semantic_role": "location_info",
                    "props": {
                        "poi_name": "华为线下体验店",
                        "location": "如果你想先摸真机，建议先去线下体验店确认手感、屏幕和影像风格，再决定是否下单。",
                    },
                },
                title="地点卡真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#2563eb", "#dbeafe", "#f8fbff"),
            ),
        },
    },
    {
        "id": "component_weather_polaroid",
        "component_type": "WeatherPolaroid",
        "label": "氛围拍立得",
        "semantic_role": "ambience_snapshot",
        "supported_scenarios": ["seeding"],
        "summary": "氛围块应该补情绪和现场感，不该冒出无关风景图。",
        "fixture": {
            "id": "component_weather_polaroid",
            "title": "氛围拍立得真实样例",
            "description": "用来观察氛围块是否真的和场景内容对齐。",
            "note_document": _component_note(
                {
                    "id": "weather_1",
                    "type": "WeatherPolaroid",
                    "semantic_role": "ambience_snapshot",
                    "props": {
                        "image_url": EARBUD_ALT,
                        "desc": "这类氛围图在正式产品里只适合作为第一眼补充，不应该盖过购买结论本身。",
                        "location": "产品首屏氛围",
                        "weather": "Studio",
                        "time": "首图",
                    },
                },
                title="氛围拍立得真实样例",
                scenarios=["seeding"],
                theme=_build_theme("#4f46e5", "#dbeafe", "#f6f7ff"),
            ),
        },
    },
    {
        "id": "component_quote_block",
        "component_type": "QuoteBlock",
        "label": "金句块",
        "semantic_role": "quote_highlight",
        "supported_scenarios": ["seeding"],
        "summary": "金句块适合承接观点，不适合凭空端一句空话。",
        "fixture": {
            "id": "component_quote_block",
            "title": "金句块真实样例",
            "description": "用于观察金句是否真的有观点密度，而不是装饰话术。",
            "note_document": _component_note(
                {
                    "id": "quote_1",
                    "type": "QuoteBlock",
                    "semantic_role": "quote_highlight",
                    "props": {
                        "quote": "真正影响购买决策的，往往不是某一个参数，而是它在一整天使用里有没有拖后腿。",
                        "author": "编辑室结论摘录",
                    },
                },
                title="金句块真实样例",
                scenarios=["general"],
                theme=_build_theme("#2563eb", "#dbeafe", "#f8fbff"),
            ),
        },
    },
    {
        "id": "component_timeline_block",
        "component_type": "TimelineBlock",
        "label": "时间轴",
        "semantic_role": "timeline",
        "supported_scenarios": ["seeding"],
        "summary": "时间轴适合讲过程和节奏，不适合只挂几个无意义时间点。",
        "fixture": {
            "id": "component_timeline_block",
            "title": "时间轴真实样例",
            "description": "用于观察节奏类内容是否能自然展开。",
            "note_document": _component_note(
                {
                    "id": "timeline_1",
                    "type": "TimelineBlock",
                    "semantic_role": "timeline",
                    "props": {
                        "events": [
                            {"time": "09:30", "title": "先看参数", "description": "快速排除明显短板，锁定需要重点验证的维度。"},
                            {"time": "13:00", "title": "进入实测", "description": "拍照、续航、手感和系统稳定性一起验证。"},
                            {"time": "18:40", "title": "形成结论", "description": "保留事实依据，再决定到底是推荐、观望还是劝退。"},
                        ],
                    },
                },
                title="时间轴真实样例",
                scenarios=["general"],
                theme=_build_theme("#2563eb", "#dbeafe", "#f8fbff"),
            ),
        },
    },
]


SCENARIO_FIXTURES: list[dict[str, Any]] = [
    {
        "scenario_id": "seeding_compare",
        "title": "数码对比种草",
        "description": "高频对比块、雷达块和互动块一起看，适合锁定比例和信息层级。",
        "fixture": {
            "id": "seeding_compare",
            "title": "数码对比种草",
            "description": "高频对比块、雷达块和互动块一起看，适合锁定比例和信息层级。",
            "note_document": {
                "document_meta": {"title": "华为 Mate 60：超预期与代价并存的真实结论", "scenarios": ["seeding"]},
                "theme": _build_theme("#ff5b7f", "#ffd7de"),
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": [MATE_HERO_A, MATE_HERO_B]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "华为 Mate 60：超预期与代价并存的真实结论"}},
                    {
                        "id": "story_1",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {
                            "paragraphs": [
                                "如果你在找的是一台“综合体验很强、但不追求把纸面参数堆到极致”的手机，Mate 60 依然很能打。",
                                "它真正拉开差距的地方不是某一个绝对跑分，而是手感、系统稳定性和影像调性组合出来的整体验证感。",
                            ],
                            "sections": [
                                {"label": "开场判断", "role": "summary", "paragraph": "如果你在找的是一台“综合体验很强、但不追求把纸面参数堆到极致”的手机，Mate 60 依然很能打。", "summary": "先告诉读者为什么值得继续看。"},
                                {"label": "为什么成立", "role": "selling_point", "paragraph": "它真正拉开差距的地方不是某一个绝对跑分，而是手感、系统稳定性和影像调性组合出来的整体验证感。", "summary": "把理由拆开。"},
                            ],
                        },
                    },
                    {
                        "id": "radar_1",
                        "type": "RadarChartBlock",
                        "semantic_role": "score_overview",
                        "props": {
                            "title": "五维体验雷达",
                            "dimensions": ["性能", "影像", "续航", "手感", "系统"],
                            "scores": [85, 90, 83, 88, 92],
                            "metrics": [
                                {"label": "性能", "value": 85, "reason": "重度使用下依然够稳，不会拖后腿。", "confidence": "medium", "evidence": "长时间切换与常用负载表现"},
                                {"label": "影像", "value": 90, "reason": "风格辨识度很强，属于容易让人记住的优势。", "confidence": "high", "evidence": "日景与夜景样张"},
                                {"label": "续航", "value": 83, "reason": "一天够用，但不是绝对无脑优势。", "confidence": "medium", "evidence": "中高强度续航反馈"},
                                {"label": "手感", "value": 88, "reason": "上手氛围和握持反馈都很完整。", "confidence": "medium", "evidence": "机身尺寸与重量平衡"},
                                {"label": "系统", "value": 92, "reason": "流畅度和整体一致性是它真正拉开差距的地方。", "confidence": "high", "evidence": "日常操作与反馈节奏"},
                            ],
                        },
                    },
                    COMPONENT_FIXTURES[4]["fixture"]["note_document"]["blocks"][0],
                    COMPONENT_FIXTURES[5]["fixture"]["note_document"]["blocks"][0],
                ],
                "assets": [],
            },
        },
    },
    {
        "scenario_id": "seeding_budget_pick",
        "title": "预算优先决策页",
        "description": "重点观察价格、参数和取舍边界是否能自然落成一页。",
        "fixture": {
            "id": "seeding_budget_pick",
            "title": "预算优先决策页",
            "description": "重点观察价格、参数和取舍边界是否能自然落成一页。",
            "note_document": {
                "document_meta": {"title": "小米 14：预算优先时更容易给出明确结论", "scenarios": ["seeding"]},
                "theme": _build_theme("#2563eb", "#dbeafe", "#f8fbff"),
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": [PHONE_ALT_A, PHONE_ALT_B]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "小米 14：预算优先时更容易给出明确结论"}},
                    {
                        "id": "story_2",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {
                            "paragraphs": [
                                "如果你最在意的是价格、性能和充电效率，小米 14 会比强调整机氛围感的机型更容易做出直接判断。",
                                "这类页面最重要的不是堆参数，而是把“更低预算换到什么”和“因此要接受什么”讲清楚。",
                            ],
                            "sections": [
                                {"label": "预算判断", "role": "summary", "paragraph": "如果你最在意的是价格、性能和充电效率，小米 14 会比强调整机氛围感的机型更容易做出直接判断。", "summary": "先告诉用户适合谁。"},
                                {"label": "为什么成立", "role": "selling_point", "paragraph": "这类页面最重要的不是堆参数，而是把“更低预算换到什么”和“因此要接受什么”讲清楚。", "summary": "把取舍讲透。"},
                            ],
                        },
                    },
                    COMPONENT_FIXTURES[4]["fixture"]["note_document"]["blocks"][0],
                ],
                "assets": [],
            },
        },
    },
    {
        "scenario_id": "seeding_camera_focus",
        "title": "影像优先决策页",
        "description": "更强调影像、质感和偏好分流，重点看判断是否足够鲜明。",
        "fixture": {
            "id": "seeding_camera_focus",
            "title": "影像优先决策页",
            "description": "更强调影像、质感和偏好分流，重点看判断是否足够鲜明。",
            "note_document": {
                "document_meta": {"title": "iPhone 17：如果你只看影像和系统质感", "scenarios": ["seeding"]},
                "theme": _build_theme("#f59e0b", "#fde68a", "#fffdf6"),
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": [LAPTOP_ALT, EARBUD_ALT]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "iPhone 17：如果你只看影像和系统质感"}},
                    {
                        "id": "story_1",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {
                            "paragraphs": [
                                "如果你只在意影像风格、系统一致性和拍完就能发的稳定感，iPhone 17 的判断会非常直接。",
                                "但如果你更在意价格门槛或快充效率，这个结论就必须明显收一收。",
                            ],
                            "sections": [
                                {"label": "开场判断", "role": "summary", "paragraph": "如果你只在意影像风格、系统一致性和拍完就能发的稳定感，iPhone 17 的判断会非常直接。", "summary": "先给面向谁的结论。"},
                                {"label": "边界提醒", "role": "selling_point", "paragraph": "但如果你更在意价格门槛或快充效率，这个结论就必须明显收一收。", "summary": "把边界讲清楚。"},
                            ],
                        },
                    },
                    {
                        "id": "poll_1",
                        "type": "PollBlock",
                        "semantic_role": "interactive_opinion",
                        "props": {
                            "question": "买旗舰时你更看重影像质感还是价格效率？",
                            "option_a": "影像和系统质感",
                            "option_b": "价格和快充效率",
                            "explanation": "互动块更适合承接偏好分流，而不是装饰。",
                            "option_cards": [
                                {"label": "影像和系统质感", "stance": "偏体验", "vote_hint": "更适合已经明确接受高预算的人。", "why_it_matters": "它代表的是为稳定体验买单。"},
                                {"label": "价格和快充效率", "stance": "偏效率", "vote_hint": "更适合预算更敏感、看重参数兑现的人。", "why_it_matters": "它代表的是更明确的性能价格取舍。"},
                            ],
                        },
                    },
                ],
                "assets": [],
            },
        },
    },
]


def get_block_gallery_overview() -> dict[str, Any]:
    allowed_components = [item for item in COMPONENT_FIXTURES if "seeding" in list(item.get("supported_scenarios") or [])]
    allowed_scenarios = [item for item in SCENARIO_FIXTURES if str(item.get("scenario_id") or "").startswith("seeding_")]
    fixtures = [deepcopy(item["fixture"]) for item in allowed_components] + [deepcopy(item["fixture"]) for item in allowed_scenarios]
    return {
        "generated_at": "2026-03-22T16:00:00+08:00",
        "components": [
            {
                "component_type": item["component_type"],
                "label": item["label"],
                "semantic_role": item["semantic_role"],
                "supported_scenarios": ["seeding"],
                "summary": item["summary"],
                "fixture": deepcopy(item["fixture"]),
            }
            for item in allowed_components
        ],
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "title": item["title"],
                "description": item["description"],
                "fixture": deepcopy(item["fixture"]),
            }
            for item in allowed_scenarios
        ],
        "fixtures": fixtures,
        "recommendations": [
            "先看单积木，再看整页购买决策场景，能更快判断是数据问题还是比例问题。",
            "优先用场景页观察结论、事实、对比和风险边界的节奏，不要只看单块细节。",
            "当某个积木需要改结构时，先更新它的 fixture，再更新视觉回归基线。",
        ],
    }


def get_block_gallery_component(component_type: str) -> dict[str, Any] | None:
    normalized = str(component_type or "").strip()
    for item in COMPONENT_FIXTURES:
        if item["component_type"] == normalized and "seeding" in list(item.get("supported_scenarios") or []):
            return deepcopy({
                "component_type": item["component_type"],
                "label": item["label"],
                "semantic_role": item["semantic_role"],
                "supported_scenarios": ["seeding"],
                "summary": item["summary"],
                "fixture": item["fixture"],
            })
    return None


def get_block_gallery_scenario(scenario_id: str) -> dict[str, Any] | None:
    normalized = str(scenario_id or "").strip()
    for item in SCENARIO_FIXTURES:
        if item["scenario_id"] == normalized and str(item["scenario_id"]).startswith("seeding_"):
            return deepcopy({
                "scenario_id": item["scenario_id"],
                "title": item["title"],
                "description": item["description"],
                "fixture": item["fixture"],
            })
    return None
