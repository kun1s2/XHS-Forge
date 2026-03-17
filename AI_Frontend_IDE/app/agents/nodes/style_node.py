import json
from pathlib import Path
from typing import Dict, Any, List
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.services.scenario_manager import scenario_manager

# ✨ 3.0 终极闭环：STYLE_MAP 已被物理隔离至 scenarios/*/config.json
# 这里不再保留任何硬编码样式。

def apply_visual_styles(node: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
    """
    【递归样式注入算法 3.0】：动态加载场景字典执行映射
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 1. 动态获取场景词典
    local_style_map = scenario_manager.get_style_mappings(scenario_id)
    
    # 2. 执行场景自治的映射逻辑
    for key, value in props.items():
        if key in local_style_map and value in local_style_map[key]:
            computed_classes.append(local_style_map[key][value])
            
    # 3. 写入最终类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 4. 递归
    children = node.get("children") or []
    for child in children:
        if isinstance(child, dict):
            apply_visual_styles(child, scenario_id)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监 - 3.0 场景自治版】：不再瞎猜，完全尊重插件配置
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    
    # 获取识别到的场景标签
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    
    if not ast_root:
        return {}
        
    print(f"🎨 [Style Agent] 正在应用场景 [{scenario_id}] 的自治样式词典...")
    
    # 执行递归样式注入
    styled_ast = apply_visual_styles(ast_root, scenario_id)
    
    # 更新 DSL
    data_dsl["root"] = styled_ast
    
    return {
        "data_dsl": data_dsl
    }
