from app.agents.state import UIProjectState

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监 7.1】：规则式稳定涂装。
    优先保证样式结果可预测、可复现，避免 ReAct 子图污染共享状态。
    """
    print("🎨 [美术指导 Agent] 开始审视画布，准备精准涂装...")
    
    # 1. 物理打底：初始化基础样式表
    # 此时 data_dsl 中的 blocks 已经定稿
    data_dsl = state.get("data_dsl", {})
    blocks = data_dsl.get("blocks", [])
    
    # 初始化 style_dsl
    initial_style_dsl = {}
    for block in blocks:
        initial_style_dsl[block["id"]] = {
            "css_classes": "transition-all duration-700", 
            "inline_styles": {}
        }
    
    # 2. 提取全局导演定调与雷达信号
    intent_res = state.get("intent_result")
    if isinstance(intent_res, dict):
        vibe = intent_res.get("visual_vibe", "general")
        intensity = intent_res.get("intensity_level", 0.0)
    else:
        vibe = getattr(intent_res, "visual_vibe", "general") if intent_res else "general"
        intensity = getattr(intent_res, "intensity_level", 0.0) if intent_res else 0.0

    VIBE_CLASS_MAP = {
        "general": "rounded-[28px] bg-white shadow-[0_24px_60px_rgba(15,23,42,0.08)]",
        "minimalist": "rounded-[24px] bg-white border border-slate-200 shadow-sm",
        "cyberpunk": "rounded-[26px] bg-zinc-950 text-cyan-100 border border-cyan-500/40 shadow-[0_0_30px_rgba(34,211,238,0.18)]",
        "vintage": "rounded-[18px] bg-[#fffaf1] border border-amber-900/10 shadow-[0_18px_40px_rgba(92,63,33,0.10)]",
        "luxury": "rounded-[30px] bg-zinc-950 text-amber-100 border border-amber-400/20 shadow-[0_24px_60px_rgba(0,0,0,0.30)]",
    }

    EMPHASIS_MAP = {
        "TitleBlock": "pt-8 pb-2",
        "StoryText": "px-1",
        "ProductSpecCard": "p-4",
        "RadarChartBlock": "p-4",
        "VersusCard": "overflow-hidden",
        "PollBlock": "p-4",
        "LocationBlock": "p-4",
        "WeatherPolaroid": "overflow-hidden",
        "CoverSwiper": "overflow-hidden",
    }

    final_style_dsl = dict(initial_style_dsl)
    base_vibe_classes = VIBE_CLASS_MAP.get(vibe, VIBE_CLASS_MAP["general"])
    animated_class = "transition-all duration-700"
    intensity_class = "scale-[1.01]" if intensity >= 0.7 else ""

    for block in blocks:
        block_id = block["id"]
        block_type = block.get("component_type", "")
        emphasis = EMPHASIS_MAP.get(block_type, "")
        final_style_dsl[block_id] = {
            "css_classes": " ".join(part for part in [animated_class, base_vibe_classes, emphasis, intensity_class] if part).strip(),
            "inline_styles": {}
        }

    STYLE_VARS_MAP = {
        "minimalist": {"--bg-color": "#ffffff", "--primary-vibe": "#333333"},
        "cyberpunk": {"--bg-color": "#050505", "--primary-vibe": "#00f2ff"},
        "vintage": {"--bg-color": "#f4efe1", "--primary-vibe": "#5d4037"},
        "luxury": {"--bg-color": "#1a1a1a", "--primary-vibe": "#d4af37"}
    }
    page_theme = data_dsl.get("page_theme") or {}
    base_global_vars = STYLE_VARS_MAP.get(vibe, {"--bg-color": "#f1f5f9", "--primary-vibe": "#ff2442"})
    final_style_dsl["global_vars"] = {**base_global_vars, **page_theme}

    print(f"✅ [美术指导] 涂装完毕，共处理 {len(blocks)} 个区块。")
    return {"style_dsl": final_style_dsl}
