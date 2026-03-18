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
            temperature=0.7 # 增加随机性以提升创意度
        )
    return _llm_instance

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def outline_agent(state: UIProjectState) -> dict:
    """
    【X-Forge 6.0 导演级大纲节点】：引入场景配方，彻底告别“纯文本”枯燥排版。
    """
    llm = get_outline_llm()
    structured_llm = llm.with_structured_output(OutlineOutput, method="function_calling")
    
    active_archetype = state.get("active_archetype", "general")
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    intent_res = state.get("intent_result")
    
    image_assets = state.get("image_assets") or []
    image_count = len(image_assets)
    
    # 信号提取
    mode = getattr(intent_res, "narrative_mode", "spatial") if not isinstance(intent_res, dict) else intent_res.get("narrative_mode", "spatial")
    cta = getattr(intent_res, "call_to_action", "none") if not isinstance(intent_res, dict) else intent_res.get("call_to_action", "none")

    scenario_prompt = scenario_manager.get_prompt(scenario_id)
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    # 2. 构造“导演级”提示词
    base_system = f"""你是一个顶级的 Generative UI 导演。你的任务是将枯燥的内容转化为【高交互、多维度】的一维区块流。

【🚀 积木多样性铁律 (禁止平庸)】:
1. 拒绝复读文本：全页 StoryText 严禁超过 2 个。如果话太多，请将其拆解到其他功能积木中。
2. 强制交互：必须根据内容，从下述组件中【至少选择 3 种】不同的非文本积木进行组合。
3. 视觉节奏：利用 CoverSwiper 置顶，利用 TagList 收尾，中间必须有‘视觉高潮’（如雷达图或翻转卡）。

【🎬 场景专属配方 (必选其一)】:
- 如果是【测评/科技】: 必须包含 [RadarChartBlock, VersusCard, ProductSpecCard]。
- 如果是【生活/分享】: 必须包含 [WeatherPolaroid, HandwrittenText, LocationBlock]。
- 如果是【互动/引流】: 必须包含 [PollBlock, FlipCard, GiftBox]。

【可用组件库详解】:
- RadarChartBlock: 性能多维对比（测评必选）
- VersusCard: 极性观点对撞（有争议必选）
- ProductSpecCard: 参数网格（呈现硬核数据）
- WeatherPolaroid: 时态氛围拍立得（增加真实感）
- FlipCard: 翻转卡片（用于‘正面/背面’、‘真相/假象’对比）
- PollBlock: 投票（引导评论）
- StoryText: 仅用于必要的故事过渡
- TagList: 亮点总结

【当前资产与信号】:
- 图片数: {image_count} | 模式: {mode} | 目标: {cta}
- 导演定调: {content_context}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", base_system),
        ("human", "请根据资产数({image_count})和导演定调，规划一个极具活力的积木排版。")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        result: OutlineOutput = await invoke_with_retry(chain, {
            "content_context": content_context, 
            "image_count": image_count
        })
        
        blocks = [b.model_dump() for b in result.blocks]
        
        # 物理熔断
        if image_count == 0:
            visual_components = ["CoverSwiper", "CollageContainer", "PolaroidImage", "WeatherPolaroid"]
            blocks = [b for b in blocks if b["component_type"] not in visual_components]

        return {
            "data_dsl": {
                "page_title": result.page_title, 
                "page_theme": result.page_theme, 
                "blocks": blocks
            },
            "active_archetype": str(result.detected_archetype) if result.detected_archetype else active_archetype
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 失败: {e}")
        return {}
