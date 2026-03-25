import { computed, onMounted, ref, type Ref } from 'vue'
import type {
  AgentMeta,
  BenchmarkOverview,
  EvaluationOverview,
  EvaluationCategory,
  ExecutionTrace,
  FactBinding,
  InspectorSummary,
  NoteDocument,
  NoteDocumentAsset,
  NoteDocumentBlock,
  PlannerOutput,
  PlannerPolicy,
  RetrievedKnowledge,
  TurnTrace,
} from '../../types/chat'

type AnyRef<T = unknown> = Ref<T>

type DiagnosticsOptions = {
  chatStore: ReturnType<typeof import('../../stores/useChatStore').useChatStore>
  plannerOutput: AnyRef<PlannerOutput | Record<string, unknown>>
  plannerPolicy: AnyRef<PlannerPolicy | Record<string, unknown>>
  noteDocument: AnyRef<NoteDocument | Record<string, unknown>>
  scenarioTags: AnyRef<string[]>
  patchTracks: AnyRef<Record<string, unknown[]>>
  agentBackends: AnyRef<Record<string, string>>
  turnTrace: AnyRef<TurnTrace | Record<string, unknown>>
  inspectorSummary: AnyRef<InspectorSummary | Record<string, unknown>>
  agentMeta: AnyRef<AgentMeta | Record<string, unknown>>
  benchmarkOverview: AnyRef<BenchmarkOverview | Record<string, unknown>>
  evaluationOverview: AnyRef<EvaluationOverview | Record<string, unknown>>
}

const TRACE_WARNING_LABELS: Record<string, string> = {
  noop: '本轮没有实际内容改动',
  fallback_used: '本轮触发了兜底路径',
  style_changed_without_content: '样式变化了，但内容没有变',
  auto_resume_guard: '命中过度续火保护',
  max_auto_resume_exceeded: '超过最大自动续火次数',
}

const TRACE_EVENT_LABELS: Record<string, string> = {
  worker_start: '角色开始',
  worker_end: '角色完成',
  tool_start: '工具调用',
}

const TRACE_ACTION_LABELS: Record<string, string> = {
  create_canvas: '首版创建',
  update_block: '更新区块',
  replace_block: '替换区块',
  move_block: '移动区块',
  remove_block: '删除区块',
  append_block: '新增区块',
  rewrite_paragraph: '重写段落',
  update_page_theme: '修改主题',
  update_page_title: '修改标题',
  noop: '无实际改动',
  error: '执行失败',
  workspace_import_asset: '素材入池',
  workspace_set_cover: '设为封面',
  workspace_remove_asset: '删除素材',
  workspace_confirm_fact: '确认事实',
  workspace_rollback_component: '组件回滚',
  workspace_select_region: '锁定区块',
  workspace_fork: '创建分支',
}

const FACT_FIELD_LABELS: Record<string, string> = {
  battery_capacity: '电池容量',
  price: '价格',
}

