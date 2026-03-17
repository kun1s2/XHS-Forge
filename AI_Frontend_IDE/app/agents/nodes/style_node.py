import json
from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.scenario_manager import scenario_manager

def apply_visual_styles(node: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    """
    【递归样式映射引擎】：不再拥有自身意识，完全执行插件字典指令。
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 动态获取当前场景的自治词典 (style_rules)
    scenario_config = scenario_manager.get_config(scenario_id)
    style_rules = scenario_config.get("style_rules", {})
    
    # 执行映射匹配
    for category, mappings in style_rules.items():
        val = props.get(category)
        if val and val in mappings:
            computed_classes.append(mappings[val])
            
    # 写入翻译后的 Tailwind 类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 递归遍历 AST
    for child in node.get("children", []):
        if isinstance(child, dict):
            apply_visual_styles(child, scenario_id)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉翻译官】：将语义 Props 转化为物理类名
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    scenario_id = state.get("scenarios", ["general"])[0]
    
    if not ast_root:
        return {}
        
    print(f"🎨 [Style Agent] 正在根据场景 [{scenario_id}] 执行自治样式翻译...")
    
    # 注入样式
    styled_ast = apply_visual_styles(ast_root, scenario_id)
    data_dsl["root"] = styled_ast
    
    return {"data_dsl": data_dsl}
