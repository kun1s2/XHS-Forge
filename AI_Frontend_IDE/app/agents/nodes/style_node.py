import json
from pathlib import Path
from typing import Dict, Any, List
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings

# 🎨 【样式词典】：语义 Props ➔ 真实 Tailwind 咒语的翻译官
STYLE_MAP = {
    "variant": {
        "glassmorphism": "bg-white/40 backdrop-blur-xl border border-white/50 shadow-xl",
        "flat-dark": "bg-gray-900 text-gray-100 border border-gray-800 shadow-2xl",
        "neumorphic": "bg-gray-100 shadow-[20px_20px_60px_#bebebe,-20px_-20px_60px_#ffffff] rounded-3xl",
        "neon": "bg-black border border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] text-cyan-400",
        "claymorphism": "bg-white shadow-[inset_0_-8px_12px_rgba(0,0,0,0.1),0_20px_40px_rgba(0,0,0,0.15)] rounded-[40px] border-4 border-white/20",
        "paper-cut": "bg-white shadow-[0_4px_10px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.06)] border-b-4 border-gray-200 transition-transform active:translate-y-1",
        "holographic": "bg-gradient-to-br from-fuchsia-500/20 via-cyan-500/20 to-lime-500/20 backdrop-blur-md border border-white/30"
    },
    "corner_style": {
        "rounded-none": "rounded-none",
        "rounded-md": "rounded-md",
        "rounded-2xl": "rounded-2xl",
        "rounded-full": "rounded-full",
        "asymmetric": "rounded-tl-[60px] rounded-br-[60px] rounded-tr-2xl rounded-bl-2xl"
    },
    "animation": {
        "fade-up": "animate-in fade-in slide-in-from-bottom-4 duration-700",
        "bouncy-pop": "hover:scale-105 active:scale-95 transition-transform duration-300",
        "cyber-glitch": "hover:skew-x-1 hover:brightness-110 transition-all",
        "smooth-fade": "transition-opacity duration-1000"
    }
}

# 🌈 【色彩高亮表】：根据主色调自动匹配辅助色
COLOR_ACCENT_MAP = {
    "slate": "text-slate-900 border-slate-200 bg-slate-50",
    "rose": "text-rose-600 border-rose-100 bg-rose-50",
    "emerald": "text-emerald-600 border-emerald-100 bg-emerald-50",
    "gold": "text-amber-700 border-amber-200 bg-gradient-to-b from-amber-50 to-white",
    "violet": "text-violet-600 border-violet-100 bg-violet-50",
    "orange": "text-orange-600 border-orange-100 bg-orange-50",
    "cyan": "text-cyan-600 border-cyan-100 bg-cyan-50"
}

def apply_visual_styles(node: Dict[str, Any], tokens: Dict[str, Any]) -> Dict[str, Any]:
    """
    【递归样式注入算法 2.0】：支持材质魔法与视觉优先级
    """
    props = node.get("props", {})
    computed_classes = []
    
    # 1. 基础映射
    for key, value in props.items():
        if key in STYLE_MAP and value in STYLE_MAP[key]:
            computed_classes.append(STYLE_MAP[key][value])
            
    # 2. 注入全局令牌样式
    palette = tokens.get("color_palette", "slate")
    if palette in COLOR_ACCENT_MAP:
        # 仅对叶子业务组件应用高亮色
        if node.get("component_type") not in ["Container", "BentoGrid"]:
            computed_classes.append(COLOR_ACCENT_MAP[palette])

    # 3. 视觉优先级 (visual_priority) 处理
    priority = props.get("visual_priority", "medium")
    if priority == "high":
        computed_classes.append("ring-4 ring-offset-2 ring-opacity-50 " + f"ring-{palette}-400")
        computed_classes.append("shadow-2xl z-10 scale-[1.02]")
    elif priority == "low":
        computed_classes.append("opacity-70 scale-95 grayscale-[20%]")

    # 4. 特殊布局处理
    if props.get("layout_vibe") == "organic":
        computed_classes.append("skew-y-1 rotate-1")

    # 5. 写入最终类名
    node["computed_classes"] = " ".join(computed_classes)
    
    # 6. 递归
    children = node.get("children") or []
    for child in children:
        if isinstance(child, dict):
            apply_visual_styles(child, tokens)
            
    return node

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监】：执行原子化设计令牌的深度映射
    """
    print("🎨 [Style Agent] 执行审美多样性爆发映射...")
    
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    
    # 假设这里我们已经通过 LLM 获得了 StyleVibeTokens
    # 为了演示，我们从 state 中提取或使用默认
    style_result = state.get("style_result")
    if not style_result:
        # 兼容性兜底：如果没有 style_result，则尝试构造
        tokens = {
            "color_palette": "rose",
            "bg_material": "glassmorphism",
            "corner_style": "rounded-2xl",
            "shadow_vibe": "shadow-xl",
            "animation_rhythm": "bouncy-pop"
        }
    else:
        tokens = style_result.global_tokens.model_dump()

    if not ast_root:
        return {}
        
    # 执行递归样式注入
    styled_ast = apply_visual_styles(ast_root, tokens)
    
    # 更新 DSL
    data_dsl["root"] = styled_ast
    
    print(f"✅ [Style Agent] 多样性样式应用完成: {tokens.get('bg_material')}")
    
    return {
        "data_dsl": data_dsl
    }
