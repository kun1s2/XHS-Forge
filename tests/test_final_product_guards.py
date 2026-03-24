from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "AI_Frontend_IDE" / "app"
TEST_ROOT = ROOT / "tests"
FRONTEND_COMPONENTS_ROOT = ROOT / "ai-frontend-ide" / "src" / "components"
FRONTEND_STORE_PATH = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"
FRONTEND_PREVIEW_PATH = ROOT / "ai-frontend-ide" / "src" / "components" / "canvas" / "PreviewIframe.vue"
FRONTEND_TYPES_PATH = ROOT / "ai-frontend-ide" / "src" / "types" / "chat.ts"


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
    text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    assert "pageData?:" not in text
    assert "styleData?:" not in text


def test_frontend_note_document_types_stay_first_class():
    text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    assert "export interface NoteDocument " in text
    assert "export interface PlannerOutput " in text
    assert "export interface PlannerPolicy " in text
    assert "export interface TurnTrace " in text
    assert "export interface InspectorSummary " in text
    assert "export interface BenchmarkOverview " in text
    assert "export interface EvaluationOverview " in text
    assert "noteDocument?: NoteDocument" in text
    assert "note_document?: NoteDocument" in text
    assert "plannerOutput?: PlannerOutput" in text
    assert "planner_policy?: PlannerPolicy" in text
    assert "turnTrace?: TurnTrace" in text
    assert "inspectorSummary?: InspectorSummary" in text
    assert "benchmarkOverview?: BenchmarkOverview" in text
    assert "evaluationOverview?: EvaluationOverview" in text
    assert "noteDocument?: Record<string, unknown>" not in text


def test_formal_product_preview_no_longer_exposes_block_gallery_as_mainline_workspace_tab():
    preview_text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")
    assert "积木大全" not in preview_text
    assert "BlockGalleryPanel" not in preview_text


def test_formal_product_preview_keeps_selection_capability_inside_real_preview_shell_only():
    renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "XForgeRenderer.vue"
    dynamic_renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "DynamicRenderer.vue"

    renderer_text = renderer_path.read_text(encoding="utf-8")
    dynamic_renderer_text = dynamic_renderer_path.read_text(encoding="utf-8")

    assert "interactive?: boolean;" in renderer_text
    assert "const isInteractive = computed(() => props.interactive !== false);" in renderer_text
    assert ':interactive="true"' in dynamic_renderer_text


def test_preview_exposes_explicit_select_mode_and_renderer_uses_selection_overlay():
    renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "XForgeRenderer.vue"
    dynamic_renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "DynamicRenderer.vue"

    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    preview_text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")
    types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    renderer_text = renderer_path.read_text(encoding="utf-8")
    dynamic_renderer_text = dynamic_renderer_path.read_text(encoding="utf-8")

    assert "export type PreviewInteractionMode = 'browse' | 'select'" in types_text
    assert "const previewInteractionMode = ref<PreviewInteractionMode>('browse')" in store_text
    assert "const setPreviewInteractionMode = (mode: PreviewInteractionMode)" in store_text
    assert "开启选择模式" in preview_text
    assert "退出选择模式" in preview_text
    assert "当前点击积木会直接选中并高亮" in preview_text
    assert "当前是浏览模式，组件原生交互优先" in preview_text
    assert "selectionEnabled?: boolean;" in renderer_text
    assert "recentlyChanged?: boolean;" in renderer_text
    assert "data-selection-overlay" in renderer_text
    assert "点击选择" in renderer_text
    assert "已选中" in renderer_text
    assert "刚刚修改" in renderer_text
    assert ':selection-enabled="previewInteractionMode === \'select\'"' in dynamic_renderer_text
    assert ':recently-changed="recentlyChangedBlockIds.includes(block.id)"' in dynamic_renderer_text
    assert ':recent-change="recentlyChangedBlockDetails[block.id] || null"' in dynamic_renderer_text
    assert "const recentlyChangedBlockIds = computed(() => getRecentlyChangedBlockIds(turnTrace.value))" in store_text
    assert "const recentlyChangedBlockDetails = ref<Record<string, { fields: string[]; paragraph_indices?: number[]; item_indices?: number[] }>>({})" in store_text
    assert "recentlyChangedBlockDetails.value = buildRecentlyChangedBlockDetails(previousNoteDocument, nextNoteDocument, nextTurnTrace)" in store_text


