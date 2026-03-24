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

    async def ainvoke(self, inputs: Any) -> dict[str, Any]:
        result = await self._runnable.ainvoke(inputs)
        if isinstance(result, dict):
            return result
        if hasattr(result, "messages"):
            return {"messages": list(getattr(result, "messages") or [])}
        if isinstance(result, list):
            return {"messages": result}
        return {"messages": [result]}


def create_controlled_agent(
    *,
    model: Any,
    tools: Any,
    prompt: Any = None,
    state_schema: Any = None,
    name: str | None = None,
    prefer_create_agent: bool = True,
    middleware: list[Any] | None = None,
) -> CompatibleAgentRunner:
    if not prefer_create_agent:
        raise ValueError("Legacy react-style agent runtime is no longer supported in the formal product path")

    if _create_agent is None:  # pragma: no cover - env dependent
        raise RuntimeError("langchain.agents.create_agent is unavailable in the current environment")

    if state_schema is not None or not isinstance(prompt, str):
        raise ValueError("create_controlled_agent now only supports static string system prompts without state_schema")

    runnable = _create_agent(
        model=model,
        tools=tools,
        system_prompt=prompt,
        name=name,
        middleware=middleware or [],
    )
    return CompatibleAgentRunner(runnable, backend="langchain_create_agent")
