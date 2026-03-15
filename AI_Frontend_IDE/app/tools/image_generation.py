# app/tools/image_generation.py
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def _get_zhipu_client():
    """未配置或未安装 zai 时返回 None。"""
    try:
        from app.core.config import settings
        api_key = (getattr(settings, "ZHI_PU_API_KEY", None) or "").strip()
        if not api_key:
            return None
        from zai import ZhipuAiClient
        return ZhipuAiClient(api_key=api_key)
    except ImportError:
        return None
    except Exception as e:
        logger.warning("获取智谱 client 失败: %s", e)
        return None

def generate_image(prompt: str, model: str = "cogview-3-plus") -> Optional[str]:
    """
    调用智谱 CogView 模型生成图片，返回图片 URL。
    """
    client = _get_zhipu_client()
    if not client:
        logger.warning("智谱 SDK 未安装或 API Key 未配置，无法生成图片。")
        return None

    try:
        logger.info("🚀 [CogView] 正在生成图片, Prompt: %s", prompt)
        response = client.images.generations(
            model=model,
            prompt=prompt
        )
        if response and response.data:
            url = response.data[0].url
            logger.info("✅ [CogView] 图片生成成功: %s", url)
            return url
        return None
    except Exception as e:
        logger.error("❌ [CogView] 图片生成失败: %s", e)
        return None