def test_recent_change_local_highlight_is_wired_into_high_frequency_blocks():
    block_root = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks"

    story_text = (block_root / "StoryText.vue").read_text(encoding="utf-8")
    poll_text = (block_root / "PollBlock.vue").read_text(encoding="utf-8")
    versus_text = (block_root / "VersusCard.vue").read_text(encoding="utf-8")
    spec_text = (block_root / "ProductSpecCard.vue").read_text(encoding="utf-8")
    cover_text = (block_root / "CoverSwiper.vue").read_text(encoding="utf-8")

    assert "recentChange?: { fields?: string[]; paragraph_indices?: number[] } | null" in story_text
    assert "changedParagraphIndices" in story_text

    assert "recentChange?: { fields?: string[] } | null" in poll_text
    assert "highlightBoxStyle(recentFields.has('question'))" in poll_text
    assert "highlightBoxStyle(recentFields.has('options'))" in poll_text

    assert "recentChange?: { fields?: string[] } | null" in versus_text
    assert "localHighlightStyle(recentFields.has('pros'))" in versus_text
    assert "localHighlightStyle(recentFields.has('cons'))" in versus_text
    assert "localHighlightStyle(recentFields.has('decision'))" in versus_text

    assert "recentChange?: { fields?: string[]; item_indices?: number[] } | null" in spec_text
    assert "changedItemIndices" in spec_text

    assert "recentChange?: { fields?: string[] } | null" in cover_text
    assert "localHighlightStyle(recentFields.has('images'))" in cover_text


def test_runtime_note_blocks_no_longer_render_developer_guidance_copy_inside_user_content():
    block_root = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks"
    target_files = (
        "CoverSwiper.vue",
        "VersusCard.vue",
        "PollBlock.vue",
        "ProductSpecCard.vue",
        "StoryText.vue",
    )
    forbidden_tokens = (
        "QUICK REFINE",
        "Usage Note",
        "COMPARISON READING",
        "BALANCE SIGNAL",
        "READING POSTURE",
        "DECISION SIGNAL",
        "RISK NOTE",
        "Interaction Mood",
        "Current Split",
        "Opinion Clash",
        "Story Rhythm",
        "Hero Media",
        "Current Frame",
        "Narrative Flow",
        "Cover Story",
        "Source Signal",
        "Decision Impact",
    )

    offenders: list[str] = []
    for filename in target_files:
        text = (block_root / filename).read_text(encoding="utf-8")
        hit_tokens = [token for token in forbidden_tokens if token in text]
        if hit_tokens:
            offenders.append(f"{filename}: {hit_tokens}")
    assert offenders == [], f"Runtime note blocks should not render developer guidance copy inside user-facing content: {offenders}"


def test_fact_binding_support_blocks_render_shared_grounding_footer():
    block_root = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks"
    fact_binding_blocks = (
        "StoryText.vue",
        "ProductSpecCard.vue",
        "RadarChartBlock.vue",
        "VersusCard.vue",
        "LocationBlock.vue",
        "QuoteBlock.vue",
        "TimelineBlock.vue",
    )

    footer_text = (block_root / "FactBindingFooter.vue").read_text(encoding="utf-8")
    assert "来源" in footer_text
    assert "证据条数" in footer_text
    assert ":href=\"source.url || undefined\"" in footer_text

    for filename in fact_binding_blocks:
        text = (block_root / filename).read_text(encoding="utf-8")
        assert "FactBindingFooter" in text, f"{filename} should expose block-level grounding footer"
        assert '<FactBindingFooter :node="node" />' in text, f"{filename} should render unified grounding footer"


def test_radar_and_product_spec_guidance_match_real_contract_slots():
    manifest_text = (ROOT / "ai-frontend-ide" / "src" / "config" / "componentManifest.json").read_text(encoding="utf-8")
    guidance_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "chatEditingGuidance.ts").read_text(encoding="utf-8")
    support_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "note_editor_support.py").read_text(encoding="utf-8")
    schema_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "schema.py").read_text(encoding="utf-8")

    assert '"type": "RadarChartBlock"' in manifest_text
    assert '"editable_targets": ["title", "dimensions", "scores", "metrics"]' in manifest_text
    assert '"type": "ProductSpecCard"' in manifest_text
    assert '"editable_targets": ["core_features", "spec_items", "feature_meta"]' in manifest_text

    assert "metrics: Optional[List[Dict[str, Any]]]" in schema_text
    assert "feature_meta: Optional[List[Dict[str, Any]]]" in schema_text
    assert "spec_items: Optional[List[Dict[str, Any]]]" in schema_text

    assert '"metrics": ["结论摘要", "雷达总结", "维度理由", "判断说明"]' in support_text
    assert '"spec_items": ["参数标题", "参数表达", "参数项", "参数卡", "规格项"]' in support_text
    assert '"feature_meta": ["边界提醒", "确认提醒", "保守表达", "参数提醒"]' in support_text

    assert "只改这个雷达图的结论摘要，维度和分数不动。" in guidance_text
    assert "只改这个参数卡每条参数的表达方式，不动事实值。" in guidance_text


def test_structure_prompt_uses_current_travel_and_seeding_block_contracts():
    structure_prompt_text = (ROOT / "AI_Frontend_IDE" / "app" / "prompts" / "structure_system.xml").read_text(encoding="utf-8")

    assert "ProductCard(置顶)" not in structure_prompt_text
    assert "InteractionsBar" not in structure_prompt_text
    assert "TagList" not in structure_prompt_text
    assert "模拟真实打卡" not in structure_prompt_text
    assert "很像现场感受的旅行金句" not in structure_prompt_text
    assert "candidate_components 是候选容器" in structure_prompt_text
    assert "不要为了用积木而用积木" in structure_prompt_text
    assert "[travel 旅行副场景]: 优先考虑 CoverSwiper, TitleBlock, LocationBlock, TimelineBlock, StoryText, QuoteBlock 作为候选容器。" in structure_prompt_text
    assert "[seeding 数码测评]: 优先考虑 CoverSwiper, TitleBlock, ProductSpecCard, VersusCard, PollBlock, StoryText 作为候选容器。" in structure_prompt_text
    assert "允许先退回 StoryText" in structure_prompt_text


