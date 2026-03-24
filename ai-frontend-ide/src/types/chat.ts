/** WS 协议与消息类型定义 */

export type WorkspaceArea = 'session' | 'global'
export type WorkspaceViewMode =
  | 'session_preview'
  | 'session_code'
  | 'session_prompts'
  | 'session_state'
  | 'session_knowledge'
  | 'global_assets'
  | 'global_gallery'
  | 'global_observability'
export type PreviewInteractionMode = 'browse' | 'select'
export type WorkbenchInteractionMode = 'browse' | 'select' | 'edit' | 'diagnostics'

export interface FactBinding {
  field: string
  fact_fields?: string[]
  fact_field_labels?: string[]
  kind?: string
  sources?: string[]
  source_items?: Array<{
    label: string
    url?: string
    source_scope?: string
  }>
  hint?: string
  confidence?: string
}

export type AssetSupportLevel = 'none' | 'optional' | 'required'

export interface NoteDocumentAsset {
  id?: string
  url: string
  desc?: string
  source_type?: string
  query?: string
  role?: 'cover' | 'inline' | 'supporting' | string
  locked?: boolean
  selection_state?: 'available' | 'excluded' | string
  source_reason?: string
  used_by_blocks?: string[]
}

export interface NoteDocumentBlock {
  id: string
  type: string
  label?: string
  semantic_role?: string
  content_brief?: string
  props?: Record<string, unknown>
  style?: Record<string, unknown>
  asset_refs?: string[]
  fact_bindings?: FactBinding[]
  editable_targets?: string[]
  asset_support?: AssetSupportLevel
  fact_binding_support?: boolean
  order?: number
}

export interface NoteDocument {
  document_meta?: Record<string, unknown> & {
    title?: string
    active_archetype?: string
    scenarios?: string[]
  }
  theme?: {
    page_theme?: Record<string, unknown>
    global_vars?: Record<string, unknown>
  }
  blocks?: NoteDocumentBlock[]
  assets?: NoteDocumentAsset[]
  fact_bindings?: Array<{
    block_id: string
    bindings: FactBinding[]
  }>
  provenance?: Record<string, unknown>
  ui_state?: Record<string, unknown> & {
    selected_element_id?: string | null
    active_panel?: string
    patch_tracks?: Record<string, unknown>
    cover_asset_url?: string | null
  }
  planner?: Record<string, unknown>
}

export interface PlannerIntent {
  block_id?: string
  block_index?: number
  intent?: string
  semantic_role?: string
  preferred_component?: string
  candidate_components?: string[]
  selection_mode?: 'anchored' | 'flexible' | string
  content_brief?: string
  [key: string]: unknown
}

export interface PlannerOutput {
  block_intents?: PlannerIntent[]
  scenario_scores?: Record<string, number>
  [key: string]: unknown
}

export interface PlannerPolicy {
  scenario_scores?: Record<string, number>
  theme_policy?: {
    preset?: string
    [key: string]: unknown
  }
  layout_policy?: {
    preferred_block_intents?: string[]
    [key: string]: unknown
  }
  [key: string]: unknown
}

export interface TurnTraceEvent {
  event?: string
  node?: string
  tool?: string
  [key: string]: unknown
}

export interface ExecutionTrace {
  action?: string
  target_block_id?: string
  block_id?: string
  structured?: boolean
  fallback_used?: boolean
  [key: string]: unknown
}

export interface ChangedBlockTrace {
  id?: string
  type?: string
  changed_fields?: string[]
  [key: string]: unknown
}

export interface BuilderSummary {
  component_count?: number
  fallback_count?: number
  contract_filter_count?: number
  precheck_warning_count?: number
  fact_summary_count?: number
  asset_count?: number
  prompt_modes?: string[]
  component_types?: string[]
  contract_first?: boolean
  [key: string]: unknown
}

export interface InspectorSummary {
  status?: string
  headline?: string
  focus?: Record<string, unknown>
  document?: Record<string, unknown>
  execution?: Record<string, unknown>
  builder?: BuilderSummary
  facts?: Record<string, unknown>
  retrieval?: Record<string, unknown>
  assets?: Record<string, unknown>
  suggestions?: string[]
  [key: string]: unknown
}

