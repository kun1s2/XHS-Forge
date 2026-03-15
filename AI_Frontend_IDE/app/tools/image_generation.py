import logging
import asyncio
from typing import Optional
from zhipuai import ZhipuAI
from app.core.config import settings

logger = logging.getLogger(__name__)

def _get_zhipu_client():
    """获取智谱原生 SDK Client"""
    try:
        api_key = (getattr(settings, "ZHI_PU_API_KEY", None) or "").strip()
        if not api_key: return None
        return ZhipuAI(api_key=api_key)
    except Exception as e:
        logger.warning("获取智谱 Client 失败: %s", e)
        return None

def generate_image(prompt: str, model: str = "cogview-3-plus") -> Optional[str]:
    """[多模态感知] 使用智谱 CogView-3-Plus 绘图"""
    client = _get_zhipu_client()
    if not client: return None

    try:
        response = client.images.generations(
            model=model,
            prompt=prompt
        )
        return response.data[0].url
    except Exception as e:
        logger.error("智谱绘图异常: %s", e)
        return None

async def generate_image_async(prompt: str, model: str = "cogview-3-plus") -> Optional[str]:
    return await asyncio.to_thread(generate_image, prompt, model)
