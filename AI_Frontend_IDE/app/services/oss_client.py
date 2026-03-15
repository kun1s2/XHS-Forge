# app/services/oss_client.py — 与主项目 src/storage/oss_upload.py 对齐：笔记 HTML 上传到 OSS/S3，返回可访问 URL
"""
使用环境变量 OFFLOAD_BACKEND（s3 | aliyun_oss）、S3_* 或 OSS_*。
与主项目 .env 一致即可复用同一套配置。
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_backend_kind() -> str:
    return (os.environ.get("OFFLOAD_BACKEND") or "s3").strip().lower()


def _s3_put(bucket: str, key: str, body: bytes, content_type: str) -> str:
    import boto3
    from botocore.config import Config
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    sig = (os.environ.get("S3_SIGNATURE_VERSION") or "s3v4").strip().lower()
    if sig == "s3v4":
        config = Config(signature_version="s3v4", s3={"addressing_style": "path"}) if endpoint else None
    else:
        config = Config(signature_version="s3", s3={"addressing_style": "path"}) if endpoint else None
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.environ.get("S3_REGION") or "us-east-1",
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY"),
        config=config,
    )
    # 与旧项目一致：不传 ACL，避免 MinIO/OSS 因桶策略报错
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    base = (endpoint or "").rstrip("/")
    if base:
        return f"{base}/{bucket}/{key}"
    return f"s3://{bucket}/{key}"


def _oss_put(bucket: str, key: str, body: bytes, content_type: str) -> str:
    import oss2
    endpoint = os.environ.get("OSS_ENDPOINT", "")
    ep = endpoint if "://" in endpoint else f"https://{endpoint}"
    auth = oss2.Auth(
        os.environ.get("OSS_ACCESS_KEY_ID", ""),
        os.environ.get("OSS_ACCESS_KEY_SECRET", ""),
    )
    b = oss2.Bucket(auth, ep, bucket)
    b.put_object(key, body, headers={"Content-Type": content_type})
    if "://" not in endpoint:
        return f"https://{bucket}.{endpoint}/{key}"
    return f"{ep}/{bucket}/{key}"


def _upload_note_artifacts(
    key_prefix: str,
    html_body: bytes,
    skeleton_json: bytes | None = None,
) -> str:
    ts = int(time.time())
    prefix = key_prefix.rstrip("/")
    key_html = f"{prefix}/note_{ts}.html"
    kind = _get_backend_kind()
    if kind == "s3":
        bucket = os.environ.get("S3_BUCKET")
        if not bucket:
            raise ValueError("未配置 S3_BUCKET")
        url = _s3_put(bucket, key_html, html_body, "text/html; charset=utf-8")
        if skeleton_json:
            key_sk = f"{prefix}/note_{ts}.skeleton.json"
            _s3_put(bucket, key_sk, skeleton_json, "application/json; charset=utf-8")
        return url
    if kind == "aliyun_oss":
        bucket = os.environ.get("OSS_BUCKET")
        if not bucket:
            raise ValueError("未配置 OSS_BUCKET")
        url = _oss_put(bucket, key_html, html_body, "text/html; charset=utf-8")
        if skeleton_json:
            key_sk = f"{prefix}/note_{ts}.skeleton.json"
            _oss_put(bucket, key_sk, skeleton_json, "application/json; charset=utf-8")
        return url
    raise ValueError(
        "未配置 OSS/S3。请设置 OFFLOAD_BACKEND=s3 或 aliyun_oss，并配置 S3_* 或 OSS_* 环境变量。"
    )


def upload_html_to_oss(html: str, key_prefix: str = "notes") -> str:
    """
    将笔记完整 HTML 上传到 OSS/S3，返回可访问 URL。
    使用 .env 中 OFFLOAD_BACKEND、S3_* 或 OSS_*（与主项目 src/storage/oss_upload 一致）。
    """
    body = html.encode("utf-8")
    return _upload_note_artifacts(key_prefix, body, skeleton_json=None)


def upload_to_oss(html_content: str, key_prefix: str = "notes") -> str:
    """兼容旧调用：等同于 upload_html_to_oss(html_content, key_prefix)。"""
    return upload_html_to_oss(html_content, key_prefix=key_prefix)


def upload_image_to_oss(
    body: bytes,
    key_prefix: str = "images",
    content_type: str | None = None,
) -> str:
    """
    将图片二进制上传到 OSS/S3，返回可访问 URL。与主项目 src/storage/oss_upload.upload_image_to_oss 对齐。
    """
    ext = "png" if (content_type or "").lower().find("png") >= 0 else "jpg"
    key = f"{key_prefix.rstrip('/')}/img_{int(time.time())}.{ext}"
    ct = "image/png" if ext == "png" else "image/jpeg"
    kind = _get_backend_kind()
    if kind == "s3":
        bucket = os.environ.get("S3_BUCKET")
        if not bucket:
            raise ValueError("未配置 S3_BUCKET")
        return _s3_put(bucket, key, body, ct)
    if kind == "aliyun_oss":
        bucket = os.environ.get("OSS_BUCKET")
        if not bucket:
            raise ValueError("未配置 OSS_BUCKET")
        return _oss_put(bucket, key, body, ct)
    raise ValueError(
        "未配置 OSS/S3。请设置 OFFLOAD_BACKEND=s3 或 aliyun_oss，并配置 S3_* 或 OSS_* 环境变量。"
    )
