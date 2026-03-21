<script setup lang="ts">
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from '../../stores/useChatStore';
import type {
  AgentMeta,
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
} from '../../types/chat';

const chatStore = useChatStore();
const { renderPageData, renderStyleData, plannerOutput, plannerPolicy, noteDocument, scenarioTags, patchTracks, agentBackends, turnTrace, inspectorSummary, agentMeta } = storeToRefs(chatStore)
const activeTab = ref<'meta' | 'dsl' | 'plan' | 'rag' | 'patch' | 'trace'>('meta');
const agentMetaState = computed<AgentMeta>(() => agentMeta.value || {})

// 递归 JSON 树组件 (内部局部定义)
const JsonTree = {
  name: 'JsonTree',
  props: ['data', 'label'],
  template: `
    <div class="pl-3 border-l border-[#333] my-1">
      <details class="group" open>
        <summary class="cursor-pointer text-[11px] hover:text-blue-400 transition-colors list-none flex items-center gap-1">
          <span class="w-3 h-3 text-[8px] opacity-40 transition-transform group-open:rotate-90">▶</span>
          <span class="font-bold text-gray-500">{{ label }}:</span>
          <span v-if="!isObject(data)" class="text-blue-300 font-mono">{{ formatValue(data) }}</span>
          <span v-else class="text-[9px] opacity-30 italic">{ Object }</span>
        </summary>
        <div v-if="isObject(data)" class="pl-2 space-y-0.5 mt-1">
          <JsonTree v-for="(val, key) in data" :key="key" :data="val" :label="key" />
        </div>
      </details>
    </div>
  `,
  methods: {
    isObject: (val: any) => val !== null && typeof val === 'object',
    formatValue: (val: any) => typeof val === 'string' ? `"${val}"` : val
  }
};

const tabs = [
  { id: 'meta', name: '总览', icon: '⚡' },
  { id: 'trace', name: '本轮追踪', icon: '📍' },
  { id: 'plan', name: '策略规划', icon: '🧭' },
  { id: 'rag', name: '事实与检索', icon: '🔍' },
  { id: 'patch', name: '补丁历史', icon: '💉' },
  { id: 'dsl', name: '原始协议', icon: '🛠️' }
];

const metaInfo = computed(() => [
  { label: '创作者人设', value: chatStore.creatorPersona || '默认博主', color: 'text-yellow-400' },
  { label: '意图路由', value: chatStore.currentNode || 'IDLE', color: 'text-pink-400' },
  { label: 'Checkpoint', value: chatStore.activeCheckpointId?.slice(0, 8) || 'NONE', color: 'text-gray-500' }
]);

const inspectorSummaryState = computed<InspectorSummary>(() => inspectorSummary.value || agentMetaState.value.inspector_summary || {})
const inspectorFocus = computed(() => (inspectorSummaryState.value?.focus || {}) as Record<string, unknown>)
const inspectorDocument = computed(() => (inspectorSummaryState.value?.document || {}) as Record<string, unknown>)
const inspectorExecution = computed(() => (inspectorSummaryState.value?.execution || {}) as Record<string, unknown>)
const inspectorBuilder = computed(() => (inspectorSummaryState.value?.builder || {}))
const inspectorFacts = computed(() => (inspectorSummaryState.value?.facts || {}) as Record<string, unknown>)
const inspectorAssets = computed(() => (inspectorSummaryState.value?.assets || {}) as Record<string, unknown>)
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
    helper: `${(inspectorFocus.value.scenarios || []).join(' / ') || 'general'} · ${inspectorFocus.value.intent_route || '等待指令'}`,
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
])
const getOverviewCardClasses = (tone: string) => {
  if (tone === 'rose') return 'border-rose-800/25 bg-rose-950/10'
  if (tone === 'amber') return 'border-amber-800/25 bg-amber-950/10'
  if (tone === 'violet') return 'border-violet-800/25 bg-violet-950/10'
  if (tone === 'emerald') return 'border-emerald-800/25 bg-emerald-950/10'
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

const knowledge = computed<RetrievedKnowledge>(() => (agentMetaState.value.retrieved_knowledge || {}) as RetrievedKnowledge)
const factSources = computed(() => Array.isArray(knowledge.value?.fact_sources) ? knowledge.value.fact_sources : [])
const factConflicts = computed(() => Array.isArray(knowledge.value?.fact_conflicts) ? knowledge.value.fact_conflicts : [])
const factConfidence = computed(() => String(knowledge.value?.fact_confidence || 'unknown'))
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

const plannerOutputState = computed<PlannerOutput>(() => plannerOutput.value || {})
const plannerPolicyState = computed<PlannerPolicy>(() => plannerPolicy.value || {})
const noteDocumentState = computed<NoteDocument>(() => noteDocument.value || {})
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
  })
)
const patchTrackMap = computed<Record<string, unknown[]>>(() => (patchTracks.value as Record<string, unknown[]>) || {})
const runtimeBackends = computed(() => {
  const fromStore = agentBackends.value || {}
  if (Object.keys(fromStore).length) return fromStore
  return agentMetaState.value.agent_backends || {}
})
const turnTraceState = computed<TurnTrace>(() => turnTrace.value || agentMetaState.value.turn_trace || {})
const traceTimeline = computed(() => Array.isArray(turnTraceState.value?.timeline) ? turnTraceState.value.timeline : [])
const traceWarnings = computed(() => Array.isArray(turnTraceState.value?.warnings) ? turnTraceState.value.warnings : [])
const traceChangedBlocks = computed(() => Array.isArray(turnTraceState.value?.changed_blocks) ? turnTraceState.value.changed_blocks : [])
const noteEditorTrace = computed<ExecutionTrace>(() => (turnTraceState.value?.note_editor || {}) as ExecutionTrace)
const workspaceActionTrace = computed<ExecutionTrace>(() => (turnTraceState.value?.workspace_action || {}) as ExecutionTrace)
const activeExecutionTrace = computed(() => Object.keys(noteEditorTrace.value).length ? noteEditorTrace.value : workspaceActionTrace.value)

