import uuid
from typing import Annotated, Dict, Any, List
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import ToolMessage

# 安全的 CSS 变体字典
SAFE_VARIANTS = {
    "neon_glow": "bg-black/80 border border-cyan-500 shadow-[0_0_15px_rgba(0,242,255,0.3)] text-cyan-400",
    "danger_alert": "ring-2 ring-red-500 shadow-2xl scale-[1.02] transform",
    "vintage_film": "sepia-[0.3] contrast-[0.9]",
    "elegant_reading": "font-serif tracking-wide leading-relaxed text-gray-800"
}

# --- 🛠️ 画布手术刀：大纲 Agent 的 CRUD 工具箱 ---

@tool
def append_block(
    component_type: str, 
    content_brief: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【追加积木】：当你需要在页面末尾新增一个组件时，调用此工具。
    - component_type: 组件的类型名称 (如 'CoverSwiper', 'PollBlock', 'VersusCard')。
    - content_brief: 给下游撰稿工兵的指令简报 (如 '提取核心参数，语气要激动')。
    """
    new_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
    new_block = {
        "id": new_id,
        "component_type": component_type,
        "content_brief": content_brief
    }
    
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = list(current_blocks)
    updated_blocks.append(new_block)
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功追加积木: {new_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def insert_block(
    component_type: str, 
    content_brief: str, 
    insert_index: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【插入积木】：当你需要将新组件精确插入到页面的特定位置时，调用此工具。
    - component_type: 组件的类型名称。
    - content_brief: 撰稿指令简报。
    - insert_index: 插入的数组索引 (0 表示插在最前面)。请先通过观测仪表盘确认当前 blocks 的长度！
    """
    new_id = f"{component_type.lower()}_{uuid.uuid4().hex[:6]}"
    new_block = {"id": new_id, "component_type": component_type, "content_brief": content_brief}
    
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = list(current_blocks)
    
    safe_index = min(max(0, insert_index), len(updated_blocks))
    updated_blocks.insert(safe_index, new_block)
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功在索引 {safe_index} 插入积木: {new_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def remove_block(
    block_id: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【删除积木】：当你发现某个组件排版多余，或用户明确要求删除时，调用此工具。
    - block_id: 必须提供你想要删除的积木的精确 ID。
    """
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = [b for b in current_blocks if b.get("id") != block_id]
    
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=f"成功删除积木: {block_id}", tool_call_id=tool_call_id)]
        }
    )

@tool
def update_block_brief(
    block_id: str, 
    new_brief: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【更新积木简报】：当你不需要更换组件，只需要调整工兵的撰写要求时，调用此工具。
    - block_id: 要修改的积木 ID。
    - new_brief: 全新的撰写指令。
    """
    current_blocks = state.get("data_dsl", {}).get("blocks", [])
    updated_blocks = []
    
    found = False
    for b in current_blocks:
        new_b = dict(b)
        if new_b.get("id") == block_id:
            new_b["content_brief"] = new_brief
            new_b["needs_rebuild"] = True 
            found = True
        updated_blocks.append(new_b)
            
    msg = f"成功更新积木简报: {block_id}" if found else f"未找到积木: {block_id}"
    return Command(
        update={
            "data_dsl": {"blocks": updated_blocks, "_blocks_override": True},
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]
        }
    )

@tool
def finish_layout(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """
    【结束排版】：当你认为画布已经完美（积木总数在 5-8 个左右，且视觉打断节奏良好），或者已经彻底完成了用户的修改需求时，【必须】调用此工具跳出循环！
    """
    return Command(
        update={
            "messages": [ToolMessage(content="排版总编已完成画布定稿。", tool_call_id=tool_call_id)]
        }
    )

# --- 🎨 美术指导专用工具集 ---

@tool
def apply_component_variant(
    block_id: str, 
    variant_name: str, 
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[dict, InjectedState]
) -> Command:
    """
    【应用视觉变体】：当你认为某个积木需要特殊的视觉渲染时调用。
    可用变体：
    - 'neon_glow': 赛博朋克发光特效（适合硬核测评/对比卡）
    - 'danger_alert': 危险警示特效（适合情绪强烈的红黑榜或痛点金句）
    - 'vintage_film': 复古胶片滤镜（【绝对且仅能】用于 CoverSwiper/WeatherPolaroid 等图片组件！）
    - 'elegant_reading': 优雅阅读体验（适合 StoryText 等长文本组件）
    """
    style_dsl = state.get("style_dsl", {})
    updated_style = dict(style_dsl)
    
    if variant_name in SAFE_VARIANTS:
        if block_id in updated_style:
            # 拼接类名
            current_classes = updated_style[block_id].get("css_classes", "")
            if SAFE_VARIANTS[variant_name] not in current_classes:
                updated_style[block_id]["css_classes"] = f"{current_classes} {SAFE_VARIANTS[variant_name]}".strip()
            msg = f"✅ 成功为组件 {block_id} 挂载 {variant_name} 视觉特效。"
        else:
            msg = f"❌ 组件 {block_id} 不在样式表中。"
    else:
        msg = f"❌ 变体 {variant_name} 不存在。"
        
    return Command(
        update={
            "style_dsl": updated_style,
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]
        }
    )

@tool
def analyze_hero_image_colors(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """【色彩嗅探器】：扫描头图并返回主色调，帮助你做出更协调的色彩决策。"""
    # 模拟探针返回
    msg = "📸 扫描完毕，当前氛围主色调推荐使用：深红色 (Deep Red)。"
    return Command(
        update={
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]
        }
    )
