<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import AgentInspectorJsonTree from './AgentInspectorJsonTree.vue'
import { useAgentInspectorDiagnostics } from './useAgentInspectorDiagnostics'

const props = withDefaults(defineProps<{
  scope?: 'session' | 'global'
}>(), {
  scope: 'session',
})

const chatStore = useChatStore()
const {
  renderPageData,
  renderStyleData,
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
} = storeToRefs(chatStore)

const activeTab = ref<'meta' | 'dsl' | 'plan' | 'rag' | 'evaluation' | 'benchmark' | 'patch' | 'trace'>(props.scope === 'global' ? 'benchmark' : 'meta')
const JsonTree = AgentInspectorJsonTree

const tabs = computed(() => (
  props.scope === 'global'
    ? [
        { id: 'benchmark', name: 'Benchmark', icon: '📊' },
        { id: 'evaluation', name: '评估', icon: '🧪' },
      ]
    : [
        { id: 'meta', name: '总览', icon: '⚡' },
        { id: 'trace', name: '本轮追踪', icon: '📍' },
        { id: 'plan', name: '策略规划', icon: '🧭' },
        { id: 'rag', name: '事实与检索', icon: '🔍' },
        { id: 'patch', name: '补丁历史', icon: '💉' },
        { id: 'dsl', name: '原始协议', icon: '🛠️' },
      ]
))

const metaInfo = computed(() => [
  { label: '创作者人设', value: chatStore.creatorPersona || '默认博主', color: 'text-yellow-400' },
  { label: '当前执行角色', value: chatStore.activeWorker || 'IDLE', color: 'text-pink-400' },
  { label: 'Checkpoint', value: chatStore.activeCheckpointId?.slice(0, 8) || 'NONE', color: 'text-gray-500' },
])

const {
  knowledge,
  factSources,
  factConflicts,
  factConfidence,
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
  inspectorFocus,
  inspectorDocument,
  inspectorExecution,
  inspectorBuilder,
  inspectorSuggestions,
  inspectorHeadline,
  inspectorStatus,
  inspectorAgentic,
  builderPromptModeLabel,
  getInspectorStatusClasses,
  getInspectorStatusLabel,
  overviewCards,
  agenticCards,
  getOverviewCardClasses,
  getAssetSupportBadgeClasses,
  humanizeAssetSupport,
  benchmarkSummary,
  benchmarkRag,
  benchmarkCache,
  benchmarkExecution,
  benchmarkSessions,
  benchmarkRecommendations,
  benchmarkScenarioRows,
  benchmarkComponentRows,
  benchmarkThemeRows,
  benchmarkEntityRows,
  benchmarkCards,
  benchmarkGeneratedAt,
  evaluationCategories,
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
  evaluationSessions,
  getEvaluationStatusClasses,
  getTraceEventToneClasses,
  getTraceMarkerClasses,
  getDiagnosticToneClasses,
  getTraceWarningBadgeClasses,
  getTraceWarningBadgeLabel,
  humanizeTraceAction,
  humanizeTraceWarning,
  tracePrimaryTarget,
  copiedDebugSummary,
  copiedTraceExport,
  traceExportPending,
  traceStructuredStatus,
  tracePrimarySignal,
  traceDiagnostics,
  getStructuredStatusClasses,
  structuredStatusLabel,
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
  formatFactFieldLabels,
  confirmFact,
} = useAgentInspectorDiagnostics({
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
})
</script>

