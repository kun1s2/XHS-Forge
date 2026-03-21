from types import SimpleNamespace

import pytest

from app.core import agent_runtime


class _FakeRunnable:
    def __init__(self, result):
        self._result = result

    async def ainvoke(self, _inputs):
        return self._result


def test_create_controlled_agent_rejects_legacy_stateful_prompt(monkeypatch):
    monkeypatch.setattr(agent_runtime, '_create_agent', object())

    with pytest.raises(ValueError, match='static string system prompts without state_schema'):
        agent_runtime.create_controlled_agent(
            model='llm',
            tools=['tool'],
            prompt=lambda state: 'prompt',
            state_schema=dict,
            name='note_editor',
        )


def test_create_controlled_agent_requires_langchain_create_agent(monkeypatch):
    monkeypatch.setattr(agent_runtime, '_create_agent', None)

    with pytest.raises(RuntimeError, match='create_agent is unavailable'):
        agent_runtime.create_controlled_agent(
            model='llm',
            tools=['tool'],
            prompt='static prompt',
            name='enrichment_agent',
        )


def test_create_controlled_agent_prefers_langchain_create_agent_for_static_prompt(monkeypatch):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return _FakeRunnable(SimpleNamespace(messages=['ok']))

    monkeypatch.setattr(agent_runtime, '_create_agent', fake_create_agent)

    runner = agent_runtime.create_controlled_agent(
        model='llm',
        tools=['tool'],
        prompt='static prompt',
        name='enrichment_agent',
    )

    assert runner.backend == 'langchain_create_agent'
    assert captured['system_prompt'] == 'static prompt'
    assert captured['name'] == 'enrichment_agent'
