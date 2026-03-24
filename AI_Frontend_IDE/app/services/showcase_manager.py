from typing import Any, Dict, List


SHOWCASE_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "digital_purchase_decision",
        "scenario_id": "seeding",
        "title": "数码购买决策 Agent",
        "persona": "硬核数码决策顾问",
        "why_this_matters": "最适合展示结构化知识优先、候选知识审查、多工具调用和购买决策档案生成能力。",
        "highlight_features": [
            "热点缓存与型号预热",
            "参数 / 价格 / 竞品事实审查",
            "决策结论 / 对比卡 / 风险边界",
            "基于同一档案持续编辑与复盘",
        ],
        "talking_points": [
            "先展示用户提出购买决策问题后，agent 如何先做知识计划，再生成一份决策档案。",
            "再演示用户补资料、补图片、增加竞品后，agent 如何沿同一份档案持续修改结论与结构。",
            "最后展示 checkpoint / 分支和知识审查，强调这是数码购买决策工作台，而不是一次性页面生成器。",
        ],
        "demo_script": [
            {
                "label": "第 1 步",
                "goal": "生成一份单品购买决策档案",
                "action": "start",
                "prompt": "帮我做一份华为 Mate 60 值不值得买的购买决策档案",
            },
            {
                "label": "第 2 步",
                "goal": "补充竞品并改成更像购买决策",
                "action": "fill",
                "prompt": "把小米 14 加进对比里，再把结论写得更像给预算 5000 左右用户的建议",
            },
            {
                "label": "第 3 步",
                "goal": "补图片并强化视觉引导",
                "action": "fill",
                "prompt": "怎么没有图片，加一些真机图，再让开头更吸引用户眼球",
            },
            {
                "label": "第 4 步",
                "goal": "分叉一个更保守的降价观望版本",
                "action": "fill",
                "prompt": "基于当前版本分叉一个更偏向等等降价再买的版本",
            },
        ],
        "starter_prompt": "帮我做一份华为 Mate 60 值不值得买的购买决策档案",
        "edit_prompt": "把小米 14 加进对比里，再把结论写得更像给预算 5000 左右用户的建议",
        "theme_prompt": "怎么没有图片，加一些真机图，再让开头更吸引用户眼球",
        "branch_prompt": "基于当前版本分叉一个更偏向等等降价再买的版本",
    },
]


class ShowcaseManager:
    def list_profiles(self) -> List[Dict[str, Any]]:
        return SHOWCASE_PROFILES


showcase_manager = ShowcaseManager()
