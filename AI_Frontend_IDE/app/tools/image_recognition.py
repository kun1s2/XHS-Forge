# app/tools/image_recognition.py — 图片识别（视觉描述），从旧项目 src/agent/zhipu_tools + state_helpers 移植
"""
将图片 URL 转为视觉模型可用的 data URL（内网图），并调用智谱视觉模型生成文字描述。
在需要「识图」的节点中引用：from app.tools.image_recognition import describe_image
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_FETCH_IMAGE_MAX_BYTES = 10 * 1024 * 1024
_FETCH_IMAGE_TIMEOUT = 30
_DEFAULT_DESCRIBE_PROMPT = "请用一两句话描述这张图片的内容，不要输出思考过程，只输出描述。"


def fetch_image_to_data_url(url: str) -> Optional[str]:
    """
    将图片 URL 拉取后转为 data URL（base64），供视觉 API 使用（避免服务端无法访问内网/私网 URL）。
    若已是 data: 或拉取失败，返回 None，调用方用原 url。
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("data:"):
        return url
    if not url.startswith(("http://", "https://")):
        return None
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Frontend-IDE/1.0"})
        with urllib.request.urlopen(req, timeout=_FETCH_IMAGE_TIMEOUT) as r:
            raw = r.read(_FETCH_IMAGE_MAX_BYTES + 1)
            if len(raw) > _FETCH_IMAGE_MAX_BYTES:
                logger.warning("图片过大，未转 base64: %s", url[:80])
                return None
            content_type = r.headers.get_content_type() or "image/jpeg"
            if "image/" not in content_type:
                content_type = "image/jpeg"
            b64 = base64.standard_b64encode(raw).decode("ascii")
            return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning("拉取图片转 base64 失败，将使用原 URL: %s", e)
        return None


def _get_zhipu_client():
    """未配置或未安装 zai 时返回 None。"""
    try:
        from app.core.config import settings
        api_key = (getattr(settings, "ZHI_PU_API_KEY", None) or "").strip()
        if not api_key:
            return None
        from zai import ZhipuAiClient
        return ZhipuAiClient(api_key=api_key)
    except ImportError as e:
        logger.debug("zai 未安装，智谱识图不可用: %s", e)
        return None
    except Exception as e:
        logger.warning("获取智谱 client 失败: %s", e)
        return None


def describe_image(
    image_url: str,
    prompt: str = _DEFAULT_DESCRIBE_PROMPT,
    use_thinking: bool = False,
) -> str:
    """
    对一张图片进行视觉理解，返回文字描述（如场景、主体、氛围）。
    优先使用智谱视觉模型（ZHI_PU_API_KEY + zai）；内网 URL 会先转为 data URL 再请求。
    :param image_url: 公网或 data URL
    :param prompt: 向模型提问的文本
    :param use_thinking: 是否开启思考模式（智谱）
    :return: 描述文本；失败时返回「（图片识别暂不可用）」或具体错误说明
    """
    if not image_url or not isinstance(image_url, str):
        return "（图片 URL 无效）"
    image_url = image_url.strip()
    url_to_send = fetch_image_to_data_url(image_url) if image_url.startswith(("http://", "https://")) else image_url
    if not url_to_send:
        url_to_send = image_url

    client = _get_zhipu_client()
    if not client:
        return "（图片识别服务不可用：未配置 ZHI_PU_API_KEY 或未安装 zai）"

    try:
        messages = [
            {
                "content": [
                    {"type": "image_url", "image_url": {"url": url_to_send}},
                    {"type": "text", "text": prompt},
                ],
                "role": "user",
            }
        ]
        kwargs = {
            "model": "glm-4.6v-flashx",
            "messages": messages,
        }
        if use_thinking:
            kwargs["thinking"] = {"type": "enabled"}

        response = client.chat.completions.create(**kwargs)
        choice = getattr(response, "choices", None)
        if choice and len(choice) > 0:
            msg = choice[0].message
            content = (getattr(msg, "content", None) or "").strip()
            if content and ("未配置" in content or "调用失败" in content):
                return "（图片识别服务暂不可用）"
            return content or "（未识别到内容）"
        return "（视觉模型返回无有效结果）"
    except Exception as e:
        logger.warning("图片识别失败: %s", e)
        return "（图片识别暂不可用）"
