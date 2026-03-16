from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi
from app.core.config import settings

def create_llm(
    model: str = None,
    temperature: float = 0.1,
    max_retries: int = 2,
    **kwargs
):
    """
    LLM 兼容层工厂方法：根据配置动态选择底层 SDK。
    支持 ChatTongyi 和 ChatOpenAI。
    """
    # 兼容性：如果调用方传了 api_key 或 base_url，将其弹出，统一使用 settings 里的配置
    kwargs.pop("api_key", None)
    kwargs.pop("base_url", None)
    
    model_name = model or settings.LLM_MODEL
    base_url = settings.LLM_BASE_URL
    api_key = settings.LLM_API_KEY
    
    # ✨ 核心修正：判断是否真正使用原生 ChatTongyi
    # 只有当 URL 不包含 compatible-mode 或 /v1 这种 OpenAI 专属后缀时，才使用原生驱动
    is_openai_compatible = "compatible-mode" in (base_url or "").lower() or "/v1" in (base_url or "").lower()
    
    if "dashscope" in (base_url or "").lower() and not is_openai_compatible:
        # 使用阿里原生驱动（适用于 https://dashscope.aliyuncs.com/api/v1 或未配置 URL）
        return ChatTongyi(
            model=model_name,
            dashscope_api_key=api_key,
            temperature=temperature,
            max_retries=max_retries,
            **kwargs
        )
    else:
        # 其他（如包含 compatible-mode 的阿里 Key、DeepSeek、OpenAI 等）统一走标准 OpenAI 协议
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_retries=max_retries,
            **kwargs
        )