def test_planner_and_frontend_types_expose_semantic_first_candidate_components():
    planner_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "planner_node.py").read_text(encoding="utf-8")
    schema_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "schema.py").read_text(encoding="utf-8")
    frontend_types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")

    assert '"candidate_components": candidate_components' in planner_text
    assert '"selection_mode": "flexible"' in planner_text or '"selection_mode": "anchored"' in planner_text
    assert "candidate_components: List[str]" in schema_text
    assert "selection_mode: str = \"anchored\"" in schema_text
    assert "candidate_components?: string[]" in frontend_types_text
    assert "selection_mode?: 'anchored' | 'flexible' | string" in frontend_types_text


def test_high_risk_block_fallbacks_no_longer_invent_fake_weather_or_fake_year_timestamps():
    builder_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "component_builder.py").read_text(encoding="utf-8")
    timeline_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "TimelineBlock.vue").read_text(encoding="utf-8")
    weather_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "WeatherPolaroid.vue").read_text(encoding="utf-8")

    assert '"weather": "晴"' not in builder_text
    assert '"temperature": "24C"' not in builder_text
    assert '"time": "今日"' not in builder_text
    assert '"2023"' not in timeline_text
    assert '"2024"' not in timeline_text
    assert "场景氛围卡" in weather_text


def test_visual_fixtures_and_block_gallery_use_local_demo_assets_for_media_examples():
    visual_fixtures_path = ROOT / "ai-frontend-ide" / "src" / "visualFixtures.ts"
    block_gallery_path = ROOT / "AI_Frontend_IDE" / "app" / "services" / "block_gallery.py"

    visual_text = visual_fixtures_path.read_text(encoding="utf-8")
    gallery_text = block_gallery_path.read_text(encoding="utf-8")

    assert "/demo-assets/" in visual_text
    assert "/demo-assets/" in gallery_text


def test_frontend_observer_ignores_browser_extension_runtime_errors():
    observer_text = (ROOT / "ai-frontend-ide" / "src" / "utils" / "frontendObserver.ts").read_text(encoding="utf-8")
    assert "chrome-extension://" in observer_text
    assert "moz-extension://" in observer_text


def test_note_editor_streaming_output_does_not_append_structured_json_into_user_visible_reply():
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    assert "sourceNode === 'note_editor'" in store_text
    assert "最终用户可见文案统一在 turn_end 时用结果摘要收口" in store_text
    assert "['direct_chat_node', 'rag_node'].includes(sourceNode)" in store_text


def test_frontend_store_workspace_snapshot_no_longer_reads_legacy_page_or_style_aliases():
    text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    assert "data.pageData" not in text
    assert "data.styleData" not in text
    assert "currentPage.page_title" not in text


def test_preview_iframe_avoids_legacy_any_fallback_for_note_document_and_prompt_messages():
    text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")
    assert "(noteDocument.value as Record<string, any>)" not in text
    assert "Array<Record<string, any>>" not in text


def test_preview_shell_no_longer_forces_420px_narrow_mobile_canvas():
    dynamic_renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "DynamicRenderer.vue"
    html_renderer_path = ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "document_renderer_node.py"

    dynamic_renderer_text = dynamic_renderer_path.read_text(encoding="utf-8")
    html_renderer_text = html_renderer_path.read_text(encoding="utf-8")

    assert "max-w-[420px]" not in dynamic_renderer_text
    assert "max-width: 420px" not in dynamic_renderer_text
    assert "max-width: 420px" not in html_renderer_text


def test_weather_polaroid_no_longer_uses_random_scenery_placeholder():
    path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "WeatherPolaroid.vue"
    text = path.read_text(encoding="utf-8")
    assert "picsum.photos" not in text
    assert "Somewhere in the world" not in text


def test_visual_regression_lab_restores_page_scrolling():
    path = ROOT / "ai-frontend-ide" / "src" / "components" / "visual" / "VisualRegressionLab.vue"
    text = path.read_text(encoding="utf-8")
    assert "element.style.overflow = 'auto'" in text
    assert "element.style.height = 'auto'" in text
    assert "element.style.minHeight = '100vh'" in text


def test_agent_inspector_avoids_agent_meta_any_shortcuts():
    path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "AgentInspector.vue"
    text = path.read_text(encoding="utf-8")
    assert "chatStore.agentMeta as any" not in text
    assert "retrieved_knowledge as any" not in text


def test_chat_panel_keeps_editor_guidance_in_workbench_not_embedded_inspector():
    path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue"
    text = path.read_text(encoding="utf-8")
    assert "AgentInspector" not in text
    assert "编辑助手" in text
    assert "创作对话" in text
    assert "interactionMode === 'edit' && selectedComponentId" in text


