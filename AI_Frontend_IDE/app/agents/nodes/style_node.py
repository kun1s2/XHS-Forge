import json
from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.scenario_manager import scenario_manager

def apply_visual_styles(node: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    """
    【递归样式映射引擎 3.0】：强制通透化，抹除一切“滤镜”隐患
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 1. 动态获取场景自治词典
    scenario_config = scenario_manager.get_config(scenario_id)
    style_rules = scenario_config.get("visual_rules", {})
    
    for category, mappings in style_rules.items():
        val = props.get(category)
        if val and val in mappings:
            computed_classes.append(mappings[val])
            
    # 2. 通用布局拦截器 (Infrastructure Props)
    if "col_span" in props:
        computed_classes.append(f"col-span-{props['col_span']}")
    
    # 视觉优先级处理 (✨ 哨兵修复：抹除灰度滤镜，仅保留阴影和缩放)
    priority = props.get("visual_priority", "medium")
    if priority == "high":
        computed_classes.append("shadow-2xl z-10 scale-[1.03]")
    elif priority == "low":
        computed_classes.append("opacity-90 scale-95") # 移除 grayscale 

    # 3. 注入翻译后的物理类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 4. 递归处理
    for child in node.get("children", []):
        if isinstance(child, dict):
            apply_visual_styles(child, scenario_id)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监】：接管全量视觉变量，撕掉白布滤镜
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    scenario_id = state.get("scenarios", ["general"])[0]
    
    if not ast_root: return {}

    # 获取场景偏好
    scenario_config = scenario_manager.get_config(scenario_id)
    vibe = scenario_config.get("visual_preference", {})
    
    # ✨ 核心修复：优先使用配置中的 bg_color，否则根据材质自动降级
    bg_color = vibe.get("bg_color")
    if not bg_color:
        material = vibe.get("variant", "flat-light")
        bg_color = "#0f172a" if material == "flat-dark" else "#f9fafb"
    
    # 构造全局变量补丁 (确保投送到 style_dsl)
    global_vars = {
        "--bg-color": bg_color,
        "--primary-vibe": vibe.get("color_palette", "#ff2442")
    }

    print(f"🎨 [Style Agent] 视觉通透化处理完成，底色: {bg_color}")
    
    # 执行递归映射
    styled_ast = apply_visual_styles(ast_root, scenario_id)
    data_dsl["root"] = styled_ast
    
    return {
        "data_dsl": data_dsl,
        "style_dsl": {
            "global_vars": global_vars
        }
    }
