<template>
  <div class="mt-3 rounded-[22px] border border-[#2f3d59] bg-[linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(17,24,39,0.96))] p-4">
    <div class="flex flex-wrap items-center gap-2">
      <span class="rounded-full border border-blue-900/40 bg-blue-950/30 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-blue-300">
        Agent 协作
      </span>
      <span
        v-if="action.blocking"
        class="rounded-full border border-amber-800/40 bg-amber-950/20 px-2 py-0.5 text-[10px] font-semibold text-amber-200"
      >
        需要先确认
      </span>
    </div>

    <div class="mt-3 text-[14px] font-bold text-gray-100">{{ action.title }}</div>
    <div v-if="action.summary" class="mt-1 text-[12px] leading-relaxed text-gray-400">{{ action.summary }}</div>

    <div class="mt-4 grid gap-2">
      <button
        v-for="option in action.options"
        :key="option.value"
        @click="$emit('select', option)"
        class="rounded-2xl border px-3 py-3 text-left transition-all"
        :class="option.recommended || action.recommended_option === option.value
          ? 'border-blue-500/50 bg-blue-950/20 hover:border-blue-400 hover:bg-blue-950/30'
          : 'border-[#334155] bg-[#0f172a] hover:border-[#4b5563] hover:bg-[#131c2f]'"
      >
        <div class="flex items-start gap-3">
          <div
            v-if="option.asset_url"
            class="h-14 w-14 shrink-0 overflow-hidden rounded-2xl border border-[#334155] bg-[#0b1220]"
          >
            <img :src="option.asset_url" alt="" class="h-full w-full object-cover" loading="lazy" />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <div class="text-[12px] font-semibold text-gray-100">{{ option.label }}</div>
              <span
                v-if="option.recommended || action.recommended_option === option.value"
                class="rounded-full border border-blue-800/40 bg-blue-950/30 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-blue-200"
              >
                推荐
              </span>
            </div>
            <div v-if="option.description" class="mt-1 text-[11px] leading-relaxed text-gray-400">{{ option.description }}</div>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ConversationCheckpointAction, ConversationCheckpointOption } from '../../types/chat'

defineProps<{
  action: ConversationCheckpointAction
}>()

defineEmits<{
  (event: 'select', option: ConversationCheckpointOption): void
}>()
</script>
