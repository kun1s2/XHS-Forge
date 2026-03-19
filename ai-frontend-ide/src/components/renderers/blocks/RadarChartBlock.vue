<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    title?: string;
    metrics?: Array<{ label: string; value: number }>; // value 为 0-100
  };
  style?: any;
}>();

const title = computed(() => props.data.title || "综合能力评估");
const metrics = computed(() => {
  const defaultMetrics = [
    { label: "性能", value: 85 },
    { label: "续航", value: 70 },
    { label: "颜值", value: 95 },
    { label: "便携", value: 80 },
    { label: "性价比", value: 65 }
  ];
  return props.data.metrics || defaultMetrics;
});
const cssClasses = computed(() => props.style?.css_classes || '');
const inlineStyles = computed(() => props.style?.inline_styles || {});

// 计算雷达图坐标
const sides = computed(() => metrics.value.length);
const radius = 80;
const center = 100;

const points = computed(() => {
  return metrics.value.map((m, i) => {
    const angle = (Math.PI * 2 * i) / sides.value - Math.PI / 2;
    const x = center + radius * (m.value / 100) * Math.cos(angle);
    const y = center + radius * (m.value / 100) * Math.sin(angle);
    return `${x},${y}`;
  }).join(' ');
});

const gridLines = computed(() => {
  return [0.25, 0.5, 0.75, 1].map(scale => {
    return metrics.value.map((_, i) => {
      const angle = (Math.PI * 2 * i) / sides.value - Math.PI / 2;
      const x = center + radius * scale * Math.cos(angle);
      const y = center + radius * scale * Math.sin(angle);
      return `${x},${y}`;
    }).join(' ');
  });
});
</script>

<template>
  <div :class="['w-full bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex flex-col items-center animate-in fade-in slide-in-from-bottom-4 duration-700', cssClasses]" :style="inlineStyles">
    <div class="text-sm font-black text-gray-800 mb-6 flex items-center gap-2">
      <span class="w-1.5 h-1.5 bg-[var(--primary-vibe)] rounded-full animate-ping"></span>
      {{ title }}
    </div>

    <div class="relative w-full max-w-[240px] aspect-square">
      <svg viewBox="0 0 200 200" class="w-full h-full transform transition-transform duration-1000 hover:scale-105">
        <!-- 网格背景 -->
        <polygon v-for="(line, idx) in gridLines" :key="idx" :points="line" fill="none" stroke="#f1f5f9" stroke-width="1" />
        
        <!-- 轴线 -->
        <line v-for="(m, i) in metrics" :key="i" 
          :x1="center" :y1="center" 
          :x2="center + radius * Math.cos((Math.PI * 2 * i) / sides - Math.PI / 2)" 
          :y2="center + radius * Math.sin((Math.PI * 2 * i) / sides - Math.PI / 2)" 
          stroke="#f1f5f9" stroke-width="1" 
        />

        <!-- 填充区域 -->
        <polygon 
          :points="points" 
          fill="var(--primary-vibe)" 
          fill-opacity="0.15" 
          stroke="var(--primary-vibe)" 
          stroke-width="2.5"
          stroke-linejoin="round"
          class="drop-shadow-[0_0_8px_rgba(var(--primary-vibe-rgb),0.3)]"
        />

        <!-- 顶点标识 -->
        <circle v-for="(m, i) in metrics" :key="'dot-'+i"
          :cx="center + radius * (m.value / 100) * Math.cos((Math.PI * 2 * i) / sides - Math.PI / 2)"
          :cy="center + radius * (m.value / 100) * Math.sin((Math.PI * 2 * i) / sides - Math.PI / 2)"
          r="3.5"
          fill="white"
          stroke="var(--primary-vibe)"
          stroke-width="2"
        />
      </svg>

      <!-- 标签文字 -->
      <div v-for="(m, i) in metrics" :key="'label-'+i" 
        class="absolute text-[10px] font-bold text-gray-400 whitespace-nowrap"
        :style="{
          left: (50 + 55 * Math.cos((Math.PI * 2 * i) / sides - Math.PI / 2)) + '%',
          top: (50 + 55 * Math.sin((Math.PI * 2 * i) / sides - Math.PI / 2)) + '%',
          transform: 'translate(-50%, -50%)'
        }"
      >
        {{ m.label }}
      </div>
    </div>

    <!-- 数据图例 -->
    <div class="mt-6 grid grid-cols-3 gap-x-6 gap-y-2 w-full">
      <div v-for="m in metrics" :key="m.label" class="flex flex-col items-center">
        <span class="text-[9px] text-gray-400 uppercase tracking-tighter">{{ m.label }}</span>
        <span class="text-xs font-black text-gray-700">{{ m.value }}</span>
      </div>
    </div>
  </div>
</template>
