import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 加载 .env 文件到环境变量中
load_dotenv()

# ✨ 指挥官“逆向分流”战略：默认全站直连，按需开启代理
# 1. 强行清除进程级别的代理环境变量，确保国内请求 100% 不会被代理软件拦截
proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

# 2. 开启 LangSmith 监控底座
# 注意：若 LangSmith 无法连接，我们需要在后续单独为其配置代理
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"

class Settings(BaseSettings):
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str = "LangChainProject"

    LLM_API_KEY: str
    LLM_BASE_URL: str 
    LLM_MODEL: str 
    LLM_SMALL_MODEL: str 
    
    # === X-Forge 异构模型编排矩阵 (New) ===
    LLM_LOGIC_MODEL: str = "gpt-4o-mini"
    LLM_BRAIN_MODEL: str = "gemini-3.0-flash"
    LLM_WORKER_MODEL: str = "gemini-2.5-flash-lite-nothinking"
    LLM_VISION_MODEL: str = "gemini-2.0-flash"
    
    ZHI_PU_API_KEY: str

    REDIS_URL: str = "redis://localhost:6379/0"

    POSTGRES_URL: str
    PGVector_URL: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # 可选：使用 OpenAI 兼容接口的 Embedding 时填写；当前默认使用智谱 ZhipuAIEmbeddings(ZHI_PU_API_KEY)
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    S3_ENDPOINT_URL: str
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str
    S3_BUCKET: str = "agent"
    S3_REGION: str = "us-east-1"

    # 联网检索：可选 backend，目前主推 zhipu
    NETWORK_SEARCH_BACKEND: str = "zhipu"  # "serpapi" | "zhipu"
    SERPAPI_API_KEY: Optional[str] = None
    SERPAPI_ENGINE: str = "google"
    SERPAPI_GL: str = "cn"
    SERPAPI_HL: str = "zh-cn"

    # 高德地图 Web 服务（地理编码、逆地理、输入提示、POI 搜索等）
    AMAP_WEB_SERVICE_KEY: Optional[str] = None

    # 是否开启调试模式（开启后会打印全量 Node IO 日志）
    XHS_FORGE_DEBUG: bool = True
    # 开发模式：设为 True 则节点报错不再兜底，直接抛出异常
    DEBUG_MODE: bool = True
    
    # ✨ 哨兵总控：是否开启人工干预 (Human-In-The-Loop)
    HITL_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()