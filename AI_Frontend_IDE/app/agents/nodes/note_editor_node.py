import json
from copy import deepcopy
from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, field_validator

from app.agents.state import UIProjectState, merge_dsl
from app.agents.tools_registry import LOCAL_NOTE_EDITOR_TOOLS, NOTE_EDITOR_TOOLS
from app.agents.utils.fact_utils import build_fact_grounding_context
from app.core.config import settings
from app.core.llm_factory import create_llm


SUPPORTED_COMPONENTS = {
    "TitleBlock": ["title"],
    "StoryText": ["paragraphs"],
    "ProductSpecCard": ["core_features"],
    "RadarChartBlock": ["dimensions", "scores"],
    "VersusCard": ["title", "proText", "conText"],
    "PollBlock": ["question", "option_a", "option_b"],
    "CoverSwiper": ["image_urls"],
    "LocationBlock": ["poi_name", "location"],
    "WeatherPolaroid": ["image_url", "desc"],
}

COMPONENT_QUERY_ALIASES = {
    "TitleBlock": ["标题", "标题卡", "大标题"],
    "StoryText": ["正文", "段落", "文案", "故事", "文本"],
    "ProductSpecCard": ["参数", "参数卡", "配置", "规格", "配置卡"],
    "RadarChartBlock": ["雷达图", "雷达", "评分图", "对比雷达"],
    "VersusCard": ["对比", "对比卡", "优缺点", "vs", "PK"],
    "PollBlock": ["投票", "投票卡", "互动投票", "poll"],
    "CoverSwiper": ["封面", "轮播", "大图", "图片轮播"],
    "LocationBlock": ["地点", "位置", "地图", "地址"],
    "WeatherPolaroid": ["天气", "拍立得", "天气卡", "天气拍立得"],
}

THEME_PATCH_PRESETS = {
    "gray_blue": {
        "--bg-color": "#e2e8f0",
        "--primary-vibe": "#475569",
        "--surface-color": "#f8fafc",
        "--text-color": "#0f172a",
        "--muted-color": "#64748b",
        "--border-color": "#cbd5e1",
    },
    "minimalist": {
        "--bg-color": "#f8fafc",
        "--primary-vibe": "#334155",
        "--surface-color": "#ffffff",
        "--text-color": "#0f172a",
        "--muted-color": "#64748b",
        "--border-color": "#e2e8f0",
    },
    "cyberpunk": {
        "--bg-color": "#050505",
        "--primary-vibe": "#00f2ff",
        "--surface-color": "#111827",
        "--text-color": "#e0f2fe",
        "--muted-color": "#67e8f9",
        "--border-color": "#155e75",
    },
    "vintage": {
        "--bg-color": "#f4efe1",
        "--primary-vibe": "#7c5a3c",
        "--surface-color": "#fffaf1",
        "--text-color": "#4b3621",
        "--muted-color": "#8b6b4a",
        "--border-color": "#d6c2a1",
    },
    "luxury": {
        "--bg-color": "#111111",
        "--primary-vibe": "#d4af37",
        "--surface-color": "#1f1f1f",
        "--text-color": "#fef3c7",
        "--muted-color": "#e5c76b",
        "--border-color": "#6b5620",
    },
}

THEME_KEY_ALIASES = {
    "--primary-color": "--primary-vibe",
    "--accent-color": "--primary-vibe",
    "--secondary-color": "--muted-color",
    "--foreground-color": "--text-color",
}

COMPONENT_TYPE_ALIASES = {
    alias.lower(): component_type
    for component_type, aliases in COMPONENT_QUERY_ALIASES.items()
    for alias in aliases + [component_type, component_type.lower()]
}


class NoteEditorAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: NotRequired[int]
    data_dsl: Annotated[dict, merge_dsl]
    style_dsl: Annotated[dict, merge_dsl]
    retrieved_knowledge: Any
    selected_element_id: str | None
    has_controversy: bool
    creator_persona: str | None


class LocalNoteEditOutput(BaseModel):
    thought_process: str | None = Field(default=None, description="局部编辑的推理过程")
    reason: str = Field(default="按用户要求完成局部编辑", description="本次局部编辑理由")
    action: Literal["update_block", "replace_block", "move_block", "remove_block", "noop"] = Field(
        default="update_block",
        description="对当前选中区块执行的动作",
    )
    block_id: str = Field(..., description="当前被编辑的区块 ID")
    new_component_type: str | None = Field(default=None, description="替换后的组件类型")
    content_brief: str | None = Field(default=None, description="更新后的区块职责描述")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="组件数据补丁")
    style_patch: dict[str, Any] = Field(default_factory=dict, description="组件样式补丁")
    move_to_index: int | None = Field(default=None, description="目标顺序索引")


class LocalTextRewriteOutput(BaseModel):
    reason: str = Field(default="已补全文案补丁", description="补全文案补丁的理由")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="需要回写到组件中的文案字段补丁")