export interface BenchmarkOverview {
  generated_at?: string
  session_count?: number
  active_document_count?: number
  summary?: {
    avg_block_count?: number
    avg_asset_count?: number
    avg_changed_block_count?: number
    generated_session_rate?: number
    [key: string]: unknown
  }
  rag?: {
    session_count?: number
    grounded_session_count?: number
    avg_citation_count?: number
    avg_citation_coverage?: number
    avg_grounding_score?: number
    avg_record_count?: number
    avg_fresh_record_count?: number
    avg_stale_record_count?: number
    grounded_session_rate?: number
    [key: string]: unknown
  }
  cache?: {
    cache_hit_rate?: number
    live_search_rate?: number
    rerank_rate?: number
    fresh_cache_rate?: number
    expired_cache_rate?: number
    avg_cache_age_seconds?: number
    avg_remaining_ttl_seconds?: number
    [key: string]: unknown
  }
  execution?: {
    builder_component_total?: number
    builder_fallback_total?: number
    builder_fallback_rate?: number
    warning_session_count?: number
    warning_rate?: number
    [key: string]: unknown
  }
  distributions?: {
    scenarios?: Array<{ scenario: string; count: number }>
    components?: Array<{ component_type: string; count: number }>
    themes?: Array<{ theme_preset: string; count: number }>
    entities?: Array<{ entity_name: string; count: number }>
    [key: string]: unknown
  }
  sessions?: Array<{
    thread_id?: string
    title?: string
    updated_at?: string
    block_count?: number
    asset_count?: number
    scenario?: string
    theme_preset?: string
    entity_name?: string
    grounding_status?: string
    citation_count?: number
    cache_freshness?: string
    warning_count?: number
    [key: string]: unknown
  }>
  recommendations?: string[]
  [key: string]: unknown
}

export interface KnowledgeRecord {
  knowledge_id?: string
  record_id?: string
  document_id?: string
  chunk_id?: string
  entity_type?: string
  normalized_entity?: string
  field_or_topic?: string
  field_label?: string
  value?: string
  summary?: string
  source_type?: string
  source_scope?: string
  support_level?: string
  trust_level?: string
  knowledge_scope?: string
  review_status?: string
  recommended?: boolean
  source_title?: string
  snippet?: string
  evidence_locator?: Record<string, unknown>
  knowledge_version?: string
  used_by_blocks?: string[]
  [key: string]: unknown
}

export interface KnowledgeGroup {
  group_id?: string
  normalized_entity?: string
  entity_type?: string
  field_or_topic?: string
  field_label?: string
  recommended_record_id?: string | null
  review_status?: string
  records?: KnowledgeRecord[]
  [key: string]: unknown
}

export interface KnowledgeBucketSnapshot {
  records?: KnowledgeRecord[]
  groups?: KnowledgeGroup[]
  documents?: Array<Record<string, unknown>>
  review_queue?: Array<Record<string, unknown>>
  record_count?: number
  pending_count?: number
  knowledge_version?: string
  [key: string]: unknown
}

export interface EvaluationCategory {
  name: string
  score: number
  status: 'strong' | 'healthy' | 'attention' | 'weak' | 'idle' | string
  summary?: string
  recommendation?: string
  suite_case_count?: number
  covered_case_count?: number
  coverage_rate?: number
  metrics?: Record<string, number | string | boolean | unknown>
}

export interface EvaluationOverview {
  generated_at?: string
  overall_score?: number
  overall_status?: 'strong' | 'healthy' | 'attention' | 'weak' | 'idle' | string
  summary?: string
  suite?: {
    case_count?: number
    categories?: Array<{ category: string; count: number }>
    scenarios?: Array<{ scenario: string; count: number }>
    observed_scenarios?: string[]
    missing_scenarios?: string[]
    cases?: Array<{
      id: string
      category: string
      scenario: string
      title: string
      expectation: string
    }>
  }
  categories?: EvaluationCategory[]
  sessions?: Array<{
    thread_id?: string
    title?: string
    updated_at?: string
    scenario?: string
    intent_route?: string
    block_count?: number
    changed_block_count?: number
    warning_count?: number
    grounding_status?: string
    cache_freshness?: string
  }>
  recommendations?: string[]
}