def test_workbench_mode_is_store_driven_and_preview_panel_no_longer_owns_local_view_mode():
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    preview_text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")

    assert "const workspaceMode = ref<WorkspaceViewMode>('preview')" in store_text
    assert "const interactionMode = computed<WorkbenchInteractionMode>" in store_text
    assert "const setWorkspaceMode = (mode: WorkspaceViewMode)" in store_text
    assert "const viewMode = ref<" not in preview_text
    assert "workspaceMode === 'preview'" in preview_text
    assert "@click=\"setWorkspaceMode('preview')\"" in preview_text


def test_retrieval_gap_fill_is_registered_as_formal_block_aware_followup_search_step():
    graph_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "graph.py").read_text(encoding="utf-8")
    retrieval_profile_text = (ROOT / "AI_Frontend_IDE" / "app" / "services" / "retrieval_profiles.py").read_text(encoding="utf-8")
    gap_fill_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "retrieval_gap_fill_node.py").read_text(encoding="utf-8")
    context_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "context_engineering.py").read_text(encoding="utf-8")

    assert 'workflow.add_node("retrieval_gap_fill"' in graph_text
    assert 'workflow.add_edge("structure_checkpoint", "retrieval_gap_fill")' in graph_text
    assert (
        'workflow.add_edge("retrieval_gap_fill", "fact_gap_checkpoint")' in graph_text
        or (
            'workflow.add_edge("retrieval_gap_fill", "knowledge_review_checkpoint")' in graph_text
            and 'workflow.add_edge("knowledge_review_checkpoint", "fact_gap_checkpoint")' in graph_text
        )
    )
    assert "get_component_required_slot_keys" in retrieval_profile_text
    assert "critical_slot_keys" in retrieval_profile_text
    assert "missing_slot_keys" in gap_fill_text
    assert "critical_missing_fields" in gap_fill_text
    assert "retrieval_gap_fill_with_limit" in gap_fill_text
    assert "build_followup_query_variants" in gap_fill_text
    assert '"fact_slots"' in context_text
    assert '"missing_fields"' in context_text


def test_conversational_checkpoints_are_registered_in_graph_and_chat_panel():
    graph_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "graph.py").read_text(encoding="utf-8")
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    chat_panel_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue").read_text(encoding="utf-8")
    chat_types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    chat_api_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "chat.py").read_text(encoding="utf-8")

    for token in (
        '"structure_checkpoint"',
        '"fact_gap_checkpoint"',
        '"asset_checkpoint"',
        '"fact_conflict_checkpoint"',
        '"truth_mode_checkpoint"',
    ):
        assert token in graph_text

    assert 'workflow.add_edge("planner", "truth_mode_checkpoint")' in graph_text
    assert 'workflow.add_conditional_edges("truth_mode_checkpoint", _after_truth_mode_checkpoint' in graph_text
    assert 'workflow.add_edge("fact_gap_checkpoint", "asset_checkpoint")' in graph_text
    assert 'workflow.add_edge("asset_checkpoint", "fact_conflict_checkpoint")' in graph_text
    assert 'workflow.add_edge("fact_conflict_checkpoint", "outline_resolver")' in graph_text
    assert "export interface ConversationCheckpointAction " in chat_types_text
    assert "actionRequired?: ConversationCheckpointAction" in chat_types_text
    assert "submitCheckpointDecision" in store_text
    assert "ConversationCheckpointCard" in chat_panel_text
    assert "submit_checkpoint_decision" in chat_api_text
    assert "input_schema" in chat_api_text
    assert "input_schema" in chat_types_text
    assert "按这些真实信息继续" in (ROOT / "AI_Frontend_IDE" / "app" / "services" / "conversational_checkpoints.py").read_text(encoding="utf-8")


def test_graph_interrupt_checkpoints_are_not_logged_as_failures_by_performance_wrapper():
    graph_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "graph.py").read_text(encoding="utf-8")
    assert "from langgraph.errors import GraphInterrupt" in graph_text
    assert 'except GraphInterrupt:' in graph_text
    assert "等待用户确认" in graph_text


def test_critique_agent_runs_as_final_quality_review_and_is_visible_in_chat():
    graph_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "graph.py").read_text(encoding="utf-8")
    chat_api_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "chat.py").read_text(encoding="utf-8")
    chat_panel_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue").read_text(encoding="utf-8")
    chat_types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")

    assert 'workflow.add_edge("verify_note", "theme_compiler")' in graph_text
    assert 'workflow.add_edge("document_renderer", "critique")' in graph_text
    assert 'workflow.add_edge("critique", END)' in graph_text
    assert '"critique": critique_summary' in chat_api_text
    assert "Agent 复盘" in chat_panel_text
    assert "turnTrace" in chat_panel_text and "critique" in chat_panel_text
    assert "critique?:" in chat_types_text
    assert '"action_recipes": [' in chat_api_text
    assert "下一步怎么做" in chat_panel_text
    assert "runCritiqueAction" in store_text
    assert "critique_action" in chat_types_text
    assert "why_now" in chat_types_text
    assert "expected_effect" in chat_types_text
    assert "现在优先处理" in chat_panel_text
    assert "预计效果" in chat_panel_text


