import json
from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.scenario_manager import scenario_manager

def apply_visual_styles(node: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    """
    【递归样式映射引擎 3.0】：零硬编码逻辑，全量执行插件词典。
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 彻底解耦：从 scenario_manager 实时获取该场景的视觉规则
    scenario_config = scenario_manager.get_config(scenario_id)
    visual_rules = scenario_config.get("visual_rules", {})
    
    # 执行语义翻译 (props -> tailwind classes)
    for category, mappings in visual_rules.items():
        val = props.get(category)
        if val and val in mappings:
            computed_classes.append(mappings[val])
            
    # 注入翻译后的物理类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 递归遍历 AST 树
    for child in node.get("children", []):
        if isinstance(child, dict):
            apply_visual_styles(child, scenario_id)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉翻译官】：不再拥有个人偏好，完全尊重场景自治配置。
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    
    # 获取识别到的主场景 ID
    scenarios = state.get("scenarios", ["general"])
    scenario_id = scenarios[0]
    
    if not ast_root:
        return {}
        
    print(f"🎨 [Style Agent] 正在根据场景 [{scenario_id}] 执行自治样式翻译...")
    
    # 执行递归映射
    styled_ast = apply_visual_styles(ast_root, scenario_id)
    data_dsl["root"] = styled_ast
    
    return {"data_dsl": data_dsl}
