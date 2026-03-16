import json
import re
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import StylePatchOutput, ComponentStyle # ✨ 引入宪法模型
from tenacity import retry, stop_after_attempt, wait_exponential

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_style_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.1
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Style Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), before_sleep=log_retry)
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def style_agent(state: UIProjectState) -> dict:
    """
    【智能样式守卫】：如果工兵已经产出了样式且用户没提视觉修改要求，则直接跳过，保护性能。
    """
    llm = get_style_llm()
    
    # 2. 准备状态变量
    data_dsl = state.get("data_dsl", {})
    current_style_dsl = state.get("style_dsl", {})
    theme_id = state.get("style_template_id", "Soft_Creamy")
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    
    style_msgs = state.get("style_messages", [])
    user_style_request = style_msgs[-1].content if style_msgs else "请根据当前主题生成初始样式。"
    
    # ✨ 核心破局：智能判断是否真的需要请求大模型
    # 如果 data_dsl 里的所有组件在 current_style_dsl 中都有了样式，且意图不是 style_node，则直接透传
    intent = state.get("intent_route", "")
    page_order = data_dsl.get("page_order", [])
    has_all_styles = all(comp_id in current_style_dsl for comp_id in page_order)
    
    if has_all_styles and intent != "style_node" and current_style_dsl.get("global_vars"):
        print("⚡ [样式守卫] 样式已齐备且无视觉修改指令，跳过 LLM 请求。")
        return {"style_dsl": current_style_dsl}

    print(f"🎨 [视觉渲染大脑] 正在为您设计高定版页面样式...")
    
    # ✨ 提取视觉 Vibe：确保取到的是字符串，修复 Enum 比较失败问题
    image_assets = state.get("image_assets", [])
    raw_archetype = state.get("active_archetype", "general")
    # 如果是 Enum 对象则取其 value
    active_archetype = raw_archetype.value if hasattr(raw_archetype, 'value') else str(raw_archetype)
    
    vibe_primaries = [a.get("primary_color") for a in image_assets if a.get("primary_color")]
    vibe_accents = [a.get("accent_color") for a in image_assets if a.get("accent_color")]
    
    # 【方案三：无图配色脑补】
    ARCHETYPE_PALETTES = {
        "gourmet": {"primary": "#FF9500", "accent": "#5856D6", "light": "rgba(255, 149, 0, 0.1)"},
        "travel": {"primary": "#007AFF", "accent": "#34C759", "light": "rgba(0, 122, 255, 0.1)"},
        "seeding": {"primary": "#FF2D55", "accent": "#FFCC00", "light": "rgba(255, 45, 85, 0.1)"},
        "news": {"primary": "#111111", "accent": "#007AFF", "light": "rgba(17, 17, 17, 0.05)"},
        "general": {"primary": "#ff2442", "accent": "#333333", "light": "rgba(255, 36, 66, 0.1)"}
    }
    
    if vibe_primaries:
        primary_vibe = vibe_primaries[0]
        accent_vibe = vibe_accents[0] if vibe_accents else "#333333"
        try:
            r = int(primary_vibe[1:3], 16)
            g = int(primary_vibe[3:5], 16)
            b = int(primary_vibe[5:7], 16)
            primary_vibe_light = f"rgba({r}, {g}, {b}, 0.1)"
        except:
            primary_vibe_light = "rgba(255, 36, 66, 0.1)"
    else:
        palette = ARCHETYPE_PALETTES.get(active_archetype, ARCHETYPE_PALETTES["general"])
        primary_vibe = palette["primary"]
        accent_vibe = palette["accent"]
        primary_vibe_light = palette["light"]
        print(f"🌈 [视觉引擎] 脑补场景 {active_archetype} 配色: {primary_vibe}")
    
    is_update = bool(current_style_dsl and len(current_style_dsl.keys()) > 0)

    # 3. 加载提示词
    prompt_path = Path(__file__).parents[2] / "prompts" / "style_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "用户的最新样式指令：\n<user_input>\n{{ user_query }}\n</user_input>\n(请以 JSON 格式输出)")
    ], template_format="jinja2")

    try:
        inputs = {
            "is_update": is_update,
            "theme_id": theme_id,
            "data_dsl": json.dumps(data_dsl, ensure_ascii=False),
            "current_style_dsl": json.dumps(current_style_dsl, ensure_ascii=False),
            "selected_element": selected_element,
            "user_query": user_style_request,
            "primary_vibe": primary_vibe
        }
        
        # 1. 直接获取结构化输出
        # ✨ 架构升级：使用 List 结构消除模型对 Dict Key 的注意力幻觉
        structured_llm = llm.with_structured_output(StylePatchOutput, method="function_calling")
        
        try:
            result = await invoke_with_retry(prompt | structured_llm, inputs)
        except Exception as e:
            print(f"❌ [Style Agent] 结构化解析彻底失败: {e}")
            raise e # 允许重试或抛出，不再进行自杀式降级
        
        # ✨ 记录提示词快照
        rendered_messages = prompt.format_messages(**inputs)
        prompt_snapshot = [{"role": m.type, "content": m.content} for m in rendered_messages]

        # 6. 组装增量补丁（将 List 重新转回全局 State 兼容的 Dict）
        style_patch = {}
        style_patch["global_vars"] = {
            "--primary-vibe": primary_vibe,
            "--primary-vibe-light": primary_vibe_light,
            "--accent-vibe": accent_vibe,
        }
        
        # 合并全局变量
        if hasattr(result, 'global_vars') and result.global_vars:
            style_patch["global_vars"].update(result.global_vars)
            
        # 🌟 核心重构：List -> Dict 无损组装
        if hasattr(result, 'components') and isinstance(result.components, list):
            for patch_item in result.components:
                comp_id = patch_item.component_id
                style_data = patch_item.style
                
                # 过滤 None 并转为纯 Dict 存入 Patch
                if style_data:
                    style_patch[comp_id] = {k: v for k, v in style_data.model_dump().items() if v is not None}
                
        return {
            "style_result": result,
            "style_dsl": style_patch,
            "node_prompts": {"style_node": prompt_snapshot}
        }
                
    except Exception as e:
        print(f"❌ Style Agent 彻底失败: {e}")
        return {"style_dsl": {}, "node_prompts": {"style_node": []}}
