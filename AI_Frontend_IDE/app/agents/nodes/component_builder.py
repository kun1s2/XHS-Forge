import json
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentData, ComponentStyle
from tenacity import retry, stop_after_attempt, wait_exponential

class ComponentBuilderOutput(BaseModel):
    data: ComponentData = Field(..., description="组件的具体数据负载")
    style: ComponentStyle = Field(..., description="组件的样式数据")

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None

def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.4
        )
    return _llm_instance

def log_retry(retry_state):
    print(f"⚠️ [Component Builder 重试] 尝试次数: {retry_state.attempt_number}, 错误原因: {retry_state.outcome.exception()}")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), before_sleep=log_retry)
async def invoke_with_retry(chain, inputs):
    return await chain.ainvoke(inputs)

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点】：接收单个组件任务，并发生成其数据和样式。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    user_query = state.get("user_query", "")
    archetype = state.get("active_archetype", "general")
    knowledge = state.get("retrieved_knowledge", "")
    persona = state.get("creator_persona", "硬核数码博主")
    
    print(f"👷 [并发工兵] 开始构建组件: {comp_id} ({comp_type})...")
    
    llm = get_builder_llm()
    structured_llm = llm.with_structured_output(ComponentBuilderOutput)
    
    # 动态构建系统提示词，这里为了极速开发，将文案和样式要求整合在一起
    system_prompt = f"""你是一个全能的前端组件构建专家。
当前任务：构建一个 ID 为 {comp_id}，类型为 {comp_type} 的组件。
场景原型：{archetype}
创作者人设：{persona}
知识库参考：{knowledge}

你需要同时输出该组件的数据 (Data) 和样式 (Style)。
- 数据：必须符合 {comp_type} 的结构规范。请根据人设和知识库撰写极具吸引力的文案。
- 样式：提供 Tailwind CSS 类名。必须使用以下间距 Token 来保证呼吸感：SM(16px/p-4), MD(24px/mb-6/p-6)。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "用户指令: {query}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        result: ComponentBuilderOutput = await invoke_with_retry(chain, {"query": user_query})
        
        # 构造发给 Reducer 的增量补丁
        data_patch = {comp_id: result.data.model_dump(exclude_none=True)}
        style_patch = {comp_id: result.style.model_dump(exclude_none=True)}
        
        print(f"✅ [并发工兵] 组件 {comp_id} 构建完毕！")
        
        # 直接返回更新后的字典，LangGraph 的 Reducer 会负责将所有并发工兵的结果合并
        return {
            "data_dsl": data_patch,
            "style_dsl": style_patch
        }
        
    except Exception as e:
        print(f"❌ [并发工兵] 组件 {comp_id} 构建失败: {e}")
        return {}