export interface TurnTrace {
  query?: string
  selected_element_id?: string
  message_kind?: string
  warnings?: string[]
  timeline?: TurnTraceEvent[]
  status_timeline?: string[]
  changed_blocks?: ChangedBlockTrace[]
  note_editor?: ExecutionTrace
  workspace_action?: ExecutionTrace
  component_builder?: Record<string, Record<string, unknown>>
  agent_plan?: {
    title?: string
    summary?: string
    steps?: string[]
    watch_points?: string[]
  }
  agent_summary?: {
    title?: string
    summary?: string
    remaining_gaps?: string[]
    next_actions?: string[]
  }
  critique?: {
    score?: number
    needs_revision?: boolean
    suggestions?: string[]
    factual_issues?: string[]
    completeness_issues?: string[]
    has_hook?: boolean
    has_call_to_action?: boolean
    action_recipes?: Array<{
      label: string
      prompt: string
      scope?: string
      why_now?: string
      expected_effect?: string
      expected_blocks?: string[]
    }>
  }
  [key: string]: unknown
}

export interface TraceExportBundle {
  generated_at?: string
  thread_id?: string
  checkpoint_id?: string
  console_tail?: string
  html_preview?: string
  query?: string
  active_panel?: string
  selected_element_id?: string | null
  intent_route?: string
  active_archetype?: string
  scenarios?: string[]
  planner_output?: PlannerOutput
  planner_policy?: PlannerPolicy
  turn_trace?: TurnTrace
  checkpoint_history?: Array<Record<string, unknown>>
  agent_backends?: AgentBackends
  inspector_summary?: InspectorSummary
  retrieval?: Record<string, unknown>
  document?: Record<string, unknown>
  [key: string]: unknown
}

export type AgentBackends = Record<string, string>

export interface RetrievedKnowledge {
  knowledge_plan?: {
    goal_summary?: string
    required_fields?: string[]
    preferred_sources?: string[]
    high_risk_fields?: string[]
    missing_user_inputs?: string[]
    review_required?: boolean
    knowledge_budget?: number
    retrieval_profile?: string
    field_labels?: Record<string, string>
    entity_name?: string
    [key: string]: unknown
  }
  candidate_session_kb?: KnowledgeBucketSnapshot
  session_kb?: KnowledgeBucketSnapshot
  persistent_kb?: KnowledgeBucketSnapshot
  retrieval_eval?: {
    hit_count?: number
    scope_count?: number
    citation_count?: number
    citation_coverage?: number
    grounding_score?: number
    freshness?: string
    fresh_record_count?: number
    stale_record_count?: number
    source_quality?: string
    recommendation?: string
    [key: string]: unknown
  }
  knowledge_records?: Array<{
    record_id?: string
    doc_type?: string
    entity_name?: string
    scenario?: string
    category?: string
    source?: string
    source_scope?: string
    source_title?: string
    query?: string
    title?: string
    snippet?: string
    trust_level?: string
    ingest_mode?: string
    updated_at?: string
    expires_at?: string
    ttl_seconds?: number
    [key: string]: unknown
  }>
  retrieval_summary?: {
    strategy?: string
    policy_name?: string
    policy_path?: string
    ingest_mode?: string
    cache_hit?: boolean
    cache_freshness?: string
    cache_key?: string
    cache_age_seconds?: number
    cache_ttl_seconds?: number
    cache_remaining_ttl_seconds?: number
    live_search_used?: boolean
    query?: string
    entity_name?: string
    query_variants?: string[]
    asset_mode?: string
    image_query?: string
    source_count?: number
    citation_count?: number
    image_count?: number
    hit_scopes?: string[]
    freshness?: string
    record_count?: number
    fresh_record_count?: number
    stale_record_count?: number
    grounding_status?: string
    no_hit_reason?: string
    rerank_applied?: boolean
    [key: string]: unknown
  }
  retrieval_hits?: Array<{
    scope?: string
    query?: string
    count?: number
    titles?: string[]
    [key: string]: unknown
  }>
  entity_name?: string
  fact_conflicts?: Array<{
    field?: string
    values?: unknown[]
    [key: string]: unknown
  }>
  fact_sources?: Array<{
    title?: string
    url?: string
    snippet?: string
    source_type?: string
    source_scope?: string
    query?: string
    [key: string]: unknown
  }>
  confirmed_facts?: Record<string, {
    value?: string
    field_label?: string
    sources?: string[]
    [key: string]: unknown
  }>
  fact_confidence?: string
  [key: string]: unknown
}

