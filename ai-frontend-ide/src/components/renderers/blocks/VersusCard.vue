<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    title?: string;
    pros?: { summary: string; details: string };
    cons?: { summary: string; details: string };
    proText?: string; // 兼容老数据
    conText?: string;
  };
}>();

const title = computed(() => props.data.title || "心智博弈 / 极性对峙");
const pro = computed(() => props.data.pros?.summary || props.data.proText || "真香：优势点");
const con = computed(() => props.data.cons?.summary || props.data.conText || "避雷：下头点");
</script>

<template>
  <div class="flex flex-col gap-3 w-full animate-in fade-in zoom-in duration-500">
    <!-- 对峙标题 -->
    <div class="flex items-center gap-2 px-1">
      <span class="w-1 h-4 bg-rose-500 rounded-full"></span>
      <span class="text-xs font-black text-gray-800 uppercase tracking-tight">{{ title }}</span>
    </div>

    <div class="relative w-full h-52 rounded-[32px] overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.1)] flex border border-white/20 group cursor-pointer">
      <!-- 优点侧 (Pro) -->
      <div class="w-1/2 h-full bg-rose-500 p-6 flex flex-col justify-center items-start text-white relative transition-all duration-700 ease-in-out group-hover:w-[65%]">
        <div class="bg-white/20 backdrop-blur-sm px-2 py-0.5 rounded text-[8px] font-black uppercase mb-2 tracking-widest">PROS / 真香</div>
        <div class="text-base font-black leading-tight drop-shadow-md">{{ pro }}</div>
        <div class="mt-2 text-[9px] opacity-0 group-hover:opacity-60 transition-opacity duration-500 line-clamp-2 leading-relaxed">
          {{ data.pros?.details }}
        </div>
        <!-- 动态光效 -->
        <div class="absolute -left-10 -bottom-10 w-32 h-32 bg-white/20 rounded-full blur-[40px] animate-pulse"></div>
      </div>

      <!-- 缺点侧 (Con) -->
      <div class="w-1/2 h-full bg-zinc-900 p-6 flex flex-col justify-center items-end text-right text-zinc-400 relative transition-all duration-700 ease-in-out group-hover:w-[35%] border-l border-white/5">
        <div class="bg-white/5 px-2 py-0.5 rounded text-[8px] font-black uppercase mb-2 tracking-widest">CONS / 避雷</div>
        <div class="text-base font-black leading-tight">{{ con }}</div>
        <div class="mt-2 text-[9px] opacity-0 group-hover:opacity-40 transition-opacity duration-500 line-clamp-2 leading-relaxed">
          {{ data.cons?.details }}
        </div>
      </div>

      <!-- 核心 VS 标志 -->
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-2xl z-10 border-[6px] border-zinc-100 group-hover:scale-125 group-hover:rotate-[360deg] transition-all duration-1000 ease-out">
        <span class="text-zinc-900 font-black italic text-sm tracking-tighter">VS</span>
      </div>
    </div>
  </div>
</template>
