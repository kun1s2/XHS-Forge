<template>
  <div data-testid="session-knowledge-workbench" class="mx-auto w-full max-w-6xl space-y-4 rounded-[26px] border border-[#333] bg-[#1e1e1e] p-5 text-gray-200 shadow-[0_18px_40px_rgba(0,0,0,0.22)] lg:p-6">
    <div class="flex flex-wrap items-start justify-between gap-3 border-b border-[#333] pb-4">
      <div class="space-y-2">
        <div class="flex items-center gap-2">
          <span class="rounded-full border border-cyan-800/30 bg-cyan-950/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-cyan-300">Session Workspace</span>
          <span class="rounded-full border border-blue-800/30 bg-blue-950/20 px-2 py-0.5 text-[10px] font-semibold text-blue-200">随 thread / branch / rollback 回退</span>
        </div>
        <div class="text-[15px] font-bold text-gray-100">会话知识工作台</div>
        <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">
          这里只放当前会话的候选知识、已确认知识和会话级资料导入。长期资产、Benchmark、Evaluation 已移到全局资产中心。
        </p>
      </div>
      <div class="grid min-w-[320px] grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">待审知识</div>
          <div class="mt-1 text-[13px] font-bold text-amber-300">{{ candidateGroups.length }}</div>
        </div>
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">会话知识</div>
          <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ sessionGroups.length }}</div>
        </div>
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">版本</div>
          <div class="mt-1 text-[13px] font-bold text-slate-200">{{ sessionKnowledgeVersion }}</div>
        </div>
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">当前 Checkpoint</div>
          <div class="mt-1 truncate text-[13px] font-bold text-blue-200">{{ sessionSnapshotStatus.checkpointId || 'pending' }}</div>
          <div class="mt-1 text-[9px] text-gray-500">来源：{{ snapshotSourceLabel }}</div>
        </div>
      </div>
    </div>

    <section
      v-if="hasArtifactContext"
      class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4"
    >
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">Artifact Version</div>
          <div class="mt-2 text-[13px] font-semibold text-gray-100">{{ artifact?.title || '当前购买决策档案' }}</div>
          <div class="mt-2 flex flex-wrap gap-2 text-[10px]">
            <span class="rounded-full border border-violet-800/30 bg-violet-950/20 px-2 py-1 text-violet-200">
              当前版本 {{ artifactVersionId }}
            </span>
            <span class="rounded-full border border-slate-700/30 bg-[#111827] px-2 py-1 text-slate-300">
              父版本 {{ parentArtifactVersionId }}
            </span>
            <span class="rounded-full border border-cyan-800/30 bg-cyan-950/20 px-2 py-1 text-cyan-200">
              知识版本 {{ artifactKnowledgeVersion }}
            </span>
          </div>
        </div>
        <div class="max-w-sm rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5 text-[11px] leading-relaxed text-gray-400">
          <div>修改原因：{{ artifactRevisionReason }}</div>
          <div class="mt-1">最近变更：{{ artifactChangedBlocks.length ? artifactChangedBlocks.join(' / ') : '本轮暂无块级变化' }}</div>
        </div>
      </div>
    </section>

    <section
      v-else
      class="rounded-[22px] border border-dashed border-[#334155] bg-[#0f172a] p-4 text-[12px] leading-relaxed text-gray-400"
    >
      当前会话还没有生成购买决策档案。等第一版成品创建成功后，这里会显示 artifact 版本信息和本轮变更原因。
    </section>

    <section class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">Knowledge Plan</div>
          <div class="mt-2 text-[13px] font-semibold text-gray-100">{{ knowledgePlan.goal_summary || '当前还没有知识计划，我会在生成链触发后补齐。' }}</div>
          <div class="mt-2 flex flex-wrap gap-2 text-[10px]">
            <span
              v-for="field in knowledgePlan.required_fields || []"
              :key="field"
              class="rounded-full border border-cyan-800/30 bg-cyan-950/20 px-2 py-1 text-cyan-200"
            >
              {{ knowledgePlan.field_labels?.[field] || field }}
            </span>
          </div>
        </div>
        <div class="max-w-sm rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5 text-[11px] leading-relaxed text-gray-400">
          <div>优先来源：{{ (knowledgePlan.preferred_sources || []).join(' -> ') || 'user -> session -> persistent -> cache -> web' }}</div>
          <div class="mt-1">知识预算：{{ knowledgePlan.knowledge_budget || 0 }} 条关键知识</div>
        </div>
      </div>
    </section>

    <section class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">上传资料继续</div>
          <div class="mt-1 text-[13px] font-semibold text-gray-100">把资料直接导入当前会话知识链</div>
        </div>
        <div class="rounded-full border border-[#334155] bg-[#111827] px-3 py-1.5 text-[10px] text-gray-400">
          当前固定写入：会话级
        </div>
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <button
          v-for="mode in uploadModes"
          :key="mode.value"
          class="rounded-full border px-3 py-1 text-[10px] font-bold transition-all"
          :class="uploadMode === mode.value ? 'border-blue-500/40 bg-blue-950/30 text-blue-100' : 'border-[#334155] bg-[#111827] text-gray-400 hover:text-gray-200'"
          @click="uploadMode = mode.value"
        >
          {{ mode.label }}
        </button>
      </div>

      <div class="mt-4 grid gap-3">
        <input v-model="entityHint" type="text" placeholder="实体提示，例如：华为 Mate 60 / 阿那亚" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
        <input v-model="sceneHint" type="text" placeholder="场景提示，例如：seeding / digital_decision" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />

        <div v-if="uploadMode === 'file'" class="grid gap-2">
          <input ref="fileInputRef" type="file" class="rounded-2xl border border-dashed border-[#334155] bg-[#111827] px-3 py-3 text-[12px] text-gray-300 file:mr-3 file:rounded-full file:border-0 file:bg-blue-950/40 file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:text-blue-200" />
          <button class="rounded-full border border-blue-500/40 bg-blue-950/30 px-3 py-2 text-[11px] text-blue-100 hover:border-blue-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy" @click="handleFileUpload">
            {{ busy ? '正在解析...' : '上传文件并入会话知识链' }}
          </button>
        </div>

        <div v-else-if="uploadMode === 'text'" class="grid gap-2">
          <input v-model="textTitle" type="text" placeholder="文本标题，例如：Mate 60 参数摘要" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
          <textarea v-model="textPayload" rows="5" placeholder="直接粘贴资料内容、表格文本或你自己的笔记…" class="min-h-[140px] rounded-2xl border border-[#334155] bg-[#111827] px-3 py-3 text-[12px] leading-relaxed text-gray-200 outline-none placeholder:text-gray-600"></textarea>
          <button class="rounded-full border border-blue-500/40 bg-blue-950/30 px-3 py-2 text-[11px] text-blue-100 hover:border-blue-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy || !textTitle.trim() || !textPayload.trim()" @click="handleTextUpload">
            {{ busy ? '正在解析...' : '粘贴文本并入会话知识链' }}
          </button>
        </div>

        <div v-else class="grid gap-2">
          <input v-model="urlPayload" type="url" placeholder="输入公开网页或在线文档链接" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
          <button class="rounded-full border border-blue-500/40 bg-blue-950/30 px-3 py-2 text-[11px] text-blue-100 hover:border-blue-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy || !urlPayload.trim()" @click="handleUrlUpload">
            {{ busy ? '正在抓取...' : '抓取链接并入会话知识链' }}
          </button>
        </div>
      </div>

      <div class="mt-3 rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[11px] text-gray-400">
        如果你要管理长期知识、Demo Packs 或评估集，请切到全局资产中心。
      </div>

      <div v-if="uploadMessage" class="mt-3 rounded-2xl border border-emerald-800/30 bg-emerald-950/10 px-3 py-2 text-[11px] leading-relaxed text-emerald-200">
        {{ uploadMessage }}
      </div>
    </section>

    <section v-if="sessionEntities.length" class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
      <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">升格到全局</div>
      <div class="mt-1 text-[13px] font-semibold text-gray-100">把某个实体的会话知识整组沉淀到正式知识库</div>
      <div class="mt-3 flex flex-wrap gap-2">
        <button
          v-for="entity in sessionEntities"
          :key="entity"
          class="rounded-full border border-violet-500/30 bg-violet-950/20 px-3 py-2 text-[11px] text-violet-100 transition-colors hover:border-violet-400"
          :disabled="busy"
          @click="promoteEntity(entity)"
        >
          升格 {{ entity }}
        </button>
      </div>
    </section>

    <section class="grid gap-4 xl:grid-cols-2">
      <KnowledgeGroupSection title="待审知识" badge="会话级" tone="amber" :groups="candidateGroups" empty-text="这一轮还没有新的待审候选知识。">
        <template #header-actions>
          <div class="flex flex-wrap gap-2">
            <button
              class="rounded-full border border-amber-500/30 bg-amber-950/20 px-3 py-1.5 text-[10px] font-semibold text-amber-100 transition-colors hover:border-amber-400"
              :disabled="busy || !candidateGroups.length"
              @click="reviewAllRecommended"
            >
              采用推荐项
            </button>
            <button
              class="rounded-full border border-[#475569] bg-[#111827] px-3 py-1.5 text-[10px] font-semibold text-gray-300 transition-colors hover:border-[#64748b]"
              :disabled="busy || !candidateGroups.length"
              @click="deferAllCandidates"
            >
              全部暂不使用
            </button>
          </div>
        </template>
        <template #actions="{ group }">
          <div class="flex flex-wrap gap-2">
            <button class="rounded-full border border-amber-500/30 bg-amber-950/20 px-3 py-1.5 text-[10px] font-semibold text-amber-100 transition-colors hover:border-amber-400" :disabled="busy" @click="reviewGroup(group, 'approve_selected')">用这一组</button>
            <button class="rounded-full border border-[#475569] bg-[#111827] px-3 py-1.5 text-[10px] font-semibold text-gray-300 transition-colors hover:border-[#64748b]" :disabled="busy" @click="reviewGroup(group, 'defer_selected')">暂不使用</button>
            <button class="rounded-full border border-rose-500/30 bg-rose-950/20 px-3 py-1.5 text-[10px] font-semibold text-rose-100 transition-colors hover:border-rose-400" :disabled="busy" @click="reviewGroup(group, 'reject_selected')">驳回</button>
          </div>
        </template>
      </KnowledgeGroupSection>

      <KnowledgeGroupSection title="当前会话知识" badge="会话级" tone="cyan" :groups="sessionGroups" empty-text="当前会话还没有已确认知识。">
        <template #actions="{ group }">
          <button
            class="rounded-full border border-violet-500/30 bg-violet-950/20 px-3 py-1.5 text-[10px] font-semibold text-violet-100 transition-colors hover:border-violet-400"
            :disabled="busy"
            @click="promoteField(group)"
          >
            升格这个字段
          </button>
        </template>
      </KnowledgeGroupSection>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import type { KnowledgeGroup } from '../../types/chat'
