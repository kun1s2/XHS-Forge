import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import UIProjectState
from app.core.config import settings
from app.core.schema import StructurePatchOutput # ✨ 引入宪法模型
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import sys

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_structure_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Structure Agent 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), before_sleep=log_retry)
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def structure_agent(state: UIProjectState) -> dict:
    # 1. 初始化具有结构化输出能力的 LLM —— 强绑定全局契约
    llm = get_structure_llm()
    # ✨ 性能优化：显式使用 json_mode
    structured_llm = llm.with_structured_output(StructurePatchOutput, method="json_mode")
    
    # 2. 提取当前状态
    current_data_dsl = state.get("data_dsl", {})
    selected_element = state.get("selected_element_id", "无 (全局修改)")
    active_archetype = state.get("active_archetype", "general")
    
    main_msgs = state.get("main_messages", [])
    user_query = main_msgs[-1].content if main_msgs else "请根据要求修改页面"
    if isinstance(user_query, list):
        user_query = str([item["text"] for item in user_query if item["type"] == "text"])
    
    content_msgs = state.get("content_messages", [])
    content_context = content_msgs[-1].content if content_msgs else "无特定的前置文案要求。"

    assets = state.get("image_assets", [])
    assets_text = json.dumps(assets, ensure_ascii=False) if assets else "无"
    is_update = bool(current_data_dsl and current_data_dsl.get("page_order"))

    # 3. ====== ✨ 现代化：从外部 XML 加载系统提示词 ======
    prompt_path = Path(__file__).parents[2] / "prompts" / "structure_system.xml"
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_template = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"致命错误：未找到排版提示词文件 {prompt_path}")

    # 4. ====== ✨ 现代化：构建 ChatPromptTemplate (Jinja2) ======
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", "用户的最新排版指令: {{ user_query }}")
    ], template_format="jinja2")

    try:
        # 5. 执行 LCEL 管道调用 (带重试机制)
        chain = prompt | structured_llm
        
        inputs = {
            "is_update": is_update,
            "current_data_dsl": json.dumps(current_data_dsl, ensure_ascii=False),
            "selected_element": selected_element,
            "active_archetype": active_archetype, 
            "content_context": content_context,
            "assets_text": assets_text,
            "user_query": user_query
        }
        
        # ✨ 新增：捕获渲染后的结构化提示词
        rendered_messages = prompt.format_messages(**inputs)
        prompt_data = [{"role": m.type, "content": m.content} for m in rendered_messages]
        
        # 使用带有重试装饰器的函数
        result: StructurePatchOutput = await invoke_with_retry(chain, inputs)
        
        # 6. ====== ✨ 极简模式：直接输出生成的结构补丁包 ======
        # 依靠 state.py 里的 merge_dsl 自动完成深度合并
        dsl_patch = {
            "page_title": result.page_title,
            "page_order": result.page_order
        }
        for comp_id, comp_data in result.components.items():
            # 过滤掉 None 值，确保补丁包的纯净
            dsl_patch[comp_id] = {k: v for k, v in comp_data.model_dump().items() if v is not None}
        
        # ✨ 修复：转为字符串
        archetype_str = result.detected_archetype.value if hasattr(result.detected_archetype, 'value') else str(result.detected_archetype)
        
        # ✨ 架构级加固：如果排版大脑输出了 general，但意图大脑已经锁定了更具体的场景，则保留具体的
        if archetype_str == "general" and active_archetype != "general":
            archetype_str = active_archetype
            print(f"⚓ [原型锚点] 强制保留高级场景: {archetype_str}")
                
    except Exception as e:
        print(f"❌ Structure Agent 最终失败 (已达到最大重试次数): {e}")
        # 失败返回空字典，Reducer 会保全当前页面状态，防止白屏
        dsl_patch = {} 
        prompt_data = []
        archetype_str = "general"

    return {
        "structure_result": result, # ✨ 供 WebSocket 截获思维链
        "data_dsl": dsl_patch,
        "active_archetype": archetype_str, # ✨ 更新当前原型 (字符串)
        "node_prompts": {"structure_node": prompt_data} # ✨ 保存结构化提示词
    }
