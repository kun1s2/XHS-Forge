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
    【X-Forge 3.0 插件化大纲节点】：动态加载场景指令并规划 AST
    """
    llm = get_outline_llm()
    structured_llm = llm.with_structured_output(OutlineOutput, method="function_calling")
    
    # 1. 提取当前状态与 4.0 信号
    active_archetype = state.get("active_archetype", "general")
    scenarios = state.get("scenarios", [])
    scenario_id = scenarios[0] if scenarios else "general"
    
    intent_res = state.get("intent_result")
    vibe = getattr(intent_res, "emotional_vibe", "neutral") if intent_res else "neutral"
    conflict = getattr(intent_res, "conflict_score", 0.0) if intent_res else 0.0
    
    # ✨ 核心重构：动态注入场景专属指令与 4.0 编排信号
    scenario_prompt = scenario_manager.get_prompt(scenario_id)
    scenario_config = scenario_manager.get_config(scenario_id)
    
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    # 2. 构造 4.0 全栈架构师提示词
    base_system = f"""你是一个顶级的 Generative UI 全栈架构师 (X-Forge 4.0)。
你的任务是将全局文案转化为一棵支持无限嵌套的抽象语法树 (AST)。

【4.0 动态组件编排准则 (最高优先级)】:
1. 冲突对冲：如果检测到冲突指数 (Conflict) > 0.6，必须在关键位置使用 VersusCard (红黑对峙卡) 来展示正反观点。
2. 惊喜礼盒：如果检测到情绪 (Vibe) 为 "surprise"，必须将核心祝福或安利文案包裹在 GiftBox (惊喜礼盒) 容器中。
3. 翻转悬念：对于科普、避雷或反转内容，优先使用 FlipCard (3D 翻转卡) 制造探索感。
4. 语义化 Props：禁止输出 CSS，只能使用 variant, visual_priority 等语义属性。

【当前 4.0 编排信号】:
- 情绪特征: {vibe}
- 冲突指数: {conflict}
"""

    full_outline_system = f"""{base_system}

【场景专属指令】:
{scenario_prompt}

【场景配置参考】:
{json.dumps(scenario_config, ensure_ascii=False)}
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", full_outline_system),
        ("human", "请基于 4.0 编排信号和以下文案，规划一棵高保真的交互式 AST 树：\n<content>\n{{ content_context }}\n</content>\n(请通过调用工具输出 JSON 格式结果)")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        inputs = {"content_context": content_context}
        
        result: OutlineOutput = await invoke_with_retry(chain, inputs)
        
        # 3. 处理 AST 输出
        ast_root = result.root.model_dump(exclude_none=True)
        # ✨ 哨兵纠偏：确保 Archetype 是字符串标签
        final_archetype = str(result.detected_archetype) if result.detected_archetype else active_archetype
        
        # 初始化 data_dsl 的大纲部分
        dsl_patch = {
            "page_title": result.page_title,
            "page_theme": result.page_theme,
            "root": ast_root
        }
        
        print(f"🗺️ [插件化大纲] 场景 [{scenario_id}] AST 树生成完毕，根节点 ID: {result.root.id}")

        return {
            "page_outline": ast_root,
            "data_dsl": dsl_patch,
            "active_archetype": final_archetype
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 插件化调用失败: {e}")
        if settings.DEBUG_MODE:
            raise e
        return {"page_outline": {}}
