#!/usr/bin/env python3
import argparse
import asyncio
import json
import secrets
from typing import Any

import websockets


def _pick(data: dict[str, Any], *keys: str, default=None):
    for key in keys:
        if key in data:
            return data[key]
    return default


def _extract_blocks(page_data: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = page_data.get("blocks", [])
    return blocks if isinstance(blocks, list) else []


def _find_target_block(page_data: dict[str, Any], preferred_type: str | None) -> str | None:
    blocks = _extract_blocks(page_data)
    if preferred_type:
        for block in blocks:
            if block.get("component_type") == preferred_type:
                return block.get("id")
    return blocks[0].get("id") if blocks else None


def _find_story_block(page_data: dict[str, Any]) -> str | None:
    for block in _extract_blocks(page_data):
        if block.get("component_type") == "StoryText":
            return block.get("id")
    return None


def _find_block_count(page_data: dict[str, Any]) -> int:
    return len(_extract_blocks(page_data))


def _list_component_types(page_data: dict[str, Any]) -> list[str]:
    return [block.get("component_type", "") for block in _extract_blocks(page_data)]


def _print_turn_summary(prefix: str, turn_data: dict[str, Any]) -> dict[str, Any]:
    page = _pick(turn_data, "page_data", "pageData", "noteData", default={}) or {}
    html = _pick(turn_data, "source_code", "sourceCode", "htmlPreview", default="") or ""
    print(f"[probe] {prefix} turn complete")
    print(f"[probe] title={page.get('page_title')!r} blocks={len(_extract_blocks(page))} html_len={len(html)}")
    return page


async def _send_turn(ws, payload: dict[str, Any]) -> dict[str, Any]:
    await ws.send(json.dumps(payload, ensure_ascii=False))
    while True:
        raw = await ws.recv()
        event = json.loads(raw)
        kind = event.get("event")
        if kind == "turn_end":
            return event["data"]
        if kind == "error":
            raise RuntimeError(event.get("data") or "websocket returned error")
        if kind == "action_required":
            raise RuntimeError(f"graph requires manual action: {event.get('data')}")


async def main():
    parser = argparse.ArgumentParser(description="Probe the XHS-Forge websocket flow.")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host")
    parser.add_argument("--port", type=int, default=8000, help="Backend port")
    parser.add_argument("--thread-id", default=f"probe-{secrets.token_hex(4)}", help="Thread id to reuse")
    parser.add_argument("--create", default="帮我生成一篇关于华为 Mate 60 的对比种草笔记", help="First-turn prompt")
    parser.add_argument("--edit", default="把这个区块改得更毒舌一点", help="Second-turn prompt")
    parser.add_argument("--global-edit", default="", help="Optional third-turn prompt for editing the existing canvas globally")
    parser.add_argument("--theme-edit", default="", help="Optional fourth-turn prompt for updating page theme")
    parser.add_argument("--replace-edit", default="", help="Optional fifth-turn prompt for replacing an existing block globally")
    parser.add_argument("--remove-edit", default="", help="Optional sixth-turn prompt for removing an existing block globally")
    parser.add_argument("--panel", default="main", help="Panel name")
    parser.add_argument("--persona", default="硬核数码博主", help="Creator persona")
    parser.add_argument("--target-type", default="PollBlock", help="Preferred block type for second turn")
    parser.add_argument("--skip-edit", action="store_true", help="Only run the first turn")
    args = parser.parse_args()

    url = f"ws://{args.host}:{args.port}/ws/chat/{args.thread_id}"
    print(f"[probe] connecting to {url}")

    async with websockets.connect(url, max_size=8_000_000) as ws:
        create_payload = {
            "content": args.create,
            "panel": args.panel,
            "selected_element_id": "无 (全局修改)",
            "creator_persona": args.persona,
        }
        create_result = await _send_turn(ws, create_payload)
        create_page = _print_turn_summary("create", create_result)

        if args.skip_edit:
            return

        selected_block_id = _find_target_block(create_page, args.target_type)
        if not selected_block_id:
            raise RuntimeError("no editable block found in first turn result")
        print(f"[probe] selected block for second turn: {selected_block_id}")

        edit_payload = {
            "content": args.edit,
            "panel": args.panel,
            "selected_element_id": selected_block_id,
            "creator_persona": args.persona,
        }
        edit_result = await _send_turn(ws, edit_payload)
        edit_page = _print_turn_summary("local edit", edit_result)

        target_payload = edit_page.get(selected_block_id, {})
        print("[probe] edited block payload:")
        print(json.dumps(target_payload, ensure_ascii=False, indent=2))

        if not args.global_edit:
            return

        story_block_id = _find_story_block(edit_page)
        global_edit_payload = {
            "content": args.global_edit,
            "panel": args.panel,
            "selected_element_id": "无 (全局修改)",
            "creator_persona": args.persona,
        }
        global_result = await _send_turn(ws, global_edit_payload)
        global_page = _print_turn_summary("global edit", global_result)

        if story_block_id:
            story_payload = global_page.get(story_block_id, {})
            print("[probe] globally edited story payload:")
            print(json.dumps(story_payload, ensure_ascii=False, indent=2))

        if not args.theme_edit:
            return

        theme_payload = {
            "content": args.theme_edit,
            "panel": args.panel,
            "selected_element_id": "无 (全局修改)",
            "creator_persona": args.persona,
        }
        theme_result = await _send_turn(ws, theme_payload)
        theme_page = _print_turn_summary("theme edit", theme_result)
        page_theme = theme_page.get("page_theme", {})
        print("[probe] page theme:")
        print(json.dumps(page_theme, ensure_ascii=False, indent=2))

        current_page = theme_page
        if not args.replace_edit:
            return

        replace_payload = {
            "content": args.replace_edit,
            "panel": args.panel,
            "selected_element_id": "无 (全局修改)",
            "creator_persona": args.persona,
        }
        replace_result = await _send_turn(ws, replace_payload)
        current_page = _print_turn_summary("replace edit", replace_result)
        print(f"[probe] component types after replace: {_list_component_types(current_page)}")

        if not args.remove_edit:
            return

        remove_payload = {
            "content": args.remove_edit,
            "panel": args.panel,
            "selected_element_id": "无 (全局修改)",
            "creator_persona": args.persona,
        }
        remove_result = await _send_turn(ws, remove_payload)
        current_page = _print_turn_summary("remove edit", remove_result)
        print(f"[probe] component types after remove: {_list_component_types(current_page)}")


if __name__ == "__main__":
    asyncio.run(main())
