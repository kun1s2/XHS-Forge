<script setup lang="ts">
import { defineProps, computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    image_url?: string;
    caption?: string;
    location?: string;
    weather?: string; // Rain, Sunny, Cloudy, Night
    time?: string;
  };
}>();

const url = computed(() => props.data.image_url || "https://picsum.photos/seed/vibe/800/1000");
const caption = computed(() => props.data.caption || "这一刻的氛围感... ✨");
const location = computed(() => props.data.location || "Somewhere in the world");
const weather = computed(() => props.data.weather || "Cloudy");
const time = computed(() => props.data.time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

const weatherIcon = computed(() => {
  const icons: Record<string, string> = {
    'Rain': '🌧️',
    'Sunny': '☀️',
    'Cloudy': '☁️',
    'Night': '🌙',
    'Snow': '❄️'
  };
  return icons[weather.value] || '✨';
});
</script>

<template>
  <div class="w-full px-2 animate-in fade-in slide-in-from-top-4 duration-1000">
    <div class="bg-white p-3 pb-8 rounded-sm shadow-[0_10px_30px_rgba(0,0,0,0.08)] border border-gray-100 transform -rotate-1 hover:rotate-0 transition-transform duration-500 cursor-pointer group">
      <!-- 图片容器 -->
      <div class="relative aspect-[4/5] overflow-hidden rounded-sm mb-4">
        <img 
          :src="url" 
          class="w-full h-full object-cover grayscale-[0.2] contrast-[1.1] group-hover:grayscale-0 transition-all duration-700" 
          alt="" 
        />
        
        <!-- 天气/时间挂件 -->
        <div class="absolute top-3 left-3 flex flex-col gap-1">
          <div class="bg-black/40 backdrop-blur-md px-2 py-1 rounded flex items-center gap-1.5 border border-white/20">
            <span class="text-xs">{{ weatherIcon }}</span>
            <span class="text-[9px] text-white font-bold tracking-widest uppercase">{{ weather }}</span>
          </div>
          <div class="bg-white/90 px-2 py-1 rounded flex items-center gap-1.5 border border-gray-100 self-start shadow-sm">
            <span class="text-[9px] text-gray-800 font-black">{{ time }}</span>
          </div>
        </div>

        <!-- 装饰暗角 -->
        <div class="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent pointer-events-none"></div>
      </div>

      <!-- 拍立得手写文字 -->
      <div class="px-2 space-y-1">
        <p class="font-['STKaiti','KaiTi',serif] text-sm text-gray-700 leading-tight italic">
          {{ caption }}
        </p>
        <div class="flex items-center gap-1 opacity-40">
          <span class="text-[8px]">📍</span>
          <span class="text-[8px] font-bold uppercase tracking-tighter">{{ location }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 模拟拍立得纸张质感 */
.bg-white {
  background-image: 
    radial-gradient(circle at 50% 50%, rgba(255,255,255,0) 0%, rgba(0,0,0,0.02) 100%),
    linear-gradient(rgba(255,255,255,0.8), rgba(255,255,255,0.8));
}
</style>