export interface AgentMeta {
  checkpoint_id?: string
  checkpointId?: string
  creator_persona?: string
  active_archetype?: string
  intent_route?: string
  retrieved_knowledge?: RetrievedKnowledge
  scenarios?: string[]
  has_controversy?: boolean
  needs_disambiguation?: boolean
  agent_backends?: AgentBackends
  turn_trace?: TurnTrace
  inspector_summary?: InspectorSummary
  [key: string]: unknown
}

/** 全局图库资产：url + 语义描述，同步到后端 state，生成的页面必须全部使用 */
export interface ImageAsset {
  url: string
  desc: string
  source_type?: string
  query?: string
  primary_color?: string
  accent_color?: string
  role?: string
  locked?: boolean
  selection_state?: string
  source_reason?: string
  used_by_blocks?: string[]
}

export interface ShowcaseProfile {
  id: string
  scenarioId: string
  title: string
  persona: string
  whyThisMatters: string
  highlightFeatures: string[]
  talkingPoints: string[]
  demoScript: ShowcaseDemoStep[]
  starterPrompt: string
  editPrompt: string
  themePrompt: string
  branchPrompt: string
}

export interface ShowcaseDemoStep {
  label: string
  goal: string
  action: 'start' | 'fill'
  prompt: string
}

export interface TrendItem {
  keyword: string
  score?: number
  scenario_hint?: string
  entity_type?: string
  source?: string
  freshness?: string
  cache_freshness?: string
  record_count?: number
  recommended_prompt?: string
}

export interface BlockGalleryFixture {
  id: string
  title: string
  description?: string
  note_document: NoteDocument
}

export interface BlockGalleryComponentGuide {
  component_type: string
  label: string
  semantic_role: string
  supported_scenarios?: string[]
  summary?: string
  fixture: BlockGalleryFixture
}

export interface BlockGalleryScenarioGuide {
  scenario_id: string
  title: string
  description?: string
  fixture: BlockGalleryFixture
}

export interface BlockGalleryOverview {
  generated_at?: string
  components?: BlockGalleryComponentGuide[]
  scenarios?: BlockGalleryScenarioGuide[]
  fixtures?: BlockGalleryFixture[]
  recommendations?: string[]
}

export type ConversationCheckpointActionType =
  | 'truth_mode_checkpoint'
  | 'structure_checkpoint'
  | 'knowledge_review_checkpoint'
  | 'fact_gap_checkpoint'
  | 'fact_conflict_checkpoint'
  | 'asset_checkpoint'
  | 'stance_decision'
  | 'entity_disambiguation'

export interface ConversationCheckpointOption {
  label: string
  value: string
  description?: string
  recommended?: boolean
  asset_url?: string | null
  selected_asset_ids?: string[]
  selected_fact_value?: string | null
  user_provided_facts?: Record<string, string | string[]>
  metadata?: Record<string, unknown>
}

export interface ConversationCheckpointFieldOption {
  label: string
  value: string
  recommended?: boolean
}

export interface ConversationCheckpointInputField {
  id: string
  label: string
  placeholder?: string
  type?: 'text' | 'textarea' | 'single_select' | 'multi_select'
  required?: boolean
  options?: ConversationCheckpointFieldOption[]
  allow_custom?: boolean
  custom_placeholder?: string
}

export interface ConversationCheckpointInputSchema {
  submit_label?: string
  helper_text?: string
  fields: ConversationCheckpointInputField[]
}