def test_primary_user_path_no_longer_points_people_to_right_side_for_next_steps():
    derivation_text = (ROOT / "ai-frontend-ide" / "src" / "stores" / "chatStoreDerivations.ts").read_text(encoding="utf-8")
    diagnostics_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace_diagnostics.py").read_text(encoding="utf-8")

    assert "建议在右侧 Agent 状态中确认" not in derivation_text
    assert "先在右侧确认冲突值" not in diagnostics_text
    assert "继续在聊天区确认或修正" in derivation_text
    assert "先在聊天区继续确认或改写成更保守表达" in diagnostics_text


def test_agent_narrative_layer_is_visible_in_chat_flow():
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    chat_panel_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue").read_text(encoding="utf-8")
    chat_types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")
    chat_api_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "chat.py").read_text(encoding="utf-8")

    assert "agent_plan" in chat_types_text
    assert "agent_status" in chat_types_text
    assert "agent_receipt" in chat_types_text
    assert "agent_summary" in chat_types_text
    assert "buildAgentPlanCard" in store_text
    assert "buildAgentStatusCard" in store_text
    assert "buildAgentSummaryCard" in store_text
    assert "buildCheckpointReceiptCard" in store_text
    assert "Agent 计划" in chat_panel_text
    assert "Agent 进度" in chat_panel_text
    assert "Agent 接单" in chat_panel_text
    assert "Agent 小结" in chat_panel_text
    assert '"agent_plan": _build_agent_plan' in chat_api_text
    assert '"agent_summary": _build_agent_summary' in chat_api_text


def test_checkpoint_cards_are_rendered_as_agent_proposals_with_other_input():
    card_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ConversationCheckpointCard.vue").read_text(encoding="utf-8")
    checkpoint_text = (ROOT / "AI_Frontend_IDE" / "app" / "services" / "conversational_checkpoints.py").read_text(encoding="utf-8")
    assert "推荐原因：" in card_text
    assert "其他补充" in card_text
    assert "proposal_summary" in checkpoint_text
    assert "recommended_reason" in checkpoint_text
    assert "other_allowed" in checkpoint_text


def test_content_and_block_language_is_no_longer_defaulting_to_over_marketing_or_fake_checkin_copy():
    content_prompt_text = (ROOT / "AI_Frontend_IDE" / "app" / "prompts" / "content_system.xml").read_text(encoding="utf-8")
    block_registry_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "block_registry.py").read_text(encoding="utf-8")
    spec_card_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "ProductSpecCard.vue").read_text(encoding="utf-8")
    radar_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "RadarChartBlock.vue").read_text(encoding="utf-8")

    assert "多用感叹号和生动的 Emoji" not in content_prompt_text
    assert "结尾一定要带上几个相关的 #话题标签" not in content_prompt_text
    assert "地图打卡卡" not in block_registry_text
    assert "带时间天气水印的图片，增强现场感" not in block_registry_text
    assert "值不值得买，先看这几条" in spec_card_text
    assert "重点维度对比" in radar_text
    assert "维度对比" in radar_text


def test_asset_checkpoint_deduplicates_assets_by_url_and_uses_distinguishable_labels():
    checkpoint_text = (ROOT / "AI_Frontend_IDE" / "app" / "services" / "conversational_checkpoints.py").read_text(encoding="utf-8")
    checkpoint_card_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ConversationCheckpointCard.vue").read_text(encoding="utf-8")
    assert "seen_asset_urls" in checkpoint_text
    assert "_asset_checkpoint_label" in checkpoint_text
    assert "第{position}张" in checkpoint_text
    assert 'v-if="option.asset_url"' in checkpoint_card_text
    assert '<img :src="option.asset_url"' in checkpoint_card_text


def test_history_actions_live_under_user_messages_and_use_formal_thread_rollback_and_fork():
    chat_panel_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue").read_text(encoding="utf-8")
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    workspace_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py").read_text(encoding="utf-8")
    state_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "state.py").read_text(encoding="utf-8")

    assert "回到这里" in chat_panel_text
    assert "从这里分支" in chat_panel_text
    assert "撤销最近回滚" in chat_panel_text
    assert "回退到此版本" not in chat_panel_text
    assert "branchFromCheckpoint" in store_text
    assert "rollbackUndoTarget" in store_text
    assert "undoLastRollback" in store_text
    assert 'fetch(`${baseUrl}/workspace/${threadId.value}/rollback`' in store_text
    assert 'fetch(`${baseUrl}/workspace/fork`' in store_text
    assert "已回到这条消息对应的历史状态。" not in store_text
    assert "已从这条消息创建一个新分支会话。" not in store_text
    assert '@router.post("/{thread_id}/rollback"' in workspace_text
    assert "turn_anchors:" in state_text


