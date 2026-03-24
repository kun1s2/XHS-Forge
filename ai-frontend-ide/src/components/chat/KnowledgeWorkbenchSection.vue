<template>
  <section class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">{{ title }}</div>
        <div class="mt-1 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold" :class="badgeClass">{{ badge }}</div>
      </div>
      <div class="flex items-center gap-3">
        <slot name="header-actions" />
        <div class="text-[11px] text-gray-500">{{ groups.length }} 组</div>
      </div>
    </div>

    <div v-if="groups.length" class="mt-3 grid gap-3">
      <article
        v-for="group in groups"
        :key="group.group_id || `${group.normalized_entity}-${group.field_or_topic}`"
        class="rounded-2xl border border-[#334155] bg-[#111827] p-3"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-1">
            <div class="text-[12px] font-semibold text-gray-100">{{ group.field_label || group.field_or_topic || '知识条目' }}</div>
            <div class="text-[10px] text-gray-500">{{ group.normalized_entity || '未归一化实体' }} · {{ group.entity_type || '未分类' }}</div>
          </div>
          <slot name="actions" :group="group" />
        </div>
        <div class="mt-3 grid gap-2">
          <div
            v-for="record in group.records || []"
            :key="record.record_id || record.knowledge_id"
            class="rounded-xl border border-[#253247] bg-[#0b1220] px-3 py-2"
          >
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-[11px] text-gray-200">{{ record.summary || record.value || '—' }}</span>
              <span v-if="record.recommended" class="rounded-full border border-blue-800/40 bg-blue-950/30 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-blue-200">推荐</span>
              <span class="rounded-full border border-[#334155] px-2 py-0.5 text-[9px] uppercase tracking-[0.12em] text-gray-400">{{ record.review_status || 'unknown' }}</span>
            </div>
            <div class="mt-1 text-[10px] leading-relaxed text-gray-500">
              {{ record.source_title || '未命名来源' }}
              <span v-if="record.support_level"> · {{ record.support_level }}</span>
            </div>
          </div>
        </div>
      </article>
    </div>
    <div v-else class="mt-4 rounded-2xl border border-dashed border-[#334155] bg-[#111827] px-4 py-6 text-[11px] leading-relaxed text-gray-500">
      {{ emptyText }}
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeGroup } from '../../types/chat'

const props = defineProps<{
  title: string
  badge: string
  tone?: 'amber' | 'cyan' | 'violet'
  groups: KnowledgeGroup[]
  emptyText: string
}>()

const badgeClass = computed(() => {
  if (props.tone === 'amber') return 'border-amber-800/30 bg-amber-950/20 text-amber-200'
  if (props.tone === 'violet') return 'border-violet-800/30 bg-violet-950/20 text-violet-200'
  return 'border-cyan-800/30 bg-cyan-950/20 text-cyan-200'
})
</script>
