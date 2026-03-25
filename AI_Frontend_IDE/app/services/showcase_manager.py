from typing import Any, Dict, List


SHOWCASE_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "persistent_notes_workspace",
        "scenario_id": "notes",
        "title": "持续笔记工作台",
        "persona": "笔记共创搭档",
        "why_this_matters": "最适合展示长期状态、资料审查、版本回滚和围绕同一份笔记持续协作的能力。",
        "highlight_features": [
            "围绕同一份笔记持续新增、修改和回顾",
            "资料导入、候选知识审查与来源保留",
            "结构化 revision loop 与版本链",
            "白盒可观察：worker、checkpoint、artifact version",
        ],
        "talking_points": [
            "先展示用户提出一个笔记目标后，agent 如何判断结构、补资料并生成首版笔记。",
            "再演示用户补充上下文、导入资料、调整语气后，agent 如何沿同一份笔记持续修改。",
            "最后展示 checkpoint、分支和版本回滚，强调这是持续交互式笔记工作台，而不是一次性聊天生成器。",
        ],
        "demo_script": [
            {
                "label": "第 1 步",
                "goal": "生成一份首版项目笔记",
                "action": "start",
                "prompt": "帮我起一份关于 AI Product Studio 的项目笔记，先给出结构，再写首版内容。",
            },
            {
                "label": "第 2 步",
                "goal": "补一段背景并把标题改得更像项目页",
                "action": "fill",
                "prompt": "保留现有结论，再补一段项目背景，并把标题改得更像正式项目主页。",
            },
            {
                "label": "第 3 步",
                "goal": "导入资料并补来源",
                "action": "fill",
                "prompt": "我上传了一份需求说明，帮我抽出关键点并补到笔记里，保留来源说明。",
            },
            {
                "label": "第 4 步",
                "goal": "分叉一个更偏简洁的版本",
                "action": "fill",
                "prompt": "基于当前版本分叉一个更简洁、更适合对外展示的版本。",
            },
        ],
        "starter_prompt": "帮我起一份关于 AI Product Studio 的项目笔记，先给出结构，再写首版内容。",
        "edit_prompt": "保留现有结论，再补一段项目背景，并把标题改得更像正式项目主页。",
        "theme_prompt": "我上传了一份需求说明，帮我抽出关键点并补到笔记里，保留来源说明。",
        "branch_prompt": "基于当前版本分叉一个更简洁、更适合对外展示的版本。",
    },
]


class ShowcaseManager:
    def list_profiles(self) -> List[Dict[str, Any]]:
        return SHOWCASE_PROFILES


showcase_manager = ShowcaseManager()
