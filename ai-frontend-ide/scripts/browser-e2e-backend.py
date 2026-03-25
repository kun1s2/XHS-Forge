from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


THREAD_ID = "thread_demo_browser"
ARTIFACT_ID = "artifact_demo_browser"


def _now() -> str:
    return datetime.now().isoformat()


def _block(block_id: str, block_type: str, props: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": block_type,
        "component_type": block_type,
        "props": props,
    }


def _base_retrieved_knowledge() -> dict[str, Any]:
    return {
        "entity_name": "华为 Mate 60",
        "knowledge_plan": {
            "goal_summary": "围绕华为 Mate 60 的购买价值，先判断结论，再补足参数与风险边界。",
            "required_fields": ["price", "camera", "battery", "charging"],
            "preferred_sources": ["session_kb", "knowledge_snapshot", "web_search"],
            "knowledge_budget": 4,
            "field_labels": {
                "price": "价格",
                "camera": "影像",
                "battery": "续航",
                "charging": "充电",
            },
        },
        "candidate_session_kb": {"groups": []},
        "session_kb": {
            "knowledge_version": "session-kb::3",
            "groups": [
                {
                    "normalized_entity": "华为 Mate 60",
                    "field_or_topic": "price",
                    "records": [{"summary": "当前讨论价格集中在 4500 元左右。", "review_status": "approved"}],
                },
                {
                    "normalized_entity": "华为 Mate 60",
                    "field_or_topic": "camera",
                    "records": [{"summary": "影像风格更偏成片观感。", "review_status": "approved"}],
                },
            ],
        },
    }


def _blank_note_document() -> dict[str, Any]:
    return {"document_meta": {"title": "空白页"}, "blocks": [], "assets": []}


def _created_blocks() -> list[dict[str, Any]]:
    return [
        _block(
            "title_1",
            "TitleBlock",
            {"title": "华为 Mate 60：4500 元档位里更适合看重拍照和续航的人"},
        ),
        _block(
            "story_1",
            "StoryText",
            {
                "paragraphs": [
                    "如果你的预算就在 4500 元左右，Mate 60 最核心的判断是：它不是参数最猛，但在拍照风格、续航和系统稳感上仍然有明显吸引力。",
                    "真正要想清楚的是，你是否愿意为这种综合体验去接受价格与同档竞品之间的取舍。",
                ]
            },
        ),
        _block(
            "spec_1",
            "ProductSpecCard",
            {
                "core_features": [
                    "价格边界：4500 元左右讨论区间",
                    "续航：稳定",
                    "充电：日常回补够用",
                    "影像：更偏成片观感",
                ]
            },
        ),
    ]


def _cover_block() -> dict[str, Any]:
    return _block(
        "cover_1",
        "CoverSwiper",
        {
            "image_urls": [
                "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1200&q=80",
                "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?auto=format&fit=crop&w=1200&q=80",
            ],
            "title": "华为 Mate 60 真机观感",
            "description": "补齐真机图后，这份档案更容易快速建立购买直觉。",
            "chips": ["真机图", "购买判断", "影像与续航"],
        },
    )


def _primary_recipe(reason: str, prompt: str) -> dict[str, Any]:
    return {
        "label": "把结论说得更直接",
        "prompt": prompt,
        "scope": "summary",
        "why_now": reason,
        "expected_effect": "读者第一眼就能看出值不值得买。",
        "expected_blocks": ["story_1"],
    }


