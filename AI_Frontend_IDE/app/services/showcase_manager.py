from typing import Any, Dict, List


SHOWCASE_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "digital_review",
        "scenario_id": "seeding",
        "title": "数码评测 / 热点种草",
        "persona": "硬核数码博主",
        "why_this_matters": "最适合展示热点追踪、事实检索、争议对立和组件化生成能力。",
        "highlight_features": [
            "热点缓存与趋势预热",
            "事实增强与争议对撞",
            "雷达图 / 对比卡 / 投票卡",
            "自然语言编辑已有笔记",
        ],
        "talking_points": [
            "先展示热点话题下的整页生成，不是静态模板，而是会结合事实与争议生成内容结构。",
            "再演示把投票改成雷达图，证明系统不是一次性生成，而是可持续编辑同一篇笔记。",
            "最后切灰蓝主题并展示 checkpoint / 分支，强调这是创作工作台而不是聊天机器人。",
        ],
        "demo_script": [
            {
                "label": "第 1 步",
                "goal": "一键生成热点数码评测页",
                "action": "start",
                "prompt": "帮我生成一篇关于华为 Mate 60 的对比种草笔记",
            },
            {
                "label": "第 2 步",
                "goal": "把交互卡换成更强信息密度的雷达图",
                "action": "fill",
                "prompt": "把投票换成雷达图，再把第二段改得更尖锐一点",
            },
            {
                "label": "第 3 步",
                "goal": "切换成更克制的评测风格",
                "action": "fill",
                "prompt": "把整体页面改成更克制的灰蓝风格",
            },
            {
                "label": "第 4 步",
                "goal": "从当前版本分叉一条黑红榜吐槽路线",
                "action": "fill",
                "prompt": "基于当前版本分叉一条更像黑红榜吐槽风格的版本",
            },
        ],
        "starter_prompt": "帮我生成一篇关于华为 Mate 60 的对比种草笔记",
        "edit_prompt": "把投票换成雷达图，再把第二段改得更尖锐一点",
        "theme_prompt": "把整体页面改成更克制的灰蓝风格",
        "branch_prompt": "基于当前版本分叉一条更像黑红榜吐槽风格的版本",
    },
    {
        "id": "travel_explore",
        "scenario_id": "travel",
        "title": "旅行探店 / 城市探索",
        "persona": "温柔探店达人",
        "why_this_matters": "最适合展示地点检索、天气信息、路线感叙事和时效信息融合。",
        "highlight_features": [
            "地点 / 天气类事实补全",
            "路线与攻略型叙事",
            "位置卡与天气卡",
            "多轮修改与时间线回溯",
        ],
        "talking_points": [
            "先讲这条业务线展示的是地点、天气、旅行叙事这些外部信息融合能力。",
            "然后用局部或全局修改证明用户可以持续把同一篇旅行笔记往攻略化方向推进。",
            "最后强调这套编辑器适合长线程创作，而不是一次性生成完就结束。",
        ],
        "demo_script": [
            {
                "label": "第 1 步",
                "goal": "生成一篇旅行分享页",
                "action": "start",
                "prompt": "帮我做一篇周末去阿那亚看海的旅行分享笔记",
            },
            {
                "label": "第 2 步",
                "goal": "补一个地点卡并增强松弛感",
                "action": "fill",
                "prompt": "保留标题，把第二段改得更有松弛感，再补一个地点卡",
            },
            {
                "label": "第 3 步",
                "goal": "切成更像手账的旅行视觉",
                "action": "fill",
                "prompt": "整体改成更像纸质旅行手账的风格",
            },
            {
                "label": "第 4 步",
                "goal": "分叉成更像探店攻略的版本",
                "action": "fill",
                "prompt": "从当前版本分叉一个更像探店攻略的版本",
            },
        ],
        "starter_prompt": "帮我做一篇周末去阿那亚看海的旅行分享笔记",
        "edit_prompt": "保留标题，把第二段改得更有松弛感，再补一个地点卡",
        "theme_prompt": "整体改成更像纸质旅行手账的风格",
        "branch_prompt": "从当前版本分叉一个更像探店攻略的版本",
    },
    {
        "id": "daily_share",
        "scenario_id": "daily_share",
        "title": "日常分享 / 长期陪伴记录",
        "persona": "深夜感性诗人",
        "why_this_matters": "最适合展示长期上下文、人设一致性、可回滚编辑和分支版本能力。",
        "highlight_features": [
            "长期线程与 checkpoint 追踪",
            "组件级回滚与分支创作",
            "围绕同一创作者人设持续编辑",
            "轻量情绪化内容重写",
        ],
        "talking_points": [
            "这条业务线专门讲长期追踪和创作者人设一致性，不强调重搜索。",
            "你可以连续改语气、改主题，再回滚到旧版本，证明状态是持久化的。",
            "最后再从旧版本分叉出周末总结版，突出 checkpoint / rollback / fork 的产品感。",
        ],
        "demo_script": [
            {
                "label": "第 1 步",
                "goal": "生成一篇日常晚霞记录",
                "action": "start",
                "prompt": "帮我写一篇下班后散步看晚霞的日常分享笔记",
            },
            {
                "label": "第 2 步",
                "goal": "改成更轻松碎碎念的口吻",
                "action": "fill",
                "prompt": "保留标题，把正文改得更像轻松碎碎念，再加一点天气感",
            },
            {
                "label": "第 3 步",
                "goal": "切换到奶油手账风",
                "action": "fill",
                "prompt": "整体改成更柔和的奶油手账风",
            },
            {
                "label": "第 4 步",
                "goal": "分叉出一条更适合周末总结的版本",
                "action": "fill",
                "prompt": "从这个版本分叉一个更适合周末总结的版本",
            },
        ],
        "starter_prompt": "帮我写一篇下班后散步看晚霞的日常分享笔记",
        "edit_prompt": "保留标题，把正文改得更像轻松碎碎念，再加一点天气感",
        "theme_prompt": "整体改成更柔和的奶油手账风",
        "branch_prompt": "从这个版本分叉一个更适合周末总结的版本",
    },
]


class ShowcaseManager:
    def list_profiles(self) -> List[Dict[str, Any]]:
        return SHOWCASE_PROFILES


showcase_manager = ShowcaseManager()
