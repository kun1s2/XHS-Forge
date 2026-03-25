from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.runtime import supervisor_runtime
from app.agents.workers import composition_worker as composition_worker_module
from app.agents.workers import retrieval_worker as retrieval_worker_module
from app.core import agent_runtime


class _FakeRunnable:
    def __init__(self, result):
        self._result = result

    async def ainvoke(self, _inputs, config=None):
        return self._result


def test_create_controlled_agent_requires_langchain_create_agent(monkeypatch):
    monkeypatch.setattr(agent_runtime, "_create_agent", None)

    with pytest.raises(RuntimeError, match="create_agent is unavailable"):
        agent_runtime.create_controlled_agent(
            model="llm",
            tools=["tool"],
            prompt="static prompt",
            name="enrichment_agent",
        )


def test_create_controlled_agent_forwards_state_schema_and_middleware(monkeypatch):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return _FakeRunnable(SimpleNamespace(messages=["ok"]))

    monkeypatch.setattr(agent_runtime, "_create_agent", fake_create_agent)

    middleware = [object()]
    runner = agent_runtime.create_controlled_agent(
        model="llm",
        tools=["tool"],
        prompt="static prompt",
        name="supervisor_agent",
        state_schema=dict,
        middleware=middleware,
        response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": {"type": "object"}}},
    )

    assert runner.backend == "langchain_create_agent"
    assert captured["system_prompt"] == "static prompt"
    assert captured["name"] == "supervisor_agent"
    assert captured["state_schema"] is dict
    assert captured["middleware"] == middleware
    assert "response_format" in captured


@pytest.mark.asyncio
async def test_compatible_agent_runner_wraps_non_dict_results():
    runner = agent_runtime.CompatibleAgentRunner(_FakeRunnable(SimpleNamespace(messages=["ok"])), backend="x")
    result = await runner.ainvoke({"messages": []})

    assert result == {"messages": ["ok"]}


def test_supervisor_structured_response_is_normalized_to_plain_dict():
    response = supervisor_runtime.SupervisorStructuredResponse(
        reply="ok",
        next_step="continue",
        turn_outcome="analysis",
    )

    normalized = supervisor_runtime._normalize_structured_response(response)

    assert normalized == {
        "reply": "ok",
        "next_step": "continue",
        "turn_outcome": "analysis",
    }


def test_sanitize_persistent_messages_removes_orphaned_tool_entries():
    ai_with_tool_call = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "retrieval_worker", "args": {}}])
    safe_ai = AIMessage(content="普通回复")
    human = HumanMessage(content="帮我补图")
    tool = ToolMessage(content="tool result", tool_call_id="call_1")

    sanitized = supervisor_runtime._sanitize_persistent_messages([human, ai_with_tool_call, tool, safe_ai])

    assert sanitized == [human, safe_ai]


def test_sanitize_model_messages_keeps_valid_tool_pairs_and_drops_orphans():
    human = HumanMessage(content="帮我补图")
    ai_with_tool_call = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "retrieval_worker", "args": {}}])
    valid_tool = ToolMessage(content="检索结果", tool_call_id="call_1")
    orphan_tool = ToolMessage(content="脏数据", tool_call_id="missing")
    safe_ai = AIMessage(content="我先整理好候选图。")

    sanitized = supervisor_runtime._sanitize_model_messages([human, ai_with_tool_call, valid_tool, orphan_tool, safe_ai])

    assert sanitized == [human, ai_with_tool_call, valid_tool, safe_ai]


@pytest.mark.asyncio
async def test_retrieval_worker_payload_survives_agent_runner_failure(monkeypatch):
    class _FailingRunner:
        backend = "langchain_create_agent"

        async def ainvoke(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    async def _fake_research_service(_state):
        return {
            "retrieved_knowledge": {"retrieval_summary": {"strategy": "structured_first"}},
        }

    monkeypatch.setattr(retrieval_worker_module, "_get_retrieval_runner", lambda: _FailingRunner())
    monkeypatch.setattr(retrieval_worker_module, "research_service", _fake_research_service)

    payload = await retrieval_worker_module.retrieval_worker_payload(
        {
            "main_messages": [],
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "knowledge_plan": {"required_fields": ["price"]},
        }
    )

    trace = payload["turn_trace"]["retrieval_worker"]
    assert trace["skill_execution_result"] == "success"
    assert trace["skill_fallback"] == ["retrieval_worker_agent_runner_error:RuntimeError"]


@pytest.mark.asyncio
async def test_composition_worker_payload_uses_resume_directive_when_no_user_query(monkeypatch):
    captured = {}

    class _Runner:
        backend = "langchain_create_agent"

        async def ainvoke(self, inputs, **_kwargs):
            captured.update(inputs)
            return {"messages": []}

    async def _fake_composition_service(_state):
        return {"note_document": {"blocks": [], "assets": []}, "turn_trace": {"changed_blocks": []}}

    monkeypatch.setattr(composition_worker_module, "_get_composition_runner", lambda: _Runner())
    monkeypatch.setattr(composition_worker_module, "composition_service", _fake_composition_service)

    await composition_worker_module.composition_worker_payload(
        {
            "main_messages": [],
            "resume_directive": {"resume_query": "继续把已确认的结构落成持续笔记"},
            "intent_decision": {"task_type": "create", "operation_type": "generate"},
            "knowledge_plan": {"required_fields": ["price"]},
        }
    )

    rendered = captured["messages"][0][1]
    assert "继续把已确认的结构落成持续笔记" in rendered


@pytest.mark.asyncio
async def test_composition_worker_payload_prefers_latest_human_query_over_trailing_ai(monkeypatch):
    captured = {}

    class _Runner:
        backend = "langchain_create_agent"

        async def ainvoke(self, inputs, **_kwargs):
            captured.update(inputs)
            return {"messages": []}

    async def _fake_composition_service(_state):
        return {"note_document": {"blocks": [], "assets": []}, "turn_trace": {"changed_blocks": []}}

    monkeypatch.setattr(composition_worker_module, "_get_composition_runner", lambda: _Runner())
    monkeypatch.setattr(composition_worker_module, "composition_service", _fake_composition_service)

    await composition_worker_module.composition_worker_payload(
        {
            "main_messages": [
                HumanMessage(content="在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。"),
                AIMessage(content="我先整理销量信息。"),
            ],
            "resume_directive": {"resume_query": "继续把素材落到页面中。"},
            "intent_decision": {"task_type": "edit", "operation_type": "generate"},
            "knowledge_plan": {"required_fields": ["price"]},
        }
    )

    rendered = captured["messages"][0][1]
    assert "销量" in rendered
    assert "素材落到页面中" not in rendered

