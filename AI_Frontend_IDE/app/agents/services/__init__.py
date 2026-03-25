"""服务层懒导出，避免子模块导入时把整套运行时重依赖一起拉起。"""

from importlib import import_module

__all__ = [
    "build_artifact_patch",
    "build_artifact_version",
    "ensure_artifact_manifest",
    "get_knowledge_version",
    "build_revision_plan",
    "build_revision_result",
    "build_revision_status",
    "select_primary_recipe",
    "ensure_session_runtime_defaults",
    "build_component_fallback",
    "component_builder_node",
    "enforce_component_contract",
    "composition_service",
    "research_service",
]

_EXPORTS = {
    "build_artifact_patch": ("app.agents.services.artifact_service", "build_artifact_patch"),
    "build_artifact_version": ("app.agents.services.artifact_service", "build_artifact_version"),
    "ensure_artifact_manifest": ("app.agents.services.artifact_service", "ensure_artifact_manifest"),
    "get_knowledge_version": ("app.agents.services.artifact_service", "get_knowledge_version"),
    "build_revision_plan": ("app.agents.services.revision_service", "build_revision_plan"),
    "build_revision_result": ("app.agents.services.revision_service", "build_revision_result"),
    "build_revision_status": ("app.agents.services.revision_service", "build_revision_status"),
    "select_primary_recipe": ("app.agents.services.revision_service", "select_primary_recipe"),
    "ensure_session_runtime_defaults": ("app.agents.services.session_state_service", "ensure_session_runtime_defaults"),
    "build_component_fallback": ("app.agents.services.component_builder", "build_component_fallback"),
    "component_builder_node": ("app.agents.services.component_builder", "component_builder_node"),
    "enforce_component_contract": ("app.agents.services.component_builder", "enforce_component_contract"),
    "composition_service": ("app.agents.services.composition_service", "composition_service"),
    "research_service": ("app.agents.services.research_service", "research_service"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
