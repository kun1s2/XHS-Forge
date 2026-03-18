import json
from pathlib import Path
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import OutlineOutput 
from tenacity import retry, stop_after_attempt, wait_exponential
from app.services.scenario_manager import scenario_manager

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_outline_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_BRAIN_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Outline Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), before_sleep=log_retry)
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def outline_agent(state: UIProjectState) -> dict:
    """
    【X-Forge 4.0 插件化大纲节点】：具备“无图防御”与“语义去重”的智能编排大脑
    """
    llm = get_outline_llm()
    structured_llm = llm.with_structured_output(OutlineOutput, method="function_calling")
    
    # 1. 状态提取
    active_archetype = state.get("active_archetype", "general")
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    intent_res = state.get("intent_result")
    
    # 获取图片资产数 (核心物理约束)
    image_assets = state.get("image_assets") or []
    image_count = len(image_assets)
    
    # 兼容处理信号源
    if isinstance(intent_res, dict):
        mode = intent_res.get("narrative_mode", "spatial")
        intensity = intent_res.get("intensity_level", 0.0)
        cta = intent_res.get("call_to_action", "none")
        temporal = intent_res.get("temporal_context")
    else:
        mode = getattr(intent_res, "narrative_mode", "spatial") if intent_res else "spatial"
        intensity = getattr(intent_res, "intensity_level", 0.0) if intent_res else 0.0
        cta = getattr(intent_res, "call_to_action", "none") if intent_res else "none"
        temporal = getattr(intent_res, "temporal_context", None) if intent_res else None

    scenario_prompt = scenario_manager.get_prompt(scenario_id)
    scenario_config = scenario_manager.get_config(scenario_id)
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    # 2. 构造 4.0 全栈架构师提示词
    base_system = f"""你是一个顶级的移动端图流排版主编 (X-Forge 4.0)。
你的任务是根据当前资产状况和叙事信号，编排一维线性“区块流 (Block Stream)”。

【🚨 核心排版红线 (生死铁律)】:
1. 视觉熔断：当前可用图片数为 [{image_count}]。
   - 如果图片数为 0: 绝对严禁使用 CoverSwiper, CollageContainer, WeatherPolaroid, PolaroidImage 等图片积木！
   - 如果图片数 > 0: 必须优先使用图片积木作为视觉锚点。
2. 语义去重：
   - 严禁连续开出职责重复的 StoryText。
   - 如果需要多个文字块，必须在 content_brief 中明确区分侧重点（如：'block_1 讲外观', 'block_2 讲实测性能'），绝不允许模糊填充！
3. 结构紧凑：页面由 4-6 个积木组成即可，拒绝冗余。

【可用组件库】:
- TitleBlock: 标题
- StoryText: 叙事文本
- VersusCard: 深度对比 (mode=contrast 时必选)
- ProductCard: 单品展示
- ProductSpecCard: 核心参数网格
- CoverSwiper: 大图轮播 (要求图片数>0)
- WeatherPolaroid: 时态氛围挂件 (要求图片数>0)
- PollBlock: 互动投票
- TagList: 话题标签

【当前六维雷达信号】:
- 叙事模式: {mode}
- 情绪烈度: {intensity} | 互动目标: {cta}
- 环境感知: {temporal or "无"} | 可用图片数: {image_count}
"""

    full_outline_system = f"""{base_system}\n\n【场景专属指令】:\n{scenario_prompt}\n\n【场景配置】:\n{json.dumps(scenario_config, ensure_ascii=False)}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", full_outline_system),
        ("human", "请根据资产数({{ image_count }})进行排版。内容背景:\n<content>\n{{ content_context }}\n</content>")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        inputs = {"content_context": content_context, "image_count": image_count}
        
        result: OutlineOutput = await invoke_with_retry(chain, inputs)
        
        # 3. ✨ [逻辑干预：全链路信号物理注入]
        blocks = [b.model_dump() for b in result.blocks]
        
        # 物理兜底：再次检查无图熔断
        if image_count == 0:
            original_len = len(blocks)
            blocks = [b for b in blocks if b["component_type"] not in ["CoverSwiper", "CollageContainer", "PolaroidImage", "WeatherPolaroid"]]
            if len(blocks) < original_len:
                print(f"🧹 [排版纠偏] 物理移除 {original_len - len(blocks)} 个无图可用的组件")

        # 情绪对冲注入 (VersusCard)
        if mode == "contrast" and intensity > 0.4:
            if not any(b["component_type"] == "VersusCard" for b in blocks):
                blocks.insert(1, {"id": "forced_vs", "component_type": "VersusCard", "content_brief": "对撞分析产品的核心极性对峙点。"})

        final_archetype = str(result.detected_archetype) if result.detected_archetype else active_archetype
        
        return {
            "data_dsl": {
                "page_title": result.page_title, 
                "page_theme": result.page_theme, 
                "blocks": blocks
            },
            "active_archetype": final_archetype
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 失败: {e}")
        if settings.DEBUG_MODE: raise e
        return {}
