# app/api/upload.py — 用户上传图片到 OSS，与主项目 src/agent/routers/upload.py 及前端 upload API 对齐

import logging
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload/image", tags=["Upload"])
async def upload_image(file: UploadFile = File(..., description="图片文件")):
    """
    上传单张图片到 OSS。请求：multipart/form-data 字段名 file；响应：{ "url": "..." }。
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片类型")
    try:
        body = await file.read()
    except Exception as e:
        logger.exception("upload_image: read file failed")
        raise HTTPException(status_code=400, detail="读取文件失败") from e
    if not body:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        from app.services.oss_client import upload_image_to_oss

        url = upload_image_to_oss(body, key_prefix="images", content_type=file.content_type)
        return {"url": url}
    except ValueError as e:
        logger.warning("upload_image: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("upload_image: upload_image_to_oss failed")
        raise HTTPException(status_code=500, detail=f"上传失败: {e!s}") from e


@router.post("/upload/images", tags=["Upload"])
async def upload_images(files: List[UploadFile] = File(..., description="图片文件列表")):
    """
    批量上传图片到 OSS。请求：multipart/form-data 字段名 files；响应：{ "urls": ["...", ...] }。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")
    urls = []
    for f in files:
        body = await f.read()
        if not body:
            continue
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        try:
            from app.services.oss_client import upload_image_to_oss

            url = upload_image_to_oss(body, key_prefix="images", content_type=f.content_type)
            urls.append(url)
        except ValueError as e:
            logger.warning("upload_images: %s", e)
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            logger.exception("upload_images: upload_image_to_oss failed for %s", f.filename)
            raise HTTPException(status_code=500, detail=f"上传失败: {e!s}") from e
    return {"urls": urls}
