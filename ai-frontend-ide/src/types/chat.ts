/** WS 协议与消息类型定义 */

export interface FactBinding {
  field: string
  fact_fields?: string[]
  fact_field_labels?: string[]
  kind?: string
  sources?: string[]
  hint?: string
}

export type AssetSupportLevel = 'none' | 'optional' | 'required'

export interface NoteDocumentAsset {
  id?: string
  url: string
  desc?: string
  source_type?: string
  query?: string
  role?: string
  locked?: boolean
  selection_state?: string
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
  ui_state?: Record<string, unknown>
  planner?: Record<string, unknown>
}

export interface PlannerIntent {
  block_id?: string
  block_index?: number
  intent?: string
  semantic_role?: string
  preferred_component?: string
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
  assets?: Record<string, unknown>
  suggestions?: string[]
  [key: string]: unknown
}

export interface TurnTrace {
  query?: string
  selected_element_id?: string
  warnings?: string[]
  timeline?: TurnTraceEvent[]
  changed_blocks?: ChangedBlockTrace[]
  note_editor?: ExecutionTrace
  workspace_action?: ExecutionTrace
  component_builder?: Record<string, Record<string, unknown>>
  [key: string]: unknown
}

export type AgentBackends = Record<string, string>

export interface RetrievedKnowledge {
  entity_name?: string
  fact_conflicts?: Array<{
    field?: string
    values?: unknown[]
    [key: string]: unknown
  }>
  fact_sources?: Array<{
    title?: string
    url?: string
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

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
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
  /** 待打标的新图片 URL，后端塞进 pending_images 由 asset_node 识图后写入图库 */
  image_urls?: string[]
}
