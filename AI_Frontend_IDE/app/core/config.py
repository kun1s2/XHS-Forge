import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# 加载 AI_Frontend_IDE 根目录下的 .env，避免测试/脚本因 cwd 不同而丢配置。
load_dotenv(_ENV_FILE)

# ✨ 指挥官“逆向分流”战略：默认全站直连，按需开启代理
# 1. 强行清除进程级别的代理环境变量，确保国内请求 100% 不会被代理软件拦截
proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

class Settings(BaseSettings):
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str = "LangChainProject"

    # 这些字段在运行时会被下游服务校验；这里保留空字符串默认值，
    # 让纯逻辑测试和只读导入不会因为缺少基础设施配置而在 import 阶段失败。
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    
    ZHI_PU_API_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    POSTGRES_URL: str = ""
    PGVector_URL: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    # 可选：使用 OpenAI 兼容接口的 Embedding 时填写；当前默认使用智谱 ZhipuAIEmbeddings(ZHI_PU_API_KEY)
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
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

    ENABLE_COMPONENT_MANIFEST: bool = True
    ENABLE_NOTE_DOCUMENT_RUNTIME: bool = True

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    def require(self, *fields: str) -> None:
        missing = [name for name in fields if not str(getattr(self, name, "") or "").strip()]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required settings: {joined}. Please update AI_Frontend_IDE/.env")


settings = Settings()


def _configure_langsmith_runtime() -> None:
    tracing_enabled = bool(settings.LANGSMITH_API_KEY) and bool(settings.LANGSMITH_TRACING)
    if tracing_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_API_KEY"] = str(settings.LANGSMITH_API_KEY or "")
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    for key in ("LANGCHAIN_ENDPOINT", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"):
        os.environ.pop(key, None)


_configure_langsmith_runtime()