import {
  promoteKnowledgeToPersistent,
  reviewKnowledgeCandidates,
  uploadKnowledgeFile,
  uploadKnowledgeText,
  uploadKnowledgeUrl,
} from '../../api/upload'
import KnowledgeGroupSection from './KnowledgeWorkbenchSection.vue'

const chatStore = useChatStore()
const { threadId, agentMeta, sessionSnapshotStatus, artifact, artifactVersion, revisionStatus } = storeToRefs(chatStore)

const uploadModes = [
  { value: 'file', label: '上传文件' },
  { value: 'text', label: '粘贴文本' },
  { value: 'url', label: '抓取链接' },
]

const uploadMode = ref<'file' | 'text' | 'url'>('file')
const entityHint = ref('')
const sceneHint = ref('')
const textTitle = ref('')
const textPayload = ref('')
const urlPayload = ref('')
const uploadMessage = ref('')
const busy = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const knowledge = computed(() => agentMeta.value?.retrieved_knowledge || {})
const knowledgePlan = computed<Record<string, any>>(() => (knowledge.value?.knowledge_plan || {}) as Record<string, any>)
const candidateGroups = computed<KnowledgeGroup[]>(() =>
  ((knowledge.value?.candidate_session_kb?.groups || []) as KnowledgeGroup[]).filter(group =>
    Array.isArray(group.records) && group.records.some(record => String(record.review_status || '') === 'pending_review'),
  ),
)
const sessionGroups = computed<KnowledgeGroup[]>(() => (knowledge.value?.session_kb?.groups || []) as KnowledgeGroup[])
const sessionKnowledgeVersion = computed(() => String(knowledge.value?.session_kb?.knowledge_version || 'v0'))
const artifactVersionId = computed(() => String(artifactVersion.value?.version_id || artifact.value?.current_version_id || '未生成'))
const parentArtifactVersionId = computed(() => String(artifactVersion.value?.parent_version_id || '首版'))
const artifactRevisionReason = computed(() => String(artifactVersion.value?.revision_reason || revisionStatus.value?.primary_recipe?.why_now || '本轮暂无修订原因'))
const artifactKnowledgeVersion = computed(() => String(artifactVersion.value?.knowledge_version || sessionKnowledgeVersion.value || 'session-kb::0'))
const artifactOwnsCurrentThread = computed(() => {
  const versionThreadId = String(artifactVersion.value?.thread_id || '').trim()
  const activeThreadId = String(threadId.value || '').trim()
  return Boolean(versionThreadId && activeThreadId && versionThreadId === activeThreadId)
})
const hasArtifactContext = computed(() => {
  const versionId = String(artifactVersion.value?.version_id || '').trim()
  return Boolean(artifactOwnsCurrentThread.value && versionId)
})
const artifactChangedBlocks = computed(() =>
  Array.isArray(artifactVersion.value?.changed_blocks)
    ? artifactVersion.value?.changed_blocks?.map((item) => String(item?.id || '').trim()).filter(Boolean)
    : [],
)
const sessionEntities = computed(() => {
  const entities = new Set<string>()
  for (const group of sessionGroups.value) {
    const entity = String(group.normalized_entity || '').trim()
    if (entity) entities.add(entity)
  }
  return [...entities]
})
const snapshotSourceLabel = computed(() => {
  const source = String(sessionSnapshotStatus.value?.source || 'init')
  if (source === 'turn_end') return '本轮结束包'
  if (source === 'inspect') return '白盒探针'
  if (source === 'recover') return '恢复快照'
  if (source === 'workspace') return '工作台快照'
  return '初始化'
})

