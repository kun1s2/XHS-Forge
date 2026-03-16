import json
import asyncio
import random
from pydantic import BaseModel, Field, field_validator
from typing import Any, Union, List, Dict
from app.core.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentData, ComponentStyle
from tenacity import retry, stop_after_attempt, wait_exponential

# 🛡️ 【GitHub 专属限流信号量】：限制最多同时只有 3 个工兵请求 API
# 解决 GitHub Models "Too many requests" 的物理手段
_github_limiter = asyncio.Semaphore(3)

class ComponentBuilderOutput(BaseModel):
    """单组件构建输出模型"""
    data: ComponentData = Field(..., description="组件的具体数据负载")
    style: Union[ComponentStyle, str, List[str]] = Field(..., description="组件的样式数据")

    @field_validator('style', mode='before')
    @classmethod
    def ensure_style_object(cls, v: Any) -> Any:
        if isinstance(v, str): return {"css_classes": v, "inline_styles": {}}
        if isinstance(v, list): return {"css_classes": " ".join([str(i) for i in v]), "inline_styles": {}}
        return v

# ✨ 性能优化：全局复用 LLM 实例
_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.4
        )
    return _llm_instance

async def component_builder_node(state: ComponentTaskState) -> dict:
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    user_query = state.get("user_query", "")
    
    # 🌟 使用信号量进行排队，并加入随机抖动，防止 GitHub 封锁
    async with _github_limiter:
        jitter = random.uniform(0.5, 2.5)
        if settings.XHS_FORGE_DEBUG:
            print(f"⏳ [限流排队] 组件 {comp_id} 正在抖动等待 {jitter:.2f}s...")
        await asyncio.sleep(jitter)
        
        print(f"👷 [并发工兵] 开始构建组件: {comp_id} ({comp_type})...")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        system_prompt = f"""你是一个严谨的前端组件数据构建专家。构建 ID 为 [{comp_id}]，类型为 "{comp_type}" 的组件。
必须输出 JSON 格式，包含 data (结构符合 {comp_type}) 和 style (Tailwind CSS) 两个字段。"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "请根据用户指令构建组件数据并以 JSON 格式输出：\n{query}")
        ])
        
        try:
            # 内部执行重试逻辑已通过 signals 管理，此处简化
            result = await (prompt | structured_llm).ainvoke({"query": user_query})
            
            # 数据加工
            res_data = result.data.model_dump(exclude_none=True) if hasattr(result.data, "model_dump") else result.data
            res_data["type"] = comp_type
            
            style_patch = result.style.model_dump(exclude_none=True) if isinstance(result.style, ComponentStyle) else ({"css_classes": result.style} if isinstance(result.style, str) else result.style)
            
            if settings.XHS_FORGE_DEBUG:
                print(f"✅ [DEBUG Output] 组件 {comp_id} 数据包预览: {str(res_data)[:150]}...")

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_patch}
            }
        except Exception as e:
            print(f"❌ [并发工兵] 组件 {comp_id} 构建失败: {e}")
            return {
                "data_dsl": {comp_id: {"type": comp_type, "title": "内容生成异常"}},
                "style_dsl": {comp_id: {"css_classes": "opacity-50"}}
            }
