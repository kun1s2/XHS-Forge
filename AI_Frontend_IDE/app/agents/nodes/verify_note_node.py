"""Deterministic document verifier.

This node validates the current NoteDocument execution view before render time
and repairs component payloads through contract-enforced fallbacks when needed.
"""

from copy import deepcopy

from app.agents.nodes.component_builder import build_component_fallback, enforce_component_contract
from app.agents.state import UIProjectState
from app.core.component_manifest import is_component_supported_for_verifier
from app.core.note_document import (
    build_note_document_layout_from_state,
    build_note_document_from_state,
    replace_note_document_blocks,
    update_note_document_block,
    update_note_document_title,
)


async def verify_note_node(state: UIProjectState) -> dict:
    """
    Deterministic verifier for the digital decision composition flow.
    在渲染前补齐关键字段、移除不支持的组件，尽量保证页面可渲染。
    """
    note_document = build_note_document_from_state(state)
    execution_view = build_note_document_layout_from_state(state)
    blocks = list(execution_view.get("blocks", []))
    user_query = str(state.get("main_messages", [])[-1].content) if state.get("main_messages") else ""
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    image_assets = state.get("image_assets", [])

    verified_blocks = []
    verified_document = deepcopy(note_document)
    changed = False

    for block in blocks:
        comp_type = block.get("component_type")
        comp_id = block.get("id")
        if not comp_type or not comp_id:
            changed = True
            continue
        if not is_component_supported_for_verifier(comp_type):
            print(f"⚠️ [Note Verifier] 移除暂不支持的组件: {comp_type} ({comp_id})")
            changed = True
            continue

        current_payload = deepcopy(block.get("props") or {})
        fallback_payload = build_component_fallback(
            comp_type=comp_type,
            comp_id=comp_id,
            content_brief=block.get("content_brief", ""),
            user_query=user_query,
            retrieved_knowledge=retrieved_knowledge,
            image_assets=image_assets,
        )
        verified_payload = enforce_component_contract(comp_type, current_payload, fallback_payload)
        if verified_payload != current_payload:
            verified_document = update_note_document_block(verified_document, comp_id, props=verified_payload)
            changed = True
            block = {**block, "props": deepcopy(verified_payload)}
        verified_blocks.append(block)

    if len(verified_blocks) != len(blocks):
        verified_document = replace_note_document_blocks(verified_document, verified_blocks)
        changed = True

    if not note_document.get("document_meta", {}).get("title"):
        verified_document = update_note_document_title(verified_document, "XHS-Forge Note")
        changed = True

    if changed:
        print(f"✅ [Note Verifier] 已完成结构补强，共校验 {len(verified_blocks)} 个区块。")
        return {"note_document": verified_document}
    return {"note_document": note_document}


document_verifier_node = verify_note_node