<template>
  <div class="bg-[#1e1e1e] text-gray-400 rounded-[26px] font-sans text-xs shadow-2xl border border-[#333] w-full overflow-hidden flex flex-col h-full min-h-[720px]">
    <div v-if="props.scope === 'session'" class="shrink-0 border-b border-[#333] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] px-6 py-5 lg:px-7">
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
            当前焦点：{{ inspectorFocus.entity_name || '未识别主体' }} · 场景 {{ (inspectorFocus.scenarios || []).join(' / ') || 'notes' }} · 命中 {{ inspectorExecution.target_block_id || inspectorFocus.selected_block_id || 'global' }}
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
    <div v-else class="shrink-0 border-b border-[#333] bg-[radial-gradient(circle_at_top_left,_rgba(139,92,246,0.12),_transparent_35%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] px-6 py-5 lg:px-7">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center gap-1 rounded-full border border-violet-700/30 bg-violet-950/15 px-2 py-1 text-[9px] font-bold text-violet-300">
              <span>📊</span>
              <span>全局观测</span>
            </span>
          </div>
          <div class="text-[14px] font-bold text-gray-100">Benchmark 与 Evaluation</div>
          <div class="text-[10px] leading-relaxed text-gray-400 max-w-3xl">
            这里展示跨会话、全局级的稳定性与评估结果，不再混入当前会话的事实确认或块级编辑交互。
          </div>
        </div>
        <div class="grid min-w-[240px] grid-cols-2 gap-2 sm:min-w-[320px]">
          <div class="rounded-2xl border border-violet-800/25 bg-violet-950/10 p-3">
            <div class="text-[9px] uppercase tracking-widest text-gray-500">Benchmark</div>
            <div class="mt-1 text-[12px] font-bold text-gray-100">{{ benchmarkCards[0]?.value || 0 }}</div>
            <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ benchmarkCards[0]?.helper || '暂无聚合会话。' }}</div>
          </div>
          <div class="rounded-2xl border border-cyan-800/25 bg-cyan-950/10 p-3">
            <div class="text-[9px] uppercase tracking-widest text-gray-500">Evaluation</div>
            <div class="mt-1 text-[12px] font-bold text-gray-100">{{ evaluationOverallScore.toFixed(1) }}</div>
            <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ evaluationSummary || '暂无评估摘要。' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 头部 Tabs -->
    <div class="sticky top-0 z-20 shrink-0 border-b border-[#333] bg-[linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,0.96))] px-4 py-3 backdrop-blur-xl lg:px-5">
      <div class="flex flex-wrap gap-2">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'px-3 py-2 text-[10px] font-bold rounded-xl transition-all flex items-center justify-center gap-1.5 border',
            activeTab === tab.id ? 'border-blue-500/40 text-blue-300 bg-blue-950/20 shadow-[0_10px_24px_rgba(37,99,235,0.14),inset_0_1px_0_rgba(255,255,255,0.03)] -translate-y-[1px]' : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-[#2d2d2d]'
          ]"
        >
          <span>{{ tab.icon }}</span>
          <span>{{ tab.name }}</span>
        </button>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto p-4 lg:p-5 xl:p-6 custom-scrollbar bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.05),_transparent_26%),linear-gradient(180deg,_#1e1e1e,_#1b1b1c)]">
      
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

        <div class="mt-4 space-y-2">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest">Agent 白盒</div>
          <div class="grid gap-2 md:grid-cols-3">
            <div
              v-for="card in agenticCards"
              :key="card.title"
              class="rounded-2xl border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
              :class="getOverviewCardClasses(card.tone)"
            >
              <div class="text-[9px] uppercase tracking-widest text-gray-500">{{ card.title }}</div>
              <div class="mt-1 text-[12px] font-bold text-gray-100 break-words">{{ card.value }}</div>
              <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ card.helper }}</div>
            </div>
          </div>
          <div v-if="agentSkillRows.length" class="grid gap-2">
            <div
              v-for="row in agentSkillRows"
              :key="row.name"
              class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
            >
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="text-[10px] font-bold text-gray-100">{{ row.name }}</div>
                <span class="rounded-full border border-cyan-700/25 bg-cyan-950/10 px-2 py-0.5 text-[8px] font-bold text-cyan-300">
                  {{ row.executionResult || 'unknown' }}
                </span>
              </div>
              <div class="mt-2 text-[9px] text-gray-400">
                skills：{{ row.selectedSkills.length ? row.selectedSkills.join(' / ') : '暂无' }}
              </div>
            </div>
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

        <div class="mt-6 text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Render Page Snapshot</div>
        <JsonTree :data="renderPageData" label="UI_PROJECT_STATE" />
        
        <div class="mt-6 text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Render Style Snapshot</div>
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
        <div class="rounded-2xl border border-cyan-800/20 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.12),_transparent_38%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <span class="inline-flex items-center rounded-full border px-2 py-1 text-[9px] font-bold" :class="getGroundingToneClasses(retrievalGroundingStatus)">
                  {{ humanizeGroundingStatus(retrievalGroundingStatus) }}
                </span>
                <span class="inline-flex items-center rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 text-[9px] font-bold text-cyan-300">
                  {{ humanizeRetrievalStrategy(retrievalStrategy) }}
                </span>
                <span v-if="retrievalCacheHit" class="inline-flex items-center rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[9px] font-bold text-violet-300">
                  cache hit
                </span>
                <span v-if="retrievalLiveSearchUsed" class="inline-flex items-center rounded-full border border-emerald-700/30 bg-emerald-950/10 px-2 py-1 text-[9px] font-bold text-emerald-300">
                  live search
                </span>
              </div>
              <div class="text-[12px] font-bold text-gray-100">这轮 RAG 怎么搜、搜到了什么、最后引用了哪些证据</div>
              <div class="text-[10px] leading-relaxed text-gray-400">
                {{ retrievalPrimaryQuery || '当前这轮还没有正式检索 query。' }}
              </div>
              <div class="flex flex-wrap items-center gap-2 text-[9px]">
                <span v-if="retrievalPolicyName" class="inline-flex items-center rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 font-bold text-cyan-300">
                  {{ retrievalPolicyName }}
                </span>
                <span class="inline-flex items-center rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 font-bold text-slate-200">
                  {{ humanizeRetrievalIngestMode(retrievalIngestMode) }}
                </span>
                <span class="inline-flex items-center rounded-full border px-2 py-1 font-bold" :class="getSourceQualityClasses(retrievalSourceQuality)">
                  {{ humanizeSourceQuality(retrievalSourceQuality) }}
                </span>
                <span v-if="retrievalRerankApplied" class="inline-flex items-center rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 font-bold text-violet-300">
                  rerank applied
                </span>
                <span v-if="retrievalRecommendation" class="text-[9px] leading-relaxed text-gray-500">
                  {{ retrievalRecommendation }}
                </span>
              </div>
              <div v-if="retrievalPolicyPath" class="text-[9px] leading-relaxed text-gray-500">
                policy path: {{ retrievalPolicyPath }}
              </div>
              <div v-if="retrievalNoHitReason" class="text-[10px] leading-relaxed text-amber-300">
                {{ retrievalNoHitReason }}
              </div>
            </div>
            <div class="grid min-w-[220px] grid-cols-2 gap-2">
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">引用数</div>
                <div class="mt-1 text-[13px] font-bold text-emerald-300">{{ retrievalCitationCount }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">命中分组</div>
                <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ retrievalHitScopes.length || retrievalHitCount }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">图片证据</div>
                <div class="mt-1 text-[13px] font-bold text-violet-300">{{ retrievalImageCount }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">新鲜度</div>
                <div class="mt-1 text-[13px] font-bold text-amber-300">{{ retrievalFreshness }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">缓存状态</div>
                <div class="mt-1 text-[13px] font-bold text-violet-300">{{ humanizeCacheFreshness(retrievalCacheFreshness) }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">沉淀记录</div>
                <div class="mt-1 text-[13px] font-bold text-slate-200">{{ retrievalRecordCount }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">新鲜/过期</div>
                <div class="mt-1 text-[13px] font-bold text-slate-200">{{ retrievalFreshRecordCount }}/{{ retrievalStaleRecordCount }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">引用覆盖率</div>
                <div class="mt-1 text-[13px] font-bold text-emerald-300">{{ Math.round(retrievalCitationCoverage * 100) }}%</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Grounding 分</div>
                <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ retrievalGroundingScore.toFixed(2) }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="retrievalCacheHit || retrievalCacheKey" class="space-y-2">
          <div class="flex items-center gap-2 bg-violet-900/10 text-violet-400 p-2 rounded-lg border border-violet-800/20">
            <span>🧊</span>
            <span class="font-bold">缓存诊断</span>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-2">
              <div class="text-[10px] font-bold text-gray-200">缓存键</div>
              <div class="text-[10px] text-gray-400 break-all">{{ retrievalCacheKey || '本轮未写入缓存键' }}</div>
            </div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 grid grid-cols-3 gap-2 text-center">
              <div>
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Age</div>
                <div class="mt-1 text-[12px] font-bold text-slate-200">{{ retrievalCacheAgeSeconds }}s</div>
              </div>
              <div>
                <div class="text-[9px] uppercase tracking-wider text-gray-500">TTL</div>
                <div class="mt-1 text-[12px] font-bold text-cyan-300">{{ retrievalCacheTtlSeconds }}s</div>
              </div>
              <div>
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Remaining</div>
                <div class="mt-1 text-[12px] font-bold text-emerald-300">{{ retrievalCacheRemainingTtlSeconds }}s</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="knowledgeRecords.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-slate-900/30 text-slate-200 p-2 rounded-lg border border-slate-700/20">
            <span>🗃️</span>
            <span class="font-bold">知识沉淀快照</span>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div v-for="record in knowledgeRecords.slice(0, 4)" :key="record.record_id || `${record.source}-${record.title}`" class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-2">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-[10px] font-bold text-gray-200 leading-tight">{{ record.title || record.source_title || '未命名知识' }}</div>
                  <div class="mt-1 text-[9px] text-gray-500">{{ record.doc_type || 'fact' }} · {{ record.source_scope || 'general' }}</div>
                </div>
                <span class="rounded-full border px-2 py-0.5 text-[8px] font-bold" :class="getSourceQualityClasses(String(record.trust_level || 'unknown'))">
                  {{ String(record.trust_level || 'unknown') }}
                </span>
              </div>
              <div class="text-[10px] leading-relaxed text-gray-400">{{ record.snippet || record.content || '暂无摘要' }}</div>
              <div class="grid grid-cols-2 gap-2 text-[9px] text-gray-500">
                <div>updated: {{ record.updated_at || 'N/A' }}</div>
                <div>expires: {{ record.expires_at || 'N/A' }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="retrievalQueryVariants.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-cyan-900/10 text-cyan-400 p-2 rounded-lg border border-cyan-800/20">
            <span>🧭</span>
            <span class="font-bold">检索策略与 Query 变体</span>
          </div>
          <div class="grid gap-2">
            <div v-for="(query, idx) in retrievalQueryVariants" :key="`${query}-${idx}`" class="rounded-2xl border border-[#333] bg-[#252526] p-3">
              <div class="flex items-center justify-between gap-2">
                <div class="text-[10px] font-bold text-gray-200">{{ humanizeRetrievalScope(retrievalHits[idx]?.scope || retrievalHitScopes[idx] || '') }}</div>
                <span class="rounded-full border border-cyan-800/25 bg-cyan-950/10 px-2 py-0.5 text-[8px] font-bold text-cyan-300">
                  {{ retrievalHits[idx]?.count || 0 }} hits
                </span>
              </div>
              <div class="mt-2 text-[10px] leading-relaxed text-gray-400">{{ query }}</div>
            </div>
          </div>
        </div>

        <div v-if="retrievalHits.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-violet-900/10 text-violet-400 p-2 rounded-lg border border-violet-800/20">
            <span>📚</span>
            <span class="font-bold">命中概览</span>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div v-for="hit in retrievalHits" :key="`${hit.scope}-${hit.query}`" class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-2">
              <div class="flex items-center justify-between gap-2">
                <div class="text-[10px] font-bold text-gray-200">{{ humanizeRetrievalScope(String(hit.scope || '')) }}</div>
                <span class="rounded-full border border-violet-800/25 bg-violet-950/10 px-2 py-0.5 text-[8px] font-bold text-violet-300">
                  {{ hit.count || 0 }} 命中
                </span>
              </div>
              <div class="text-[10px] text-gray-400 leading-relaxed">{{ hit.query }}</div>
              <div v-if="Array.isArray(hit.titles) && hit.titles.length" class="flex flex-wrap gap-1.5">
                <span v-for="title in hit.titles" :key="title" class="rounded-full border border-[#3a3a3a] bg-black/10 px-2 py-1 text-[8px] text-gray-300">
                  {{ title }}
                </span>
              </div>
            </div>
          </div>
        </div>

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
                @click="chatStore.setWorkspaceMode('session_knowledge')"
                class="rounded-md border border-cyan-700/40 bg-cyan-900/10 px-2 py-1 text-[9px] font-bold text-cyan-300 transition-all hover:bg-cyan-900/20"
              >
                去会话知识处理
              </button>
            </div>
          </div>
        </div>

        <div v-if="factSources.length > 0" class="space-y-2">
          <div class="flex items-center gap-2 bg-emerald-900/10 text-emerald-400 p-2 rounded-lg border border-emerald-800/20">
            <span>📎</span>
            <span class="font-bold">本轮引用来源</span>
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
                :class="source.source_scope === 'official' || source.source_type === 'official' ? 'text-emerald-300 border-emerald-700/40 bg-emerald-900/10' : 'text-slate-400 border-slate-700/40 bg-slate-900/10'"
              >
                {{ source.source_scope === 'official' || source.source_type === 'official' ? 'official' : source.source_scope || 'web' }}
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

      <div v-if="activeTab === 'benchmark'" class="space-y-3 animate-in fade-in duration-300">
        <div class="rounded-2xl border border-violet-800/20 bg-[radial-gradient(circle_at_top_left,_rgba(139,92,246,0.14),_transparent_38%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <span class="inline-flex items-center rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[9px] font-bold text-violet-300">
                  system evaluation
                </span>
                <span v-if="benchmarkGeneratedAt" class="inline-flex items-center rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 text-[9px] font-bold text-slate-200">
                  {{ benchmarkGeneratedAt }}
                </span>
              </div>
              <div class="text-[12px] font-bold text-gray-100">跨会话 benchmark 面板：直接展示这套系统的 RAG、缓存和执行质量</div>
              <div class="text-[10px] leading-relaxed text-gray-400">
                这里不是看单轮 trace，而是看最近整批会话的平均表现，方便面试时证明系统稳定性和工程质量。
              </div>
            </div>
          </div>
        </div>

        <div class="grid gap-2 md:grid-cols-3">
          <div v-for="card in benchmarkCards" :key="card.title" class="rounded-2xl border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]" :class="getOverviewCardClasses(card.tone)">
            <div class="text-[9px] uppercase tracking-widest text-gray-500">{{ card.title }}</div>
            <div class="mt-2 text-[13px] font-bold text-gray-100">{{ card.value }}</div>
            <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ card.helper }}</div>
          </div>
        </div>

        <div v-if="benchmarkRecommendations.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-amber-900/10 text-amber-300 p-2 rounded-lg border border-amber-800/20">
            <span>🧠</span>
            <span class="font-bold">系统建议</span>
          </div>
          <div class="grid gap-2">
            <div v-for="(item, idx) in benchmarkRecommendations" :key="idx" class="rounded-2xl border border-[#333] bg-[#252526] p-3 text-[10px] leading-relaxed text-gray-300">
              {{ item }}
            </div>
          </div>
        </div>

        <div class="grid gap-3 xl:grid-cols-2">
          <div class="space-y-2">
            <div class="flex items-center gap-2 bg-cyan-900/10 text-cyan-300 p-2 rounded-lg border border-cyan-800/20">
              <span>🧭</span>
              <span class="font-bold">场景 / 主题分布</span>
            </div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-3">
              <div>
                <div class="text-[10px] uppercase tracking-widest text-gray-500">Scenarios</div>
                <div class="mt-2 grid gap-2">
                  <div v-for="item in benchmarkScenarioRows" :key="item.scenario" class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                    <div class="flex items-center justify-between gap-3 text-[10px]">
                      <span class="font-bold text-gray-200">{{ item.scenario }}</span>
                      <span class="font-mono text-cyan-300">{{ item.count }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div>
                <div class="text-[10px] uppercase tracking-widest text-gray-500">Themes</div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="item in benchmarkThemeRows" :key="item.theme_preset" class="rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[9px] font-bold text-violet-300">
                    {{ item.theme_preset }} · {{ item.count }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <div class="flex items-center gap-2 bg-violet-900/10 text-violet-300 p-2 rounded-lg border border-violet-800/20">
              <span>🧱</span>
              <span class="font-bold">组件 / 主体分布</span>
            </div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-3">
              <div>
                <div class="text-[10px] uppercase tracking-widest text-gray-500">Top Components</div>
                <div class="mt-2 grid gap-2">
                  <div v-for="item in benchmarkComponentRows" :key="item.component_type" class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                    <div class="flex items-center justify-between gap-3 text-[10px]">
                      <span class="font-bold text-gray-200">{{ item.component_type }}</span>
                      <span class="font-mono text-violet-300">{{ item.count }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div>
                <div class="text-[10px] uppercase tracking-widest text-gray-500">Top Entities</div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="item in benchmarkEntityRows" :key="item.entity_name" class="rounded-full border border-emerald-700/30 bg-emerald-950/10 px-2 py-1 text-[9px] font-bold text-emerald-300">
                    {{ item.entity_name }} · {{ item.count }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="grid gap-3 xl:grid-cols-2">
          <div class="space-y-2">
            <div class="flex items-center gap-2 bg-emerald-900/10 text-emerald-300 p-2 rounded-lg border border-emerald-800/20">
              <span>🔍</span>
              <span class="font-bold">RAG / Cache 指标</span>
            </div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 grid grid-cols-2 gap-2 text-center">
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">RAG 会话</div>
                <div class="mt-1 text-[12px] font-bold text-cyan-300">{{ Number(benchmarkRag.session_count || 0) }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Grounded 会话</div>
                <div class="mt-1 text-[12px] font-bold text-emerald-300">{{ Number(benchmarkRag.grounded_session_count || 0) }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">平均引用数</div>
                <div class="mt-1 text-[12px] font-bold text-violet-300">{{ Number(benchmarkRag.avg_citation_count || 0).toFixed(2) }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Fresh / Stale</div>
                <div class="mt-1 text-[12px] font-bold text-slate-200">{{ Number(benchmarkRag.avg_fresh_record_count || 0).toFixed(1) }}/{{ Number(benchmarkRag.avg_stale_record_count || 0).toFixed(1) }}</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Cache Hit</div>
                <div class="mt-1 text-[12px] font-bold text-violet-300">{{ Math.round(Number(benchmarkCache.cache_hit_rate || 0) * 100) }}%</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">Rerank</div>
                <div class="mt-1 text-[12px] font-bold text-cyan-300">{{ Math.round(Number(benchmarkCache.rerank_rate || 0) * 100) }}%</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">平均 Cache Age</div>
                <div class="mt-1 text-[12px] font-bold text-amber-300">{{ Number(benchmarkCache.avg_cache_age_seconds || 0).toFixed(1) }}s</div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">平均剩余 TTL</div>
                <div class="mt-1 text-[12px] font-bold text-emerald-300">{{ Number(benchmarkCache.avg_remaining_ttl_seconds || 0).toFixed(1) }}s</div>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <div class="flex items-center gap-2 bg-rose-900/10 text-rose-300 p-2 rounded-lg border border-rose-800/20">
              <span>🛠️</span>
              <span class="font-bold">执行与稳定性</span>
            </div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-2">
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">Builder 组件总数</span>
                  <span class="font-mono text-rose-300">{{ Number(benchmarkExecution.builder_component_total || 0) }}</span>
                </div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">Builder fallback 次数</span>
                  <span class="font-mono text-amber-300">{{ Number(benchmarkExecution.builder_fallback_total || 0) }}</span>
                </div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">Builder fallback rate</span>
                  <span class="font-mono text-amber-300">{{ Math.round(Number(benchmarkExecution.builder_fallback_rate || 0) * 100) }}%</span>
                </div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">Warning session rate</span>
                  <span class="font-mono text-rose-300">{{ Math.round(Number(benchmarkExecution.warning_rate || 0) * 100) }}%</span>
                </div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">平均变更区块数</span>
                  <span class="font-mono text-cyan-300">{{ Number(benchmarkSummary.avg_changed_block_count || 0).toFixed(2) }}</span>
                </div>
              </div>
              <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2">
                <div class="flex items-center justify-between gap-3 text-[10px]">
                  <span class="text-gray-500">页面生成率</span>
                  <span class="font-mono text-emerald-300">{{ Math.round(Number(benchmarkSummary.generated_session_rate || 0) * 100) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="benchmarkSessions.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-slate-900/30 text-slate-200 p-2 rounded-lg border border-slate-700/20">
            <span>🗂️</span>
            <span class="font-bold">最近会话样本</span>
          </div>
          <div class="grid gap-2">
            <div v-for="session in benchmarkSessions" :key="session.thread_id" class="rounded-2xl border border-[#333] bg-[#252526] p-3">
              <div class="flex flex-wrap items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-[10px] font-bold text-gray-200">{{ session.title || session.thread_id }}</div>
                  <div class="mt-1 text-[9px] text-gray-500">{{ session.thread_id }} · {{ session.updated_at }}</div>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span class="rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 text-[8px] font-bold text-cyan-300">{{ session.scenario || 'general' }}</span>
                  <span class="rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[8px] font-bold text-violet-300">{{ session.theme_preset || 'default' }}</span>
                  <span class="rounded-full border border-emerald-700/30 bg-emerald-950/10 px-2 py-1 text-[8px] font-bold text-emerald-300">{{ session.grounding_status || 'unknown' }}</span>
                </div>
              </div>
              <div class="mt-3 grid grid-cols-4 gap-2 text-center">
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Blocks</div>
                  <div class="mt-1 text-[11px] font-bold text-slate-200">{{ session.block_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Assets</div>
                  <div class="mt-1 text-[11px] font-bold text-slate-200">{{ session.asset_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Citations</div>
                  <div class="mt-1 text-[11px] font-bold text-emerald-300">{{ session.citation_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Warnings</div>
                  <div class="mt-1 text-[11px] font-bold text-amber-300">{{ session.warning_count || 0 }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'evaluation'" class="space-y-3 animate-in fade-in duration-300">
        <div class="rounded-2xl border border-emerald-800/20 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.14),_transparent_38%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <span class="inline-flex items-center rounded-full border px-2 py-1 text-[9px] font-bold" :class="getEvaluationStatusClasses(evaluationOverallStatus)">
                  评估总览
                </span>
                <span v-if="evaluationGeneratedAt" class="inline-flex items-center rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 text-[9px] font-bold text-slate-200">
                  {{ evaluationGeneratedAt }}
                </span>
              </div>
              <div class="text-[12px] font-bold text-gray-100">固定评测集 + 最近会话样本：统一评估路由、规划、执行、RAG、缓存和系统稳定性</div>
              <div class="text-[10px] leading-relaxed text-gray-400">
                {{ evaluationSummary || '这里展示的是正式评估结果，不是单轮 trace。' }}
              </div>
            </div>
          </div>
        </div>

        <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <div v-for="card in evaluationCards" :key="card.title" class="rounded-2xl border p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]" :class="getOverviewCardClasses(card.tone)">
            <div class="text-[9px] uppercase tracking-widest text-gray-500">{{ card.title }}</div>
            <div class="mt-2 text-[13px] font-bold text-gray-100">{{ card.value }}</div>
            <div class="mt-1 text-[9px] leading-relaxed text-gray-500">{{ card.helper }}</div>
          </div>
        </div>

        <div class="grid gap-3 xl:grid-cols-[1.3fr_0.7fr]">
          <div class="space-y-2">
            <div class="flex items-center gap-2 bg-emerald-900/10 text-emerald-300 p-2 rounded-lg border border-emerald-800/20">
              <span>📐</span>
              <span class="font-bold">六类评估结果</span>
            </div>
            <div class="grid gap-2">
              <div v-for="category in evaluationCategories" :key="category.name" class="rounded-2xl border border-[#333] bg-[#252526] p-3">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="min-w-0 space-y-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="text-[11px] font-bold text-gray-100">{{ category.name }}</span>
                      <span class="inline-flex items-center rounded-full border px-2 py-0.5 text-[9px] font-bold" :class="getEvaluationStatusClasses(category.status)">
                        {{ category.status }}
                      </span>
                    </div>
                    <div class="text-[10px] leading-relaxed text-gray-400">{{ category.summary }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-[9px] uppercase tracking-widest text-gray-500">Score</div>
                    <div class="text-[16px] font-bold text-gray-100">{{ Number(category.score || 0).toFixed(1) }}</div>
                  </div>
                </div>

                <div class="mt-3 grid gap-2 md:grid-cols-2">
                  <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2 text-[9px] leading-relaxed text-gray-300">
                    <div class="uppercase tracking-widest text-gray-500">评测集覆盖</div>
                    <div class="mt-1 font-mono text-emerald-300">
                      {{ category.covered_case_count || 0 }} / {{ category.suite_case_count || 0 }}
                      · {{ Math.round(Number(category.coverage_rate || 0) * 100) }}%
                    </div>
                  </div>
                  <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-3 py-2 text-[9px] leading-relaxed text-gray-300">
                    <div class="uppercase tracking-widest text-gray-500">系统建议</div>
                    <div class="mt-1">{{ category.recommendation }}</div>
                  </div>
                </div>

                <div v-if="category.metrics" class="mt-3 flex flex-wrap gap-1.5">
                  <span
                    v-for="(metricValue, metricKey) in category.metrics"
                    :key="`${category.name}-${String(metricKey)}`"
                    class="rounded-full border border-[#3a3a3a] bg-black/10 px-2 py-1 text-[9px] font-bold text-gray-300"
                  >
                    {{ String(metricKey) }} · {{ typeof metricValue === 'number' ? Number(metricValue).toFixed(3).replace(/\\.000$/, '') : metricValue }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div class="space-y-2">
              <div class="flex items-center gap-2 bg-cyan-900/10 text-cyan-300 p-2 rounded-lg border border-cyan-800/20">
                <span>🧱</span>
                <span class="font-bold">评测集结构</span>
              </div>
              <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 space-y-3">
                <div>
                  <div class="text-[10px] uppercase tracking-widest text-gray-500">按维度</div>
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    <span v-for="row in evaluationCategoryRows" :key="row.category" class="rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 text-[9px] font-bold text-cyan-300">
                      {{ row.category }} · {{ row.count }}
                    </span>
                  </div>
                </div>
                <div>
                  <div class="text-[10px] uppercase tracking-widest text-gray-500">按场景</div>
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    <span v-for="row in evaluationScenarioRows" :key="row.scenario" class="rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[9px] font-bold text-violet-300">
                      {{ row.scenario }} · {{ row.count }}
                    </span>
                  </div>
                </div>
                <div>
                  <div class="text-[10px] uppercase tracking-widest text-gray-500">已覆盖场景</div>
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    <span v-for="scenario in evaluationObservedScenarios" :key="scenario" class="rounded-full border border-emerald-700/30 bg-emerald-950/10 px-2 py-1 text-[9px] font-bold text-emerald-300">
                      {{ scenario }}
                    </span>
                    <span v-if="!evaluationObservedScenarios.length" class="text-[9px] text-gray-500">暂无样本</span>
                  </div>
                </div>
                <div v-if="evaluationMissingScenarios.length">
                  <div class="text-[10px] uppercase tracking-widest text-gray-500">缺失场景</div>
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    <span v-for="scenario in evaluationMissingScenarios" :key="scenario" class="rounded-full border border-amber-700/30 bg-amber-950/10 px-2 py-1 text-[9px] font-bold text-amber-300">
                      {{ scenario }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="evaluationRecommendations.length" class="space-y-2">
              <div class="flex items-center gap-2 bg-amber-900/10 text-amber-300 p-2 rounded-lg border border-amber-800/20">
                <span>🧠</span>
                <span class="font-bold">评估建议</span>
              </div>
              <div class="grid gap-2">
                <div v-for="(item, idx) in evaluationRecommendations" :key="idx" class="rounded-2xl border border-[#333] bg-[#252526] p-3 text-[10px] leading-relaxed text-gray-300">
                  {{ item }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="evaluationSessions.length" class="space-y-2">
          <div class="flex items-center gap-2 bg-violet-900/10 text-violet-300 p-2 rounded-lg border border-violet-800/20">
            <span>🗂️</span>
            <span class="font-bold">最近评估样本</span>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div v-for="session in evaluationSessions" :key="session.thread_id" class="rounded-2xl border border-[#333] bg-[#252526] p-3">
              <div class="flex flex-wrap items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-[10px] font-bold text-gray-200">{{ session.title || session.thread_id }}</div>
                  <div class="mt-1 text-[9px] text-gray-500">{{ session.thread_id }} · {{ session.updated_at }}</div>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span class="rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 text-[8px] font-bold text-cyan-300">{{ session.scenario || 'general' }}</span>
                  <span class="rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 text-[8px] font-bold text-violet-300">{{ session.intent_route || '等待指令' }}</span>
                </div>
              </div>
              <div class="mt-3 grid grid-cols-4 gap-2 text-center">
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Blocks</div>
                  <div class="mt-1 text-[11px] font-bold text-slate-200">{{ session.block_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Changed</div>
                  <div class="mt-1 text-[11px] font-bold text-cyan-300">{{ session.changed_block_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Warnings</div>
                  <div class="mt-1 text-[11px] font-bold text-amber-300">{{ session.warning_count || 0 }}</div>
                </div>
                <div class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-2">
                  <div class="text-[8px] uppercase tracking-wider text-gray-500">Grounding</div>
                  <div class="mt-1 text-[11px] font-bold text-emerald-300">{{ session.grounding_status || 'unknown' }}</div>
                </div>
              </div>
            </div>
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
                  <button
                    @click="copyStructuredTraceExport"
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 text-[9px] font-bold text-slate-200 transition hover:border-violet-700/30 hover:text-violet-300"
                  >
                    <span>{{ copiedTraceExport ? '✅' : '🧾' }}</span>
                    <span>{{ copiedTraceExport ? '已复制 trace 包' : (traceExportPending ? '导出中...' : '复制结构化 trace') }}</span>
                  </button>
                  <button
                    @click="downloadStructuredTraceExport"
                    class="inline-flex items-center gap-1 rounded-full border border-slate-700/30 bg-slate-950/20 px-2 py-1 text-[9px] font-bold text-slate-200 transition hover:border-emerald-700/30 hover:text-emerald-300"
                  >
                    <span>⬇️</span>
                    <span>{{ traceExportPending ? '准备中...' : '下载 trace JSON' }}</span>
                  </button>
                </div>
                <div class="text-[12px] font-bold text-gray-100">{{ humanizeTraceAction(String(compositionTrace.action || '')) }}</div>
                <div class="text-[10px] leading-relaxed text-gray-300">{{ turnTraceState.query || '本轮没有记录到用户输入。' }}</div>
                <div class="text-[10px] leading-relaxed text-gray-500">{{ tracePrimarySignal.description }}</div>
                <div class="flex flex-wrap items-center gap-2 text-[9px]">
                  <span class="inline-flex items-center rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-1 font-bold text-violet-300">
                    当前 agent · {{ currentAgentName }}
                  </span>
                  <span class="inline-flex items-center rounded-full border border-cyan-700/30 bg-cyan-950/10 px-2 py-1 font-bold text-cyan-300">
                    当前阶段 · {{ currentStageName }}
                  </span>
                  <span
                    v-for="skill in selectedSkills"
                    :key="skill"
                    class="inline-flex items-center rounded-full border border-emerald-700/30 bg-emerald-950/10 px-2 py-1 font-bold text-emerald-300"
                  >
                    {{ skill }}
                  </span>
                </div>
                <div v-if="currentFailurePoint" class="text-[10px] leading-relaxed text-amber-300">
                  当前失败点：{{ currentFailurePoint }}
                </div>
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
                  <div class="mt-1 text-[13px] font-bold text-emerald-300 truncate">{{ compositionTrace.target_block_id || 'global' }}</div>
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

          <div v-if="agentSkillRows.length || recommendedSkills.length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">Skill Trace</div>
            <div class="grid gap-2 md:grid-cols-2">
              <div v-if="recommendedSkills.length" class="rounded-2xl border border-[#333] bg-[#252526] p-3">
                <div class="text-[10px] font-bold text-gray-100">knowledge plan 推荐 skills</div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span
                    v-for="skill in recommendedSkills"
                    :key="`recommended-${skill}`"
                    class="rounded-full border border-violet-700/30 bg-violet-950/10 px-2 py-0.5 text-[8px] font-bold text-violet-300"
                  >
                    {{ skill }}
                  </span>
                </div>
              </div>
              <div
                v-for="row in agentSkillRows"
                :key="`trace-${row.name}`"
                class="rounded-2xl border border-[#333] bg-[#252526] p-3"
              >
                <div class="flex items-center justify-between gap-2">
                  <div class="text-[10px] font-bold text-gray-100">{{ row.name }}</div>
                  <span class="rounded-full border border-cyan-700/25 bg-cyan-950/10 px-2 py-0.5 text-[8px] font-bold text-cyan-300">
                    {{ row.executionResult || 'unknown' }}
                  </span>
                </div>
                <div class="mt-2 text-[9px] text-gray-400">
                  {{ row.selectedSkills.length ? row.selectedSkills.join(' / ') : '暂无 skill' }}
                </div>
                <div v-if="row.toolPlan.length" class="mt-2 space-y-1">
                  <div
                    v-for="(toolRow, idx) in row.toolPlan"
                    :key="`${row.name}-${idx}`"
                    class="rounded-xl border border-[#3a3a3a] bg-black/10 px-2 py-1.5 text-[9px] text-gray-400"
                  >
                    <span class="font-bold text-gray-200">{{ toolRow.skill || row.name }}</span>
                    <span v-if="Array.isArray(toolRow.tool_hints) && toolRow.tool_hints.length">
                      · {{ toolRow.tool_hints.join(' / ') }}
                    </span>
                  </div>
                </div>
              </div>
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
              <div v-for="(item, idx) in traceTimeline" :key="item.event + '-' + item.worker + '-' + idx" class="relative">
                <div class="absolute -left-[26px] top-3 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[#1e1e1e] text-[9px] font-bold text-[#0b0b0b]" :class="getTraceMarkerClasses(String(item.event || ''))">{{ idx + 1 }}</div>
                <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div class="text-[11px] font-bold text-gray-100">{{ item.worker }}</div>
                      <div class="mt-1 text-[10px] text-gray-500">{{ humanizeTraceEvent(String(item.event || '')) }}</div>
                    </div>
                    <span class="rounded-full border px-2 py-0.5 text-[9px] font-bold" :class="getTraceEventToneClasses(String(item.event || ''))">{{ item.event }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="Object.keys(compositionTrace).length" class="space-y-2">
            <div class="text-[10px] text-gray-500 uppercase tracking-widest">结构化计划</div>
            <div class="rounded-2xl border border-[#333] bg-[#252526] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <JsonTree :data="compositionTrace" label="COMPOSITION_TRACE" />
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
      <span>OBS_DIGITAL_1.0</span>
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

