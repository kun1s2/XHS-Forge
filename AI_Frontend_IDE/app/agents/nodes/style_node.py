from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.scenario_manager import scenario_manager

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监 4.0】：六维雷达驱动的调性引擎。
    不再依赖图片取色，而是根据 visual_vibe 信号强制注入美学风格。
    """
    data_dsl = state.get("data_dsl", {})
    blocks = data_dsl.get("blocks", [])
    scenario_id = state.get("scenarios", ["general"])[0]
    
    intent_res = state.get("intent_result")
    if isinstance(intent_res, dict):
        vibe_signal = intent_res.get("visual_vibe", "general")
        intensity = intent_res.get("intensity_level", 0.0)
    else:
        vibe_signal = getattr(intent_res, "visual_vibe", "general") if intent_res else "general"
        intensity = getattr(intent_res, "intensity_level", 0.0) if intent_res else 0.0

    # 1. 定义风格映射表 (Style Matrix)
    STYLE_MATRIX = {
        "minimalist": {
            "--bg-color": "#ffffff",
            "--primary-vibe": "#333333",
            "--radius": "8px",
            "--spacing": "12px"
        },
        "cyberpunk": {
            "--bg-color": "#050505",
            "--primary-vibe": "#00f2ff",
            "--accent-vibe": "#ff00ff",
            "--radius": "0px",
            "--spacing": "24px"
        },
        "vintage": {
            "--bg-color": "#f4efe1",
            "--primary-vibe": "#5d4037",
            "--radius": "16px",
            "--spacing": "20px"
        },
        "luxury": {
            "--bg-color": "#1a1a1a",
            "--primary-vibe": "#d4af37",
            "--radius": "4px",
            "--spacing": "32px"
        },
        "kawaii": {
            "--bg-color": "#fff5f7",
            "--primary-vibe": "#ff8fab",
            "--radius": "32px",
            "--spacing": "16px"
        }
    }

    # 2. 确定全局变量
    style_config = STYLE_MATRIX.get(vibe_signal, {
        "--bg-color": "#f1f5f9",
        "--primary-vibe": "#ff2442",
        "--radius": "16px",
        "--spacing": "20px"
    })

    # 3. 情绪烈度补丁 (High Intensity Patch)
    if intensity > 0.8:
        style_config["--primary-vibe"] = "#ff0000" # 强制警示红
        style_config["--shadow-vibe"] = "0 10px 40px rgba(255, 0, 0, 0.2)"
    else:
        style_config["--shadow-vibe"] = "0 10px 40px rgba(0, 0, 0, 0.05)"

    # 4. 生成组件级样式补丁 (Component-level Style Overrides)
    style_dsl = {
        "global_vars": style_config
    }

    # 为每个 block 预分配风格 class
    for block in blocks:
        block_id = block["id"]
        comp_type = block["component_type"]
        
        classes = ["transition-all duration-500"]
        
        # 针对风格注入特定的 Tailwind 类名
        if vibe_signal == "cyberpunk":
            classes.append("border border-[#00f2ff]/30 shadow-[0_0_15px_rgba(0,242,255,0.2)] bg-black/80")
        elif vibe_signal == "minimalist":
            classes.append("border-b border-gray-100 pb-4 mb-4")
        elif vibe_signal == "vintage":
            classes.append("sepia-[0.2] contrast-[0.9] brightness-[1.05]")
        
        # 情绪高涨时的动态效果
        if intensity > 0.8:
            classes.append("ring-2 ring-red-500/20")

        style_dsl[block_id] = {
            "css_classes": " ".join(classes),
            "inline_styles": {}
        }

    print(f"🎨 [六维风格引擎] 激活风格: {vibe_signal} | 情绪烈度: {intensity:.1f}")
    
    return {
        "style_dsl": style_dsl
    }