@dataclass
class SessionState:
    thread_id: str
    artifact_id: str = ARTIFACT_ID
    version_counter: int = 0
    checkpoint_id: str = "checkpoint_blank"
    note_document: dict[str, Any] = field(default_factory=_blank_note_document)
    image_assets: list[dict[str, Any]] = field(default_factory=list)
    artifact: dict[str, Any] = field(default_factory=dict)
    artifact_version: dict[str, Any] = field(default_factory=dict)
    revision_plan: dict[str, Any] = field(default_factory=dict)
    revision_result: dict[str, Any] = field(default_factory=dict)
    revision_status: dict[str, Any] = field(default_factory=dict)
    turn_trace: dict[str, Any] = field(default_factory=dict)
    retrieved_knowledge: dict[str, Any] = field(default_factory=_base_retrieved_knowledge)
    worker_prompts: dict[str, Any] = field(default_factory=dict)
    planner_output: dict[str, Any] = field(default_factory=dict)
    planner_policy: dict[str, Any] = field(default_factory=dict)
    agent_backends: dict[str, Any] = field(default_factory=dict)

    def _next_version_id(self) -> str:
        self.version_counter += 1
        return f"version_{self.version_counter:03d}"

    def _checkpoint(self, suffix: str) -> str:
        self.checkpoint_id = f"checkpoint_{suffix}_{self.version_counter:03d}"
        return self.checkpoint_id

    def _manifest(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": "purchase_decision_note",
            "current_version_id": self.artifact_version.get("version_id") or "",
            "current_snapshot_id": self.artifact_version.get("snapshot_id") or "",
            "title": self.note_document.get("document_meta", {}).get("title") or "华为 Mate 60 购买决策档案",
            "status": "active",
        }

    def _make_version(self, *, reason: str, changed_blocks: list[dict[str, Any]], assets_delta: list[dict[str, Any]]) -> dict[str, Any]:
        previous_id = self.artifact_version.get("version_id")
        version = {
            "version_id": self._next_version_id(),
            "parent_version_id": previous_id or None,
            "snapshot_id": f"snapshot_{self.version_counter:03d}",
            "checkpoint_id": self.checkpoint_id,
            "revision_reason": reason,
            "changed_blocks": deepcopy(changed_blocks),
            "assets_delta": deepcopy(assets_delta),
            "knowledge_version": "session-kb::3",
            "created_at": _now(),
            "artifact_id": self.artifact_id,
        }
        self.artifact_version = version
        self.artifact = self._manifest()
        return version

    def to_workspace_snapshot(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "messages": {"main": []},
            "note_document": deepcopy(self.note_document),
            "image_assets": deepcopy(self.image_assets),
            "artifact": deepcopy(self.artifact),
            "artifact_version": deepcopy(self.artifact_version),
            "revision_plan": deepcopy(self.revision_plan),
            "revision_result": deepcopy(self.revision_result),
            "revision_status": deepcopy(self.revision_status),
            "turn_trace": deepcopy(self.turn_trace),
            "retrieved_knowledge": deepcopy(self.retrieved_knowledge),
            "worker_prompts": deepcopy(self.worker_prompts),
            "planner_output": deepcopy(self.planner_output),
            "planner_policy": deepcopy(self.planner_policy),
            "agent_backends": deepcopy(self.agent_backends),
        }

    def created_payload(self) -> dict[str, Any]:
        self.note_document = {
            "document_meta": {"title": "华为 Mate 60 购买决策档案"},
            "blocks": _created_blocks(),
            "assets": [],
        }
        self.image_assets = []
        self._checkpoint("create")
        changed_blocks = [
            {"id": "title_1", "type": "TitleBlock", "changed_fields": ["added"]},
            {"id": "story_1", "type": "StoryText", "changed_fields": ["added"]},
            {"id": "spec_1", "type": "ProductSpecCard", "changed_fields": ["added"]},
        ]
        reason = "当前结论还不够利落。"
        self._make_version(reason=reason, changed_blocks=changed_blocks, assets_delta=[])
        recipe = _primary_recipe(reason, "把结论改得更像给朋友的购买建议。")
        self.revision_plan = {
            "recipe_id": "summary",
            "label": recipe["label"],
            "prompt": recipe["prompt"],
            "reason": reason,
            "scope": "global_canvas",
            "target_block_id": None,
            "target_block_type": None,
            "operation_type": "text_edit",
            "allowed_change_surface": ["summary"],
            "expected_effect": recipe["expected_effect"],
            "expected_blocks": recipe["expected_blocks"],
            "primary_recipe": deepcopy(recipe),
        }
        self.revision_result = {
            "status": "success",
            "changed_blocks": deepcopy(changed_blocks),
            "assets_delta": [],
            "failure_reason": "",
            "worker_name": "composition_worker",
            "revision_reason": reason,
        }
        self.revision_status = {
            "status": "ready",
            "needs_revision": True,
            "primary_recipe": deepcopy(recipe),
            "suggestion_count": 1,
            "failure_reason": "",
        }
        self.turn_trace = {
            "query": "生成购买决策档案",
            "message_kind": "checkpoint_decision",
            "selected_element_id": "无 (全局修改)",
            "changed_blocks": deepcopy(changed_blocks),
            "revision": {
                "status": "ready",
                "reason": reason,
                "changed_blocks": deepcopy(changed_blocks),
                "failure_reason": "",
            },
        }
        return self._turn_end_payload()

    def asset_payload(self) -> dict[str, Any]:
        blocks = [block for block in self.note_document.get("blocks", []) if block.get("id") != "cover_1"]
        blocks.insert(1, _cover_block())
        self.note_document = {
            **self.note_document,
            "blocks": blocks,
            "assets": deepcopy(_cover_block()["props"]["image_urls"]),
        }
        self.image_assets = [
            {"url": url, "desc": "华为 Mate 60 真机图"} for url in _cover_block()["props"]["image_urls"]
        ]
        self._checkpoint("asset")
        changed_blocks = [{"id": "cover_1", "type": "CoverSwiper", "changed_fields": ["added"]}]
        assets_delta = [{"url": item["url"], "desc": item["desc"]} for item in self.image_assets]
        reason = "先把真机图补齐，让页面更容易建立购买直觉。"
        self._make_version(reason=reason, changed_blocks=changed_blocks, assets_delta=assets_delta)
        self.revision_result = {
            "status": "success",
            "changed_blocks": deepcopy(changed_blocks),
            "assets_delta": deepcopy(assets_delta),
            "failure_reason": "",
            "worker_name": "composition_worker",
            "revision_reason": reason,
        }
        self.turn_trace = {
            "query": "这份档案图片太少了，补几张更像真机质感的图片。",
            "message_kind": "user_prompt",
            "selected_element_id": "无 (全局修改)",
            "changed_blocks": deepcopy(changed_blocks),
            "revision": {
                "status": "applied",
                "reason": reason,
                "changed_blocks": deepcopy(changed_blocks),
                "failure_reason": "",
            },
        }
        return self._turn_end_payload()

    def direct_edit_payload(self) -> dict[str, Any]:
        blocks = deepcopy(self.note_document.get("blocks", []))
        for block in blocks:
            if block.get("id") == "story_1":
                block["props"]["paragraphs"] = [
                    "如果你预算就在 4500 元上下、又把拍照和续航放在前面，华为 Mate 60 依然值得优先看。",
                    "它真正的代价不是配置弱，而是你要接受价格和同档竞品之间的取舍。",
                ]
        self.note_document = {**self.note_document, "blocks": blocks}
        self._checkpoint("edit")
        changed_blocks = [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}]
        reason = "把结论先说得更直接，方便快速判断。"
        self._make_version(reason=reason, changed_blocks=changed_blocks, assets_delta=[])
        recipe = _primary_recipe("继续把结论改得更像朋友之间的购买建议。", "把结论改得更像给朋友的购买建议")
        self.revision_plan = {
            **self.revision_plan,
            "reason": recipe["why_now"],
            "primary_recipe": deepcopy(recipe),
            "prompt": recipe["prompt"],
        }
        self.revision_result = {
            "status": "success",
            "changed_blocks": deepcopy(changed_blocks),
            "assets_delta": [],
            "failure_reason": "",
            "worker_name": "composition_worker",
            "revision_reason": reason,
        }
        self.revision_status = {
            "status": "ready",
            "needs_revision": True,
            "primary_recipe": deepcopy(recipe),
            "suggestion_count": 1,
            "failure_reason": "",
        }
        self.turn_trace = {
            "query": "把结论改得更直接一点",
            "message_kind": "user_prompt",
            "selected_element_id": "story_1",
            "changed_blocks": deepcopy(changed_blocks),
            "revision": {
                "status": "applied",
                "reason": reason,
                "changed_blocks": deepcopy(changed_blocks),
                "failure_reason": "",
            },
        }
        return self._turn_end_payload()

    def revision_payload(self) -> dict[str, Any]:
        blocks = deepcopy(self.note_document.get("blocks", []))
        for block in blocks:
            if block.get("id") == "story_1":
                block["props"]["paragraphs"] = [
                    "如果你朋友现在就拿着 4500 元来问我，我会直接把华为 Mate 60 放进优先考虑名单。",
                    "它不是这个价位最堆料的那台，但如果你更看重拍照观感、续航和整体稳感，这个取舍是说得通的。",
                ]
        self.note_document = {**self.note_document, "blocks": blocks}
        self._checkpoint("revision")
        changed_blocks = [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}]
        reason = "继续把结论改得更像朋友之间的购买建议。"
        self._make_version(reason=reason, changed_blocks=changed_blocks, assets_delta=[])
        recipe = _primary_recipe("这轮已经应用到当前档案。", "把结论改得更像给朋友的购买建议")
        self.revision_result = {
            "status": "success",
            "changed_blocks": deepcopy(changed_blocks),
            "assets_delta": [],
            "failure_reason": "",
            "worker_name": "composition_worker",
            "revision_reason": reason,
        }
        self.revision_status = {
            "status": "applied",
            "needs_revision": True,
            "primary_recipe": deepcopy(recipe),
            "suggestion_count": 1,
            "failure_reason": "",
        }
        self.turn_trace = {
            "query": "把结论改得更像给朋友的购买建议",
            "message_kind": "revision_action",
            "selected_element_id": "story_1",
            "changed_blocks": deepcopy(changed_blocks),
            "revision": {
                "status": "applied",
                "reason": reason,
                "changed_blocks": deepcopy(changed_blocks),
                "failure_reason": "",
            },
        }
        return self._turn_end_payload()

    def _turn_end_payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "oss_url": None,
            "image_assets": deepcopy(self.image_assets),
            "source_code": "<html><body>browser-e2e</body></html>",
            "worker_prompts": deepcopy(self.worker_prompts),
            "note_document": deepcopy(self.note_document),
            "planner_output": deepcopy(self.planner_output),
            "planner_policy": deepcopy(self.planner_policy),
            "turn_trace": deepcopy(self.turn_trace),
            "agent_backends": deepcopy(self.agent_backends),
            "artifact": deepcopy(self.artifact),
            "artifact_version": deepcopy(self.artifact_version),
            "revision_plan": deepcopy(self.revision_plan),
            "revision_result": deepcopy(self.revision_result),
            "revision_status": deepcopy(self.revision_status),
            "revision_reason": str(self.artifact_version.get("revision_reason") or ""),
        }


