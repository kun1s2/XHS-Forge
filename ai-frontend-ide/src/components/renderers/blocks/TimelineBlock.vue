<script setup lang="ts">
import { computed } from 'vue';
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  node: any;
  data: {
    items?: Array<{ time: string; title: string; desc: string }>;
  };
}>();

const timelineItems = computed(() => {
  return props.data.items || [
    { time: "2023", title: "初次邂逅", desc: "那是一个充满阳光的午后" },
    { time: "2024", title: "深度磨合", desc: "我们共同走过了风风雨雨" }
  ];
});
</script>

<template>
  <div class="px-6 py-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
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
