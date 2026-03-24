from types import SimpleNamespace

import pytest

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
