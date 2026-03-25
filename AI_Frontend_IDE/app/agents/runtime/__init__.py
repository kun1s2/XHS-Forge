from __future__ import annotations

from typing import Any


def build_supervisor_runtime(*args: Any, **kwargs: Any):
    from .phase_graph_runtime import build_supervisor_runtime as _impl

    return _impl(*args, **kwargs)


def apply_supervisor_checkpoint_decision(*args: Any, **kwargs: Any):
    from .supervisor_runtime import apply_supervisor_checkpoint_decision as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "apply_supervisor_checkpoint_decision",
    "build_supervisor_runtime",
]