const refreshKnowledge = async () => {
  await chatStore.fetchAgentMeta()
}

const withBusy = async (runner: () => Promise<void>) => {
  if (!threadId.value) {
    uploadMessage.value = '请先创建或打开一个会话，再导入知识资料。'
    return
  }
  busy.value = true
  uploadMessage.value = ''
  try {
    await runner()
    await refreshKnowledge()
  } catch (error) {
    console.error(error)
    uploadMessage.value = error instanceof Error ? error.message : '知识操作失败，请稍后重试。'
  } finally {
    busy.value = false
  }
}

const buildBasePayload = () => ({
  threadId: threadId.value,
  kbScope: 'session' as const,
  entityHint: entityHint.value.trim(),
  sceneHint: sceneHint.value.trim() || String(agentMeta.value?.active_archetype || 'seeding'),
})

const handleFileUpload = async () => {
  const file = fileInputRef.value?.files?.[0]
  if (!file) {
    uploadMessage.value = '请先选择一份资料文件。'
    return
  }
  await withBusy(async () => {
    const result = await uploadKnowledgeFile(file, buildBasePayload())
    uploadMessage.value = `已导入 ${String((result.document as Record<string, unknown> | undefined)?.title || file.name)}，资料已进入待审知识。`
    if (fileInputRef.value) fileInputRef.value.value = ''
  })
}