SESSIONS: dict[str, SessionState] = {THREAD_ID: SessionState(thread_id=THREAD_ID)}


def get_session(thread_id: str) -> SessionState:
    if thread_id not in SESSIONS:
        SESSIONS[thread_id] = SessionState(thread_id=thread_id)
    return SESSIONS[thread_id]


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/workspace/sessions")
async def workspace_sessions():
    return {
        "sessions": [
            {
                "thread_id": THREAD_ID,
                "title": "Mate 60 浏览器演示",
                "updated_at": _now(),
            }
        ]
    }


@app.get("/workspace/trends")
async def workspace_trends():
    return {"trends": []}


@app.get("/workspace/benchmark/overview")
async def benchmark_overview():
    return {"data": {}}


@app.get("/workspace/evaluation/overview")
async def evaluation_overview():
    return {"data": {}}


@app.get("/workspace/block-gallery/overview")
async def block_gallery_overview():
    return {"data": {}}


@app.get("/workspace/showcase/profiles")
async def showcase_profiles():
    return {"profiles": []}


@app.get("/workspace/{thread_id}")
async def workspace_snapshot(thread_id: str):
    return get_session(thread_id).to_workspace_snapshot()


@app.get("/workspace/{thread_id}/inspect")
async def workspace_inspect(thread_id: str):
    return {"status": "success", "data": get_session(thread_id).to_workspace_snapshot()}


