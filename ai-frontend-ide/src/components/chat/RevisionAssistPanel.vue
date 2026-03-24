<template>
  <div
    v-if="visible"
    class="mb-3 rounded-2xl border border-violet-900/30 bg-violet-950/10 px-4 py-3"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <span class="rounded-full border border-violet-800/40 bg-violet-950/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-violet-300">Revision Assist</span>
          <span
            class="rounded-full border px-2 py-0.5 text-[10px]"
            :class="statusBadgeClass"
          >
            {{ statusLabel }}
          </span>
          <span
            v-if="artifactVersion?.version_id"
            class="rounded-full border border-[#334155] bg-[#111827] px-2 py-0.5 text-[10px] text-gray-300"
          >
            {{ artifactVersion.version_id }}
          </span>
        </div>
        <div class="mt-2 text-[13px] font-semibold text-gray-100">
          {{ headline }}
        </div>
        <div v-if="summary" class="mt-1 text-[11px] leading-relaxed text-gray-300">
          {{ summary }}
        </div>
        <div v-if="detailLine" class="mt-2 text-[10px] leading-relaxed text-gray-400">
          {{ detailLine }}
        </div>
      </div>

      <button
        v-if="canAccept"
        @click="$emit('accept')"
        :disabled="disabled"
        class="shrink-0 rounded-full border border-violet-700/40 bg-violet-900/20 px-3 py-1.5 text-[11px] font-semibold text-violet-100 transition-all hover:border-violet-500/50 hover:bg-violet-900/30 disabled:cursor-not-allowed disabled:border-[#334155] disabled:bg-[#1b2334] disabled:text-gray-500"
      >
        听取意见
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ArtifactVersion, RevisionPlan, RevisionResult, RevisionStatus } from '../../types/chat'

const props = defineProps<{
  artifactVersion?: ArtifactVersion | null
  revisionPlan?: RevisionPlan | null
  revisionResult?: RevisionResult | null
  revisionStatus?: RevisionStatus | null
  disabled?: boolean
}>()

defineEmits<{
  (e: 'accept'): void
}>()

const primaryRecipe = computed(() => props.revisionStatus?.primary_recipe || props.revisionPlan?.primary_recipe || null)
const visible = computed(() => Boolean(primaryRecipe.value || props.revisionResult?.failure_reason || props.revisionResult?.status === 'applied'))
const canAccept = computed(() => Boolean(primaryRecipe.value?.prompt && primaryRecipe.value?.label))

const headline = computed(() => {
  if (primaryRecipe.value?.label) return String(primaryRecipe.value.label)
  if (props.revisionResult?.status === 'applied') return '这一轮修订已经应用到当前档案'
  if (props.revisionResult?.failure_reason) return '这轮修订还没完全落到成品上'
  return '当前没有新的修订建议'
})

const summary = computed(() => {
  if (props.revisionPlan?.reason) return String(props.revisionPlan.reason)
  if (primaryRecipe.value?.why_now) return String(primaryRecipe.value.why_now)
  if (props.revisionResult?.failure_reason) return String(props.revisionResult.failure_reason)
  return ''
})

const detailLine = computed(() => {
  const parts: string[] = []
  if ((props.artifactVersion?.changed_blocks || []).length > 0) {
    parts.push(`最近变更 ${props.artifactVersion?.changed_blocks?.length || 0} 个区块`)
  }
  if (props.artifactVersion?.revision_reason) {
    parts.push(`本轮原因：${props.artifactVersion.revision_reason}`)
  } else if (props.revisionPlan?.expected_effect) {
    parts.push(`预期效果：${props.revisionPlan.expected_effect}`)
  }
  return parts.join(' · ')
})

const statusLabel = computed(() => {
  const status = String(props.revisionStatus?.status || '').trim()
  if (status === 'applied') return '已应用'
  if (status === 'failed') return '待重试'
  if (status === 'ready') return '可继续'
  return props.revisionStatus?.needs_revision ? '建议修订' : '观察中'
})

const statusBadgeClass = computed(() => {
  const status = String(props.revisionStatus?.status || '').trim()
  if (status === 'applied') return 'border-emerald-700/40 bg-emerald-950/20 text-emerald-200'
  if (status === 'failed') return 'border-rose-700/40 bg-rose-950/20 text-rose-200'
  if (status === 'ready') return 'border-amber-700/40 bg-amber-950/20 text-amber-200'
  return 'border-violet-700/40 bg-violet-950/20 text-violet-200'
})
</script>