const handleTextUpload = async () => {
  await withBusy(async () => {
    await uploadKnowledgeText({
      ...buildBasePayload(),
      title: textTitle.value,
      text: textPayload.value,
    })
    uploadMessage.value = '文本资料已进入待审知识；确认后会转入当前会话知识。'
    textTitle.value = ''
    textPayload.value = ''
  })
}

const handleUrlUpload = async () => {
  await withBusy(async () => {
    await uploadKnowledgeUrl({
      ...buildBasePayload(),
      url: urlPayload.value,
    })
    uploadMessage.value = '链接资料已抓取并进入待审知识，确认后我会继续用它生成。'
    urlPayload.value = ''
  })
}

const promoteEntity = async (entity: string) => {
  await withBusy(async () => {
    await promoteKnowledgeToPersistent({ threadId: threadId.value, normalizedEntity: entity })
    uploadMessage.value = `已把「${entity}」相关会话知识提交到正式知识库。`
  })
}

const promoteField = async (group: KnowledgeGroup) => {
  await withBusy(async () => {
    await promoteKnowledgeToPersistent({
      threadId: threadId.value,
      normalizedEntity: String(group.normalized_entity || ''),
      fieldOrTopic: String(group.field_or_topic || ''),
    })
    uploadMessage.value = `已把「${group.field_label || group.field_or_topic}」提交到正式知识库。`
  })
}

const reviewGroup = async (group: KnowledgeGroup, decision: 'approve_selected' | 'reject_selected' | 'defer_selected') => {
  const fallbackRecordId = Array.isArray(group.records) && group.records.length
    ? String(group.records[0]?.record_id || group.records[0]?.knowledge_id || '')
    : ''
  const recordIds = decision === 'approve_selected'
    ? [String(group.recommended_record_id || fallbackRecordId || '')].filter(Boolean)
    : Array.isArray(group.records)
      ? group.records.map(item => String(item.record_id || item.knowledge_id || '')).filter(Boolean)
      : []
  if (!recordIds.length) return
  await withBusy(async () => {
    await reviewKnowledgeCandidates({
      threadId: String(threadId.value || ''),
      decision,
      recordIds,
      normalizedEntity: String(group.normalized_entity || ''),
      fieldOrTopic: String(group.field_or_topic || ''),
    })
    uploadMessage.value =
      decision === 'approve_selected' ? '已采用这一组候选知识。'
      : decision === 'reject_selected' ? '已驳回这一组候选知识。'
      : '已把这一组候选标记为暂不使用。'
  })
}

const reviewAllRecommended = async () => {
  await withBusy(async () => {
    await reviewKnowledgeCandidates({
      threadId: String(threadId.value || ''),
      decision: 'approve_recommended',
    })
    uploadMessage.value = '已采用当前推荐候选知识，并同步更新会话知识。'
  })
}

const deferAllCandidates = async () => {
  await withBusy(async () => {
    await reviewKnowledgeCandidates({
      threadId: String(threadId.value || ''),
      decision: 'defer_all',
    })
    uploadMessage.value = '这一轮候选知识已暂不使用，后续可以继续补资料或再审。'
  })
}
</script>
