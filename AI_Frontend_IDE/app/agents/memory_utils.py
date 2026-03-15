from langchain_core.messages import trim_messages
from app.core.config import settings
from langchain_openai import ChatOpenAI

# 默认使用主模型作为 Token 计数器
_trim_llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)

def get_trimmed_messages(messages: list, max_tokens: int = 4000):
    """
    【官方记忆截断器】：使用 LangChain 官方 trimmers 确保上下文永不溢出。
    配置：保留最新消息，强制保留 System Prompt，不保留半截消息。
    """
    if not messages:
        return []

    # 定义截断策略
    trimmer = trim_messages(
        max_tokens=max_tokens,
        strategy="last",
        token_counter=_trim_llm,
        include_system=True,
        allow_partial=False,
        start_on="human", # 确保截断后以 HumanMessage 开始（除了 SystemMessage）
    )
    
    # 强制将输入转为 list
    trimmed = trimmer.invoke(list(messages))
    
    # 打印一条隐形的性能日志
    if len(trimmed) < len(messages):
        print(f"✂️ [记忆截断] 原始消息 {len(messages)} 轮 -> 截断后 {len(trimmed)} 轮 (Safe Tokens: {max_tokens})")
        
    return trimmed