export function useAgentInspectorDiagnostics(options: DiagnosticsOptions) {
  const {
    chatStore,
    plannerOutput,
    plannerPolicy,
    noteDocument,
    scenarioTags,
    patchTracks,
    agentBackends,
    turnTrace,
    inspectorSummary,
    agentMeta,
    benchmarkOverview,
    evaluationOverview,
  } = options

  const agentMetaState = computed<AgentMeta>(() => (agentMeta.value || {}) as AgentMeta)
  const inspectorSummaryState = computed<InspectorSummary>(() => (inspectorSummary.value || agentMetaState.value.inspector_summary || {}) as InspectorSummary)
  const benchmarkOverviewState = computed<BenchmarkOverview>(() => (benchmarkOverview.value || {}) as BenchmarkOverview)
  const evaluationOverviewState = computed<EvaluationOverview>(() => (evaluationOverview.value || {}) as EvaluationOverview)
  const inspectorFocus = computed(() => (inspectorSummaryState.value?.focus || {}) as Record<string, unknown>)
  const inspectorDocument = computed(() => (inspectorSummaryState.value?.document || {}) as Record<string, unknown>)
  const inspectorExecution = computed(() => (inspectorSummaryState.value?.execution || {}) as Record<string, unknown>)
  const inspectorBuilder = computed(() => inspectorSummaryState.value?.builder || {})
  const inspectorFacts = computed(() => (inspectorSummaryState.value?.facts || {}) as Record<string, unknown>)
  const inspectorRetrieval = computed(() => (inspectorSummaryState.value?.retrieval || {}) as Record<string, unknown>)
  const inspectorArtifact = computed(() => (inspectorSummaryState.value?.artifact || {}) as Record<string, unknown>)
  const inspectorAgentic = computed(() => (inspectorSummaryState.value?.agentic || {}) as Record<string, unknown>)
  const inspectorAssets = computed(() => (inspectorSummaryState.value?.assets || {}) as Record<string, unknown>)
  const inspectorRevision = computed(() => (inspectorSummaryState.value?.revision || {}) as Record<string, unknown>)
  const inspectorSuggestions = computed(() => Array.isArray(inspectorSummaryState.value?.suggestions) ? inspectorSummaryState.value.suggestions : [])
  const inspectorHeadline = computed(() => String(inspectorSummaryState.value?.headline || '当前还没有可展示的诊断摘要'))
  const inspectorStatus = computed(() => String(inspectorSummaryState.value?.status || 'idle'))
  const builderPromptModeLabel = computed(() => {
    const modes = Array.isArray(inspectorBuilder.value?.prompt_modes) ? inspectorBuilder.value.prompt_modes : []
    return modes.length ? modes.join(' / ') : '未记录'
  })

  const getInspectorStatusClasses = (status: string) => {
    if (status === 'attention') return 'border-amber-700/30 bg-amber-950/20 text-amber-300'
    if (status === 'active') return 'border-emerald-700/30 bg-emerald-950/20 text-emerald-300'
    return 'border-slate-700/30 bg-slate-950/20 text-slate-300'
  }

  const getInspectorStatusLabel = (status: string) => {
    if (status === 'attention') return '需关注'
    if (status === 'active') return '运行中'
    return '待启动'
  }

  const overviewCards = computed(() => [
    {
      title: '当前焦点',
      value: inspectorFocus.value.entity_name || '未识别主体',
      helper: `${(inspectorFocus.value.scenarios || []).join(' / ') || 'seeding'} · ${inspectorFocus.value.intent_route || '等待指令'}`,
      tone: 'cyan',
    },
    {
      title: '页面状态',
      value: `${inspectorDocument.value.block_count || 0} 个区块`,
      helper: `${inspectorDocument.value.asset_count || 0} 个资产 · 主题 ${inspectorDocument.value.theme_preset || 'default'}`,
      tone: 'emerald',
    },
    {
      title: '最近执行',
      value: inspectorExecution.value.last_action || '暂无动作',
      helper: `命中 ${inspectorExecution.value.target_block_id || 'global'} · ${inspectorExecution.value.changed_block_count || 0} 处变更`,
      tone: 'violet',
    },
    {
      title: '产物版本',
      value: inspectorArtifact.value.current_version_id || '未生成',
      helper: `${inspectorArtifact.value.artifact_type || 'purchase_decision_note'} · ${inspectorArtifact.value.revision_reason || '本轮暂无修订原因'}`,
      tone: 'slate',
    },
    {
      title: '积木构建',
      value: `${inspectorBuilder.value.component_count || 0} 个组件`,
      helper: inspectorBuilder.value.component_count
        ? `${inspectorBuilder.value.fallback_count || 0} 次 fallback · ${inspectorBuilder.value.fact_summary_count || 0} 条事实摘要 · ${builderPromptModeLabel.value}`
        : '当前这轮没有新的组件构建',
      tone: 'rose',
    },
    {
      title: '可信状态',
      value: `${inspectorFacts.value.conflict_count || 0} 个冲突`,
      helper: `${inspectorFacts.value.confirmed_count || 0} 个已确认 · ${inspectorFacts.value.source_count || 0} 个来源`,
      tone: 'amber',
    },
    {
      title: '修订状态',
      value: inspectorRevision.value.status || 'idle',
      helper: `${inspectorRevision.value.changed_block_count || 0} 个改动 · ${inspectorRevision.value.failure_reason || inspectorRevision.value.revision_reason || '当前没有失败或待处理原因'}`,
      tone: 'rose',
    },
  ])

  const getOverviewCardClasses = (tone: string) => {
    if (tone === 'rose') return 'border-rose-800/25 bg-rose-950/10'
    if (tone === 'amber') return 'border-amber-800/25 bg-amber-950/10'
    if (tone === 'violet') return 'border-violet-800/25 bg-violet-950/10'
    if (tone === 'emerald') return 'border-emerald-800/25 bg-emerald-950/10'
    if (tone === 'slate') return 'border-slate-800/25 bg-slate-950/10'
    return 'border-cyan-800/25 bg-cyan-950/10'
  }

  const getAssetSupportBadgeClasses = (support: string) => {
    if (support === 'required') return 'border-rose-700/30 bg-rose-900/10 text-rose-300'
    if (support === 'optional') return 'border-amber-700/30 bg-amber-900/10 text-amber-300'
    return 'border-slate-700/30 bg-slate-900/10 text-slate-400'
  }

  const humanizeAssetSupport = (support: string) => {
    if (support === 'required') return '素材必需'
    if (support === 'optional') return '素材可选'
    return '无需素材'
  }

  const benchmarkSummary = computed(() => (benchmarkOverviewState.value?.summary || {}) as Record<string, unknown>)
  const benchmarkRag = computed(() => (benchmarkOverviewState.value?.rag || {}) as Record<string, unknown>)
  const benchmarkCache = computed(() => (benchmarkOverviewState.value?.cache || {}) as Record<string, unknown>)
  const benchmarkExecution = computed(() => (benchmarkOverviewState.value?.execution || {}) as Record<string, unknown>)
  const benchmarkDistributions = computed(() => (benchmarkOverviewState.value?.distributions || {}) as Record<string, unknown>)
  const benchmarkSessions = computed(() => Array.isArray(benchmarkOverviewState.value?.sessions) ? benchmarkOverviewState.value.sessions : [])
  const benchmarkRecommendations = computed(() => Array.isArray(benchmarkOverviewState.value?.recommendations) ? benchmarkOverviewState.value.recommendations : [])
  const benchmarkSessionCount = computed(() => Number(benchmarkOverviewState.value?.session_count || 0))
  const benchmarkActiveDocumentCount = computed(() => Number(benchmarkOverviewState.value?.active_document_count || 0))
  const benchmarkScenarioRows = computed(() => Array.isArray(benchmarkDistributions.value?.scenarios) ? benchmarkDistributions.value.scenarios : [])
  const benchmarkComponentRows = computed(() => Array.isArray(benchmarkDistributions.value?.components) ? benchmarkDistributions.value.components : [])
  const benchmarkThemeRows = computed(() => Array.isArray(benchmarkDistributions.value?.themes) ? benchmarkDistributions.value.themes : [])
  const benchmarkEntityRows = computed(() => Array.isArray(benchmarkDistributions.value?.entities) ? benchmarkDistributions.value.entities : [])
  const benchmarkCards = computed(() => [
    {
      title: '会话数',
      value: benchmarkSessionCount.value,
      helper: `${benchmarkActiveDocumentCount.value} 个会话已生成页面`,
      tone: 'cyan',
    },
    {
      title: '平均区块数',
      value: Number(benchmarkSummary.value?.avg_block_count || 0).toFixed(1),
      helper: `平均资产 ${Number(benchmarkSummary.value?.avg_asset_count || 0).toFixed(1)} 个`,
      tone: 'emerald',
    },
    {
      title: 'Grounding',
      value: Number(benchmarkRag.value?.avg_grounding_score || 0).toFixed(2),
      helper: `引用覆盖率 ${Math.round(Number(benchmarkRag.value?.avg_citation_coverage || 0) * 100)}%`,
      tone: 'violet',
    },
    {
      title: '缓存命中率',
      value: `${Math.round(Number(benchmarkCache.value?.cache_hit_rate || 0) * 100)}%`,
      helper: `live search ${Math.round(Number(benchmarkCache.value?.live_search_rate || 0) * 100)}%`,
      tone: 'rose',
    },
    {
      title: 'Builder Fallback',
      value: `${Math.round(Number(benchmarkExecution.value?.builder_fallback_rate || 0) * 100)}%`,
      helper: `${Number(benchmarkExecution.value?.builder_fallback_total || 0)} / ${Number(benchmarkExecution.value?.builder_component_total || 0)} 次`,
      tone: 'amber',
    },
    {
      title: '告警率',
      value: `${Math.round(Number(benchmarkExecution.value?.warning_rate || 0) * 100)}%`,
      helper: `${Number(benchmarkExecution.value?.warning_session_count || 0)} 个会话有 warning`,
      tone: 'slate',
    },
  ])
  const benchmarkGeneratedAt = computed(() => String(benchmarkOverviewState.value?.generated_at || ''))
  const evaluationCategories = computed<EvaluationCategory[]>(() => Array.isArray(evaluationOverviewState.value?.categories) ? evaluationOverviewState.value.categories : [])
  const evaluationSuite = computed(() => (evaluationOverviewState.value?.suite || {}) as Record<string, unknown>)
  const evaluationSessions = computed(() => Array.isArray(evaluationOverviewState.value?.sessions) ? evaluationOverviewState.value.sessions : [])
  const evaluationRecommendations = computed(() => Array.isArray(evaluationOverviewState.value?.recommendations) ? evaluationOverviewState.value.recommendations : [])
  const evaluationSummary = computed(() => String(evaluationOverviewState.value?.summary || ''))
  const evaluationOverallScore = computed(() => Number(evaluationOverviewState.value?.overall_score || 0))
  const evaluationOverallStatus = computed(() => String(evaluationOverviewState.value?.overall_status || 'idle'))
  const evaluationGeneratedAt = computed(() => String(evaluationOverviewState.value?.generated_at || ''))
  const evaluationScenarioRows = computed(() => Array.isArray(evaluationSuite.value?.scenarios) ? evaluationSuite.value.scenarios : [])
  const evaluationCategoryRows = computed(() => Array.isArray(evaluationSuite.value?.categories) ? evaluationSuite.value.categories : [])
  const evaluationMissingScenarios = computed(() => Array.isArray(evaluationSuite.value?.missing_scenarios) ? evaluationSuite.value.missing_scenarios : [])
  const evaluationObservedScenarios = computed(() => Array.isArray(evaluationSuite.value?.observed_scenarios) ? evaluationSuite.value.observed_scenarios : [])
  const evaluationCards = computed(() => [
    {
      title: '总分',
      value: evaluationOverallScore.value.toFixed(1),
      helper: `状态 ${evaluationOverallStatus.value || 'idle'}`,
      tone: evaluationOverallStatus.value === 'strong' ? 'emerald' : evaluationOverallStatus.value === 'healthy' ? 'cyan' : evaluationOverallStatus.value === 'attention' ? 'amber' : 'rose',
    },
    {
      title: '评测集',
      value: Number(evaluationSuite.value?.case_count || 0),
      helper: `${evaluationObservedScenarios.value.length} 个正式数码场景切片已覆盖`,
      tone: 'violet',
    },
    {
      title: '分类数',
      value: evaluationCategories.value.length,
      helper: '路由 / 规划 / 执行 / RAG / 缓存 / 系统',
      tone: 'cyan',
    },
    {
      title: '建议数',
      value: evaluationRecommendations.value.length,
      helper: evaluationMissingScenarios.value.length ? `缺失场景 ${evaluationMissingScenarios.value.join(' / ')}` : '评估样本覆盖正常',
      tone: 'amber',
    },
  ])

  const getEvaluationStatusClasses = (status: string) => {
    if (status === 'strong') return 'border-emerald-700/30 bg-emerald-950/15 text-emerald-300'
    if (status === 'healthy') return 'border-cyan-700/30 bg-cyan-950/15 text-cyan-300'
    if (status === 'attention') return 'border-amber-700/30 bg-amber-950/15 text-amber-300'
    return 'border-rose-700/30 bg-rose-950/15 text-rose-300'
  }

  onMounted(() => {
    void chatStore.fetchBenchmarkOverview()
    void chatStore.fetchEvaluationOverview()
  })

  const knowledge = computed<RetrievedKnowledge>(() => (agentMetaState.value.retrieved_knowledge || {}) as RetrievedKnowledge)
  const factSources = computed(() => Array.isArray(knowledge.value?.fact_sources) ? knowledge.value.fact_sources : [])
  const factConflicts = computed(() => Array.isArray(knowledge.value?.fact_conflicts) ? knowledge.value.fact_conflicts : [])
  const factConfidence = computed(() => String(knowledge.value?.fact_confidence || 'unknown'))
  const retrievalSummary = computed(() => (knowledge.value?.retrieval_summary || {}) as Record<string, unknown>)
  const retrievalEval = computed(() => (knowledge.value?.retrieval_eval || {}) as Record<string, unknown>)
  const knowledgeRecords = computed(() => Array.isArray(knowledge.value?.knowledge_records) ? knowledge.value.knowledge_records : [])
  const retrievalHits = computed(() => Array.isArray(knowledge.value?.retrieval_hits) ? knowledge.value.retrieval_hits : [])
  const retrievalQueryVariants = computed(() => {
    const variants = retrievalSummary.value?.query_variants
    return Array.isArray(variants) ? variants.map((item) => String(item || '')).filter(Boolean) : []
  })
  const retrievalHitScopes = computed(() => {
    const scopes = retrievalSummary.value?.hit_scopes
    return Array.isArray(scopes) ? scopes.map((item) => String(item || '')).filter(Boolean) : []
  })
  const retrievalStrategy = computed(() => String(inspectorRetrieval.value?.strategy || retrievalSummary.value?.strategy || 'none'))
  const retrievalGroundingStatus = computed(() => String(inspectorRetrieval.value?.grounding_status || retrievalSummary.value?.grounding_status || 'unknown'))
  const retrievalFreshness = computed(() => String(inspectorRetrieval.value?.freshness || retrievalSummary.value?.freshness || 'unknown'))
  const retrievalNoHitReason = computed(() => String(inspectorRetrieval.value?.no_hit_reason || retrievalSummary.value?.no_hit_reason || ''))
  const retrievalPrimaryQuery = computed(() => String(inspectorRetrieval.value?.query || retrievalSummary.value?.query || ''))
  const retrievalPolicyName = computed(() => String(inspectorRetrieval.value?.policy_name || retrievalSummary.value?.policy_name || ''))
  const retrievalPolicyPath = computed(() => String(inspectorRetrieval.value?.policy_path || retrievalSummary.value?.policy_path || ''))
  const retrievalCitationCount = computed(() => Number(inspectorRetrieval.value?.citation_count || retrievalSummary.value?.citation_count || factSources.value.length || 0))
  const retrievalImageCount = computed(() => Number(inspectorRetrieval.value?.image_count || retrievalSummary.value?.image_count || 0))
  const retrievalCacheHit = computed(() => Boolean(inspectorRetrieval.value?.cache_hit || retrievalSummary.value?.cache_hit))
  const retrievalCacheFreshness = computed(() => String(inspectorRetrieval.value?.cache_freshness || retrievalSummary.value?.cache_freshness || 'unknown'))
  const retrievalCacheKey = computed(() => String(inspectorRetrieval.value?.cache_key || retrievalSummary.value?.cache_key || ''))
  const retrievalCacheAgeSeconds = computed(() => Number(inspectorRetrieval.value?.cache_age_seconds || retrievalSummary.value?.cache_age_seconds || 0))
  const retrievalCacheTtlSeconds = computed(() => Number(inspectorRetrieval.value?.cache_ttl_seconds || retrievalSummary.value?.cache_ttl_seconds || 0))
  const retrievalCacheRemainingTtlSeconds = computed(() => Number(inspectorRetrieval.value?.cache_remaining_ttl_seconds || retrievalSummary.value?.cache_remaining_ttl_seconds || 0))
  const retrievalLiveSearchUsed = computed(() => Boolean(inspectorRetrieval.value?.live_search_used || retrievalSummary.value?.live_search_used))
  const retrievalHitCount = computed(() => Number(inspectorRetrieval.value?.hit_count || retrievalHits.value.length || 0))
  const retrievalIngestMode = computed(() => String(inspectorRetrieval.value?.ingest_mode || retrievalSummary.value?.ingest_mode || 'unknown'))
  const retrievalRecordCount = computed(() => Number(inspectorRetrieval.value?.record_count || retrievalSummary.value?.record_count || knowledgeRecords.value.length || 0))
  const retrievalFreshRecordCount = computed(() => Number(inspectorRetrieval.value?.fresh_record_count || retrievalSummary.value?.fresh_record_count || retrievalEval.value?.fresh_record_count || 0))
  const retrievalStaleRecordCount = computed(() => Number(inspectorRetrieval.value?.stale_record_count || retrievalSummary.value?.stale_record_count || retrievalEval.value?.stale_record_count || 0))
  const retrievalCitationCoverage = computed(() => Number(inspectorRetrieval.value?.citation_coverage || retrievalEval.value?.citation_coverage || 0))
  const retrievalGroundingScore = computed(() => Number(inspectorRetrieval.value?.grounding_score || retrievalEval.value?.grounding_score || 0))
  const retrievalSourceQuality = computed(() => String(inspectorRetrieval.value?.source_quality || retrievalEval.value?.source_quality || 'unknown'))
  const retrievalRecommendation = computed(() => String(inspectorRetrieval.value?.recommendation || retrievalEval.value?.recommendation || ''))
  const retrievalRerankApplied = computed(() => Boolean(inspectorRetrieval.value?.rerank_applied || retrievalSummary.value?.rerank_applied))

  const getGroundingToneClasses = (status: string) => {
    if (status === 'grounded') return 'border-emerald-700/30 bg-emerald-950/20 text-emerald-300'
    if (status === 'visual_only' || status === 'weak') return 'border-amber-700/30 bg-amber-950/20 text-amber-300'
    return 'border-slate-700/30 bg-slate-950/20 text-slate-300'
  }

  const humanizeGroundingStatus = (status: string) => {
    if (status === 'grounded') return '已落地引用'
    if (status === 'visual_only') return '只有视觉素材'
    if (status === 'weak') return '证据较弱'
    return '未记录'
  }

  const humanizeRetrievalStrategy = (strategy: string) => {
    if (strategy === 'cache_hit') return '热点缓存命中'
    if (strategy === 'live_search_with_citations') return '在线搜证 + 引用归因'
    return strategy || '未记录'
  }

  const humanizeRetrievalScope = (scope: string) => {
    if (scope === 'official') return '官方/参数'
    if (scope === 'review') return '口碑/体验'
    return scope || '未分组'
  }

  const humanizeRetrievalIngestMode = (mode: string) => {
    if (mode === 'system_preload') return '系统预热知识'
    if (mode === 'task_triggered_ingest') return '任务触发沉淀'
    return mode || '未记录'
  }

  const humanizeCacheFreshness = (status: string) => {
    if (status === 'fresh') return '缓存新鲜'
    if (status === 'expired') return '缓存过期'
    if (status === 'miss') return '未命中缓存'
    return status || '未知'
  }

  const humanizeSourceQuality = (quality: string) => {
    if (quality === 'high') return '高可信来源'
    if (quality === 'medium') return '中可信来源'
    if (quality === 'low') return '低可信来源'
    return '未评估'
  }

  const getSourceQualityClasses = (quality: string) => {
    if (quality === 'high') return 'border-emerald-700/30 bg-emerald-950/20 text-emerald-300'
    if (quality === 'medium') return 'border-amber-700/30 bg-amber-950/20 text-amber-300'
    return 'border-slate-700/30 bg-slate-950/20 text-slate-300'
  }

  const confirmedFacts = computed(() => {
    const raw = knowledge.value?.confirmed_facts
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return []
    return Object.entries(raw).map(([field, payload]) => ({
      field,
      fieldLabel: payload?.field_label || field,
      value: payload?.value || '',
      sources: Array.isArray(payload?.sources) ? payload.sources : [],
    }))
  })

  const plannerOutputState = computed<PlannerOutput>(() => (plannerOutput.value || {}) as PlannerOutput)
  const plannerPolicyState = computed<PlannerPolicy>(() => (plannerPolicy.value || {}) as PlannerPolicy)
  const noteDocumentState = computed<NoteDocument>(() => (noteDocument.value || {}) as NoteDocument)
  const plannerIntents = computed(() => Array.isArray(plannerOutputState.value?.block_intents) ? plannerOutputState.value.block_intents : [])
  const plannerScenarioScores = computed(() => (plannerOutputState.value?.scenario_scores || plannerPolicyState.value?.scenario_scores || {}) as Record<string, number>)
  const noteBlocks = computed<NoteDocumentBlock[]>(() => Array.isArray(noteDocumentState.value?.blocks) ? noteDocumentState.value.blocks : [])
  const noteAssets = computed<NoteDocumentAsset[]>(() => Array.isArray(noteDocumentState.value?.assets) ? noteDocumentState.value.assets : [])
  const noteScenarios = computed(() => (scenarioTags.value as string[]) || ['general'])
  const documentThemeLabel = computed(() => {
    const inspectorPreset = String(inspectorDocument.value?.theme_preset || '').trim()
    if (inspectorPreset) return inspectorPreset
    const plannerPreset = String(plannerPolicyState.value?.theme_policy?.preset || '').trim()
    if (plannerPreset) return plannerPreset
    const pageTheme = (noteDocumentState.value?.theme?.page_theme || {}) as Record<string, unknown>
    const pageThemeKeys = Object.keys(pageTheme)
    if (pageThemeKeys.length) return `${pageThemeKeys.length} 个主题变量`
    return 'default'
  })

  const noteBlockCapabilityRows = computed(() =>
    noteBlocks.value.slice(0, 4).map((block: NoteDocumentBlock) => {
      const editableTargets = Array.isArray(block?.editable_targets) ? block.editable_targets : []
      return {
        id: String(block?.id || ''),
        label: String(block?.label || block?.type || '未命名块'),
        semanticRole: String(block?.semantic_role || 'content'),
        assetSupport: String(block?.asset_support || 'none'),
        factBindingSupport: Boolean(block?.fact_binding_support),
        editableSummary: editableTargets.length ? editableTargets.slice(0, 2).join(' / ') : '无显式目标',
      }
    }),
  )

  const patchTrackMap = computed<Record<string, unknown[]>>(() => (patchTracks.value as Record<string, unknown[]>) || {})
  const runtimeBackends = computed(() => {
    const fromStore = agentBackends.value || {}
    if (Object.keys(fromStore).length) return fromStore
    return agentMetaState.value.agent_backends || {}
  })
  const turnTraceState = computed<TurnTrace>(() => (turnTrace.value || agentMetaState.value.turn_trace || {}) as TurnTrace)
  const traceTimeline = computed(() => Array.isArray(turnTraceState.value?.timeline) ? turnTraceState.value.timeline : [])
  const traceWarnings = computed(() => Array.isArray(turnTraceState.value?.warnings) ? turnTraceState.value.warnings : [])
  const traceChangedBlocks = computed(() => Array.isArray(turnTraceState.value?.changed_blocks) ? turnTraceState.value.changed_blocks : [])
  const compositionTrace = computed<ExecutionTrace>(() => (turnTraceState.value?.composition_worker || {}) as ExecutionTrace)
  const workspaceActionTrace = computed<ExecutionTrace>(() => (turnTraceState.value?.workspace_action || {}) as ExecutionTrace)
  const activeExecutionTrace = computed(() => Object.keys(compositionTrace.value).length ? compositionTrace.value : workspaceActionTrace.value)

  const humanizeTraceWarning = (warning: string) => TRACE_WARNING_LABELS[warning] || warning
  const humanizeTraceEvent = (event: string) => TRACE_EVENT_LABELS[event] || event
  const humanizeTraceAction = (action: string) => TRACE_ACTION_LABELS[action] || action || '未识别动作'
  const traceSummaryTone = computed(() => traceWarnings.value.length ? 'warn' : 'ok')
  const tracePrimaryTarget = computed(() => activeExecutionTrace.value.target_block_id || compositionTrace.value.block_id || turnTraceState.value.selected_element_id || 'global')
  const copiedDebugSummary = ref(false)
  const copiedTraceExport = ref(false)
  const traceExportPending = ref(false)
  const traceStructuredStatus = computed(() => {
    if (activeExecutionTrace.value.fallback_used) return 'fallback'
    if (activeExecutionTrace.value.structured === false) return 'loose'
    return 'structured'
  })
  const tracePrimarySignal = computed(() => {
    if (traceWarnings.value.includes('style_changed_without_content')) {
      return {
        label: '样式变了，但内容没变',
        tone: 'warn',
        description: '这通常说明本轮命中了样式层或空转路径，建议先确认命中区块和结构化动作。',
      }
    }
    if (traceWarnings.value.includes('noop')) {
      return {
        label: '本轮没有实际内容改动',
        tone: 'warn',
        description: '系统顺利执行了流程，但没有找到可落地的内容差异，建议看结构化计划是否命中了正确区块。',
      }
    }
    if (activeExecutionTrace.value.fallback_used) {
      return {
        label: '本轮使用了兜底路径',
        tone: 'warn',
        description: '说明结构化动作没有完全覆盖这次请求，建议优先检查命中目标和动作推断。',
      }
    }
    return {
      label: '本轮结构化执行正常',
      tone: 'ok',
      description: '系统已经产出了结构化计划，并记录了命中区块与变更摘要，可以直接用来排查是否改中了地方。',
    }
  })
  const traceDiagnostics = computed(() => {
    const cards = [
      {
        title: '动作判定',
        tone: 'cyan',
        description: humanizeTraceAction(String(activeExecutionTrace.value.action || '')),
        helper: activeExecutionTrace.value.structured === false ? '这次更像开放式输出' : '这次是结构化动作',
      },
      {
        title: '命中对象',
        tone: 'emerald',
        description: String(tracePrimaryTarget.value),
        helper: activeExecutionTrace.value.reason || '根据 query、文档语义和 planner policy 推断目标。',
      },
      {
        title: '实际变更',
        tone: 'violet',
        description: traceChangedBlocks.value.length ? `${traceChangedBlocks.value.length} 个区块发生变化` : '没有记录到块级变化',
        helper: traceChangedBlocks.value.length ? '可以展开下面的“实际变更”继续看字段差异。' : '如果预期有改动，优先检查 warnings 和结构化计划。',
      },
    ]

    if (traceWarnings.value.length) {
      cards.push({
        title: '风险提示',
        tone: 'amber',
        description: traceWarnings.value.map((item) => humanizeTraceWarning(String(item))).join('；'),
        helper: '这类信号通常是排障优先入口。',
      })
    }

    return cards
  })
  const getTraceEventTone = (event: string) => {
    if (event === 'worker_start') return 'cyan'
    if (event === 'worker_end') return 'emerald'
    if (event === 'tool_start') return 'violet'
    return 'slate'
  }
  const getTraceEventToneClasses = (event: string) => {
    const tone = getTraceEventTone(event)
    if (tone === 'emerald') return 'border-emerald-800/25 bg-emerald-950/10 text-emerald-300'
    if (tone === 'violet') return 'border-violet-800/25 bg-violet-950/10 text-violet-300'
    if (tone === 'cyan') return 'border-cyan-800/25 bg-cyan-950/10 text-cyan-300'
    return 'border-slate-800/25 bg-slate-950/10 text-slate-300'
  }
  const getTraceMarkerClasses = (event: string) => {
    const tone = getTraceEventTone(event)
    if (tone === 'emerald') return 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.28)]'
    if (tone === 'violet') return 'bg-violet-500 shadow-[0_0_12px_rgba(139,92,246,0.28)]'
    if (tone === 'cyan') return 'bg-cyan-500 shadow-[0_0_12px_rgba(34,211,238,0.28)]'
    return 'bg-slate-500 shadow-[0_0_12px_rgba(148,163,184,0.2)]'
  }
  const getDiagnosticToneClasses = (tone: string) => {
    if (tone === 'amber') return 'border-amber-800/25 bg-amber-950/10'
    if (tone === 'violet') return 'border-violet-800/25 bg-violet-950/10'
    if (tone === 'emerald') return 'border-emerald-800/25 bg-emerald-950/10'
    return 'border-cyan-800/25 bg-cyan-950/10'
  }
  const getTraceWarningBadgeClasses = (warning: string) => {
    if (warning === 'style_changed_without_content') return 'border-rose-700/30 bg-rose-950/20 text-rose-300'
    if (warning === 'fallback_used' || warning === 'auto_resume_guard' || warning === 'max_auto_resume_exceeded') return 'border-amber-700/30 bg-amber-950/20 text-amber-300'
    return 'border-slate-700/30 bg-slate-950/20 text-slate-300'
  }
  const getTraceWarningBadgeLabel = (warning: string) => {
    if (warning === 'style_changed_without_content') return '红色告警'
    if (warning === 'fallback_used' || warning === 'auto_resume_guard' || warning === 'max_auto_resume_exceeded') return '黄色提醒'
    return '一般提醒'
  }
  const getStructuredStatusClasses = (status: string) => {
    if (status === 'fallback') return 'border-amber-700/30 text-amber-300 bg-amber-900/10'
    if (status === 'loose') return 'border-slate-700/30 text-slate-300 bg-slate-900/10'
    return 'border-emerald-700/30 text-emerald-300 bg-emerald-900/10'
  }
  const structuredStatusLabel = computed(() => {
    if (traceStructuredStatus.value === 'fallback') return '兜底执行'
    if (traceStructuredStatus.value === 'loose') return '非结构化'
    return '结构化执行'
  })
  const traceDebugSummary = computed(() => {
    const lines = [
      `query: ${turnTraceState.value.query || 'N/A'}`,
      `action: ${humanizeTraceAction(String(compositionTrace.value.action || ''))}`,
      `target: ${tracePrimaryTarget.value}`,
      `status: ${structuredStatusLabel.value}`,
      `changed_blocks: ${traceChangedBlocks.value.map((item) => `${item.id}(${item.type})`).join(', ') || 'none'}`,
      `warnings: ${traceWarnings.value.map((item) => humanizeTraceWarning(String(item))).join('；') || 'none'}`,
      `timeline: ${traceTimeline.value.map((item) => `${item.worker}:${item.event}`).join(' -> ') || 'none'}`,
    ]
    if (compositionTrace.value.reason) {
      lines.push(`reason: ${compositionTrace.value.reason}`)
    }
    return lines.join('\n')
  })
  const copyTraceDebugSummary = async () => {
    try {
      await navigator.clipboard.writeText(traceDebugSummary.value)
      copiedDebugSummary.value = true
      window.setTimeout(() => {
        copiedDebugSummary.value = false
      }, 1800)
    } catch (error) {
      console.error('复制 trace 摘要失败', error)
    }
  }

  const copyStructuredTraceExport = async () => {
    traceExportPending.value = true
    try {
      const copied = await chatStore.copyCurrentTraceExport()
      if (copied) {
        copiedTraceExport.value = true
        window.setTimeout(() => {
          copiedTraceExport.value = false
        }, 1800)
      }
    } finally {
      traceExportPending.value = false
    }
  }

  const downloadStructuredTraceExport = async () => {
    traceExportPending.value = true
    try {
      await chatStore.downloadCurrentTraceExport()
    } finally {
      traceExportPending.value = false
    }
  }

  const noteFactBindings = computed<Array<{ block_id: string; bindings: FactBinding[] }>>(() =>
    Array.isArray(noteDocumentState.value?.fact_bindings) ? noteDocumentState.value.fact_bindings : [],
  )
  const currentAgentName = computed(() => String(inspectorAgentic.value?.current_agent || turnTraceState.value?.agentic_runtime?.current_agent || 'orchestrator'))
  const currentStageName = computed(() => String(inspectorAgentic.value?.current_stage || turnTraceState.value?.agentic_runtime?.current_stage || 'intent_decision'))
  const selectedSkills = computed(() => {
    const fromInspector = Array.isArray(inspectorAgentic.value?.selected_skills) ? inspectorAgentic.value.selected_skills : []
    const fromTrace = Array.isArray(turnTraceState.value?.agentic_runtime?.selected_skills) ? turnTraceState.value.agentic_runtime.selected_skills : []
    return [...new Set([...fromInspector, ...fromTrace].map((item) => String(item || '')).filter(Boolean))]
  })
  const recommendedSkills = computed(() => {
    const raw = inspectorAgentic.value?.recommended_skills
    return Array.isArray(raw) ? raw.map((item) => String(item || '')).filter(Boolean) : []
  })
  const currentFailurePoint = computed(() => String(inspectorAgentic.value?.failure_point || turnTraceState.value?.agentic_runtime?.failure_point || ''))
  const agentSkillRows = computed(() => {
    const rows = Array.isArray(inspectorAgentic.value?.agents) ? inspectorAgentic.value.agents : []
    return rows.map((row) => ({
      name: String(row?.name || ''),
      executionResult: String(row?.execution_result || ''),
      selectedSkills: Array.isArray(row?.selected_skills) ? row.selected_skills.map((item) => String(item || '')).filter(Boolean) : [],
      toolPlan: Array.isArray(row?.tool_plan) ? row.tool_plan : [],
    })).filter((row) => row.name)
  })
  const agenticCards = computed(() => [
    {
      title: '当前阶段',
      value: currentStageName.value || 'intent_decision',
      helper: `当前 agent：${currentAgentName.value || 'orchestrator'}`,
      tone: 'cyan',
    },
    {
      title: '激活 Skills',
      value: selectedSkills.value.length ? selectedSkills.value.join(' / ') : '暂无',
      helper: recommendedSkills.value.length ? `推荐：${recommendedSkills.value.join(' / ')}` : '当前轮没有额外推荐 skill',
      tone: 'violet',
    },
    {
      title: '知识版本',
      value: String(inspectorAgentic.value?.knowledge_version || '未记录'),
      helper: currentFailurePoint.value ? `失败点：${currentFailurePoint.value}` : '当前轮没有显式失败点',
      tone: currentFailurePoint.value ? 'amber' : 'emerald',
    },
  ])
  const formatFactFieldLabels = (fields: unknown, labels?: unknown) => {
    if (Array.isArray(labels) && labels.length) {
      return labels.map((label) => String(label || '')).filter(Boolean)
    }
    if (!Array.isArray(fields)) return []
    return fields.map((field) => {
      const key = String(field || '')
      return FACT_FIELD_LABELS[key] || key
    }).filter(Boolean)
  }

  const confirmFact = async (field: string, value: string, sources: string[] = []) => {
    await chatStore.confirmFactValue(field, value, sources)
  }

  return {
    agentMetaState,
    inspectorSummaryState,
    benchmarkOverviewState,
    evaluationOverviewState,
    inspectorFocus,
    inspectorDocument,
    inspectorExecution,
    inspectorBuilder,
    inspectorFacts,
    inspectorRetrieval,
    inspectorAgentic,
    inspectorAssets,
    inspectorSuggestions,
    inspectorHeadline,
    inspectorStatus,
    builderPromptModeLabel,
    getInspectorStatusClasses,
    getInspectorStatusLabel,
    overviewCards,
    getOverviewCardClasses,
    getAssetSupportBadgeClasses,
    humanizeAssetSupport,
    benchmarkSummary,
    benchmarkRag,
    benchmarkCache,
    benchmarkExecution,
    benchmarkDistributions,
    benchmarkSessions,
    benchmarkRecommendations,
    benchmarkSessionCount,
    benchmarkActiveDocumentCount,
    benchmarkScenarioRows,
    benchmarkComponentRows,
    benchmarkThemeRows,
    benchmarkEntityRows,
    benchmarkCards,
    benchmarkGeneratedAt,
    evaluationCategories,
    evaluationSuite,
    evaluationSessions,
    evaluationRecommendations,
    evaluationSummary,
    evaluationOverallScore,
    evaluationOverallStatus,
    evaluationGeneratedAt,
    evaluationScenarioRows,
    evaluationCategoryRows,
    evaluationMissingScenarios,
    evaluationObservedScenarios,
    evaluationCards,
    getEvaluationStatusClasses,
    knowledge,
    factSources,
    factConflicts,
    factConfidence,
    retrievalSummary,
    retrievalEval,
    knowledgeRecords,
    retrievalHits,
    retrievalQueryVariants,
    retrievalHitScopes,
    retrievalStrategy,
    retrievalGroundingStatus,
    retrievalFreshness,
    retrievalNoHitReason,
    retrievalPrimaryQuery,
    retrievalPolicyName,
    retrievalPolicyPath,
    retrievalCitationCount,
    retrievalImageCount,
    retrievalCacheHit,
    retrievalCacheFreshness,
    retrievalCacheKey,
    retrievalCacheAgeSeconds,
    retrievalCacheTtlSeconds,
    retrievalCacheRemainingTtlSeconds,
    retrievalLiveSearchUsed,
    retrievalHitCount,
    retrievalIngestMode,
    retrievalRecordCount,
    retrievalFreshRecordCount,
    retrievalStaleRecordCount,
    retrievalCitationCoverage,
    retrievalGroundingScore,
    retrievalSourceQuality,
    retrievalRecommendation,
    retrievalRerankApplied,
    getGroundingToneClasses,
    humanizeGroundingStatus,
    humanizeRetrievalStrategy,
    humanizeRetrievalScope,
    humanizeRetrievalIngestMode,
    humanizeCacheFreshness,
    humanizeSourceQuality,
    getSourceQualityClasses,
    confirmedFacts,
    plannerOutputState,
    plannerPolicyState,
    noteDocumentState,
    plannerIntents,
    plannerScenarioScores,
    noteBlocks,
    noteAssets,
    noteScenarios,
    documentThemeLabel,
    noteBlockCapabilityRows,
    patchTrackMap,
    runtimeBackends,
    turnTraceState,
    traceTimeline,
    traceWarnings,
    traceChangedBlocks,
    compositionTrace,
    workspaceActionTrace,
    activeExecutionTrace,
    humanizeTraceWarning,
    humanizeTraceEvent,
    humanizeTraceAction,
    traceSummaryTone,
    tracePrimaryTarget,
    copiedDebugSummary,
    copiedTraceExport,
    traceExportPending,
    traceStructuredStatus,
    tracePrimarySignal,
    traceDiagnostics,
    getTraceEventToneClasses,
    getTraceMarkerClasses,
    getDiagnosticToneClasses,
    getTraceWarningBadgeClasses,
    getTraceWarningBadgeLabel,
    getStructuredStatusClasses,
    structuredStatusLabel,
    traceDebugSummary,
    copyTraceDebugSummary,
    copyStructuredTraceExport,
    downloadStructuredTraceExport,
    noteFactBindings,
    currentAgentName,
    currentStageName,
    selectedSkills,
    recommendedSkills,
    currentFailurePoint,
    agentSkillRows,
    agenticCards,
    formatFactFieldLabels,
    confirmFact,
  }
}
