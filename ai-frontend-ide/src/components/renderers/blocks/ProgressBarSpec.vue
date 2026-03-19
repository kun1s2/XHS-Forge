<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    label?: string;
    unit?: string;
    current_value?: number;
    target_value?: number;
    compare_label?: string;
  };
}>();

const percentage = computed(() => {
  const val = props.data.current_value || 0;
  const target = props.data.target_value || 100;
  return Math.min(100, Math.round((val / target) * 100));
});
</script>

<template>
  <div class="px-6 py-4 bg-white rounded-3xl border border-gray-100 shadow-sm animate-in fade-in slide-in-from-right-4 duration-500">
    <div class="flex justify-between items-end mb-2">
      <div class="flex flex-col">
        <span class="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{{ data.compare_label || 'Performance' }}</span>
        <span class="text-sm font-black text-gray-800">{{ data.label || '核心指标' }}</span>
      </div>
      <div class="flex items-baseline gap-0.5">
        <span class="text-xl font-black text-[var(--primary-vibe)]">{{ data.current_value || 0 }}</span>
        <span class="text-[10px] font-bold text-gray-400">{{ data.unit || '' }}</span>
      </div>
    </div>
    
    <div class="w-full h-3 bg-gray-100 rounded-full overflow-hidden relative">
      <div 
        class="h-full bg-gradient-to-r from-[var(--primary-vibe)] to-rose-400 rounded-full transition-all duration-1000 ease-out"
        :style="{ width: percentage + '%' }"
      >
        <!-- 扫描光效 -->
        <div class="absolute inset-0 bg-white/20 w-1/2 -skew-x-12 animate-[shimmer_2s_infinite]"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% { transform: translateX(-150%); }
  100% { transform: translateX(250%); }
}
</style>
