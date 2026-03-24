from __future__ import annotations

from typing import Any

try:
    from langchain.agents import create_agent as _create_agent  # type: ignore
except Exception:  # pragma: no cover - env dependent
    _create_agent = None


class CompatibleAgentRunner:
    def __init__(self, runnable: Any, backend: str):
        self._runnable = runnable
        self.backend = backend

    def __getattr__(self, item: str) -> Any:
        return getattr(self._runnable, item)

    async def ainvoke(self, inputs: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self._runnable.ainvoke(inputs, config=config)
        if isinstance(result, dict):
            return result
        if hasattr(result, "messages"):
            return {"messages": list(getattr(result, "messages") or [])}
        if isinstance(result, list):
            return {"messages": result}
        return {"messages": [result]}

    async def astream_events(self, *args, **kwargs):
        async for item in self._runnable.astream_events(*args, **kwargs):
            yield item

    async def aget_state(self, *args, **kwargs):
        return await self._runnable.aget_state(*args, **kwargs)

    async def aupdate_state(self, *args, **kwargs):
        return await self._runnable.aupdate_state(*args, **kwargs)

    async def aget_state_history(self, *args, **kwargs):
        async for item in self._runnable.aget_state_history(*args, **kwargs):
            yield item


def create_controlled_agent(
    *,
    model: Any,
    tools: Any,
    prompt: Any = None,
    state_schema: Any = None,
    context_schema: Any = None,
    store: Any = None,
    checkpointer: Any = None,
    response_format: Any = None,
    name: str | None = None,
    prefer_create_agent: bool = True,
    middleware: list[Any] | None = None,
) -> CompatibleAgentRunner:
    if not prefer_create_agent:
        raise ValueError("Legacy react-style agent runtime is no longer supported in the formal product path")

    if _create_agent is None:  # pragma: no cover - env dependent
        raise RuntimeError("langchain.agents.create_agent is unavailable in the current environment")

    kwargs: dict[str, Any] = {
        "model": model,
        "tools": tools,
        "name": name,
        "middleware": middleware or [],
    }
    if prompt is not None:
        kwargs["system_prompt"] = prompt
    if state_schema is not None:
        kwargs["state_schema"] = state_schema
    if context_schema is not None:
        kwargs["context_schema"] = context_schema
    if store is not None:
        kwargs["store"] = store
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if response_format is not None:
        kwargs["response_format"] = response_format

    runnable = _create_agent(**kwargs)
    return CompatibleAgentRunner(runnable, backend="langchain_create_agent")
