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
TRAVEL_HERO_A = "/demo-assets/travel-hero-a.jpg"
TRAVEL_HERO_B = "/demo-assets/travel-hero-b.jpg"
DAILY_HERO = "/demo-assets/daily-hero.jpg"
DAILY_COFFEE = "/demo-assets/daily-coffee.jpg"


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
        "supported_scenarios": ["general", "seeding", "travel", "daily_share"],
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
        "supported_scenarios": ["general", "seeding", "travel", "daily_share"],
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
        "supported_scenarios": ["general", "seeding", "travel"],
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
        "supported_scenarios": ["general", "seeding"],
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
        "supported_scenarios": ["general", "seeding"],
        "summary": "更像路线分流卡，不该再退化成左右两坨长文。",
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
        "supported_scenarios": ["general", "seeding", "daily_share"],
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
        "supported_scenarios": ["general", "seeding", "travel", "daily_share"],
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
        "supported_scenarios": ["travel", "general"],
        "summary": "地点卡要回答“去哪、怎么走、为什么要去”，不是只贴地址。",
        "fixture": {
            "id": "component_location_block",
            "title": "地点卡真实样例",
            "description": "适合观察地点信息和生活方式内容是否兼容。",
            "note_document": _component_note(
                {
                    "id": "location_1",
                    "type": "LocationBlock",
                    "semantic_role": "location_info",
                    "props": {
                        "poi_name": "阿那亚社区",
                        "location": "从园区步行到海边、书店和礼堂都很顺，路线建议围绕海边散步和日落展开。",
                    },
                },
                title="地点卡真实样例",
                scenarios=["travel"],
                theme=_build_theme("#4f46e5", "#dbeafe", "#f6f7ff"),
            ),
        },
    },
    {
        "id": "component_weather_polaroid",
        "component_type": "WeatherPolaroid",
        "label": "氛围拍立得",
        "semantic_role": "ambience_snapshot",
        "supported_scenarios": ["travel", "daily_share"],
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
                        "image_url": DAILY_COFFEE,
                        "desc": "当天的海风偏软，晚霞落下来的那十几分钟最适合慢慢走。",
                        "location": "阿那亚海边步道",
                        "weather": "Cloudy",
                        "time": "18:24",
                    },
                },
                title="氛围拍立得真实样例",
                scenarios=["travel"],
                theme=_build_theme("#4f46e5", "#dbeafe", "#f6f7ff"),
            ),
        },
    },
    {
        "id": "component_quote_block",
        "component_type": "QuoteBlock",
        "label": "金句块",
        "semantic_role": "quote_highlight",
        "supported_scenarios": ["general", "daily_share", "travel"],
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
        "supported_scenarios": ["general", "travel", "daily_share"],
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
        "scenario_id": "travel_story",
        "title": "旅行生活方式页",
        "description": "重点观察封面、地点卡和氛围块是否和主题一致。",
        "fixture": {
            "id": "travel_story",
            "title": "旅行生活方式页",
            "description": "重点观察封面、地点卡和氛围块是否和主题一致。",
            "note_document": {
                "document_meta": {"title": "阿那亚一日游：不赶行程，也能把海边过得很满", "scenarios": ["travel"]},
                "theme": _build_theme("#4f46e5", "#dbeafe", "#f6f7ff"),
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": [TRAVEL_HERO_A, TRAVEL_HERO_B]}},
                    COMPONENT_FIXTURES[7]["fixture"]["note_document"]["blocks"][0],
                    {
                        "id": "story_2",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {
                            "paragraphs": [
                                "这篇攻略不追求把景点打卡清单塞满，而是更强调“什么时候去、怎么走、哪里最容易出片”。",
                                "如果时间只有一天，最值得保留的是海边散步、书店停留和傍晚那段光线变化。",
                            ],
                            "sections": [
                                {"label": "路线判断", "role": "summary", "paragraph": "这篇攻略不追求把景点打卡清单塞满，而是更强调“什么时候去、怎么走、哪里最容易出片”。", "summary": "先告诉用户重点不是清单堆砌。"},
                                {"label": "真正值得留的时间", "role": "selling_point", "paragraph": "如果时间只有一天，最值得保留的是海边散步、书店停留和傍晚那段光线变化。", "summary": "把最值得留的体验留给读者。"},
                            ],
                        },
                    },
                    COMPONENT_FIXTURES[8]["fixture"]["note_document"]["blocks"][0],
                ],
                "assets": [],
            },
        },
    },
    {
        "scenario_id": "daily_share",
        "title": "日常分享页",
        "description": "更轻的叙事和互动，重点看整体节奏是否自然。",
        "fixture": {
            "id": "daily_share",
            "title": "日常分享页",
            "description": "更轻的叙事和互动，重点看整体节奏是否自然。",
            "note_document": {
                "document_meta": {"title": "周末书店散步：轻叙事也要有层次", "scenarios": ["daily_share"]},
                "theme": _build_theme("#f59e0b", "#fde68a", "#fffdf6"),
                "blocks": [
                    {"id": "cover_1", "type": "CoverSwiper", "semantic_role": "hero_media", "props": {"image_urls": [DAILY_HERO]}},
                    {"id": "title_1", "type": "TitleBlock", "semantic_role": "heading", "props": {"title": "周末书店散步：轻叙事也要有层次"}},
                    {
                        "id": "story_1",
                        "type": "StoryText",
                        "semantic_role": "narrative_text",
                        "props": {
                            "paragraphs": [
                                "这类日常分享最怕的是“看起来很松弛，实际上什么也没说”。",
                                "真正好看的地方不只在照片，而在于你有没有把当下那点轻松和停顿感写出来。",
                            ],
                            "sections": [
                                {"label": "开场氛围", "role": "summary", "paragraph": "这类日常分享最怕的是“看起来很松弛，实际上什么也没说”。", "summary": "先把写作目标说清楚。"},
                                {"label": "真正有感觉的地方", "role": "selling_point", "paragraph": "真正好看的地方不只在照片，而在于你有没有把当下那点轻松和停顿感写出来。", "summary": "把情绪落点讲出来。"},
                            ],
                        },
                    },
                    {
                        "id": "poll_1",
                        "type": "PollBlock",
                        "semantic_role": "interactive_opinion",
                        "props": {
                            "question": "周末你更想留在书店还是去外面散步？",
                            "option_a": "留在书店慢慢翻",
                            "option_b": "出去走一圈看天色",
                            "explanation": "轻互动更适合承接情绪和偏好，而不是假票仓。",
                            "option_cards": [
                                {"label": "留在书店慢慢翻", "stance": "安静一点", "vote_hint": "更适合承接停下来、慢慢看的情绪。", "why_it_matters": "它代表的是更安静的周末节奏。"},
                                {"label": "出去走一圈看天色", "stance": "动起来", "vote_hint": "更适合承接走出去、看光线变化的情绪。", "why_it_matters": "它代表的是更流动的周末节奏。"},
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
    fixtures = [deepcopy(item["fixture"]) for item in COMPONENT_FIXTURES] + [deepcopy(item["fixture"]) for item in SCENARIO_FIXTURES]
    return {
        "generated_at": "2026-03-22T16:00:00+08:00",
        "components": [
            {
                "component_type": item["component_type"],
                "label": item["label"],
                "semantic_role": item["semantic_role"],
                "supported_scenarios": item["supported_scenarios"],
                "summary": item["summary"],
                "fixture": deepcopy(item["fixture"]),
            }
            for item in COMPONENT_FIXTURES
        ],
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "title": item["title"],
                "description": item["description"],
                "fixture": deepcopy(item["fixture"]),
            }
            for item in SCENARIO_FIXTURES
        ],
        "fixtures": fixtures,
        "recommendations": [
            "先看单积木，再看整页场景，能更快判断是数据问题还是比例问题。",
            "优先用场景页观察主题贴合和块之间的节奏，不要只看单块细节。",
            "当某个积木需要改结构时，先更新它的 fixture，再更新视觉回归基线。",
        ],
    }


def get_block_gallery_component(component_type: str) -> dict[str, Any] | None:
    normalized = str(component_type or "").strip()
    for item in COMPONENT_FIXTURES:
        if item["component_type"] == normalized:
            return deepcopy({
                "component_type": item["component_type"],
                "label": item["label"],
                "semantic_role": item["semantic_role"],
                "supported_scenarios": item["supported_scenarios"],
                "summary": item["summary"],
                "fixture": item["fixture"],
            })
    return None


def get_block_gallery_scenario(scenario_id: str) -> dict[str, Any] | None:
    normalized = str(scenario_id or "").strip()
    for item in SCENARIO_FIXTURES:
        if item["scenario_id"] == normalized:
            return deepcopy({
                "scenario_id": item["scenario_id"],
                "title": item["title"],
                "description": item["description"],
                "fixture": item["fixture"],
            })
    return None
