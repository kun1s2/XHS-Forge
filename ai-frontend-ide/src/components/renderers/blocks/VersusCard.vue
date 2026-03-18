<script setup lang="ts">
import { defineProps, computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    proText?: string;
    conText?: string;
  };
}>();

const pro = computed(() => props.data.proText || "令人心动的优点");
const con = computed(() => props.data.conText || "无法忽视的槽点");
</script>

<template>
  <div class="relative w-full h-48 rounded-3xl overflow-hidden shadow-2xl flex border border-white/10 group">
    <!-- 优点侧 (Pro) -->
    <div class="w-1/2 h-full bg-rose-500 p-5 flex flex-col justify-center items-start text-white relative transition-all duration-500 group-hover:w-[60%]">
      <div class="bg-white/20 px-2 py-0.5 rounded text-[9px] font-black uppercase mb-2 tracking-tighter">THE GOOD</div>
      <div class="text-base font-black leading-tight line-clamp-3">{{ pro }}</div>
      <!-- 动态装饰 -->
      <div class="absolute -left-4 -bottom-4 w-20 h-20 bg-white/10 rounded-full blur-xl animate-pulse"></div>
    </div>

    <!-- 缺点侧 (Con) -->
    <div class="w-1/2 h-full bg-zinc-900 p-5 flex flex-col justify-center items-end text-right text-zinc-400 relative transition-all duration-500 group-hover:w-[40%] border-l border-white/5">
      <div class="bg-white/5 px-2 py-0.5 rounded text-[9px] font-black uppercase mb-2 tracking-tighter">THE BAD</div>
      <div class="text-base font-black leading-tight line-clamp-3">{{ con }}</div>
    </div>

    <!-- VS 标志 -->
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-2xl z-10 border-4 border-zinc-100 group-hover:scale-110 transition-transform duration-500">
      <span class="text-zinc-900 font-black italic text-xs tracking-tighter">VS</span>
    </div>
  </div>
</template>
