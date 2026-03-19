import asyncio
from typing import Dict, Any
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import create_llm
from app.agents.state import UIProjectState
from app.core.config import settings
from app.tools.canvas_tools import apply_component_variant, analyze_hero_image_colors

# 🎨 美术指导专属工具箱
STYLE_TOOLS = [apply_component_variant, analyze_hero_image_colors]

async def style_agent(state: UIProjectState) -> dict:
    """
    【视觉总监 7.0】：语义化美术指导 Agent (Art Director)。
    废除静态覆盖，改用 ReAct 循环实现组件级精准涂装。
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

    # 3. 构造美术指导的“作战室”
    # 注意：这里我们使用 LLM_LOGIC_MODEL 处理复杂的审美决策
    llm = create_llm(
        model=settings.LLM_LOGIC_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        temperature=0.3
    )
    
    # 构建专门的美术指导智能体
    art_director = create_react_agent(
        model=llm,
        tools=STYLE_TOOLS,
        state_modifier=f"""你是一个顶级的小红书/抖音风格网页美术指导。
当前全局氛围设定：视觉风向 [{vibe}], 情绪烈度 [{intensity:.1f}]。

【职责说明】：
1. 你需要根据当前的 vibe 和积木列表，决定哪些组件需要特殊的视觉增强。
2. 调用 apply_component_variant 工具为特定组件注入灵魂（如赛博风发光、胶片滤镜等）。
3. 如果你认为配色需要参考头图，调用 analyze_hero_image_colors 获取建议。
4. 【铁律】：绝对不能给纯文字积木加上胶片滤镜！
5. 涂装完成后，直接停止调用工具并退出。"""
    )
    
    # 4. 执行涂装循环
    # 为了保证 state 在 ReAct 内部正确更新，我们将当前 state 传给它
    # 特别注意：create_react_agent 默认操作 messages，我们需要它修改我们的 style_dsl
    try:
        # 初始指令
        inputs = {"messages": [("user", "请开始对当前画布的积木进行高级定制涂装。")], **state}
        # 更新 style_dsl 底色
        inputs["style_dsl"] = initial_style_dsl
        
        result = await art_director.ainvoke(inputs)
        
        # 5. 提取产物
        final_style_dsl = result.get("style_dsl", initial_style_dsl)
        
        # ✨ 额外注入：全局 CSS 变量（基于 vibe 的硬核映射）
        STYLE_VARS_MAP = {
            "minimalist": {"--bg-color": "#ffffff", "--primary-vibe": "#333333"},
            "cyberpunk": {"--bg-color": "#050505", "--primary-vibe": "#00f2ff"},
            "vintage": {"--bg-color": "#f4efe1", "--primary-vibe": "#5d4037"},
            "luxury": {"--bg-color": "#1a1a1a", "--primary-vibe": "#d4af37"}
        }
        global_vars = STYLE_VARS_MAP.get(vibe, {"--bg-color": "#f1f5f9", "--primary-vibe": "#ff2442"})
        final_style_dsl["global_vars"] = global_vars

        print(f"✅ [美术指导] 涂装完毕，共处理 {len(blocks)} 个区块。")
        return {"style_dsl": final_style_dsl}
        
    except Exception as e:
        print(f"❌ [美术指导异常]: {e}")
        return {"style_dsl": initial_style_dsl}
