from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "AI_Frontend_IDE" / "app"
TEST_ROOT = ROOT / "tests"
FRONTEND_COMPONENTS_ROOT = ROOT / "ai-frontend-ide" / "src" / "components"
FRONTEND_STORE_PATH = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"
FRONTEND_PREVIEW_PATH = ROOT / "ai-frontend-ide" / "src" / "components" / "canvas" / "PreviewIframe.vue"


def _scan_text_files(base: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return [path for path in base.rglob("*") if path.is_file() and path.suffix in suffixes]


def test_formal_runtime_codebase_contains_no_create_react_agent_references():
    forbidden_tokens = ("create_react_agent", "langgraph_create_react_agent")
    offenders: list[str] = []
    for base in (APP_ROOT, TEST_ROOT):
        for path in _scan_text_files(base, (".py", ".ts", ".vue", ".md")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden_tokens):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"Formal product path regressed to legacy react agent references: {offenders}"


def test_frontend_components_do_not_directly_depend_on_legacy_page_or_style_state():
    forbidden_tokens = ("pageData", "styleData")
    offenders: list[str] = []
    for path in _scan_text_files(FRONTEND_COMPONENTS_ROOT, (".vue", ".ts")):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden_tokens):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"Frontend components should consume NoteDocument/store-derived state instead of legacy pageData/styleData: {offenders}"


def test_store_public_api_no_longer_exposes_legacy_page_or_style_cache():
    text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    forbidden_patterns = (
        r"^\s*pageData,\s*$",
        r"^\s*styleData,\s*$",
        r"^\s*legacyPageCache,\s*$",
        r"^\s*legacyStyleCache,\s*$",
    )
    offenders = [pattern for pattern in forbidden_patterns if re.search(pattern, text, flags=re.MULTILINE)]
    assert offenders == [], f"Store public API should not expose legacy page/style cache: {offenders}"


def test_store_contains_no_legacy_page_or_style_cache_state():
    text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    assert "legacyPageCache" not in text
    assert "legacyStyleCache" not in text


def test_frontend_ws_types_no_longer_expose_legacy_page_or_style_aliases():
    path = ROOT / "ai-frontend-ide" / "src" / "types" / "chat.ts"
    text = path.read_text(encoding="utf-8")
    assert "pageData?:" not in text
    assert "styleData?:" not in text


def test_frontend_note_document_types_stay_first_class():
    path = ROOT / "ai-frontend-ide" / "src" / "types" / "chat.ts"
    text = path.read_text(encoding="utf-8")
    assert "export interface NoteDocument " in text
    assert "export interface PlannerOutput " in text
    assert "export interface PlannerPolicy " in text
    assert "export interface TurnTrace " in text
    assert "export interface InspectorSummary " in text
    assert "noteDocument?: NoteDocument" in text
    assert "note_document?: NoteDocument" in text
    assert "plannerOutput?: PlannerOutput" in text
    assert "planner_policy?: PlannerPolicy" in text
    assert "turnTrace?: TurnTrace" in text
    assert "inspectorSummary?: InspectorSummary" in text
    assert "noteDocument?: Record<string, unknown>" not in text


def test_frontend_store_workspace_snapshot_no_longer_reads_legacy_page_or_style_aliases():
    text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    assert "data.pageData" not in text
    assert "data.styleData" not in text
    assert "currentPage.page_title" not in text


def test_preview_iframe_avoids_legacy_any_fallback_for_note_document_and_prompt_messages():
    text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")
    assert "(noteDocument.value as Record<string, any>)" not in text
    assert "Array<Record<string, any>>" not in text


def test_agent_inspector_avoids_agent_meta_any_shortcuts():
    path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "AgentInspector.vue"
    text = path.read_text(encoding="utf-8")
    assert "chatStore.agentMeta as any" not in text
    assert "retrieved_knowledge as any" not in text


def test_workspace_title_extraction_no_longer_reads_legacy_page_title():
    path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"
    text = path.read_text(encoding="utf-8")
    assert 'get("page_title")' not in text


def test_workspace_response_schema_no_longer_exposes_legacy_page_or_style_fields():
    path = ROOT / "AI_Frontend_IDE" / "app" / "schemas" / "responses.py"
    text = path.read_text(encoding="utf-8")
    assert "document_view:" not in text
    assert "block_style_map:" not in text


def test_formal_turn_end_payload_no_longer_contains_note_data_alias():
    chat_api_path = APP_ROOT / "api" / "chat.py"
    text = chat_api_path.read_text(encoding="utf-8")
    assert '"noteData"' not in text, "turn_end payload should not keep the obsolete noteData alias"
    assert '"pageData"' not in text, "turn_end payload should not keep the obsolete pageData alias"
    assert '"styleData"' not in text, "turn_end payload should not keep the obsolete styleData alias"