def test_story_and_spec_blocks_expose_field_level_sources_inside_user_reading_flow():
    story_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "StoryText.vue").read_text(encoding="utf-8")
    spec_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "ProductSpecCard.vue").read_text(encoding="utf-8")
    drilldown_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "SourceDrilldownPanel.vue").read_text(encoding="utf-8")
    note_document_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "note_document.py").read_text(encoding="utf-8")

    assert "SourceDrilldownPanel" in story_text
    assert "查看段落依据" in story_text
    assert "SourceDrilldownPanel" in spec_text
    assert "查看参数依据" in spec_text
    assert "来源链接" in drilldown_text
    assert "绑定说明" in drilldown_text
    assert "_project_fact_bindings_into_props" in note_document_text
    assert '"source_items": deepcopy(meta.get("source_items") or [])' in note_document_text


def test_workspace_trends_endpoint_no_longer_uses_hardcoded_demo_fallback():
    path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"
    text = path.read_text(encoding="utf-8")
    forbidden_samples = (
        "索尼 A7C2",
        "赛博朋克风测评",
        "春天第一杯咖啡",
    )
    offenders = [sample for sample in forbidden_samples if sample in text]
    assert offenders == [], f"Hot trends endpoint should not hardcode demo fallback topics: {offenders}"


def test_cover_selection_no_longer_materializes_cover_swiper_before_agent_generation():
    workspace_path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"
    store_path = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"

    workspace_text = workspace_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")

    assert "将指定素材标记为封面偏好" in workspace_text
    assert 'cover_block = next((block for block in blocks if block.get("type") == "CoverSwiper"), None)' not in workspace_text
    assert '"type": "CoverSwiper"' not in workspace_text.split('async def set_workspace_cover_asset', 1)[1].split('async def confirm_workspace_fact', 1)[0]
    assert "docBlocks.unshift(docCoverBlock)" not in store_text
    assert "type: 'CoverSwiper'" not in store_text.split('const applyCoverAssetLocally =', 1)[1].split('const setAssetAsCover =', 1)[0]


def test_asset_deletion_and_upload_flows_are_formalized():
    workspace_path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"
    store_path = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"
    chat_panel_path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue"

    workspace_text = workspace_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")
    chat_panel_text = chat_panel_path.read_text(encoding="utf-8")

    assert '@router.delete("/{thread_id}/assets"' in workspace_text
    assert 'action="workspace_remove_asset"' in workspace_text
    assert "const deleteAssetFromLibrary = async" in store_text
    assert "method: 'DELETE'" in store_text
    assert "await chatStore.importAssetToLibrary({ url, desc: '用户上传图片', source_type: 'upload' })" in chat_panel_text


def test_asset_library_exposes_formal_usage_controls_and_backend_preferences_endpoint():
    asset_library_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "AssetLibrary.vue").read_text(encoding="utf-8")
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    workspace_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py").read_text(encoding="utf-8")

    assert "改成正文图" in asset_library_text
    assert "标记必用" in asset_library_text
    assert "暂不使用" in asset_library_text
    assert "const updateAssetPreferences = async" in store_text
    assert '@router.patch("/{thread_id}/assets/preferences"' in workspace_text
    assert "update_note_document_asset_preferences" in workspace_text


def test_chat_panel_hot_trends_no_longer_uses_one_size_fits_all_deep_seeding_prompt():
    chat_panel_path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue"
    trend_panel_path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "TrendPanel.vue"
    chat_panel_text = chat_panel_path.read_text(encoding="utf-8")
    trend_panel_text = trend_panel_path.read_text(encoding="utf-8")

    assert "帮我针对「${trend}」做一个深度种草笔记" not in trend_panel_text
    assert "trend.recommended_prompt" in trend_panel_text
    assert "chatStore.sendMessage(prompt)" in trend_panel_text
    assert "Hot Trends" not in chat_panel_text
    assert "hotTrends.length > 0" not in chat_panel_text


def test_formal_product_preview_no_longer_uses_trend_panel_as_primary_workspace_tab():
    preview_text = FRONTEND_PREVIEW_PATH.read_text(encoding="utf-8")
    types_text = FRONTEND_TYPES_PATH.read_text(encoding="utf-8")

    assert "@click=\"setWorkspaceMode('trends')\"" not in preview_text
    assert "workspaceMode === 'trends'" not in preview_text
    assert "TrendPanel" not in preview_text
    assert "'trends'" not in types_text


def test_component_builder_and_note_document_filter_placeholder_image_urls():
    builder_path = ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "component_builder.py"
    note_document_path = ROOT / "AI_Frontend_IDE" / "app" / "core" / "note_document.py"
    cache_service_path = ROOT / "AI_Frontend_IDE" / "app" / "services" / "cache_service.py"

    builder_text = builder_path.read_text(encoding="utf-8")
    note_document_text = note_document_path.read_text(encoding="utf-8")
    cache_service_text = cache_service_path.read_text(encoding="utf-8")

    assert "def _is_placeholder_image_url" in builder_text
    assert "def _sanitize_component_media_payload" in builder_text
    assert "example.com" in builder_text
    assert "picsum.photos" in builder_text
    assert "placeholder" in builder_text
    assert "not _is_placeholder_image_url(asset.get(\"url\"))" in builder_text

    assert "def _sanitize_block_media_props" in note_document_text
    assert "not _is_placeholder_image_url(item)" in note_document_text
    assert "not _is_placeholder_image_url(ref)" in note_document_text
    assert "_sanitize_cached_note_document" in cache_service_text
    assert "build_note_document_from_state({\"note_document\": raw})" in cache_service_text


