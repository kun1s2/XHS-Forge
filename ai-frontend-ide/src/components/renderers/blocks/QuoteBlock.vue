<script setup lang="ts">
import { computed } from 'vue';
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  node: any;
  data: {
    mode?: string;
    quote?: string;
    author?: string;
  };
}>();

const mode = computed(() => String(props.data.mode || 'summary'))
const isStrongQuote = computed(() => mode.value === 'source_quote' || mode.value === 'user_quote')
</script>

<template>
  <div class="px-8 py-6 relative group animate-in fade-in zoom-in duration-700">
    <template v-if="isStrongQuote">
      <div class="absolute top-0 left-4 text-6xl font-serif text-[var(--primary-vibe)] opacity-10 select-none">“</div>
      <div class="relative z-10">
        <p class="text-lg font-black text-gray-800 leading-snug tracking-tight italic border-l-4 border-[var(--primary-vibe)] pl-4">
          {{ data.quote || '有些话，必须大声说出来。' }}
        </p>
        <div v-if="data.author" class="mt-3 text-right">
          <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">— {{ data.author }}</span>
        </div>
      </div>
      <div class="absolute bottom-0 right-4 text-6xl font-serif text-[var(--primary-vibe)] opacity-10 select-none">”</div>
    </template>
    <template v-else>
      <div class="rounded-[24px] border border-[var(--card-border)] bg-[var(--card-bg-soft)] px-5 py-4">
        <div class="text-[10px] font-black uppercase tracking-[0.22em] text-[var(--primary-vibe)]">观点摘要</div>
        <p class="mt-2 text-[15px] font-semibold leading-relaxed text-gray-800">
          {{ data.quote || '把这段重点浓缩成一句更容易记住的总结。' }}
        </p>
      </div>
    </template>

    <FactBindingFooter :node="node" />
  </div>
</template>