def test_formal_graph_no_longer_contains_outline_react_tool_loop():
    graph_path = APP_ROOT / "agents" / "graph.py"
    text = graph_path.read_text(encoding="utf-8")
    forbidden = (
        'workflow.add_node("outline_node"',
        'workflow.add_node("outline_tools"',
        'workflow.add_edge("outline_tools", "outline_node")',
        'should_continue_outlining',
        'OUTLINE_TOOLS',
    )
    offenders = [token for token in forbidden if token in text]
    assert offenders == [], f"Formal graph regressed to outline ReAct loop: {offenders}"


def test_primary_execution_nodes_do_not_directly_read_legacy_dsl_state():
    targets = [
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "graph.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "intent_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "structure_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "planner_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "style_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "render_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "note_editor_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "verify_note_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "patch_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "enrichment_agent.py",
        ROOT / "AI_Frontend_IDE" / "app" / "tools" / "note_tools.py",
        ROOT / "AI_Frontend_IDE" / "app" / "tools" / "patch_tools.py",
        ROOT / "AI_Frontend_IDE" / "app" / "tools" / "canvas_tools.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "utils" / "observation_dashboard.py",
    ]
    forbidden = (
        'state.get("' + "data" + "_" + 'dsl"',
        "state.get('" + "data" + "_" + "dsl'",
        'state.get("' + "style" + "_" + 'dsl"',
        "state.get('" + "style" + "_" + "dsl'",
        'state.get("' + "runtime" + "_" + 'view"',
        "state.get('" + "runtime" + "_" + "view'",
        'state.get("' + "runtime" + "_" + 'styles"',
        "state.get('" + "runtime" + "_" + "styles'",
    )
    offenders: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        bad = [token for token in forbidden if token in text]
        if bad:
            offenders.append(f"{path.relative_to(ROOT)}: {bad}")
    assert offenders == [], f"Primary execution nodes regressed to direct legacy DSL reads: {offenders}"


def test_app_runtime_no_longer_contains_legacy_dsl_field_names():
    offenders: list[str] = []
    for path in _scan_text_files(APP_ROOT, (".py", ".xml")):
        text = path.read_text(encoding="utf-8")
        if (
            ("data" + "_" + "dsl") in text
            or ("style" + "_" + "dsl") in text
            or ("runtime" + "_" + "view") in text
            or ("runtime" + "_" + "styles") in text
        ):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"App runtime should no longer contain legacy DSL field names: {offenders}"

def test_outline_node_module_no_longer_contains_react_tool_loop_implementation():
    outline_path = APP_ROOT / "agents" / "nodes" / "outline_node.py"
    text = outline_path.read_text(encoding="utf-8")
    forbidden = ("OUTLINE_TOOLS", ".bind_tools(", "ReAct")
    offenders = [token for token in forbidden if token in text]
    assert offenders == [], f"outline_node module regressed to legacy ReAct implementation: {offenders}"


def test_modern_runtime_nodes_do_not_regress_to_legacy_theme_or_asset_signals():
    targets = {
        "AI_Frontend_IDE/app/agents/nodes/style_node.py": ("visual_vibe", "intensity_level"),
        "AI_Frontend_IDE/app/agents/nodes/note_editor_node.py": ("visual_vibe",),
        "AI_Frontend_IDE/app/agents/nodes/research_agent.py": ("asset_request",),
    }
    offenders: list[str] = []
    for relative_path, forbidden_tokens in targets.items():
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        bad = [token for token in forbidden_tokens if token in text]
        if bad:
            offenders.append(f"{relative_path}: {bad}")
    assert offenders == [], f"Modern runtime nodes regressed to legacy gateway/theme signals: {offenders}"


def test_formal_runtime_no_longer_contains_legacy_intent_schema_or_prompt():
    forbidden_paths = [
        ROOT / "AI_Frontend_IDE" / "app" / "prompts" / "intent_system.xml",
    ]
    existing = [str(path.relative_to(ROOT)) for path in forbidden_paths if path.exists()]
    assert existing == [], f"Legacy intent prompt should stay deleted: {existing}"

    targets = {
        "AI_Frontend_IDE/app/agents/nodes/intent_node.py": (r"\bIntentOutput\b", r"\bintent_result\b(?!_v2)"),
        "AI_Frontend_IDE/app/agents/state.py": (r"\bIntentOutput\b", r"\bintent_result\b(?!_v2)"),
        "AI_Frontend_IDE/app/agents/nodes/refusal_node.py": (r"\bintent_result\b(?!_v2)",),
        "AI_Frontend_IDE/app/core/persistence.py": (r"\bIntentOutput\b",),
    }
    offenders: list[str] = []
    for relative_path, patterns in targets.items():
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        bad = [pattern for pattern in patterns if re.search(pattern, text)]
        if bad:
            offenders.append(f"{relative_path}: {bad}")
    assert offenders == [], f"Formal runtime regressed to legacy intent compatibility: {offenders}"