def test_xforge_renderer_allows_child_interactions_without_losing_block_selection():
    renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "XForgeRenderer.vue"
    preview_path = ROOT / "ai-frontend-ide" / "src" / "components" / "canvas" / "PreviewIframe.vue"
    dynamic_renderer_path = ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "DynamicRenderer.vue"
    text = renderer_path.read_text(encoding="utf-8")
    preview_text = preview_path.read_text(encoding="utf-8")
    dynamic_renderer_text = dynamic_renderer_path.read_text(encoding="utf-8")

    assert "@click.capture" not in text
    assert "@click=\"handleSelect\"" in text
    assert "selectionEnabled?: boolean;" in text
    assert "data-selection-overlay" in text
    assert "点击选择" in text
    assert "已选中" in text
    assert "开启选择模式" in preview_text
    assert "退出选择模式" in preview_text
    assert ':selection-enabled="previewInteractionMode === \'select\'"' in dynamic_renderer_text


def test_poll_block_and_chat_panel_expose_real_interaction_feedback_and_precise_edit_actions():
    poll_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "PollBlock.vue").read_text(encoding="utf-8")
    chat_panel_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "ChatPanel.vue").read_text(encoding="utf-8")
    guidance_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "chatEditingGuidance.ts").read_text(encoding="utf-8")

    assert "投票结果" in poll_text
    assert "总投票" in poll_text
    assert "participationSummary" in poll_text
    assert "精准修改" in chat_panel_text
    assert "runSelectedDirectAction" in chat_panel_text
    assert "只改这个对比卡左侧的观点和细节" in guidance_text
    assert "只改这个投票块的问题句式" in guidance_text
    assert "只改这个封面轮播当前页的大标题" in guidance_text
    assert "只改这个封面轮播下方的摘要说明" in guidance_text


def test_cover_swiper_contract_and_guidance_allow_real_text_targeting_not_just_images():
    manifest_text = (ROOT / "ai-frontend-ide" / "src" / "config" / "componentManifest.json").read_text(encoding="utf-8")
    schema_text = (ROOT / "AI_Frontend_IDE" / "app" / "core" / "schema.py").read_text(encoding="utf-8")
    builder_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "component_builder.py").read_text(encoding="utf-8")
    guidance_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "chatEditingGuidance.ts").read_text(encoding="utf-8")
    support_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "note_editor_support.py").read_text(encoding="utf-8")

    assert '"type": "CoverSwiper"' in manifest_text
    assert '"deck_summary"' in manifest_text
    assert '"frame_headlines"' in manifest_text
    assert '"frame_captions"' in manifest_text
    assert 'deck_summary: Optional[str]' in schema_text
    assert 'frame_headlines: Optional[List[str]]' in schema_text
    assert 'frame_captions: Optional[List[str]]' in schema_text
    assert '"deck_summary": f"共 {max(len(image_urls[:5]), 1)} 张图' in builder_text
    assert '"frame_headlines": frame_headlines' in builder_text
    assert '"frame_captions": frame_captions' in builder_text
    assert '"deck_summary": ["摘要", "下方说明", "轮播说明", "整体说明", "底部说明"]' in support_text
    assert "只改这个封面轮播下方的摘要说明" in guidance_text


def test_benchmark_panel_is_exposed_in_frontend_and_workspace_api():
    inspector_path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "AgentInspector.vue"
    store_path = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"
    workspace_path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"

    inspector_text = inspector_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")
    workspace_text = workspace_path.read_text(encoding="utf-8")

    assert "Benchmark" in inspector_text
    assert "fetchBenchmarkOverview" in store_text
    assert '"/benchmark/overview"' in workspace_text


def test_evaluation_panel_is_exposed_in_frontend_and_workspace_api():
    inspector_path = ROOT / "ai-frontend-ide" / "src" / "components" / "chat" / "AgentInspector.vue"
    store_path = ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts"
    workspace_path = ROOT / "AI_Frontend_IDE" / "app" / "api" / "workspace.py"

    inspector_text = inspector_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")
    workspace_text = workspace_path.read_text(encoding="utf-8")

    assert "评估" in inspector_text
    assert "fetchEvaluationOverview" in store_text
    assert '"/evaluation/overview"' in workspace_text


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
        'continue_outline_resolution',
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
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "theme_compiler_node.py",
        ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "document_renderer_node.py",
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


def test_runtime_note_document_builder_no_longer_reads_legacy_layout_state():
    path = ROOT / "AI_Frontend_IDE" / "app" / "core" / "note_document.py"
    text = path.read_text(encoding="utf-8")
    assert 'state.get("document_view")' not in text
    assert "state.get('document_view')" not in text
    assert 'state.get("block_style_map")' not in text
    assert "state.get('block_style_map')" not in text

