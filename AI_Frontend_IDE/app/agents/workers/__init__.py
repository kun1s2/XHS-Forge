"""Worker 懒导出，避免只读导入时把检索/数据库链路一并拉起。"""

from importlib import import_module

__all__ = [
    "composition_worker_payload",
    "critique_worker_payload",
    "intent_worker",
    "retrieval_worker_payload",
]

_EXPORTS = {
    "composition_worker_payload": ("app.agents.workers.composition_worker", "composition_worker_payload"),
    "critique_worker_payload": ("app.agents.workers.critique_worker", "critique_worker_payload"),
    "intent_worker": ("app.agents.workers.intent_worker", "intent_worker"),
    "retrieval_worker_payload": ("app.agents.workers.retrieval_worker", "retrieval_worker_payload"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