class GlobalCanvasEditOutput(BaseModel):
    reason: str = Field(default="已按要求完成整页编辑", description="本次整页编辑理由")
    action: Literal[
        "update_page_title",
        "update_page_theme",
        "update_block",
        "rewrite_paragraph",
        "replace_block",
        "move_block",
        "remove_block",
        "noop",
    ] = Field(default="update_block", description="本次整页编辑动作")
    block_id: str | None = Field(default=None, description="目标区块 ID")
    block_index: int | None = Field(default=None, description="目标区块索引，从 0 开始")
    content_brief: str | None = Field(default=None, description="更新后的区块职责描述")
    page_title: str | None = Field(default=None, description="新的页面标题")
    payload_patch: dict[str, Any] = Field(default_factory=dict, description="区块数据补丁")
    style_patch: dict[str, Any] = Field(default_factory=dict, description="区块样式补丁")
    page_theme_patch: dict[str, Any] = Field(default_factory=dict, description="页面主题变量补丁")
    new_component_type: str | None = Field(default=None, description="替换后的组件类型")
    move_to_index: int | None = Field(default=None, description="移动后的目标索引")
    paragraph_index: int | None = Field(default=None, description="要重写的段落索引，从 0 开始")
    paragraph_text: str | None = Field(default=None, description="重写后的段落文本")

    @field_validator("new_component_type", mode="before")
    @classmethod
    def normalize_component_type(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return _normalize_component_type_name(value)
        return None

    @field_validator("page_theme_patch", mode="before")
    @classmethod
    def ensure_page_theme_patch_dict(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return _normalize_page_theme_patch(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return _normalize_page_theme_patch(parsed)
            except json.JSONDecodeError:
                pass

            theme_patch = {}
            for chunk in raw.split(";"):
                piece = chunk.strip()
                if not piece or ":" not in piece:
                    continue
                key, val = piece.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key and val:
                    theme_patch[key] = val
            return _normalize_page_theme_patch(theme_patch)
        return {}


def _normalize_page_theme_patch(theme_patch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(theme_patch, dict):
        return {}

    normalized = dict(theme_patch)
    for source_key, target_key in THEME_KEY_ALIASES.items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]

    if "--primary-vibe" in normalized and "--primary-color" not in normalized:
        normalized["--primary-color"] = normalized["--primary-vibe"]
    if "--muted-color" in normalized and "--secondary-color" not in normalized:
        normalized["--secondary-color"] = normalized["--muted-color"]

    return normalized


def _normalize_component_type_name(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw in SUPPORTED_COMPONENTS:
        return raw
    if raw.lower() in {name.lower() for name in SUPPORTED_COMPONENTS}:
        for component_name in SUPPORTED_COMPONENTS:
            if component_name.lower() == raw.lower():
                return component_name
    return COMPONENT_TYPE_ALIASES.get(raw.lower())


def _extract_component_mentions(user_query: str) -> list[tuple[int, str, str]]:
    mentions: list[tuple[int, str, str]] = []
    lowered_query = (user_query or "").lower()
    for alias, component_type in COMPONENT_TYPE_ALIASES.items():
        start = 0
        while True:
            idx = lowered_query.find(alias, start)
            if idx == -1:
                break
            mentions.append((idx, component_type, alias))
            start = idx + len(alias)
    mentions.sort(key=lambda item: (item[0], -len(item[2])))
    deduped: list[tuple[int, str, str]] = []
    seen = set()
    for idx, component_type, alias in mentions:
        key = (idx, component_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((idx, component_type, alias))
    return deduped


def _infer_replacement_component_type(user_query: str, explicit_type: str | None = None) -> str | None:
    normalized_explicit = _normalize_component_type_name(explicit_type)
    if normalized_explicit:
        return normalized_explicit

    query = user_query or ""
    for splitter in ["换成", "改成", "替换成", "改为", "变成"]:
        if splitter in query:
            suffix = query.split(splitter, 1)[1]
            mentions = _extract_component_mentions(suffix)
            if mentions:
                return mentions[0][1]

    mentions = _extract_component_mentions(query)
    return mentions[-1][1] if mentions else None


def _infer_target_component_type(
    user_query: str,
    action: str,
    replacement_type: str | None = None,
) -> str | None:
    query = user_query or ""
    heuristic_pairs = [
        ("标题", "TitleBlock"),
        ("大标题", "TitleBlock"),
        ("正文", "StoryText"),
        ("文本", "StoryText"),
        ("段落", "StoryText"),
        ("封面", "CoverSwiper"),
        ("轮播", "CoverSwiper"),
        ("参数", "ProductSpecCard"),
        ("配置", "ProductSpecCard"),
    ]
    for token, component_type in heuristic_pairs:
        if token in query:
            if action != "replace_block" or component_type != _normalize_component_type_name(replacement_type):
                return component_type

    mentions = _extract_component_mentions(user_query)
    if not mentions:
        return None

    if action == "replace_block":
        normalized_replacement_type = _normalize_component_type_name(replacement_type)
        for _, component_type, _ in mentions:
            if component_type != normalized_replacement_type:
                return component_type
        return mentions[0][1]

    return mentions[0][1]


def _summarize_blocks(data_dsl: dict) -> str:
    blocks = list((data_dsl or {}).get("blocks", []))
    if not blocks:
        return "无"

    lines = []
    for index, block in enumerate(blocks[:8]):
        lines.append(
            f"{index}. id={block.get('id')} | type={block.get('component_type')} | brief={block.get('content_brief', '')}"
        )
    if len(blocks) > 8:
        lines.append(f"... 共 {len(blocks)} 个区块")
    return "\n".join(lines)


def _has_local_selection(selected_element_id: str | None) -> bool:
    return selected_element_id not in [None, "", "无", "无 (全局修改)", "none"]


def _select_note_editor_tools(selected_element_id: str | None):
    return LOCAL_NOTE_EDITOR_TOOLS if _has_local_selection(selected_element_id) else NOTE_EDITOR_TOOLS


def _build_note_editor_prompt(state: NoteEditorAgentState) -> str:
    data_dsl = state.get("data_dsl", {}) or {}
    knowledge = state.get("retrieved_knowledge", {}) or {}
    selected_element_id = state.get("selected_element_id")
    creator_persona = state.get("creator_persona", "硬核数码博主")
    has_controversy = state.get("has_controversy", False)
    current_blocks = data_dsl.get("blocks", [])
    selected_payload = data_dsl.get(selected_element_id, {}) if selected_element_id else {}
    local_mode = _has_local_selection(selected_element_id)

    component_contract_text = "\n".join(
        [f"- {name}: 必填字段 {', '.join(fields)}" for name, fields in SUPPORTED_COMPONENTS.items()]
    )
    fact_grounding = build_fact_grounding_context(knowledge)

    return f"""你是 XHS-Forge 的 Note Editor V2。
你的职责不是走流水线，而是像真正的编辑器一样，直接把用户自然语言改成一张可渲染的笔记。

【最高目标】
通过工具直接编辑 Note DSL，完成“创建笔记”或“修改笔记”。

【当前工作模式】
- 模式: {"局部选中编辑" if local_mode else "整页编辑"}

【当前画布状态】
- 页面标题: {data_dsl.get("page_title") or "未设置"}
- 当前区块数: {len(current_blocks)}
- 当前选中组件: {selected_element_id or "无"}
- 当前创作者人设: {creator_persona}

【当前区块清单】
{_summarize_blocks(data_dsl)}

【当前选中区块数据】
{json.dumps(selected_payload, ensure_ascii=False) if selected_payload else "无"}

【可用事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【组件白名单与必填字段】
{component_contract_text}

【编辑铁律】
1. 所有页面修改必须通过工具完成，严禁空想最终 JSON。
2. 当前 prompt 已经提供了页面标题、区块清单、选中区块数据和事实知识，直接开始编辑，不要停留在重复诊断。
3. 如果页面为空，创建 4-6 个高完成度区块。
4. 如果页面不为空，优先更新现有区块；只有在用户明确要求新增，或者现有区块明显不够时，才创建新区块。
5. 如果用户选中了某个组件，优先修改该组件，不要擅自改整页。
6. 如果用户要求“替换组件类型”，优先使用 replace_note_block；如果用户要求调整顺序，使用 move_note_block。
7. 如果 battle_report 存在，优先创建或保留 VersusCard。
8. 如果 has_controversy = {str(has_controversy).lower()}，优先创建或保留 PollBlock。
9. 每个区块必须满足其必填字段，否则不能结束。
10. 除非用户明确要求，不要无意义地删除已有可用内容。
11. 同一个区块不要重复修改两次以上；如果已经达到用户要求，立即调用 finish_layout 结束。
12. 如果当前是局部选中编辑模式，默认只允许改动选中的那个区块；除非用户明确要求，不要新增区块、不要重写整页、不要修改其他区块。
13. 若“已确认事实”存在，正文、参数卡、对比结论都优先沿用这些值。
14. 若某个参数仍冲突且未确认，不要把它写成绝对参数。
"""


def _build_local_edit_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    data_dsl = state.get("data_dsl", {}) or {}
    style_dsl = state.get("style_dsl", {}) or {}
    selected_element_id = state.get("selected_element_id")
    knowledge = state.get("retrieved_knowledge", {}) or {}
    target_block = next(
        (block for block in data_dsl.get("blocks", []) if block.get("id") == selected_element_id),
        None,
    )
    target_payload = data_dsl.get(selected_element_id, {}) if selected_element_id else {}
    target_style = style_dsl.get(selected_element_id, {}) if selected_element_id else {}
    component_contract_text = "\n".join(
        [f"- {name}: 必填字段 {', '.join(fields)}" for name, fields in SUPPORTED_COMPONENTS.items()]
    )
    fact_grounding = build_fact_grounding_context(knowledge)

    return f"""你是 XHS-Forge 的局部笔记编辑器。
你的任务不是重写整页，而是只围绕当前选中区块输出一个结构化补丁计划。

【用户指令】
{user_query}

【当前选中区块】
{json.dumps(target_block or {}, ensure_ascii=False)}

【当前选中区块数据】
{json.dumps(target_payload, ensure_ascii=False)}

【当前选中区块样式】
{json.dumps(target_style, ensure_ascii=False)}

【当前画布摘要】
- 页面标题: {data_dsl.get("page_title") or "未设置"}
- 区块总数: {len(data_dsl.get("blocks", []))}
- 选中区块 ID: {selected_element_id or "无"}

【事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【组件白名单与必填字段】
{component_contract_text}

【输出规则】
1. 只能编辑 block_id={selected_element_id} 这个区块。
2. 如果只是改文案或样式，优先使用 action=update_block 或 action=noop，不要删除区块。
3. 如果用户明确要求“换成另一种组件”，使用 action=replace_block，并提供 new_component_type 与 payload_patch。
4. 如果用户明确要求调整顺序，使用 action=move_block，并填写 move_to_index。
5. 如果用户明确要求删除当前区块，才允许 action=remove_block。
6. payload_patch 只写需要变动的字段；style_patch 只写 css_classes 或 inline_styles。
7. 不要输出任何其他区块的信息，不要修改页面标题，不要新增新区块。
8. 如果用户指令不够明确，保持 action=noop，并给出最小 style_patch 或空补丁。
9. 若“已确认事实”存在，payload_patch 必须优先沿用这些值。
"""


def _build_global_edit_prompt(state: NoteEditorAgentState, user_query: str) -> str:
    data_dsl = state.get("data_dsl", {}) or {}
    style_dsl = state.get("style_dsl", {}) or {}
    knowledge = state.get("retrieved_knowledge", {}) or {}
    component_contract_text = "\n".join(
        [f"- {name}: 必填字段 {', '.join(fields)}" for name, fields in SUPPORTED_COMPONENTS.items()]
    )
    blocks = data_dsl.get("blocks", [])
    block_payloads = {
        block.get("id"): data_dsl.get(block.get("id"), {})
        for block in blocks
        if block.get("id")
    }
    block_styles = {
        block.get("id"): style_dsl.get(block.get("id"), {})
        for block in blocks
        if block.get("id")
    }
    fact_grounding = build_fact_grounding_context(knowledge)

    return f"""你是 XHS-Forge 的整页笔记编辑器。
当前页面已经存在，你的任务是根据用户自然语言修改现有页面，而不是重新生成一整页。

【用户指令】
{user_query}

【当前页面标题】
{data_dsl.get("page_title") or "未设置"}

【当前区块清单】
{_summarize_blocks(data_dsl)}

【当前区块数据】
{json.dumps(block_payloads, ensure_ascii=False)}

【当前区块样式】
{json.dumps(block_styles, ensure_ascii=False)}

【事实知识】
{json.dumps(knowledge, ensure_ascii=False)}

【事实可信度约束】
{fact_grounding or "暂无已确认事实；若仍存在参数冲突，避免写成确定数字结论。"}

【组件白名单与必填字段】
{component_contract_text}

【输出规则】
1. 当前页面已经存在，默认是在修改现有页面，不要重新生成整页。
2. 如果用户说“保留标题”，不要改 page_title。
3. 如果用户提到“第一段/第二段/第三段”，优先使用 action=rewrite_paragraph，并填写 paragraph_index。
4. 如果用户要改某个区块内容，使用 action=update_block 并给出 block_id 或 block_index。
5. 如果用户要替换组件类型，使用 action=replace_block。
6. 如果用户要调整顺序，使用 action=move_block。
7. 如果用户要改整体视觉主题、背景色、主色，使用 action=update_page_theme，并填写 page_theme_patch。
8. 如果用户要删除某个区块，使用 action=remove_block。
9. payload_patch 只写必要字段；style_patch 只写样式变化；page_theme_patch 只写页面级 CSS 变量。
10. 除非用户明确要求，不要删除其他区块，不要改写整页标题。
11. 如果指令不明确，使用 action=noop。
12. 若“已确认事实”存在，修改正文、参数卡、对比卡时必须优先沿用这些值。
"""


def _apply_local_edit_plan(
    selected_element_id: str | None,
    original_data_dsl: dict,
    original_style_dsl: dict,
    plan: LocalNoteEditOutput,
) -> tuple[dict, dict]:
    final_data_dsl = deepcopy(original_data_dsl or {})
    final_style_dsl = deepcopy(original_style_dsl or {})
    if not _has_local_selection(selected_element_id):
        return final_data_dsl, final_style_dsl

    target_id = str(selected_element_id)
    blocks = list(final_data_dsl.get("blocks", []))
    target_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == target_id), None)
    if target_index is None:
        return final_data_dsl, final_style_dsl

    target_block = deepcopy(blocks[target_index])
    current_payload = deepcopy(final_data_dsl.get(target_id, {}))
    current_style = deepcopy(final_style_dsl.get(target_id, {}))
    action = plan.action

    if action == "remove_block":
        final_data_dsl["blocks"] = [block for block in blocks if block.get("id") != target_id]
        final_data_dsl.pop(target_id, None)
        final_style_dsl.pop(target_id, None)
        return final_data_dsl, final_style_dsl

    if action == "replace_block":
        next_component_type = plan.new_component_type or target_block.get("component_type") or current_payload.get("type")
        if next_component_type:
            target_block["component_type"] = next_component_type
            current_payload = {"type": next_component_type, **(plan.payload_patch or {})}
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
    elif action in {"update_block", "move_block", "noop"}:
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
        current_payload = {**current_payload, **(plan.payload_patch or {})}
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]

    if plan.style_patch:
        inline_styles_patch = plan.style_patch.get("inline_styles", {})
        merged_style = {**current_style, **plan.style_patch}
        if isinstance(current_style.get("inline_styles"), dict) and isinstance(inline_styles_patch, dict):
            merged_style["inline_styles"] = {
                **current_style.get("inline_styles", {}),
                **inline_styles_patch,
            }
        final_style_dsl[target_id] = merged_style

    blocks[target_index] = target_block
    if action == "move_block" and plan.move_to_index is not None:
        moved_block = blocks.pop(target_index)
        safe_index = min(max(0, plan.move_to_index), len(blocks))
        blocks.insert(safe_index, moved_block)
    final_data_dsl["blocks"] = blocks
    final_data_dsl[target_id] = current_payload
    return final_data_dsl, final_style_dsl


def _has_global_edit_request(user_query: str, data_dsl: dict) -> bool:
    if not (data_dsl or {}).get("blocks"):
        return False
    return any(
        token in (user_query or "")
        for token in [
            "保留",
            "重写",
            "改",
            "修改",
            "优化",
            "调整",
            "简短",
            "简洁",
            "精简",
            "丰富",
            "删除",
            "删掉",
            "替换",
            "换成",
            "移动",
            "挪",
            "润色",
            "标题",
            "正文",
            "文本",
            "封面",
            "主题",
            "风格",
            "第二段",
            "第一段",
            "第三段",
        ]
    )


def _resolve_global_target_id(plan: GlobalCanvasEditOutput, data_dsl: dict, user_query: str = "") -> str | None:
    blocks = list((data_dsl or {}).get("blocks", []))
    inferred_target_type = _infer_target_component_type(user_query, plan.action, plan.new_component_type)

    if plan.block_id:
        explicit_type = next(
            (block.get("component_type") for block in blocks if block.get("id") == plan.block_id),
            None,
        )
        if inferred_target_type and explicit_type and explicit_type != inferred_target_type:
            hinted_block = next(
                (block for block in blocks if block.get("component_type") == inferred_target_type),
                None,
            )
            if hinted_block:
                return hinted_block.get("id")
        return plan.block_id
    if plan.block_index is not None and 0 <= plan.block_index < len(blocks):
        return blocks[plan.block_index].get("id")
    if plan.action == "rewrite_paragraph":
        for block in blocks:
            block_id = block.get("id")
            payload = data_dsl.get(block_id, {})
            paragraphs = payload.get("paragraphs")
            if isinstance(paragraphs, list) and paragraphs:
                return block_id
    if inferred_target_type:
        for block in blocks:
            if block.get("component_type") == inferred_target_type:
                return block.get("id")
    return blocks[0].get("id") if blocks else None


def _apply_global_edit_plan(
    original_data_dsl: dict,
    original_style_dsl: dict,
    plan: GlobalCanvasEditOutput,
    user_query: str = "",
) -> tuple[dict, dict]:
    final_data_dsl = deepcopy(original_data_dsl or {})
    final_style_dsl = deepcopy(original_style_dsl or {})
    blocks = list(final_data_dsl.get("blocks", []))

    if plan.action == "noop":
        return final_data_dsl, final_style_dsl

    if plan.action == "update_page_title" and plan.page_title:
        final_data_dsl["page_title"] = plan.page_title
        return final_data_dsl, final_style_dsl

    if plan.action == "update_page_theme" and plan.page_theme_patch:
        current_theme = deepcopy(final_data_dsl.get("page_theme", {}))
        final_data_dsl["page_theme"] = {**current_theme, **plan.page_theme_patch}
        return final_data_dsl, final_style_dsl

    target_id = _resolve_global_target_id(plan, final_data_dsl, user_query=user_query)
    if not target_id:
        return final_data_dsl, final_style_dsl

    target_index = next((idx for idx, block in enumerate(blocks) if block.get("id") == target_id), None)
    if target_index is None:
        return final_data_dsl, final_style_dsl

    target_block = deepcopy(blocks[target_index])
    current_payload = deepcopy(final_data_dsl.get(target_id, {}))
    current_style = deepcopy(final_style_dsl.get(target_id, {}))

    if plan.action == "remove_block":
        final_data_dsl["blocks"] = [block for block in blocks if block.get("id") != target_id]
        final_data_dsl.pop(target_id, None)
        final_style_dsl.pop(target_id, None)
        return final_data_dsl, final_style_dsl

    if plan.action == "replace_block":
        next_component_type = (
            _infer_replacement_component_type(user_query, plan.new_component_type)
            or target_block.get("component_type")
            or current_payload.get("type")
        )
        if next_component_type:
            target_block["component_type"] = next_component_type
            current_payload = {"type": next_component_type, **(plan.payload_patch or {})}
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
    elif plan.action == "rewrite_paragraph":
        paragraphs = list(current_payload.get("paragraphs", []))
        paragraph_index = plan.paragraph_index if plan.paragraph_index is not None else 0
        if 0 <= paragraph_index < len(paragraphs) and plan.paragraph_text:
            paragraphs[paragraph_index] = plan.paragraph_text
            current_payload["paragraphs"] = paragraphs
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]
    elif plan.action in {"update_block", "move_block"}:
        if plan.content_brief:
            target_block["content_brief"] = plan.content_brief
        current_payload = {**current_payload, **(plan.payload_patch or {})}
        if target_block.get("component_type") and "type" not in current_payload:
            current_payload["type"] = target_block["component_type"]

    if plan.style_patch:
        inline_styles_patch = plan.style_patch.get("inline_styles", {})
        merged_style = {**current_style, **plan.style_patch}
        if isinstance(current_style.get("inline_styles"), dict) and isinstance(inline_styles_patch, dict):
            merged_style["inline_styles"] = {
                **current_style.get("inline_styles", {}),
                **inline_styles_patch,
            }
        final_style_dsl[target_id] = merged_style

    blocks[target_index] = target_block
    if plan.action == "move_block" and plan.move_to_index is not None:
        moved_block = blocks.pop(target_index)
        safe_index = min(max(0, plan.move_to_index), len(blocks))
        blocks.insert(safe_index, moved_block)

    final_data_dsl["blocks"] = blocks
    final_data_dsl[target_id] = current_payload
    return final_data_dsl, final_style_dsl


def _extract_rewritable_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    rewritable = {}
    for key in [
        "title",
        "subtitle",
        "question",
        "option_a",
        "option_b",
        "desc",
        "quote",
        "proText",
        "conText",
        "paragraphs",
    ]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            rewritable[key] = value
        elif isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            rewritable[key] = value
    return rewritable


def _has_tone_rewrite_request(user_query: str) -> bool:
    return any(token in (user_query or "") for token in ["毒舌", "犀利", "更狠", "尖锐", "刻薄"])


def _build_theme_patch_fallback(user_query: str, intent_result: Any = None) -> dict[str, Any]:
    raw_query = (user_query or "").lower()
    vibe = ""
    if isinstance(intent_result, dict):
        vibe = str(intent_result.get("visual_vibe", "") or "").lower()
    else:
        vibe = str(getattr(intent_result, "visual_vibe", "") or "").lower()

    if any(token in raw_query for token in ["灰蓝", "蓝灰", "石板蓝", "slate blue"]):
        return deepcopy(THEME_PATCH_PRESETS["gray_blue"])
    if any(token in raw_query for token in ["黑金", "奢华", "高级黑", "luxury"]):
        return deepcopy(THEME_PATCH_PRESETS["luxury"])
    if any(token in raw_query for token in ["赛博", "霓虹", "cyberpunk", "neon"]):
        return deepcopy(THEME_PATCH_PRESETS["cyberpunk"])
    if any(token in raw_query for token in ["复古", "胶片", "vintage", "奶油"]):
        return deepcopy(THEME_PATCH_PRESETS["vintage"])
    if any(token in raw_query for token in ["极简", "简约", "克制", "minimalist"]):
        return deepcopy(THEME_PATCH_PRESETS["minimalist"])

    if vibe in THEME_PATCH_PRESETS:
        return deepcopy(THEME_PATCH_PRESETS[vibe])
    return {}


def _build_tone_rewrite_fallback(
    user_query: str,
    block_descriptor: dict[str, Any] | None,
    current_payload: dict[str, Any],
) -> dict[str, Any]:
    if not _has_tone_rewrite_request(user_query):
        return {}

    component_type = (block_descriptor or {}).get("component_type") or current_payload.get("type")
    if component_type == "PollBlock":
        fallback = {}
        question = current_payload.get("question")
        option_a = current_payload.get("option_a")
        option_b = current_payload.get("option_b")
        if isinstance(question, str) and question.strip():
            stripped = question.rstrip("？?！!。.")
            fallback["question"] = f"说句难听的，{stripped}？"
        if isinstance(option_a, str) and option_a.strip():
            fallback["option_a"] = f"真爱粉硬冲：{option_a}"
        if isinstance(option_b, str) and option_b.strip():
            fallback["option_b"] = f"清醒党避雷：{option_b}"
        return fallback

    if component_type == "StoryText":
        paragraphs = current_payload.get("paragraphs")
        if isinstance(paragraphs, list) and paragraphs and all(isinstance(item, str) for item in paragraphs):
            return {
                "paragraphs": [
                    f"说句难听的，{paragraphs[0]}" if idx == 0 else text
                    for idx, text in enumerate(paragraphs)
                ]
            }

    return {}


async def _maybe_backfill_local_payload_patch(
    llm,
    user_query: str,
    block_descriptor: dict[str, Any] | None,
    current_payload: dict[str, Any],
    plan: LocalNoteEditOutput,
) -> LocalNoteEditOutput:
    if plan.action != "update_block" or plan.payload_patch:
        return plan

    rewritable_fields = _extract_rewritable_payload_fields(current_payload)
    if not rewritable_fields:
        return plan

    component_type = (block_descriptor or {}).get("component_type") or current_payload.get("type") or "UnknownBlock"
    rewrite_prompt = f"""你要为一个已选中的组件补全文案补丁。

【用户指令】
{user_query}

【组件类型】
{component_type}

【当前可改写字段】
{json.dumps(rewritable_fields, ensure_ascii=False)}

【规则】
1. 只返回需要改写的可见文案字段，不要返回其他结构字段。
2. 如果用户是在调语气、风格、攻击性、温柔度、简洁度，必须把变化写进 payload_patch，不能只停留在说明层。
3. 尽量保留原意和字段结构；如果字段是字符串列表，返回同样结构。
4. 如果用户要求不明确，也尽量给出最小但可见的文案变化。
"""

    try:
        rewriter = llm.with_structured_output(LocalTextRewriteOutput, method="function_calling")
        rewrite = await rewriter.ainvoke(rewrite_prompt)
        if rewrite.payload_patch:
            plan.payload_patch = rewrite.payload_patch
            if not plan.reason:
                plan.reason = rewrite.reason
    except Exception as e:
        print(f"⚠️ [Note Editor V2] 文案补丁回填失败: {e}")

    if not plan.payload_patch:
        fallback_patch = _build_tone_rewrite_fallback(user_query, block_descriptor, current_payload)
        if fallback_patch:
            plan.payload_patch = fallback_patch
    return plan


def _restrict_local_edit_scope(
    selected_element_id: str | None,
    original_data_dsl: dict,
    updated_data_dsl: dict,
    original_style_dsl: dict,
    updated_style_dsl: dict,
) -> tuple[dict, dict]:
    if not _has_local_selection(selected_element_id):
        return updated_data_dsl, updated_style_dsl

    target_id = str(selected_element_id)
    original_blocks = list((original_data_dsl or {}).get("blocks", []))
    updated_blocks = list((updated_data_dsl or {}).get("blocks", original_blocks))
    original_ids = [block.get("id") for block in original_blocks]
    updated_ids = [block.get("id") for block in updated_blocks]

    original_target_block = next((block for block in original_blocks if block.get("id") == target_id), None)
    updated_target_block = next((block for block in updated_blocks if block.get("id") == target_id), None)

    final_data_dsl = deepcopy(original_data_dsl or {})
    final_style_dsl = deepcopy(original_style_dsl or {})

    if original_target_block is None:
        return final_data_dsl, final_style_dsl

    if target_id not in updated_ids:
        final_blocks = [block for block in original_blocks if block.get("id") != target_id]
        final_data_dsl["blocks"] = final_blocks
        final_data_dsl.pop(target_id, None)
        final_style_dsl.pop(target_id, None)
        return final_data_dsl, final_style_dsl

    final_blocks = []
    for block in original_blocks:
        if block.get("id") == target_id:
            final_blocks.append(deepcopy(updated_target_block or original_target_block))
        else:
            final_blocks.append(deepcopy(block))
    final_data_dsl["blocks"] = final_blocks

    if target_id in updated_data_dsl:
        final_data_dsl[target_id] = deepcopy(updated_data_dsl[target_id])

    if target_id in updated_style_dsl:
        final_style_dsl[target_id] = deepcopy(updated_style_dsl[target_id])

    for block_id in list(final_data_dsl.keys()):
        if block_id in {"blocks", "page_title", "page_theme"}:
            continue
        if block_id != target_id and block_id not in original_ids:
            final_data_dsl.pop(block_id, None)

    for style_id in list(final_style_dsl.keys()):
        if style_id == "global_vars":
            continue
        if style_id != target_id and style_id not in original_ids:
            final_style_dsl.pop(style_id, None)

    return final_data_dsl, final_style_dsl


async def note_editor_node(state: UIProjectState) -> dict:
    """
    Note Editor V2：统一处理自然语言的新建/全局修改请求。
    核心思想：直接编辑 Note DSL，而不是把请求拆成过多下游创意节点。
    """
    main_msgs = state.get("main_messages", [])
    raw_user_content = getattr(main_msgs[-1], "content", "") if main_msgs else "请整理当前笔记"
    if isinstance(raw_user_content, list):
        user_query = "".join(
            str(part.get("text"))
            for part in raw_user_content
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
        ).strip() or "请整理当前笔记"
    else:
        user_query = str(raw_user_content)
    selected_element_id = state.get("selected_element_id")
    data_dsl = state.get("data_dsl", {})
    knowledge = state.get("retrieved_knowledge", {})
    creator_persona = state.get("creator_persona", "硬核数码博主")
    has_controversy = state.get("has_controversy", False)
    intent_result = state.get("intent_result")
    local_mode = _has_local_selection(selected_element_id)
    target_exists = any(
        block.get("id") == selected_element_id
        for block in (data_dsl or {}).get("blocks", [])
    )

    llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.2,
    )

    if local_mode and target_exists:
        try:
            original_data_dsl = state.get("data_dsl", {}) or {}
            original_style_dsl = state.get("style_dsl", {}) or {}
            local_editor = llm.with_structured_output(LocalNoteEditOutput, method="function_calling")
            plan = await local_editor.ainvoke(_build_local_edit_prompt(state, user_query))
            current_target_block = next(
                (block for block in original_data_dsl.get("blocks", []) if block.get("id") == selected_element_id),
                None,
            )
            current_target_payload = original_data_dsl.get(selected_element_id, {})
            plan = await _maybe_backfill_local_payload_patch(
                llm,
                user_query,
                current_target_block,
                current_target_payload,
                plan,
            )
            updated_data_dsl, updated_style_dsl = _apply_local_edit_plan(
                selected_element_id,
                original_data_dsl,
                original_style_dsl,
                plan,
            )
            updated_data_dsl, updated_style_dsl = _restrict_local_edit_scope(
                selected_element_id,
                original_data_dsl,
                updated_data_dsl,
                original_style_dsl,
                updated_style_dsl,
            )
            print(
                f"✅ [Note Editor V2] 局部编辑完成: block={selected_element_id} | action={plan.action}"
            )
            return {
                "data_dsl": updated_data_dsl,
                "style_dsl": updated_style_dsl,
                "main_messages": [AIMessage(content=plan.reason or "已完成当前选中区块的更新。")],
            }
        except Exception as e:
            print(f"❌ [Note Editor V2] 局部编辑失败: {e}")
            return {
                "main_messages": [AIMessage(content="当前区块编辑失败，已保留原页面状态。")]
            }

    if not local_mode and _has_global_edit_request(user_query, data_dsl):
        try:
            original_data_dsl = state.get("data_dsl", {}) or {}
            original_style_dsl = state.get("style_dsl", {}) or {}
            global_editor = llm.with_structured_output(GlobalCanvasEditOutput, method="function_calling")
            plan = await global_editor.ainvoke(_build_global_edit_prompt(state, user_query))
            if plan.action == "update_page_theme" and not plan.page_theme_patch:
                plan.page_theme_patch = _build_theme_patch_fallback(user_query, intent_result)
            updated_data_dsl, updated_style_dsl = _apply_global_edit_plan(
                original_data_dsl,
                original_style_dsl,
                plan,
                user_query=user_query,
            )
            print(f"✅ [Note Editor V2] 整页编辑完成: action={plan.action} | block={plan.block_id or plan.block_index}")
            return {
                "data_dsl": updated_data_dsl,
                "style_dsl": updated_style_dsl,
                "main_messages": [AIMessage(content=plan.reason or "已完成页面更新。")],
            }
        except Exception as e:
            print(f"❌ [Note Editor V2] 整页编辑失败: {e}")
            return {
                "main_messages": [AIMessage(content="整页编辑失败，已保留原页面状态。")]
            }

    editor = create_react_agent(
        model=llm,
        tools=_select_note_editor_tools(selected_element_id),
        prompt=_build_note_editor_prompt,
        state_schema=NoteEditorAgentState,
    )

    try:
        original_data_dsl = state.get("data_dsl", {}) or {}
        original_style_dsl = state.get("style_dsl", {}) or {}
        result = await editor.ainvoke(
            {
                "messages": [("user", f"请开始编辑笔记：{user_query}")],
                "data_dsl": original_data_dsl,
                "style_dsl": original_style_dsl,
                "retrieved_knowledge": knowledge,
                "selected_element_id": selected_element_id,
                "has_controversy": has_controversy,
                "creator_persona": creator_persona,
            }
        )
        last_msg = result.get("messages", [])[-1] if result.get("messages") else None
        final_text = getattr(last_msg, "content", "") if last_msg else ""
        updated_data_dsl = result.get("data_dsl") or original_data_dsl
        updated_style_dsl = result.get("style_dsl") or original_style_dsl
        updated_data_dsl, updated_style_dsl = _restrict_local_edit_scope(
            selected_element_id,
            original_data_dsl,
            updated_data_dsl,
            original_style_dsl,
            updated_style_dsl,
        )

        block_count = len(updated_data_dsl.get("blocks", [])) if isinstance(updated_data_dsl, dict) else 0
        print(f"✅ [Note Editor V2] 已完成编辑，当前区块数: {block_count}")
        return {
            "data_dsl": updated_data_dsl,
            "style_dsl": updated_style_dsl,
            "main_messages": [AIMessage(content=final_text or "笔记已完成更新。")],
        }
    except Exception as e:
        print(f"❌ [Note Editor V2] 失败: {e}")
        return {
            "main_messages": [AIMessage(content="笔记编辑器遇到异常，已保留当前页面状态。")]
        }