@app.websocket("/ws/chat/{thread_id}")
async def websocket_chat(websocket: WebSocket, thread_id: str):
    await websocket.accept()
    session = get_session(thread_id)
    try:
        while True:
            payload = await websocket.receive_json()
            message_type = str(payload.get("type") or "").strip()
            message_kind = str(payload.get("message_kind") or "user_prompt").strip()
            content = str(payload.get("content") or "").strip()

            if message_type == "submit_checkpoint_decision":
                await websocket.send_json({"event": "turn_end", "data": session.created_payload()})
                continue

            if message_kind == "revision_action" or "给朋友的购买建议" in content:
                await websocket.send_json({"event": "turn_end", "data": session.revision_payload()})
                continue

            if "更直接一点" in content:
                await websocket.send_json({"event": "turn_end", "data": session.direct_edit_payload()})
                continue

            if any(token in content for token in ("补几张", "图片太少", "真机质感的图片", "加一些真机图")):
                await websocket.send_json({"event": "turn_end", "data": session.asset_payload()})
                continue

            await websocket.send_json(
                {
                    "event": "action_required",
                    "data": {
                        "action_type": "structure_checkpoint",
                        "checkpoint_id": "structure::seeding_compare",
                        "title": "这页先按哪种方向搭骨架？",
                        "summary": "我先给出推荐结构，你决定方向后，我再继续补齐事实、安排素材并搭完整页面。",
                        "recommended_option": "seeding_compare",
                        "blocking": True,
                        "options": [
                            {
                                "label": "更像对比测评",
                                "value": "seeding_compare",
                                "description": "先讲结论，再给参数和对比，适合做购买分流。",
                                "recommended": True,
                            }
                        ],
                        "resume_token": "thread:structure:resume",
                    },
                }
            )
    except WebSocketDisconnect:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