const TRACE_WARNING_LABELS: Record<string, string> = {
  noop: '本轮没有实际内容改动',
  fallback_used: '本轮触发了兜底路径',
  style_changed_without_content: '样式变化了，但内容没有变',
  auto_resume_guard: '命中过度续火保护',
  max_auto_resume_exceeded: '超过最大自动续火次数',
}

const TRACE_EVENT_LABELS: Record<string, string> = {
  node_start: '节点开始',
  node_end: '节点完成',
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
  workspace_confirm_fact: '确认事实',
  workspace_rollback_component: '组件回滚',
  workspace_select_region: '锁定区块',
  workspace_fork: '创建分支',
}

const humanizeTraceWarning = (warning: string) => TRACE_WARNING_LABELS[warning] || warning
const humanizeTraceEvent = (event: string) => TRACE_EVENT_LABELS[event] || event
const humanizeTraceAction = (action: string) => TRACE_ACTION_LABELS[action] || action || '未识别动作'
const traceSummaryTone = computed(() => traceWarnings.value.length ? 'warn' : 'ok')
const tracePrimaryTarget = computed(() => activeExecutionTrace.value.target_block_id || noteEditorTrace.value.block_id || turnTraceState.value.selected_element_id || 'global')
const copiedDebugSummary = ref(false)
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
  if (event === 'node_start') return 'cyan'
  if (event === 'node_end') return 'emerald'
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
    `action: ${humanizeTraceAction(String(noteEditorTrace.value.action || ''))}`,
    `target: ${tracePrimaryTarget.value}`,
    `status: ${structuredStatusLabel.value}`,
    `changed_blocks: ${traceChangedBlocks.value.map((item) => `${item.id}(${item.type})`).join(', ') || 'none'}`,
    `warnings: ${traceWarnings.value.map((item) => humanizeTraceWarning(String(item))).join('；') || 'none'}`,
    `timeline: ${traceTimeline.value.map((item) => `${item.node}:${item.event}`).join(' -> ') || 'none'}`,
  ]
  if (noteEditorTrace.value.reason) {
    lines.push(`reason: ${noteEditorTrace.value.reason}`)
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


const FACT_FIELD_LABELS: Record<string, string> = {
  battery_capacity: '电池容量',
  price: '价格',
}

const noteFactBindings = computed<Array<{ block_id: string; bindings: FactBinding[] }>>(() =>
  Array.isArray(noteDocumentState.value?.fact_bindings) ? noteDocumentState.value.fact_bindings : []
)
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
</script>

<template>
  <div class="bg-[#1e1e1e] text-gray-400 rounded-[26px] font-sans text-xs shadow-2xl border border-[#333] w-full overflow-hidden flex flex-col h-full min-h-[720px]">
    <div class="shrink-0 border-b border-[#333] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] px-6 py-5 lg:px-7">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0 space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <span class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[9px] font-bold" :class="getInspectorStatusClasses(inspectorStatus)">
              <span>{{ inspectorStatus === 'attention' ? '⚠️' : inspectorStatus === 'active' ? '✅' : '🛰️' }}</span>
              <span>{{ getInspectorStatusLabel(inspectorStatus) }}</span>
            </span>
            <span v-if="inspectorExecution.last_action" class="inline-flex items-center rounded-full border border-cyan-700/25 bg-cyan-950/10 px-2 py-1 text-[9px] font-bold text-cyan-300">
              最近动作 · {{ inspectorExecution.last_action }}
            </span>
          </div>
          <div class="text-[14px] font-bold text-gray-100">{{ inspectorHeadline }}</div>
          <div class="text-[10px] leading-relaxed text-gray-400 max-w-3xl">
            当前焦点：{{ inspectorFocus.entity_name || '未识别主体' }} · 场景 {{ (inspectorFocus.scenarios || []).join(' / ') || 'general' }} · 命中 {{ inspectorExecution.target_block_id || inspectorFocus.selected_block_id || 'global' }}
          </div>
        </div>
        <div class="grid min-w-[240px] grid-cols-2 gap-2 sm:min-w-[320px]">
          <div v-for="card in overviewCards" :key="card.title" class="rounded-2xl border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]" :class="getOverviewCardClasses(card.tone)">
            <div class="text-[9px] uppercase tracking-widest text-gray-500">{{ card.title }}</div>
            <div class="mt-1 text-[12px] font-bold text-gray-100 break-words">{{ card.value }}</div>
            <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ card.helper }}</div>
          </div>
        </div>
      </div>
      <div v-if="inspectorSuggestions.length" class="mt-3 flex flex-wrap gap-2">
        <span v-for="(tip, idx) in inspectorSuggestions" :key="idx" class="inline-flex items-center rounded-full border border-[#3a3a3a] bg-black/10 px-3 py-1 text-[9px] leading-relaxed text-gray-300">
          {{ tip }}
        </span>
      </div>
    </div>

    <!-- 头部 Tabs -->
    <div class="shrink-0 border-b border-[#333] bg-[#252526] px-4 py-3 lg:px-5">
      <div class="flex flex-wrap gap-2">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'px-3 py-2 text-[10px] font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 border',
            activeTab === tab.id ? 'border-blue-500/40 text-blue-300 bg-blue-950/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]' : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-[#2d2d2d]'
          ]"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.name }}</span>
        </button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto p-4 lg:p-5 xl:p-6 custom-scrollbar bg-[#1e1e1e]">
      
      <!-- Tab 1: 灵感架构 -->
      <div v-if="activeTab === 'meta'" class="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
        <div v-for="item in metaInfo" :key="item.label" class="flex items-center justify-between border-b border-[#333]/50 pb-2">
          <span class="text-gray-500 font-medium">{{ item.label }}:</span>
          <span :class="['font-mono font-bold', item.color]">{{ item.value }}</span>
        </div>
        
        <div class="mt-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest mb-2 flex justify-between items-center">
            <span>动态追踪雷达</span>
            <span class="text-[8px] bg-orange-900/30 text-orange-500 px-1 rounded animate-pulse">Live</span>
          </div>
          <div class="bg-[#2d2d2d]/50 p-3 rounded-lg border border-[#3c3c3c] flex flex-col gap-2">
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-gray-300">
                当前主体: 
                <span class="text-blue-400 font-bold ml-1">{{ knowledge?.entity_name || '未识别' }}</span>
              </span>
              <button 
                v-if="knowledge?.entity_name"
                @click="chatStore.trackTrend(String(knowledge.entity_name))"
                class="px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white text-[9px] rounded shadow-lg transition-all active:scale-95"
              >
                开启深度追踪
              </button>
            </div>
            <div class="text-[9px] text-gray-500 italic leading-tight">
              点击追踪后，后端将利用 Redis ZSet 提升权重并启动异步预热。
            </div>
          </div>
        </div>

        <div class="mt-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest mb-2">活跃标签</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="tag in noteScenarios" :key="tag" class="bg-blue-900/20 text-blue-400 px-2 py-0.5 rounded-full border border-blue-800/30 text-[9px] font-bold uppercase tracking-tighter">
              #{{ tag }}
            </span>
          </div>
        </div>

        <div v-if="Object.keys(runtimeBackends).length" class="mt-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest mb-2">Agent Runtime</div>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="(backend, name) in runtimeBackends"
              :key="name"
              class="bg-emerald-900/10 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-800/30 text-[9px] font-bold"
            >
              {{ name }} → {{ backend }}
            </span>
          </div>
        </div>

        <div v-if="chatStore.wsStatus === 'connecting'" class="mt-4 flex items-center gap-2 bg-yellow-900/10 text-yellow-500 p-2 rounded-lg border border-yellow-900/20 text-[10px]">
          <span class="animate-spin text-lg">⚡</span>
          <span>大脑引擎正在深度初始化...</span>
        </div>
      </div>

      <!-- Tab 2: 实时 DSL -->
      <div v-if="activeTab === 'dsl'" class="animate-in fade-in duration-300 font-mono">
        <div class="text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">NoteDocument</div>
        <JsonTree :data="noteDocument" label="NOTE_DOCUMENT" />

        <div class="mt-6 text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Legacy Page Data (Compat)</div>
        <JsonTree :data="renderPageData" label="UI_PROJECT_STATE" />
        
        <div class="mt-6 text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Legacy Style Library (Compat)</div>
        <JsonTree :data="renderStyleData" label="CSS_VARS" />
      </div>

      <!-- Tab 3: 策略规划 -->
      <div v-if="activeTab === 'plan'" class="space-y-3 animate-in fade-in duration-300">
        <div class="grid grid-cols-3 gap-2">
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">场景分布</div>
            <div class="mt-1 text-[11px] font-bold text-blue-400">{{ Object.keys(plannerScenarioScores).length || 0 }}</div>
          </div>
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">Block Intents</div>
            <div class="mt-1 text-[11px] font-bold text-violet-400">{{ plannerIntents.length }}</div>
          </div>
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">文档块数</div>
            <div class="mt-1 text-[11px] font-bold text-emerald-400">{{ noteBlocks.length }}</div>
          </div>
        </div>

        <div v-if="Object.keys(plannerScenarioScores).length" class="space-y-2">
          <div class="flex items-center gap-2 bg-blue-900/10 text-blue-400 p-2 rounded-lg border border-blue-800/20">
            <span>🧭</span>
            <span class="font-bold">混合场景权重</span>
          </div>
          <div class="grid gap-2">
            <div v-for="(score, name) in plannerScenarioScores" :key="name" class="bg-[#252526] p-3 rounded-lg border border-[#333]">
              <div class="flex items-center justify-between text-[10px] mb-1">
                <span class="font-bold text-gray-200">{{ name }}</span>
                <span class="font-mono text-blue-300">{{ Number(score).toFixed(2) }}</span>
              </div>
              <div class="h-2 rounded bg-[#1e1e1e] overflow-hidden border border-[#333]">
                <div class="h-full bg-gradient-to-r from-blue-600 to-cyan-400" :style="{ width: `${Math.min(100, Number(score) * 100)}%` }"></div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="plannerIntents.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-violet-900/10 text-violet-400 p-2 rounded-lg border border-violet-800/20">
            <span>🧱</span>
            <span class="font-bold">Block Intents</span>
          </div>
          <div class="grid gap-2">
            <div v-for="intent in plannerIntents" :key="intent.id" class="bg-[#252526] p-3 rounded-lg border border-[#333] space-y-1">
              <div class="flex items-center justify-between gap-2">
                <div class="text-[10px] font-bold text-gray-200">{{ intent.semantic_role || intent.intent_type || intent.id }}</div>
                <span class="text-[8px] px-1.5 py-0.5 rounded-full border text-violet-300 border-violet-700/40 bg-violet-900/10">{{ intent.preferred_component || 'auto' }}</span>
              </div>
              <div class="text-[9px] text-gray-500">importance: {{ intent.importance || 'medium' }}</div>
              <div v-if="intent.reasoning" class="text-[10px] text-gray-400 leading-tight">{{ intent.reasoning }}</div>
            </div>
          </div>
        </div>

        <div class="grid gap-3 md:grid-cols-2">
          <div class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">Planner Policy</div>
            <JsonTree :data="plannerPolicy" label="PLANNER_POLICY" />
          </div>
          <div class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">NoteDocument 概览</div>
            <div class="bg-[#252526] p-3 rounded-lg border border-[#333] space-y-2">
              <div class="flex items-center justify-between text-[10px]"><span class="text-gray-500">标题</span><span class="text-gray-200 font-bold">{{ noteDocumentState?.document_meta?.title || '未命名' }}</span></div>
              <div class="flex items-center justify-between text-[10px]"><span class="text-gray-500">主题</span><span class="text-emerald-300 font-mono">{{ documentThemeLabel }}</span></div>
              <div class="flex items-center justify-between text-[10px]"><span class="text-gray-500">资产数</span><span class="text-blue-300 font-mono">{{ noteAssets.length }}</span></div>
              <div class="flex items-center justify-between text-[10px]"><span class="text-gray-500">事实绑定</span><span class="text-yellow-300 font-mono">{{ noteFactBindings.length }}</span></div>
            </div>

            <div v-if="noteBlockCapabilityRows.length" class="mt-3 space-y-2">
              <div class="text-[10px] text-gray-500 uppercase tracking-widest">积木能力</div>
              <div class="grid gap-2">
                <div v-for="block in noteBlockCapabilityRows" :key="block.id" class="bg-[#1e1e1e] p-2 rounded-lg border border-[#333] space-y-1.5">
                  <div class="flex items-center justify-between gap-2">
                    <div class="min-w-0">
                      <div class="truncate text-[10px] font-bold text-gray-200">{{ block.label }}</div>
                      <div class="text-[9px] text-gray-500">{{ block.semanticRole }}</div>
                    </div>
                    <span class="rounded-full border px-2 py-0.5 text-[8px] font-bold" :class="getAssetSupportBadgeClasses(block.assetSupport)">
                      {{ humanizeAssetSupport(block.assetSupport) }}
                    </span>
                  </div>
                  <div class="text-[9px] text-gray-400">可编辑: {{ block.editableSummary }}</div>
                  <div class="text-[9px]" :class="block.factBindingSupport ? 'text-emerald-300' : 'text-slate-400'">
                    {{ block.factBindingSupport ? '支持事实绑定' : '无字段级事实绑定' }}
                  </div>
                </div>
              </div>
            </div>

            <div v-if="noteFactBindings.length" class="mt-3 space-y-2">
              <div class="text-[10px] text-gray-500 uppercase tracking-widest">字段级绑定</div>
              <div class="grid gap-2">
                <div v-for="binding in noteFactBindings" :key="binding.block_id" class="bg-[#1e1e1e] p-2 rounded-lg border border-[#333]">
                  <div class="text-[10px] font-bold text-gray-200">{{ binding.block_id }}</div>
                  <div v-for="item in binding.bindings || []" :key="`${binding.block_id}-${item.field}`" class="mt-1 text-[10px] text-gray-400">
                    <span class="text-slate-300">{{ item.field }}</span>
                    <span v-if="formatFactFieldLabels(item.fact_fields, item.fact_field_labels).length"> → {{ formatFactFieldLabels(item.fact_fields, item.fact_field_labels).join(' / ') }}</span>
                    <span v-if="item.sources?.length"> · 来源: {{ item.sources.join(' / ') }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab 3: 检索记忆 (RAG) -->
      <div v-if="activeTab === 'rag'" class="space-y-3 animate-in fade-in duration-300">
        <div class="grid grid-cols-3 gap-2">
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">置信度</div>
            <div
              class="mt-1 text-[11px] font-bold"
              :class="{
                'text-emerald-400': factConfidence === 'high',
                'text-yellow-400': factConfidence === 'medium',
                'text-rose-400': factConfidence === 'low',
              }"
            >
              {{ factConfidence }}
            </div>
          </div>
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">来源数</div>
            <div class="mt-1 text-[11px] font-bold text-blue-400">{{ factSources.length }}</div>
          </div>
          <div class="bg-[#252526] p-2 rounded-lg border border-[#333]">
            <div class="text-[9px] text-gray-500 uppercase tracking-wider">人工确认</div>
            <div
              class="mt-1 text-[11px] font-bold"
              :class="knowledge.needs_fact_confirmation ? 'text-rose-400' : 'text-emerald-400'"
            >
              {{ knowledge.needs_fact_confirmation ? '建议确认' : '当前无需' }}
            </div>
          </div>
        </div>

        <div v-if="confirmedFacts.length > 0" class="space-y-2">
          <div class="flex items-center gap-2 bg-emerald-900/10 text-emerald-400 p-2 rounded-lg border border-emerald-800/20">
            <span>✅</span>
            <span class="font-bold">已确认事实</span>
          </div>
          <div
            v-for="item in confirmedFacts"
            :key="item.field"
            class="bg-[#252526] p-3 rounded-lg border border-[#333] space-y-1"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-[10px] font-bold text-gray-200">{{ item.fieldLabel }}</div>
              <span class="text-[8px] px-1.5 py-0.5 rounded-full border text-emerald-300 border-emerald-700/40 bg-emerald-900/10">
                confirmed
              </span>
            </div>
            <div class="text-[10px] font-mono text-emerald-300">{{ item.value }}</div>
            <div v-if="item.sources.length" class="text-[9px] text-gray-500 leading-tight">
              来源: {{ item.sources.join(' / ') }}
            </div>
          </div>
        </div>

        <div v-if="factConflicts.length > 0" class="space-y-2">
          <div class="flex items-center gap-2 bg-rose-900/10 text-rose-400 p-2 rounded-lg border border-rose-800/20">
            <span>⚠️</span>
            <span class="font-bold">发现事实冲突，建议人工确认后再用于强结论</span>
          </div>
          <div
            v-for="conflict in factConflicts"
            :key="conflict.field"
            class="bg-[#252526] p-3 rounded-lg border border-[#333] space-y-2"
          >
            <div class="text-[10px] font-bold text-rose-300">{{ conflict.field }}</div>
            <div
              v-for="item in conflict.values"
              :key="item.value"
              class="rounded-lg border border-[#333] bg-[#1e1e1e] p-2 text-[10px] text-gray-300 leading-tight space-y-2"
            >
              <div>
                <span class="font-mono text-yellow-300">{{ item.value }}</span>
                <span class="text-gray-500"> ← {{ (item.sources || []).join(' / ') }}</span>
              </div>
              <button
                @click="confirmFact(conflict.field, item.value, item.sources || [])"
                :disabled="chatStore.factConfirmingField === conflict.field"
                class="rounded-md border px-2 py-1 text-[9px] font-bold transition-all"
                :class="chatStore.factConfirmingField === conflict.field
                  ? 'border-[#444] text-gray-500 bg-[#2a2a2a] cursor-not-allowed'
                  : 'border-emerald-700/40 text-emerald-300 bg-emerald-900/10 hover:bg-emerald-900/20'"
              >
                {{ chatStore.factConfirmingField === conflict.field ? '确认中...' : '采用这个值' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="factSources.length > 0" class="space-y-2">
          <div class="flex items-center gap-2 bg-emerald-900/10 text-emerald-400 p-2 rounded-lg border border-emerald-800/20">
            <span>📎</span>
            <span class="font-bold">本轮事实来源</span>
          </div>
          <div
            v-for="source in factSources"
            :key="source.url || source.title"
            class="bg-[#252526] p-3 rounded-lg border border-[#333] space-y-1"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-[10px] font-bold text-gray-200 leading-tight">{{ source.title || '未命名来源' }}</div>
              <span
                class="text-[8px] px-1.5 py-0.5 rounded-full border"
                :class="source.source_type === 'official' ? 'text-emerald-300 border-emerald-700/40 bg-emerald-900/10' : 'text-slate-400 border-slate-700/40 bg-slate-900/10'"
              >
                {{ source.source_type === 'official' ? 'official' : 'web' }}
              </span>
            </div>
            <div class="text-[9px] text-gray-500 break-all">{{ source.url }}</div>
            <div class="text-[10px] text-gray-400 leading-tight">{{ source.snippet }}</div>
          </div>
        </div>

        <!-- ✨ 4.0 增强：舆情对冲报告可视化 -->
        <div v-if="knowledge?.battle_report" class="space-y-2 mb-4">
          <div class="flex items-center gap-2 bg-gradient-to-r from-rose-900/20 to-blue-900/20 text-rose-400 p-2 rounded-lg border border-rose-800/20">
            <span class="animate-pulse">⚔️</span>
            <span class="font-bold uppercase tracking-tighter text-[10px]">Opinion Clash Report (天平对冲引擎)</span>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="bg-rose-950/20 p-2 rounded border border-rose-500/20">
              <div class="text-[8px] text-rose-500 font-bold mb-1">PROS AGENT</div>
              <div class="text-[10px] text-gray-300 leading-tight">{{ knowledge.battle_report.pros?.summary }}</div>
            </div>
            <div class="bg-blue-950/20 p-2 rounded border border-blue-500/20">
              <div class="text-[8px] text-blue-500 font-bold mb-1">CONS AGENT</div>
              <div class="text-[10px] text-gray-300 leading-tight">{{ knowledge.battle_report.cons?.summary }}</div>
            </div>
          </div>
        </div>

        <div v-if="!chatStore.thoughtText && !chatStore.nodeStreamOutput && !knowledge?.battle_report && factSources.length === 0 && factConflicts.length === 0" class="text-center py-10 opacity-30 italic text-[10px]">
          <div class="text-3xl mb-2">🔭</div>
          等待 Agent 激活搜索引擎...
        </div>
        <div v-else class="space-y-3">
          <div class="flex items-center gap-2 bg-blue-900/10 text-blue-400 p-2 rounded-lg border border-blue-800/20">
            <span class="animate-pulse">🔎</span>
            <span class="font-bold">深度联网调研中</span>
          </div>
          <div class="bg-[#000]/30 p-3 rounded-lg border border-[#333] font-mono text-[10px] leading-relaxed text-gray-400">
             {{ chatStore.thoughtText || chatStore.nodeStreamOutput }}
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'trace'" class="space-y-3 animate-in fade-in duration-300">
        <div v-if="!Object.keys(turnTraceState).length" class="rounded-2xl border border-dashed border-[#3a3a3a] bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.12),_transparent_45%),linear-gradient(180deg,_rgba(37,37,38,0.95),_rgba(30,30,30,1))] px-5 py-8 text-center">
          <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-cyan-900/30 bg-cyan-950/20 text-2xl shadow-[0_0_24px_rgba(34,211,238,0.12)]">🛰️</div>
          <div class="text-[12px] font-bold text-gray-200">本轮还没有可展示的追踪数据</div>
          <div class="mt-2 text-[10px] leading-relaxed text-gray-500">当你发送一轮生成或编辑请求后，这里会自动显示命中区块、结构化动作、真实变更和执行时间线。</div>
        </div>

        <template v-else>
          <div
            class="rounded-2xl border p-4 shadow-[0_18px_40px_rgba(0,0,0,0.22)]"
            :class="tracePrimarySignal.tone === 'warn' ? 'border-amber-800/30 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.16),_transparent_38%),linear-gradient(135deg,_rgba(41,32,16,0.78),_rgba(30,30,30,1))]' : 'border-emerald-800/25 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.14),_transparent_38%),linear-gradient(135deg,_rgba(18,41,34,0.74),_rgba(30,30,30,1))]'"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[9px] font-bold" :class="tracePrimarySignal.tone === 'warn' ? 'border-amber-700/30 text-amber-300 bg-amber-900/10' : 'border-emerald-700/30 text-emerald-300 bg-emerald-900/10'">
                    <span>{{ tracePrimarySignal.tone === 'warn' ? '⚠️' : '✅' }}</span>
                    <span>{{ tracePrimarySignal.label }}</span>
                  </span>
                  <span class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[9px] font-bold" :class="getStructuredStatusClasses(traceStructuredStatus)">
                    {{ structuredStatusLabel }}
                  </span>
                  <span class="inline-flex items-center gap-1 rounded-full border border-cyan-700/25 bg-cyan-950/10 px-2 py-1 text-[9px] font-bold text-cyan-300">
                    🎯 {{ tracePrimaryTarget }}
                  </span>
                  <button
                    @click="copyTraceDebugSummary"
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 text-[9px] font-bold text-slate-200 transition hover:border-cyan-700/30 hover:text-cyan-300"
                  >
                    <span>{{ copiedDebugSummary ? '✅' : '📋' }}</span>
                    <span>{{ copiedDebugSummary ? '已复制摘要' : '复制 debug 摘要' }}</span>
                  </button>
                </div>
                <div class="text-[12px] font-bold text-gray-100">{{ humanizeTraceAction(String(noteEditorTrace.action || '')) }}</div>
                <div class="text-[10px] leading-relaxed text-gray-300">{{ turnTraceState.query || '本轮没有记录到用户输入。' }}</div>
                <div class="text-[10px] leading-relaxed text-gray-500">{{ tracePrimarySignal.description }}</div>
              </div>
              <div class="grid min-w-[180px] grid-cols-2 gap-2">
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">变更区块</div>
                  <div class="mt-1 text-[13px] font-bold text-violet-300">{{ traceChangedBlocks.length }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">告警数</div>
                  <div class="mt-1 text-[13px] font-bold text-amber-300">{{ traceWarnings.length }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">时间线</div>
                  <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ traceTimeline.length }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">计划摘要</div>
                  <div class="mt-1 text-[13px] font-bold text-emerald-300 truncate">{{ noteEditorTrace.target_block_id || 'global' }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid gap-2 md:grid-cols-2">
            <div
              v-for="card in traceDiagnostics"
              :key="card.title"
              class="rounded-2xl border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
              :class="getDiagnosticToneClasses(card.tone)"
            >
              <div class="text-[9px] uppercase tracking-widest text-gray-500">{{ card.title }}</div>
              <div class="mt-2 text-[12px] font-bold text-gray-100">{{ card.description }}</div>
              <div class="mt-1 text-[10px] leading-relaxed text-gray-500">{{ card.helper }}</div>
            </div>
          </div>

          <div v-if="traceWarnings.length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">需要关注</div>
            <div class="grid gap-2">
              <div v-for="warning in traceWarnings" :key="warning" class="flex items-start gap-3 rounded-2xl border border-amber-800/25 bg-amber-950/15 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
                <div class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-amber-700/30 bg-amber-900/10 text-sm text-amber-300">⚠️</div>
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <div class="text-[10px] font-bold text-amber-300">{{ humanizeTraceWarning(String(warning)) }}</div>
                    <span class="inline-flex items-center rounded-full border px-2 py-0.5 text-[8px] font-bold" :class="getTraceWarningBadgeClasses(String(warning))">{{ getTraceWarningBadgeLabel(String(warning)) }}</span>
                  </div>
                  <div class="mt-1 text-[10px] text-gray-500 break-all">{{ warning }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="traceChangedBlocks.length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">实际变更</div>
            <div class="grid gap-2">
              <div v-for="item in traceChangedBlocks" :key="item.id" class="rounded-2xl border border-[#333] bg-[linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(29,29,29,1))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div class="flex flex-wrap items-center justify-between gap-2 text-[10px]">
                  <span class="font-bold text-gray-100">{{ item.id }}</span>
                  <span class="rounded-full border border-cyan-800/20 bg-cyan-950/15 px-2 py-0.5 font-mono text-[9px] text-cyan-300">{{ item.type }}</span>
                </div>
                <div class="mt-3 flex flex-wrap gap-1.5">
                  <span v-for="field in item.changed_fields || []" :key="field" class="rounded-full border border-blue-800/25 bg-blue-950/10 px-2 py-0.5 text-[9px] font-bold text-blue-300">{{ field }}</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="traceTimeline.length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">本轮时间线</div>
            <div class="relative pl-5 border-l border-[#333] space-y-3">
              <div v-for="(item, idx) in traceTimeline" :key="item.event + '-' + item.node + '-' + idx" class="relative">
                <div class="absolute -left-[26px] top-3 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[#1e1e1e] text-[9px] font-bold text-[#0b0b0b]" :class="getTraceMarkerClasses(String(item.event || ''))">{{ idx + 1 }}</div>
                <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div class="text-[11px] font-bold text-gray-100">{{ item.node }}</div>
                      <div class="mt-1 text-[10px] text-gray-500">{{ humanizeTraceEvent(String(item.event || '')) }}</div>
                    </div>
                    <span class="rounded-full border px-2 py-0.5 text-[9px] font-bold" :class="getTraceEventToneClasses(String(item.event || ''))">{{ item.event }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="Object.keys(noteEditorTrace).length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">结构化计划</div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <JsonTree :data="noteEditorTrace" label="NOTE_EDITOR_TRACE" />
            </div>
          </div>

          <div v-if="inspectorBuilder.component_count" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">积木构建摘要</div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] space-y-3">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div class="text-[12px] font-semibold text-gray-100">这轮组件是怎样落下来的</div>
                  <div class="mt-1 text-[10px] leading-relaxed text-gray-500">contract-first builder 会先按 manifest 收窄协议，再基于压缩后的事实/资产摘要填充组件，不再依赖大而全背景 prompt。</div>
                </div>
                <span class="inline-flex items-center rounded-full border border-rose-700/30 bg-rose-950/20 px-2 py-1 text-[9px] font-bold text-rose-300">
                  {{ builderPromptModeLabel }}
                </span>
              </div>
              <div class="grid gap-2 md:grid-cols-5">
                <div class="rounded-2xl border border-rose-800/25 bg-rose-950/10 p-3">
                  <div class="text-[9px] uppercase tracking-widest text-gray-500">组件数</div>
                  <div class="mt-1 text-[12px] font-bold text-gray-100">{{ inspectorBuilder.component_count }}</div>
                </div>
                <div class="rounded-2xl border border-amber-800/25 bg-amber-950/10 p-3">
                  <div class="text-[9px] uppercase tracking-widest text-gray-500">Fallback</div>
                  <div class="mt-1 text-[12px] font-bold text-gray-100">{{ inspectorBuilder.fallback_count || 0 }}</div>
                </div>
                <div class="rounded-2xl border border-cyan-800/25 bg-cyan-950/10 p-3">
                  <div class="text-[9px] uppercase tracking-widest text-gray-500">类型</div>
                  <div class="mt-1 text-[11px] font-bold text-gray-100 break-words">
                    {{ (inspectorBuilder.component_types || []).join(' / ') || 'N/A' }}
                  </div>
                </div>
                <div class="rounded-2xl border border-emerald-800/25 bg-emerald-950/10 p-3">
                  <div class="text-[9px] uppercase tracking-widest text-gray-500">事实摘要</div>
                  <div class="mt-1 text-[12px] font-bold text-gray-100">{{ inspectorBuilder.fact_summary_count || 0 }}</div>
                </div>
                <div class="rounded-2xl border border-violet-800/25 bg-violet-950/10 p-3">
                  <div class="text-[9px] uppercase tracking-widest text-gray-500">素材摘要</div>
                  <div class="mt-1 text-[12px] font-bold text-gray-100">{{ inspectorBuilder.asset_count || 0 }}</div>
                </div>
              </div>
              <div class="rounded-2xl border border-[#333] bg-black/10 p-3 text-[10px] leading-relaxed text-gray-400">
                当前模式：<span class="font-semibold text-gray-200">{{ builderPromptModeLabel }}</span>。
                这轮共过滤掉 <span class="font-semibold text-gray-200">{{ inspectorBuilder.contract_filter_count || 0 }}</span> 个越权字段，
                预检查告警 <span class="font-semibold text-gray-200">{{ inspectorBuilder.precheck_warning_count || 0 }}</span> 条。
              </div>
            </div>
          </div>

          <div v-if="Object.keys(turnTraceState).length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">完整 Trace</div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <JsonTree :data="turnTraceState" label="TURN_TRACE" />
            </div>
          </div>
        </template>
      </div>

      <!-- Tab 4: 视觉补丁 (Tracks) -->
      <div v-if="activeTab === 'patch'" class="animate-in fade-in duration-300">
        <div v-if="chatStore.selectedComponentId" class="space-y-4">
          <div class="flex items-center gap-2 bg-pink-900/10 text-pink-500 p-2 rounded-lg border border-pink-900/20 mb-4">
            <span>🎯</span>
            <span class="font-bold uppercase tracking-tighter">选中组件: {{ chatStore.selectedComponentId }}</span>
          </div>

          <!-- ✨ 核心：生长档案时间轴 -->
          <div v-if="patchTrackMap?.[chatStore.selectedComponentId]" class="relative pl-4 border-l border-[#333] space-y-6">
            <div 
              v-for="(track, idx) in patchTrackMap[chatStore.selectedComponentId]" 
              :key="idx"
              class="relative group"
            >
              <!-- 时间轴圆点 -->
              <div class="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#1e1e1e] bg-[#444] group-hover:bg-pink-500 transition-colors shadow-[0_0_8px_rgba(0,0,0,0.5)]"></div>
              
              <div class="flex flex-col gap-1.5">
                <div class="flex justify-between items-center">
                  <span class="text-[9px] font-mono text-gray-500">{{ new Date(track.timestamp).toLocaleString() }}</span>
                  <button 
                    @click="chatStore.rollbackComponent(chatStore.selectedComponentId!, idx)"
                    class="opacity-0 group-hover:opacity-100 text-[8px] bg-pink-600/20 hover:bg-pink-600 text-pink-400 hover:text-white px-1.5 py-0.5 rounded transition-all"
                  >
                    RESTORE
                  </button>
                </div>
                <div class="bg-[#2d2d2d] p-2.5 rounded-lg border border-[#3c3c3c] group-hover:border-pink-500/30 transition-all cursor-default">
                  <div class="text-[10px] text-gray-300 font-bold mb-1 italic">"{{ track.prompt }}"</div>
                  <div class="text-[9px] text-gray-500 leading-tight">{{ track.agent_thought }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="text-center py-10 opacity-30 italic text-[10px]">
            <div class="text-3xl mb-2">🧬</div>
            该组件暂无手术记录
          </div>
        </div>
        <div v-else class="text-center py-10 opacity-30 italic text-[10px]">
          <div class="text-3xl mb-2">💉</div>
          请在画布选中组件以查看微调历史
        </div>
      </div>

    </div>

    <!-- 底部栏 -->
    <div class="px-4 py-2 border-t border-[#333] bg-[#252526] text-[9px] text-gray-600 flex justify-between font-mono italic shrink-0">
      <span>OBS_V2.1.0</span>
      <span class="flex items-center gap-1">
        <span class="w-1 h-1 bg-green-500 rounded-full animate-ping"></span>
        STREAM_SYNCED
      </span>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 10px;
}
</style>
