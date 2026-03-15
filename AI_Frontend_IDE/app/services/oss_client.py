# app/services/oss_client.py
import logging
import time
from app.core.config import settings

logger = logging.getLogger(__name__)

def _get_backend_kind() -> str:
    # 优先从 settings 中尝试获取后端类型，默认 s3
    return (getattr(settings, "OFFLOAD_BACKEND", "s3") or "s3").strip().lower()

def _s3_put(bucket: str, key: str, body: bytes, content_type: str) -> str:
    import boto3
    from botocore.config import Config
    endpoint = settings.S3_ENDPOINT_URL
    sig = (getattr(settings, "S3_SIGNATURE_VERSION", "s3v4") or "s3v4").strip().lower()
    
    config = Config(signature_version=sig, s3={"addressing_style": "path"}) if endpoint else None
    
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.S3_REGION or "us-east-1",
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        config=config,
    )
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    base = (endpoint or "").rstrip("/")
    if base:
        return f"{base}/{bucket}/{key}"
    return f"s3://{bucket}/{key}"

def _oss_put(bucket: str, key: str, body: bytes, content_type: str) -> str:
    import oss2
    # 注意：如果未来有阿里云 OSS 专属 Key，需在此对接
    endpoint = getattr(settings, "OSS_ENDPOINT", "")
    ep = endpoint if "://" in endpoint else f"https://{endpoint}"
    auth = oss2.Auth(
        getattr(settings, "OSS_ACCESS_KEY_ID", ""),
        getattr(settings, "OSS_ACCESS_KEY_SECRET", ""),
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
        bucket = settings.S3_BUCKET
        if not bucket:
            raise ValueError("未配置 S3_BUCKET")
        url = _s3_put(bucket, key_html, html_body, "text/html; charset=utf-8")
        if skeleton_json:
            key_sk = f"{prefix}/note_{ts}.skeleton.json"
            _s3_put(bucket, key_sk, skeleton_json, "application/json; charset=utf-8")
        return url
    elif kind == "aliyun_oss":
        bucket = getattr(settings, "OSS_BUCKET", None)
        if not bucket:
            raise ValueError("未配置 OSS_BUCKET")
        url = _oss_put(bucket, key_html, html_body, "text/html; charset=utf-8")
        if skeleton_json:
            key_sk = f"{prefix}/note_{ts}.skeleton.json"
            _oss_put(bucket, key_sk, skeleton_json, "application/json; charset=utf-8")
        return url
    raise ValueError("未配置有效的 OSS/S3 后端类型。")

def upload_html_to_oss(html: str, key_prefix: str = "notes") -> str:
    body = html.encode("utf-8")
    return _upload_note_artifacts(key_prefix, body)

def upload_to_oss(html_content: str, key_prefix: str = "notes") -> str:
    return upload_html_to_oss(html_content, key_prefix=key_prefix)

def upload_image_to_oss(
    body: bytes,
    key_prefix: str = "images",
    content_type: str | None = None,
) -> str:
    ext = "png" if (content_type or "").lower().find("png") >= 0 else "jpg"
    key = f"{key_prefix.rstrip('/')}/img_{int(time.time())}.{ext}"
    ct = "image/png" if ext == "png" else "image/jpeg"
    kind = _get_backend_kind()
    
    if kind == "s3":
        bucket = settings.S3_BUCKET
        if not bucket:
            raise ValueError("未配置 S3_BUCKET")
        return _s3_put(bucket, key, body, ct)
    elif kind == "aliyun_oss":
        bucket = getattr(settings, "OSS_BUCKET", None)
        if not bucket:
            raise ValueError("未配置 OSS_BUCKET")
        return _oss_put(bucket, key, body, ct)
    raise ValueError("未配置有效的 OSS/S3 后端类型。")
