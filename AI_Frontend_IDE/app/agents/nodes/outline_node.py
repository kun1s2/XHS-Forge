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
    【X-Forge 4.0 插件化大纲节点】：具备“无图防御”与“协议强制”的智能编排大脑
    """
    llm = get_outline_llm()
    structured_llm = llm.with_structured_output(OutlineOutput, method="function_calling")
    
    # 1. 状态提取与协议识别
    active_archetype = state.get("active_archetype", "general")
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"

    intent_res = state.get("intent_result")
    
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
    
    know = state.get("retrieved_knowledge", {})
    available_images = know.get("image_urls", []) if isinstance(know, dict) else []

    scenario_prompt = scenario_manager.get_prompt(scenario_id)
    scenario_config = scenario_manager.get_config(scenario_id)
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    # 2. 构造 4.0 全栈架构师提示词
    base_system = f"""你是一个顶级的移动端图文排版主编 (X-Forge 4.0)。
你的任务是根据“叙事协议”信号，将文案编排为自上而下的一维线性“区块流 (Block Stream)”。

【🚀 积木排版法则 (绝对严禁嵌套)】:
1. 页面由一组顺序排列的 blocks 组成。
2. 每个 block 必须包含唯一的 id (如 title_1, product_card_2) 和 component_type。
3. 绝对不要尝试在 block 内部进行嵌套（如 Container 嵌套 Row）。
4. 动线优先：如果你检测到冲突指数 > 0.4，必须在排版中包含 VersusCard 组件。
5. 职责分配：为每个区块编写清晰的 content_brief。

【可用组件库】:
- TitleBlock: 页面标题
- StoryText: 沉浸式叙事文本
- VersusCard: 参数或观点的红蓝对比
- ProductCard: 单品展示
- ProductSpecCard: 核心参数网格
- CoverSwiper: 大图轮播
- WeatherPolaroid: 环境氛围感拍立得（自带时间/天气）
- PollBlock: 互动投票组件
- GiftBox: 惊喜感展开组件

【当前六维雷达信号】:
- 叙事模式: {mode}
- 情绪烈度: {intensity}
- 互动目标 (CTA): {cta}
- 环境感知: {temporal or "无"}
- 可用图片数: {len(available_images)}
"""

    full_outline_system = f"""{base_system}\n\n【场景专属指令】:\n{scenario_prompt}\n\n【场景配置】:\n{json.dumps(scenario_config, ensure_ascii=False)}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", full_outline_system),
        ("human", "请像搭积木一样排版页面。当前可用图片: {{ image_count }}\n<content>\n{{ content_context }}\n</content>")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        inputs = {"content_context": content_context, "image_count": len(available_images)}
        
        result: OutlineOutput = await invoke_with_retry(chain, inputs)
        
        # 3. ✨ [极简干预：全链路信号物理注入]
        blocks = [b.model_dump() for b in result.blocks]
        
        # 兜底校验：确保每个 block 都有 ID 和类型
        for i, b in enumerate(blocks):
            if not b.get("id"): b["id"] = f"block_{i}"
            if not b.get("component_type"): b["component_type"] = "StoryText"

        # A. 情绪对冲注入
        if mode == "contrast" and intensity > 0.4:
            if not any(b["component_type"] == "VersusCard" for b in blocks):
                print("🚨 [哨兵干预] 注入 VersusCard (对比信号触发)")
                blocks.insert(1, {"id": "forced_vs", "component_type": "VersusCard", "content_brief": "对撞分析产品的核心槽点与亮点。"})

        # B. 互动引导注入 (PollBlock)
        if cta in ["engagement", "help"]:
            if not any(b["component_type"] == "PollBlock" for b in blocks):
                print("🚨 [哨兵干预] 注入 PollBlock (互动信号触发)")
                blocks.append({"id": "forced_poll", "component_type": "PollBlock", "content_brief": "抛出引导性投票，引导用户评论互动。"})

        # C. 环境氛围感注入 (WeatherPolaroid)
        if temporal and temporal != "null":
            if not any(b["component_type"] == "WeatherPolaroid" for b in blocks):
                print(f"🚨 [哨兵干预] 注入 WeatherPolaroid (环境感知: {temporal})")
                blocks.insert(0, {"id": "forced_env", "component_type": "WeatherPolaroid", "content_brief": f"展示带有时态感 ({temporal}) 的氛围图片。"})

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
