<script setup lang="ts">
import { computed } from 'vue';
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  node: any;
  data: {
    mode?: string;
    events?: Array<{ timestamp?: string; title?: string; description?: string }>;
    items?: Array<{ time: string; title: string; desc: string }>;
  };
}>();

const mode = computed(() => String(props.data.mode || 'recommended'))
const isRecommendedMode = computed(() => mode.value !== 'confirmed' && mode.value !== 'user_journal')

const timelineItems = computed(() => {
  if (Array.isArray(props.data.events) && props.data.events.length) {
    return props.data.events.map((item) => ({
      time: String(item.timestamp || item.title || ''),
      title: String(item.title || item.timestamp || '行程节点'),
      desc: String(item.description || ''),
    }))
  }
  return props.data.items || [
    { time: "上午", title: "推荐起点", desc: "先把第一站和交通安排清楚，再决定后续顺序。" },
    { time: "下午", title: "推荐主线", desc: "把最值得去的主线体验放在中段，避免行程过散。" }
  ];
});
</script>

<template>
  <div class="px-6 py-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
    <div class="mb-4 flex items-center gap-2">
      <span
        class="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.18em]"
        :class="isRecommendedMode ? 'border-sky-200 bg-sky-50 text-sky-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'"
      >
        {{ isRecommendedMode ? '推荐顺序' : '已确认/用户提供' }}
      </span>
      <span v-if="isRecommendedMode" class="text-[11px] text-gray-500">默认按路线建议展示，不把它写成真实日志。</span>
    </div>
    <div class="space-y-8 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-gray-200 before:to-transparent">
      
      <div v-for="(item, idx) in timelineItems" :key="idx" class="relative flex items-start group">
        <!-- 时间点圆圈 -->
        <div class="absolute left-0 w-10 h-10 flex items-center justify-center">
          <div class="w-3 h-3 rounded-full bg-white border-2 border-[var(--primary-vibe)] shadow-[0_0_10px_rgba(var(--primary-vibe-rgb),0.3)] z-10 group-hover:scale-125 transition-transform"></div>
        </div>
        
        <div class="ml-12 pt-0.5">
          <time class="text-[9px] font-black text-[var(--primary-vibe)] uppercase tracking-widest mb-1 block">{{ item.time }}</time>
          <h4 class="text-sm font-black text-gray-800 mb-1">{{ item.title }}</h4>
          <p class="text-xs text-gray-500 leading-relaxed">{{ item.desc }}</p>
        </div>
      </div>

    </div>

    <FactBindingFooter :node="node" />
  </div>
</template>
