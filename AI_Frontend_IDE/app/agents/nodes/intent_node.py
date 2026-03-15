import json
import re
import os
import httpx
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import ArchetypeEnum, IntentOutput
from app.agents.memory_utils import get_trimmed_messages # ✨ 引入记忆截断器

# ✨ 性能优化：全局复用“物理直连”LLM 实例
_llm_instance = None

def get_intent_llm():
    global _llm_instance
    if _llm_instance is None:
        # ✨ 1. 强制禁用可能引发阻塞的 LangSmith 追踪
        os.environ["LANGSMITH_TRACING"] = "false"
        
        # ✨ 代码净化：移除之前的硬编码物理直连，交还给系统的标准 httpx
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0,
            max_retries=1
        )
    return _llm_instance

async def intent_agent(state: UIProjectState) -> dict:
    """
    【意图大脑 4.0】：回归 ainvoke 极速模式，强制代码级物理直连，彻底终结 30s 延迟。
    """
    llm = get_intent_llm()
    
    # 1. 提取用户输入与多模态资产
    active_panel = state.get("active_panel", "main")
    messages = state.get(f"{active_panel}_messages", [])
    
    # ✨ 核心优化：在处理意图之前执行记忆截断
    # 意图识别不需要太长历史，2000 token 足够
    trimmed_messages = get_trimmed_messages(messages, max_tokens=2000)
    
    raw_query = trimmed_messages[-1].content if trimmed_messages else ""
    if isinstance(raw_query, list):
        texts = [item["text"] for item in raw_query if item.get("type") == "text"]
        image_urls = [
            item["image_url"]["url"] if isinstance(item["image_url"], dict) else item["image_url"]
            for item in raw_query if item.get("type") == "image_url"
        ]
        user_query = " ".join(texts)
        if image_urls:
            user_query += f" | 🖼️ [附带图片]: {', '.join(image_urls)}"
    else:
        user_query = str(raw_query)

    print(f"\n\033[94m👤 [用户输入]: {user_query}\033[0m")

    # 2. 数据脱脂 (Skeleton)
    data_dsl = state.get("data_dsl", {})
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    if data_dsl:
        skeleton = {"components": {k: v.get("type") for k, v in data_dsl.items() if isinstance(v, dict)}}
        data_context = json.dumps(skeleton, ensure_ascii=False)
    else:
        data_context = "空"

    # 3. 加载系统提示词
    prompt_path = Path(__file__).parents[2] / "prompts" / "intent_system.xml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_template = f.read()

    # 注入当前场景辅助上下文，减少模型“忘本”概率
    active_archetype = state.get("active_archetype", "general")
    query_with_hint = f"{user_query}\n(当前场景背景: {active_archetype})"

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "用户的最新指令：{{ query }}")
    ], template_format="jinja2")
    
    try:
        inputs = {"data_context": data_context, "selected_element": selected_element, "query": query_with_hint}
        
        # 4. ✨ 极速调用：弃用 astream，回归 ainvoke
        # 在您的网络环境下，一次性传输比碎片流式传输快 10 倍以上！
        print(f"📡 正在发起【结构化输出】极速请求...")
        import time
        t_start = time.perf_counter()
        
        # ✨ 最新技术栈：直接使用 with_structured_output
        structured_llm = llm.with_structured_output(IntentOutput)
        result = await structured_llm.ainvoke(prompt.format_messages(**inputs))
        
        print(f"⏱️ [内部计时] 极速响应耗时: {time.perf_counter() - t_start:.2f}s")
        
        # ✨ 记录提示词快照
        prompt_data = [{"role": "system", "content": system_template}, {"role": "user", "content": query_with_hint}]

        # 统一转为字符串，确保全站逻辑一致
        archetype_str = result.detected_archetype.value if hasattr(result.detected_archetype, 'value') else str(result.detected_archetype)
        
        return {
            "intent_route": result.intent_route,
            "scenarios": result.scenarios,
            "active_archetype": archetype_str,
            "node_prompts": {"intent_agent": prompt_data}
        }
        
    except Exception as e:
        print(f"❌ Intent Agent 最终失败: {e}")
        # 降级路由：如果是全新生成就走 content，如果是修改就走 structure
        return {
            "intent_route": "content_node" if not data_dsl else "structure_node",
            "active_archetype": "general"
        }
