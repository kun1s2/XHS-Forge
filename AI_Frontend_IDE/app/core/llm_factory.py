from langchain_openai import ChatOpenAI
from app.core.config import settings

def create_llm(
    model: str = None,
    temperature: float = 0.1,
    max_retries: int = 2,
    **kwargs
):
    """
    LLM 工厂方法：全站统一使用 ChatOpenAI 驱动。
    支持所有兼容 OpenAI 协议的供应商（如 GitHub Models, DeepSeek, 阿里云兼容模式等）。
    """
    settings.require("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")

    # 物理隔离：确保调用方传参不会干扰核心凭证
    kwargs.pop("api_key", None)
    kwargs.pop("base_url", None)
    
    model_name = model or settings.LLM_MODEL
    base_url = settings.LLM_BASE_URL.rstrip("/")
    # 避免 base_url 已含 /chat/completions 时被 ChatOpenAI 再拼一次，导致 /v1/chat/completions/chat/completions
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")].rstrip("/")
    api_key = settings.LLM_API_KEY
    
    # 统一走标准 OpenAI 协议
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_retries=max_retries,
        timeout=30.0,  # ✨ Sentinel-X: 强制注入超时熔断
        **kwargs
    )
