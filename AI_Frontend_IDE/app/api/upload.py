import logging
from copy import deepcopy
from typing import Any, List

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.api.workspace import WORKSPACE_STATE_NODE, _aupdate_state_compat, get_agent
from app.services.knowledge_hub import (
    KNOWLEDGE_SCOPE_PERSISTENT,
    KNOWLEDGE_SCOPE_SESSION,
    apply_knowledge_review_decision,
    build_knowledge_plan,
    knowledge_hub_service,
    merge_candidate_records_into_retrieved,
    select_records_from_candidate,
    select_records_from_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class KnowledgeTextUploadRequest(BaseModel):
    thread_id: str
    title: str
    text: str
    kb_scope: str = KNOWLEDGE_SCOPE_SESSION
    entity_hint: str = ""
    scene_hint: str = ""


class KnowledgeUrlUploadRequest(BaseModel):
    thread_id: str
    url: str
    kb_scope: str = KNOWLEDGE_SCOPE_SESSION
    entity_hint: str = ""
    scene_hint: str = ""


class KnowledgePromoteRequest(BaseModel):
    thread_id: str
    record_ids: List[str] = []
    normalized_entity: str | None = None
    field_or_topic: str | None = None


class KnowledgeDemoPackRequest(BaseModel):
    thread_id: str
    pack_id: str
    kb_scope: str = KNOWLEDGE_SCOPE_SESSION


class KnowledgeReviewRequest(BaseModel):
    thread_id: str
    decision: str
    record_ids: List[str] = []
    normalized_entity: str | None = None
    field_or_topic: str | None = None


def _normalize_scope(scope: str | None) -> str:
    value = str(scope or KNOWLEDGE_SCOPE_SESSION).strip().lower()
    if value == KNOWLEDGE_SCOPE_PERSISTENT:
        return KNOWLEDGE_SCOPE_PERSISTENT
    return KNOWLEDGE_SCOPE_SESSION


def _build_appended_document(parsed, *, thread_id: str | None) -> dict[str, Any]:
    return {
        "document_id": parsed.document_id,
        "title": parsed.title,
        "file_name": parsed.file_name,
        "source_type": parsed.source_type,
        "kb_scope": parsed.kb_scope,
        "thread_id": thread_id or "",
        "entity_hint": parsed.entity_hint,
        "scene_hint": parsed.scene_hint,
        "raw_path": parsed.raw_path,
        "chunk_count": len(parsed.chunks),
    }


async def _resolve_thread_context(agent, thread_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await agent.aget_state(config)
    values = snapshot.values or {}
    return config, values


async def _update_thread_knowledge_state(
    request: Request,
    *,
    thread_id: str,
    candidate_records: list[dict[str, Any]] | None = None,
    session_records: list[dict[str, Any]] | None = None,
    appended_documents: list[dict[str, Any]] | None = None,
    persistent_entity_hint: str | None = None,
) -> dict[str, Any]:
    agent = get_agent(request)
    config, values = await _resolve_thread_context(agent, thread_id)
    persistent_snapshot = await knowledge_hub_service.list_persistent_snapshot()
    knowledge_plan = build_knowledge_plan(values)
    next_knowledge = merge_candidate_records_into_retrieved(
        values.get("retrieved_knowledge") if isinstance(values.get("retrieved_knowledge"), dict) else {},
        knowledge_plan=knowledge_plan,
        candidate_records=candidate_records,
        session_records=session_records,
        persistent_snapshot=persistent_snapshot,
        appended_documents=appended_documents,
    )
    await _aupdate_state_compat(
        agent,
        config,
        {
            "retrieved_knowledge": next_knowledge,
            "knowledge_plan": knowledge_plan,
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    return next_knowledge


async def _ingest_parsed_source(
    request: Request,
    *,
    thread_id: str,
    parsed,
) -> dict[str, Any]:
    vector_store = getattr(request.app.state, "vector_store", None)
    indexed_chunks = await knowledge_hub_service.index_chunks(parsed.chunks, vector_store)
    appended_document = _build_appended_document(parsed, thread_id=thread_id)

    candidate_records = [deepcopy(item) for item in (parsed.records or []) if isinstance(item, dict)]
    if parsed.kb_scope == KNOWLEDGE_SCOPE_PERSISTENT:
        await knowledge_hub_service.register_persistent_document(parsed)

    next_knowledge = await _update_thread_knowledge_state(
        request,
        thread_id=thread_id,
        candidate_records=candidate_records,
        appended_documents=[appended_document],
        persistent_entity_hint=parsed.entity_hint,
    )
    if parsed.kb_scope == KNOWLEDGE_SCOPE_PERSISTENT:
        return {
            "mode": "persistent_pending_review",
            "indexed_chunks": indexed_chunks,
            "document": appended_document,
            "record_count": len(candidate_records),
            "knowledge": next_knowledge,
        }

    return {
        "mode": "session",
        "indexed_chunks": indexed_chunks,
        "document": appended_document,
        "record_count": len(candidate_records),
        "knowledge": next_knowledge,
    }


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


@router.get("/upload/knowledge/demo-packs", tags=["Upload"])
async def list_demo_knowledge_packs():
    return {"packs": knowledge_hub_service.build_demo_pack_specs()}


@router.get("/upload/knowledge/eval-sets", tags=["Upload"])
async def list_demo_eval_sets():
    return {"eval_sets": knowledge_hub_service.build_demo_eval_sets()}


@router.get("/upload/knowledge/global-overview", tags=["Upload"])
async def get_global_knowledge_overview():
    snapshot = await knowledge_hub_service.list_persistent_snapshot()
    return {
        "persistent_kb": snapshot,
        "demo_packs": knowledge_hub_service.build_demo_pack_specs(),
        "eval_sets": knowledge_hub_service.build_demo_eval_sets(),
    }


@router.post("/upload/knowledge/file", tags=["Upload"])
async def upload_knowledge_file(
    request: Request,
    file: UploadFile = File(..., description="知识文件"),
    thread_id: str = Form(...),
    kb_scope: str = Form(KNOWLEDGE_SCOPE_SESSION),
    entity_hint: str = Form(""),
    scene_hint: str = Form(""),
):
    scope = _normalize_scope(kb_scope)
    try:
        body = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="读取资料失败") from exc
    if not body:
        raise HTTPException(status_code=400, detail="资料为空")
    try:
        parsed = await knowledge_hub_service.parse_upload(
            file_name=file.filename or "knowledge.txt",
            content=body,
            kb_scope=scope,
            source_type="user_kb_curated" if scope == KNOWLEDGE_SCOPE_PERSISTENT else "user_kb",
            entity_hint=entity_hint,
            scene_hint=scene_hint or "seeding",
            thread_id=thread_id,
        )
        result = await _ingest_parsed_source(request, thread_id=thread_id, parsed=parsed)
        return {
            "status": "success",
            "thread_id": thread_id,
            "kb_scope": scope,
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("upload_knowledge_file failed")
        raise HTTPException(status_code=500, detail=f"知识入库失败: {exc!s}") from exc


@router.post("/upload/knowledge/text", tags=["Upload"])
async def upload_knowledge_text(request: Request, payload: KnowledgeTextUploadRequest):
    scope = _normalize_scope(payload.kb_scope)
    try:
        parsed = await knowledge_hub_service.parse_text_input(
            title=payload.title,
            text=payload.text,
            kb_scope=scope,
            source_type="user_kb_curated" if scope == KNOWLEDGE_SCOPE_PERSISTENT else "user_kb",
            entity_hint=payload.entity_hint,
            scene_hint=payload.scene_hint or "seeding",
            thread_id=payload.thread_id,
        )
        result = await _ingest_parsed_source(request, thread_id=payload.thread_id, parsed=parsed)
        return {
            "status": "success",
            "thread_id": payload.thread_id,
            "kb_scope": scope,
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("upload_knowledge_text failed")
        raise HTTPException(status_code=500, detail=f"文本资料入库失败: {exc!s}") from exc


@router.post("/upload/knowledge/url", tags=["Upload"])
async def upload_knowledge_url(request: Request, payload: KnowledgeUrlUploadRequest):
    scope = _normalize_scope(payload.kb_scope)
    try:
        parsed = await knowledge_hub_service.parse_url_input(
            url=payload.url,
            kb_scope=scope,
            entity_hint=payload.entity_hint,
            scene_hint=payload.scene_hint or "seeding",
            thread_id=payload.thread_id,
        )
        result = await _ingest_parsed_source(request, thread_id=payload.thread_id, parsed=parsed)
        return {
            "status": "success",
            "thread_id": payload.thread_id,
            "kb_scope": scope,
            **result,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("upload_knowledge_url failed")
        raise HTTPException(status_code=500, detail=f"链接资料入库失败: {exc!s}") from exc


@router.post("/upload/knowledge/review", tags=["Upload"])
async def review_candidate_knowledge(request: Request, payload: KnowledgeReviewRequest):
    agent = get_agent(request)
    config, values = await _resolve_thread_context(agent, payload.thread_id)
    current_knowledge = values.get("retrieved_knowledge") if isinstance(values.get("retrieved_knowledge"), dict) else {}
    selected_records = select_records_from_candidate(
        current_knowledge,
        record_ids=payload.record_ids,
        normalized_entity=payload.normalized_entity,
        field_or_topic=payload.field_or_topic,
    )
    if payload.decision in {"approve_selected", "reject_selected", "defer_selected"} and not selected_records:
        raise HTTPException(status_code=404, detail="没有找到对应的候选知识")
    next_knowledge = apply_knowledge_review_decision(
        current_knowledge,
        decision=payload.decision,
        record_ids=[str(item.get("record_id") or "") for item in selected_records],
    )
    await _aupdate_state_compat(
        agent,
        config,
        {
            "retrieved_knowledge": next_knowledge,
            "knowledge_plan": build_knowledge_plan(values),
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    return {
        "status": "success",
        "thread_id": payload.thread_id,
        "decision": payload.decision,
        "knowledge": next_knowledge,
    }


@router.post("/upload/knowledge/promote", tags=["Upload"])
async def promote_session_knowledge(request: Request, payload: KnowledgePromoteRequest):
    agent = get_agent(request)
    config, values = await _resolve_thread_context(agent, payload.thread_id)
    selected_records = select_records_from_session(
        values.get("retrieved_knowledge") if isinstance(values.get("retrieved_knowledge"), dict) else {},
        record_ids=payload.record_ids,
        normalized_entity=payload.normalized_entity,
        field_or_topic=payload.field_or_topic,
    )
    if not selected_records:
        raise HTTPException(status_code=404, detail="没有找到可升格的会话知识")
    result = await knowledge_hub_service.upsert_persistent_records(selected_records)
    persistent_snapshot = await knowledge_hub_service.list_persistent_snapshot(entity_name=payload.normalized_entity or None)
    next_knowledge = merge_candidate_records_into_retrieved(
        values.get("retrieved_knowledge") if isinstance(values.get("retrieved_knowledge"), dict) else {},
        knowledge_plan=build_knowledge_plan(values),
        persistent_snapshot=persistent_snapshot,
    )
    await _aupdate_state_compat(
        agent,
        config,
        {
            "retrieved_knowledge": next_knowledge,
            "knowledge_plan": build_knowledge_plan(values),
        },
        as_node=WORKSPACE_STATE_NODE,
    )
    return {
        "status": "success",
        "thread_id": payload.thread_id,
        "promoted_count": int(result.get("promoted_count") or 0),
        "conflict_count": int(result.get("conflict_count") or 0),
        "knowledge": next_knowledge,
    }


@router.post("/upload/knowledge/demo-pack", tags=["Upload"])
async def import_demo_pack(request: Request, payload: KnowledgeDemoPackRequest):
    scope = _normalize_scope(payload.kb_scope)
    pack = next(
        (item for item in knowledge_hub_service.build_demo_pack_specs() if str(item.get("pack_id") or "") == payload.pack_id),
        None,
    )
    if not pack:
        raise HTTPException(status_code=404, detail="找不到对应的 demo 资料包")
    imported_documents: list[dict[str, Any]] = []
    indexed_chunks = 0
    candidate_records: list[dict[str, Any]] = []
    for document in pack.get("documents") or []:
        parsed = await knowledge_hub_service.parse_text_input(
            title=str(document.get("title") or "demo-knowledge"),
            text=str(document.get("text") or ""),
            kb_scope=scope,
            source_type="user_kb_curated" if scope == KNOWLEDGE_SCOPE_PERSISTENT else "user_kb",
            entity_hint=str(document.get("entity_hint") or ""),
            scene_hint=str(pack.get("scenario") or "seeding"),
            thread_id=payload.thread_id,
        )
        indexed_chunks += await knowledge_hub_service.index_chunks(parsed.chunks, getattr(request.app.state, "vector_store", None))
        imported_documents.append(_build_appended_document(parsed, thread_id=payload.thread_id))
        if scope == KNOWLEDGE_SCOPE_PERSISTENT:
            await knowledge_hub_service.register_persistent_document(parsed)
        candidate_records.extend([deepcopy(item) for item in (parsed.records or []) if isinstance(item, dict)])

    next_knowledge = await _update_thread_knowledge_state(
        request,
        thread_id=payload.thread_id,
        candidate_records=candidate_records,
        appended_documents=imported_documents,
        persistent_entity_hint=str(((pack.get("documents") or [{}])[0] or {}).get("entity_hint") or ""),
    )
    return {
        "status": "success",
        "thread_id": payload.thread_id,
        "pack_id": payload.pack_id,
        "kb_scope": scope,
        "document_count": len(imported_documents),
        "indexed_chunks": indexed_chunks,
        "record_count": len(candidate_records),
        "knowledge": next_knowledge,
    }
