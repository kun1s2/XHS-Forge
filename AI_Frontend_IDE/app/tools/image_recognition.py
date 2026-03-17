import logging
import base64
import asyncio
from typing import Optional, Union
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

def describe_image(image_input: Union[bytes, str], prompt: str = "请详细描述这张图片的内容。") -> Optional[str]:
    """
    [多模态感知] 使用智谱 GLM-4.6V-FlashX 进行图片解析。
    支持 image_bytes (bytes) 或 image_url (str)。
    """
    client = _get_zhipu_client()
    if not client: return "未配置智谱 API Key。"

    # 处理输入类型
    if isinstance(image_input, bytes):
        base64_image = base64.b64encode(image_input).decode("utf-8")
        image_url_obj = {"url": f"data:image/jpeg;base64,{base64_image}"}
    else:
        # 假设是 URL
        image_url_obj = {"url": image_input}

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": image_url_obj}
            ]
        }
    ]

    def _do_recognition():
        # 使用智谱多模态大模型
        return client.chat.completions.create(
            model="glm-4.6v-flashx",
            messages=messages,
            temperature=0.1
        )

    try:
        response = _do_recognition()
        return response.choices[0].message.content
    except Exception as e:
        logger.error("智谱识图异常: %s", e)
        return f"识图失败: {e}"

async def describe_image_async(image_input: Union[bytes, str], prompt: str = "请详细描述这张图片的内容。") -> Optional[str]:
    """异步封装"""
    return await asyncio.to_thread(describe_image, image_input, prompt)