export interface ConversationCheckpointAction {
  action_type: ConversationCheckpointActionType | string
  checkpoint_id: string
  title: string
  summary?: string
  message?: string
  recommended_option?: string
  recommended_reason?: string
  proposal_summary?: string
  other_allowed?: boolean
  other_placeholder?: string
  blocking?: boolean
  input_schema?: ConversationCheckpointInputSchema | null
  options: ConversationCheckpointOption[]
}

export interface AgentNarrativeCard {
  title: string
  summary?: string
  bullets?: string[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  messageKind?: 'user_prompt' | 'checkpoint_decision' | 'critique_action' | 'agent_plan' | 'agent_status' | 'agent_receipt' | 'agent_summary'
  streaming?: boolean
  imageUrls?: string[]
  timestamp?: number
  /** 时间胶囊：该轮结束时的世界线 */
  checkpointId?: string
  ossUrl?: string
  /** ✨ 调试用：记录该轮对话各节点的提示词输入 */
  nodePrompts?: Record<string, unknown>
  imageAssets?: ImageAsset[]
  /** 时间胶囊：该轮生成的 HTML 源码 */
  sourceCode?: string
  noteDocument?: NoteDocument
  plannerOutput?: PlannerOutput
  plannerPolicy?: PlannerPolicy
  agentBackends?: AgentBackends
  turnTrace?: TurnTrace
  inspectorSummary?: InspectorSummary
  benchmarkOverview?: BenchmarkOverview
  evaluationOverview?: EvaluationOverview
  blockGalleryOverview?: BlockGalleryOverview
  actionRequired?: ConversationCheckpointAction
  agentCard?: AgentNarrativeCard
  /** ✨ 思维链实时透传记录 */
  thoughts?: { node: string; text: string; streaming?: boolean }[]
}

export interface WSEvent {
  /** 新版协议：使用 event 和 data */
  event?: 'token' | 'thought' | 'thought_process' | 'turn_end' | 'error' | 'action_required'
  data?: Record<string, unknown>
  
  /** WebSocket 兼容字段 */
  type?: 'middleware' | 'token' | 'tool_call' | 'turn_end' | 'error'
  node?: string
  content?: string
  checkpoint_id?: string
  checkpointId?: string
  oss_url?: string
  ossUrl?: string
  message?: string
  image_assets?: ImageAsset[]
  imageAssets?: ImageAsset[]
  node_prompts?: Record<string, string>
  nodePrompts?: Record<string, unknown>
  source_code?: string
  sourceCode?: string
  htmlPreview?: string
  note_document?: NoteDocument
  noteDocument?: NoteDocument
  planner_output?: PlannerOutput
  plannerOutput?: PlannerOutput
  planner_policy?: PlannerPolicy
  plannerPolicy?: PlannerPolicy
  turn_trace?: TurnTrace
  turnTrace?: TurnTrace
  agent_backends?: AgentBackends
  agentBackends?: AgentBackends
  inspector_summary?: InspectorSummary
  inspectorSummary?: InspectorSummary
  benchmark_overview?: BenchmarkOverview
  benchmarkOverview?: BenchmarkOverview
  evaluation_overview?: EvaluationOverview
  evaluationOverview?: EvaluationOverview
  block_gallery_overview?: BlockGalleryOverview
  blockGalleryOverview?: BlockGalleryOverview
}

export interface WSPayload {
  content: string
  panel: string
  parent_checkpoint_id?: string | null
  selected_element_id?: string | null
  /** ✨ 创作者人设，同步到后端 state 影响文风 */
  creator_persona?: string | null
  /** 全局图库资产池，每次发信同步到后端 */
  current_assets?: ImageAsset[]
  /** 待打标的新图片 URL，后端塞进 pending_images 由 asset_processor 识图后写入图库 */
  image_urls?: string[]
  message_kind?: string
  type?: 'submit_checkpoint_decision' | 'submit_stance' | 'submit_disambiguation'
  action_type?: string
  checkpoint_id?: string
  decision?: string
  selected_asset_ids?: string[]
  selected_fact_value?: string | null
  user_provided_facts?: Record<string, string | string[]>
  custom_note?: string
}
