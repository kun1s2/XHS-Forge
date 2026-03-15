import tiktoken
from langchain_core.messages import trim_messages
from app.core.config import settings

def custom_token_counter(messages: list) -> int:
    """
    通用 Token 计数器：针对非 OpenAI 模型（如 Qwen）的兼容性优化。
    优先使用 cl100k_base 编码器（GPT-4 同款），失败后通过文本长度估算（兜底）。
    """
    try:
        # 使用 tiktoken 的通用编码器（大部分大模型 Tokenizer 的基础）
        encoder = tiktoken.get_encoding("cl100k_base")
        total_tokens = 0
        for m in messages:
            # 统计内容中的 Token 数量
            content = m.content if isinstance(m.content, str) else str(m.content or "")
            total_tokens += len(encoder.encode(content))
            # 加上消息头开销（Role 等，约 4 tokens）
            total_tokens += 4
        return total_tokens
    except Exception:
        # 兜底方案：中文 1.5-2 汉字/token，英文 4-5 字符/token
        # 此处按保守的 1 token = 2.5 字符估算 (len/2.5)
        return sum(len(str(m.content or "")) for m in messages) // 2

def get_trimmed_messages(messages: list, max_tokens: int = 4000):
    """
    【官方记忆截断器】：使用 LangChain 官方 trimmers 确保上下文永不溢出。
    配置：保留最新消息，强制保留 System Prompt，不保留半截消息。
    """
    if not messages:
        return []

    # 使用自定义的通用计数器，摆脱对特定 LLM 内部方法的依赖
    trimmer = trim_messages(
        max_tokens=max_tokens,
        strategy="last",
        token_counter=custom_token_counter,
        include_system=True,
        allow_partial=False,
        start_on="human", # 确保截断后以 HumanMessage 开始（除了 SystemMessage）
    )
    
    # 强制将输入转为 list
    trimmed = trimmer.invoke(list(messages))
    
    # 打印一条隐形的性能日志
    if len(trimmed) < len(messages) + 1: # 即使没变，有时也会显示已处理
         # (略过重复提示日志)
         pass
        
    return trimmed
