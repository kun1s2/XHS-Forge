from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from starlette.websockets import WebSocketState

from app.agents.runtime import apply_supervisor_checkpoint_decision
from app.agents.runtime import supervisor_runtime as supervisor_runtime_module
from app.api.chat import _run_supervisor_turn


class FakeSnapshot:
    def __init__(self, values, checkpoint_id="ckpt_e2e"):
        self.next = []
        self.values = values
        self.config = {"configurable": {"checkpoint_id": checkpoint_id}}


class FakeWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.messages = []
        self.app = SimpleNamespace(state=SimpleNamespace(vector_store=SimpleNamespace()))

    async def send_json(self, payload):
        self.messages.append(payload)


class DemoFlowAgent:
    def __init__(self, snapshot: FakeSnapshot):
        self.latest_snapshot = snapshot
        self.updated = []
        self.calls = []

    async def aget_state(self, config):
        return self.latest_snapshot

    async def aupdate_state(self, config, values, as_node=None):
        self.updated.append({"config": config, "values": values, "as_node": as_node})
        latest_values = dict(self.latest_snapshot.values)
        latest_values.update(values or {})
        self.latest_snapshot = FakeSnapshot(
            latest_values,
            checkpoint_id=self.latest_snapshot.config["configurable"]["checkpoint_id"],
        )
        return None

    async def astream_events(self, inputs, config=None, version="runtime"):
        self.calls.append({"inputs": inputs, "config": config, "version": version})
        values = deepcopy(self.latest_snapshot.values)
        prompt = ""
        for msg in inputs.get("messages") or []:
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                prompt = content.strip()
            elif isinstance(content, list):
                prompt = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict)).strip()

        if any(token in prompt for token in ("补几张", "图片太少", "真机质感的图片", "加一些真机图")):
            values.update(
                {
                    "current_phase": "composition",
                    "final_html": "<html><body>asset-updated</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": deepcopy(values["note_document"]["blocks"]),
                        "assets": [
                            {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                            {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                        ],
                    },
                    "image_assets": [
                        {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                        {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                    ],
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [],
                        "assets_delta": [
                            {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                            {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                        ],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "resume_directive": None,
                    "pending_checkpoint": None,
                }
            )
            self.latest_snapshot = FakeSnapshot(values, checkpoint_id="ckpt_e2e_asset")
        elif "给朋友的购买建议" in prompt:
            blocks = deepcopy(values["note_document"]["blocks"])
            for block in blocks:
                if block["id"] == "story_1":
                    block["props"]["paragraphs"] = [
                        "如果你朋友现在就拿着 4500 元来问我，我会直接把华为 Mate 60 放进优先考虑名单。",
                        "它不是这个价位最堆料的那台，但如果你更看重拍照观感、续航和整体稳感，这个取舍是说得通的。",
                    ]
            values.update(
                {
                    "current_phase": "composition",
                    "final_html": "<html><body>story-revision</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": blocks,
                        "assets": deepcopy(values["note_document"].get("assets") or []),
                    },
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "resume_directive": None,
                    "pending_checkpoint": None,
                }
            )
            self.latest_snapshot = FakeSnapshot(values, checkpoint_id="ckpt_e2e_revision")
        elif "更直接一点" in prompt:
            blocks = deepcopy(values["note_document"]["blocks"])
            for block in blocks:
                if block["id"] == "story_1":
                    block["props"]["paragraphs"] = [
                        "如果你预算就在 4500 元上下、又把拍照和续航放在前面，华为 Mate 60 依然值得优先看。",
                        "它真正的代价不是配置弱，而是你要接受价格和同档竞品之间的取舍。",
                    ]
            values.update(
                {
                    "current_phase": "composition",
                    "final_html": "<html><body>story-updated</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": blocks,
                        "assets": deepcopy(values["note_document"].get("assets") or []),
                    },
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "resume_directive": None,
                    "pending_checkpoint": None,
                }
            )
            self.latest_snapshot = FakeSnapshot(values, checkpoint_id="ckpt_e2e_edit")
        if False:
            yield {}


@pytest.mark.asyncio
async def test_demo_flow_create_resume_edit_revision(monkeypatch):
    async def _fake_retrieval(*, focus="", runtime=None):
        focus_text = str(focus or "")
        if any(token in focus_text for token in ("图片", "真机", "素材")):
            return Command(
                update={
                    "current_phase": "retrieval",
                    "retrieved_knowledge": {
                        "entity_name": "华为 Mate 60",
                        "retrieval_summary": {
                            "strategy": "image_search_first",
                            "entity_name": "华为 Mate 60",
                            "missing_fields": [],
                        },
                    },
                    "resume_directive": None,
                    "last_worker_result": {
                        "worker_name": "retrieval_worker",
                        "status": "success",
                        "changed_blocks": [],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": False,
                    },
                    "pending_checkpoint": None,
                }
            )
        return Command(
            update={
                "current_phase": "retrieval",
                "retrieved_knowledge": {
                    "entity_name": "华为 Mate 60",
                    "summary": "华为 Mate 60 更适合先从购买结论、关键参数和真实代价三个角度来判断。",
                    "retrieval_summary": {
                        "strategy": "structured_knowledge_first",
                        "entity_name": "华为 Mate 60",
                        "missing_fields": [],
                    },
                    "fact_slots": {
                        "price": {"summary": "当前讨论集中在 4500 元左右的入手边界。"},
                        "battery": {"summary": "续航表现稳定，适合重度日用。"},
                        "charging": {"summary": "快充能力足够覆盖日常回补。"},
                        "camera": {"summary": "影像风格更适合在意成片观感的人。"},
                    },
                },
                "resume_directive": {
                    "preferred_worker": "composition_worker",
                    "resume_query": "继续把已确认的结构和事实落成购买决策档案，不要再次请求结构确认。",
                    "decision": "seeding_compare",
                },
                "last_worker_result": {
                    "worker_name": "retrieval_worker",
                    "status": "success",
                    "changed_blocks": [],
                    "assets_delta": [],
                    "candidate_kb_delta": [{"field": "price"}, {"field": "battery"}, {"field": "camera"}],
                    "failure_reason": "",
                    "commit_eligible": False,
                },
                "pending_checkpoint": None,
            }
        )

    async def _fake_composition(*, focus="", runtime=None):
        focus_text = str(focus or "")
        if any(token in focus_text for token in ("图片", "真机", "素材")):
            current_values = deepcopy(((runtime or SimpleNamespace()).state if runtime is not None else {}) or {})
            current_document = deepcopy((current_values.get("note_document") or {}))
            blocks = deepcopy(current_document.get("blocks") or [])
            if not any(str(block.get("id") or "") == "cover_1" for block in blocks):
                blocks.append(
                    {
                        "id": "cover_1",
                        "type": "CoverSwiper",
                        "props": {
                            "image_urls": [
                                "https://img.example/mate60-1.jpg",
                                "https://img.example/mate60-2.jpg",
                            ]
                        },
                    }
                )
            return Command(
                update={
                    "current_phase": "composition",
                    "resume_directive": None,
                    "final_html": "<html><body>asset-updated</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": blocks,
                        "assets": [
                            {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                            {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                        ],
                    },
                    "image_assets": [
                        {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                        {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                    ],
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "cover_1", "type": "CoverSwiper", "changed_fields": ["added"]}],
                        "assets_delta": [
                            {"url": "https://img.example/mate60-1.jpg", "desc": "华为 Mate 60 真机图"},
                            {"url": "https://img.example/mate60-2.jpg", "desc": "华为 Mate 60 细节图"},
                        ],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "pending_checkpoint": None,
                }
            )
        if "更直接" in focus_text:
            current_values = deepcopy(((runtime or SimpleNamespace()).state if runtime is not None else {}) or {})
            current_document = deepcopy((current_values.get("note_document") or {}))
            blocks = deepcopy(current_document.get("blocks") or [])
            for block in blocks:
                if str(block.get("id") or "") == "story_1":
                    block["props"]["paragraphs"] = [
                        "如果你预算就在 4500 元上下、又把拍照和续航放在前面，华为 Mate 60 依然值得优先看。",
                        "它真正的代价不是配置弱，而是你要接受价格和同档竞品之间的取舍。",
                    ]
            return Command(
                update={
                    "current_phase": "composition",
                    "resume_directive": None,
                    "final_html": "<html><body>story-updated</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": blocks,
                        "assets": deepcopy(current_document.get("assets") or []),
                    },
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "pending_checkpoint": None,
                }
            )
        if any(token in focus_text for token in ("购买建议", "朋友")):
            current_values = deepcopy(((runtime or SimpleNamespace()).state if runtime is not None else {}) or {})
            current_document = deepcopy((current_values.get("note_document") or {}))
            blocks = deepcopy(current_document.get("blocks") or [])
            for block in blocks:
                if str(block.get("id") or "") == "story_1":
                    block["props"]["paragraphs"] = [
                        "如果你朋友现在就拿着 4500 元来问我，我会直接把华为 Mate 60 放进优先考虑名单。",
                        "它不是这个价位最堆料的那台，但如果你更看重拍照观感、续航和整体稳感，这个取舍是说得通的。",
                    ]
            return Command(
                update={
                    "current_phase": "composition",
                    "resume_directive": None,
                    "final_html": "<html><body>story-revision</body></html>",
                    "note_document": {
                        "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                        "blocks": blocks,
                        "assets": deepcopy(current_document.get("assets") or []),
                    },
                    "last_worker_result": {
                        "worker_name": "composition_worker",
                        "status": "success",
                        "changed_blocks": [{"id": "story_1", "type": "StoryText", "changed_fields": ["props"]}],
                        "assets_delta": [],
                        "candidate_kb_delta": [],
                        "failure_reason": "",
                        "commit_eligible": True,
                    },
                    "pending_checkpoint": None,
                }
            )
        return Command(
            update={
                "current_phase": "composition",
                "resume_directive": None,
                "final_html": "<html><body>created</body></html>",
                "note_document": {
                    "document_meta": {"title": "华为 Mate 60 购买决策档案"},
                    "blocks": [
                        {
                            "id": "title_1",
                            "type": "TitleBlock",
                            "props": {"title": "华为 Mate 60：4500 元档位里更适合看重拍照和续航的人"},
                        },
                        {
                            "id": "story_1",
                            "type": "StoryText",
                            "props": {
                                "paragraphs": [
                                    "如果你的预算就在 4500 元左右，Mate 60 这页最核心的判断是：它不是参数最猛，但在拍照风格、续航和系统稳感上仍然有明显吸引力。",
                                    "真正需要想清楚的是，你是否愿意为这种综合体验去接受价格和竞品差异带来的代价。",
                                ]
                            },
                        },
                        {
                            "id": "spec_1",
                            "type": "ProductSpecCard",
                            "props": {
                                "core_features": [
                                    "价格边界：4500 元左右讨论区间",
                                    "续航：稳定",
                                    "充电：日常回补够用",
                                    "影像：更偏成片观感",
                                ]
                            },
                        },
                    ],
                    "assets": [],
                },
                "critique_feedback": {
                    "action_recipes": [
                        {
                            "label": "把结论说得更直接",
                            "prompt": "把结论改得更直接一点，像给朋友的购买建议。",
                            "scope": "summary",
                            "why_now": "当前结论还不够利落。",
                            "expected_effect": "读者第一眼就能看出值不值得买。",
                        }
                    ]
                },
                "needs_revision": True,
                "last_worker_result": {
                    "worker_name": "composition_worker",
                    "status": "success",
                    "changed_blocks": [
                        {"id": "title_1", "type": "TitleBlock", "changed_fields": ["added"]},
                        {"id": "story_1", "type": "StoryText", "changed_fields": ["added"]},
                        {"id": "spec_1", "type": "ProductSpecCard", "changed_fields": ["added"]},
                    ],
                    "assets_delta": [],
                    "candidate_kb_delta": [],
                    "failure_reason": "",
                    "commit_eligible": True,
                },
                "pending_checkpoint": None,
            }
        )

    monkeypatch.setattr(supervisor_runtime_module.retrieval_worker, "coroutine", _fake_retrieval)
    monkeypatch.setattr(supervisor_runtime_module.composition_worker, "coroutine", _fake_composition)

    initial_values = {
        "active_archetype": "seeding",
        "planner_output": {"block_intents": []},
        "planner_policy": {"layout_policy": {}},
        "intent_decision": {"task_type": "create", "operation_type": "generate"},
        "pending_checkpoint": {
            "checkpoint_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding_compare",
            "title": "这页先按哪种方向搭骨架？",
            "summary": "请先确认这页的主方向。",
            "options": [{"label": "更像对比测评", "value": "seeding_compare", "recommended": True}],
            "resume_token": "thread:structure:resume",
        },
        "note_document": {"document_meta": {"title": "空白页"}, "blocks": [], "assets": []},
        "image_assets": [],
        "main_messages": [HumanMessage(content="我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。")],
    }
    agent = DemoFlowAgent(FakeSnapshot(initial_values, checkpoint_id="ckpt_e2e_initial"))
    websocket = FakeWebSocket()
    config = {"configurable": {"thread_id": "thread-e2e-demo"}}

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。")],
            "main_messages": [HumanMessage(content="我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。")],
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
        },
        config,
        websocket,
        turn_context={
            "user_query": "我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": {},
        },
    )
    assert websocket.messages[-1]["event"] == "action_required"

    checkpoint_patch = apply_supervisor_checkpoint_decision(
        agent.latest_snapshot.values,
        {
            "action_type": "structure_checkpoint",
            "checkpoint_id": "structure::seeding_compare",
            "decision": "seeding_compare",
        },
    )
    await agent.aupdate_state(config, checkpoint_patch)

    await _run_supervisor_turn(
        agent,
        {"messages": [], "main_messages": []},
        config,
        websocket,
        turn_context={
            "user_query": "",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "message_kind": "checkpoint_decision",
            "before_values": initial_values,
        },
    )
    create_payload = websocket.messages[-1]["data"]
    assert create_payload["note_document"]["document_meta"]["title"] == "华为 Mate 60 购买决策档案"
    assert create_payload["artifact_version"]["version_id"].startswith("version_")
    assert create_payload["turn_trace"]["changed_blocks"]
    create_story = next(block for block in create_payload["note_document"]["blocks"] if block["id"] == "story_1")
    assert all("Find X8 Ultra" not in paragraph for paragraph in create_story["props"]["paragraphs"])
    assert all("StoryText" not in paragraph for paragraph in create_story["props"]["paragraphs"])
    version_after_create = create_payload["artifact_version"]["version_id"]

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="这份档案图片太少了，补几张更像真机质感的图片。")],
            "main_messages": [HumanMessage(content="这份档案图片太少了，补几张更像真机质感的图片。")],
            "active_panel": "main",
            "selected_element_id": "无 (全局修改)",
        },
        config,
        websocket,
        turn_context={
            "user_query": "这份档案图片太少了，补几张更像真机质感的图片。",
            "selected_element_id": "无 (全局修改)",
            "panel": "main",
            "before_values": agent.latest_snapshot.values,
        },
    )
    asset_payload = websocket.messages[-1]["data"]
    assert asset_payload["artifact_version"]["parent_version_id"] == version_after_create
    assert len(asset_payload["image_assets"]) == 2
    assert asset_payload["artifact_version"]["assets_delta"]
    version_after_assets = asset_payload["artifact_version"]["version_id"]

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="把结论改得更直接一点")],
            "main_messages": [HumanMessage(content="把结论改得更直接一点")],
            "active_panel": "main",
            "selected_element_id": "story_1",
        },
        config,
        websocket,
        turn_context={
            "user_query": "把结论改得更直接一点",
            "selected_element_id": "story_1",
            "panel": "main",
            "before_values": agent.latest_snapshot.values,
        },
    )
    edit_payload = websocket.messages[-1]["data"]
    assert edit_payload["artifact_version"]["parent_version_id"] == version_after_assets
    assert any(item["id"] == "story_1" for item in edit_payload["turn_trace"]["changed_blocks"])
    edited_story = next(block for block in edit_payload["note_document"]["blocks"] if block["id"] == "story_1")
    assert "华为 Mate 60" in "\n".join(edited_story["props"]["paragraphs"])
    assert "Find X8 Ultra" not in "\n".join(edited_story["props"]["paragraphs"])
    version_after_edit = edit_payload["artifact_version"]["version_id"]

    await _run_supervisor_turn(
        agent,
        {
            "messages": [HumanMessage(content="把结论改得更像给朋友的购买建议")],
            "main_messages": [HumanMessage(content="把结论改得更像给朋友的购买建议")],
            "active_panel": "main",
            "selected_element_id": "story_1",
        },
        config,
        websocket,
        turn_context={
            "user_query": "把结论改得更像给朋友的购买建议",
            "selected_element_id": "story_1",
            "panel": "main",
            "message_kind": "revision_action",
            "before_values": agent.latest_snapshot.values,
        },
    )
    revision_payload = websocket.messages[-1]["data"]
    assert revision_payload["artifact_version"]["parent_version_id"] == version_after_edit
    assert revision_payload["artifact_version"]["revision_reason"] != "composition_no_effect"
    assert revision_payload["turn_trace"]["changed_blocks"]
    assert revision_payload["revision_status"]["status"] in {"ready", "applied", "idle"}
