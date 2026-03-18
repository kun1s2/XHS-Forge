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
    mode = getattr(intent_res, "narrative_mode", "spatial") if intent_res else "spatial"
    intensity = getattr(intent_res, "intensity_level", 0.0) if intent_res else 0.0
    
    # 提取资产状态 (用于执行无图防御)
    know = state.get("retrieved_knowledge", {})
    available_images = know.get("image_urls", []) if isinstance(know, dict) else []

    # 加载场景配置
    scenario_prompt = scenario_manager.get_prompt(scenario_id)
    scenario_config = scenario_manager.get_config(scenario_id)
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    # 2. 构造 4.0 全栈架构师提示词
    base_system = f"""你是一个顶级的 Generative UI 全栈架构师。
你的任务是将内容编排为具备高度交互性的 AST 树。

【🔥 无图防御机制 (最高铁律)】:
当前可用图片数: {len(available_images)}。
如果图片数为 0，你【绝对禁止】使用以下组件：
- CoverSwiper (轮播图)
- PolaroidImage (拍立得)
- BentoGrid (依赖图片的网格)
在无图状态下，你必须且只能使用纯文本与纯 CSS 交互组件：TitleBlock, VersusCard, StoryText, AccordionTimeline, TagList, InteractionsBar。

【核心优先级声明】:
大一统叙事映射准则的优先级高于场景建议顺序。

【大一统叙事映射准则】:
1. 对立模式 (contrast): 如果 intensity > 0.4，必须在核心位置挂载 VersusCard。
2. 递进模式 (sequential): 如果 intensity > 0.6，必须挂载 Timeline 类组件。
3. 悬念模式 (suspense): 如果 intensity > 0.8，必须使用 GiftBox 或 FlipCard 包裹内容。
"""

    full_outline_system = f"""{base_system}\n\n【场景专属指令】:\n{scenario_prompt}\n\n【场景配置】:\n{json.dumps(scenario_config, ensure_ascii=False)}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", full_outline_system),
        ("human", "请规划 AST 树。当前可用图片数: {{ image_count }}\n<content>\n{{ content_context }}\n</content>")
    ], template_format="jinja2")

    try:
        chain = prompt | structured_llm
        inputs = {"content_context": content_context, "image_count": len(available_images)}
        
        result: OutlineOutput = await invoke_with_retry(chain, inputs)
        
        # 3. ✨ [热修复：代码级紧箍咒] 强制拦截与补位
        ast_root = result.root.model_dump(exclude_none=True)
        
        # 拦截 A: 强制对冲组件 (VersusCard)
        if mode == "contrast" and intensity > 0.4:
            def find_vsc(node):
                if node.get("component_type") == "VersusCard": return True
                return any(find_vsc(c) for c in node.get("children", []) if isinstance(c, dict))
            
            if not find_vsc(ast_root):
                print("🚨 [哨兵干预] 强制注入 VersusCard 以满足 contrast 协议")
                vs_node = {
                    "id": "forced_vs_logic", "component_type": "VersusCard",
                    "props": {"visual_priority": "high"},
                    "content_brief": "提取产品的核心优点与槽点进行对撞分析。"
                }
                if "children" not in ast_root: ast_root["children"] = []
                ast_root["children"].insert(0, vs_node)

        # 拦截 B: 物理级图片清理 (二次保险)
        if not available_images:
            def purge(node):
                if "children" in node:
                    node["children"] = [c for c in node["children"] if c.get("component_type") not in ["CoverSwiper", "PolaroidImage"]]
                    for c in node["children"]: purge(c)
            purge(ast_root)

        final_archetype = str(result.detected_archetype) if result.detected_archetype else active_archetype
        
        return {
            "page_outline": ast_root,
            "data_dsl": {"page_title": result.page_title, "page_theme": result.page_theme, "root": ast_root},
            "active_archetype": final_archetype
        }
                
    except Exception as e:
        print(f"❌ Outline Agent 失败: {e}")
        if settings.DEBUG_MODE: raise e
        return {"page_outline": {}}