def test_outline_resolver_module_no_longer_contains_react_tool_loop_implementation():
    outline_path = APP_ROOT / "agents" / "nodes" / "outline_resolver_node.py"
    text = outline_path.read_text(encoding="utf-8")
    forbidden = ("OUTLINE_TOOLS", ".bind_tools(", "ReAct")
    offenders = [token for token in forbidden if token in text]
    assert offenders == [], f"outline_resolver module regressed to legacy ReAct implementation: {offenders}"


def test_modern_runtime_nodes_do_not_regress_to_legacy_theme_or_asset_signals():
    targets = {
        "AI_Frontend_IDE/app/agents/nodes/theme_compiler_node.py": ("visual_vibe", "intensity_level"),
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


def test_formal_runtime_uses_single_primary_text_llm_configuration():
    forbidden_tokens = (
        "LLM_SMALL_MODEL",
        "LLM_LOGIC_MODEL",
        "LLM_BRAIN_MODEL",
        "LLM_WORKER_MODEL",
    )
    offenders: list[str] = []
    for base in (APP_ROOT, TEST_ROOT):
        for path in _scan_text_files(base, (".py", ".md", ".xml")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            bad = [token for token in forbidden_tokens if token in text]
            if bad:
                offenders.append(f"{path.relative_to(ROOT)}: {bad}")
    config_text = (ROOT / "AI_Frontend_IDE" / ".env.example").read_text(encoding="utf-8")
    env_bad = [token for token in forbidden_tokens if token in config_text]
    if env_bad:
        offenders.append(f"AI_Frontend_IDE/.env.example: {env_bad}")
    assert offenders == [], f"Formal runtime should use a single primary text model configuration: {offenders}"


def test_trend_quick_send_uses_all_current_assets_as_runtime_image_context():
    store_text = FRONTEND_STORE_PATH.read_text(encoding="utf-8")
    chat_api_text = (ROOT / "AI_Frontend_IDE" / "app" / "api" / "chat.py").read_text(encoding="utf-8")

    assert "current_assets: assets" in store_text
    assert "image_urls: stagedImageUrls" in store_text
    assert "def _build_runtime_image_assets" in chat_api_text
    assert '"image_assets": _build_runtime_image_assets(payload)' in chat_api_text


def test_versus_card_uses_container_width_instead_of_viewport_breakpoints():
    text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "VersusCard.vue").read_text(encoding="utf-8")
    assert "ResizeObserver" in text
    assert "layoutMode.value = width >= 760 ? 'split' : 'stack'" in text
    assert "md:grid md:grid-cols-[minmax(0,1fr)_52px_minmax(0,1fr)]" not in text


def test_xforge_renderer_uses_container_measurement_instead_of_window_breakpoint_only():
    text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "XForgeRenderer.vue").read_text(encoding="utf-8")
    assert "const containerWidth = ref" in text
    assert "ResizeObserver" in text
    assert "getCurrentBreakpoint(containerWidth.value)" in text
    assert "const windowWidth = window.innerWidth;" not in text


def test_research_agent_and_profiles_support_missing_field_followup_search():
    profile_text = (ROOT / "AI_Frontend_IDE" / "app" / "services" / "retrieval_profiles.py").read_text(encoding="utf-8")
    research_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "nodes" / "research_agent.py").read_text(encoding="utf-8")

    assert "def compute_missing_slot_keys" in profile_text
    assert "def build_followup_query_variants" in profile_text
    assert "followup_queries" in profile_text
    assert "missing_fields_before_followup" in research_text
    assert "followup_search_used" in research_text
    assert "followup_query_variants" in research_text


def test_decision_blocks_keep_structured_rendering_paths():
    manifest_text = (ROOT / "ai-frontend-ide" / "src" / "config" / "componentManifest.json").read_text(encoding="utf-8")
    story_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "StoryText.vue").read_text(encoding="utf-8")
    spec_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "ProductSpecCard.vue").read_text(encoding="utf-8")
    radar_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "RadarChartBlock.vue").read_text(encoding="utf-8")
    poll_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "PollBlock.vue").read_text(encoding="utf-8")
    versus_text = (ROOT / "ai-frontend-ide" / "src" / "components" / "renderers" / "blocks" / "VersusCard.vue").read_text(encoding="utf-8")

    assert '"optional_props": ["paragraph_meta", "sections"]' in manifest_text
    assert '"optional_props": ["feature_meta", "spec_items"]' in manifest_text
    assert '"optional_props": ["title", "metrics"]' in manifest_text
    assert '"required_props": ["title", "pros", "cons"]' in manifest_text
    assert '"optional_props": ["decision_hint", "risk_note"]' in manifest_text
    assert '"optional_props": ["option_cards", "explanation"]' in manifest_text
    assert "props.data?.sections" in story_text
    assert "props.data?.spec_items" in spec_text
    assert "props.data.metrics" in radar_text
    assert "props.data.option_cards" in poll_text
    assert "props.data.decision_hint" in versus_text
