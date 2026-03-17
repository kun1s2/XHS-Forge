import json
from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.scenario_manager import scenario_manager

def apply_visual_styles(node: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    """
    【递归样式映射引擎】：遍历 AST，将语义 Props 翻译为物理类名
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 动态获取当前场景的自治词典
    scenario_config = scenario_manager.get_config(scenario_id)
    visual_rules = scenario_config.get("visual_rules", {})
    
    # 执行映射
    for category, mappings in visual_rules.items():
        val = props.get(category)
        if val and val in mappings:
            computed_classes.append(mappings[val])
            
    # 注入类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 递归处理子节点
    for child in node.get("children", []):
        if isinstance(child, dict):
            apply_visual_styles(child, scenario_id)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监】：不仅要翻译样式，还要控制“环境底色”
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    
    # 获取识别到的场景
    scenarios = state.get("scenarios", ["general"])
    scenario_id = scenarios[0]
    
    if not ast_root:
        return {}

    # 获取场景配置中的视觉偏好（用于决定环境底色）
    scenario_config = scenario_manager.get_config(scenario_id)
    vibe = scenario_config.get("visual_preference", {})
    
    # ✨ 核心修复：根据材质自动计算底色变量，彻底撕掉“白布”
    bg_color = "#ffffff"
    material = vibe.get("variant", "flat-light")
    
    if material == "flat-dark":
        bg_color = "#0f172a"
    elif material == "glassmorphism":
        bg_color = "#f8fafc" # 浅色蓝灰底，利于毛玻璃折射
    elif material == "claymorphism":
        bg_color = "#f1f5f9"
    
    # 构造全局变量补丁
    global_vars = {
        "--bg-color": bg_color,
        "--palette-vibe": vibe.get("color_palette", "slate"),
        "--material-vibe": material
    }

    print(f"🎨 [Style Agent] 正在应用场景 [{scenario_id}] 的视觉基调，底色: {bg_color}")
    
    # 执行递归映射
    styled_ast = apply_visual_styles(ast_root, scenario_id)
    
    # 同步到 DSL
    data_dsl["root"] = styled_ast
    
    # ✨ 关键：将全局变量同步到 style_dsl 供前端读取
    return {
        "data_dsl": data_dsl,
        "style_dsl": {
            "global_vars": global_vars
        }
    }
