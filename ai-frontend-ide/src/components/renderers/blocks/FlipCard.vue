<script setup lang="ts">
import { computed, ref } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    frontContent?: string;
    backContent?: string;
  };
}>();

const isFlipped = ref(false);
const front = computed(() => props.data.frontContent || "真相到底是什么？");
const back = computed(() => props.data.backContent || "这就是你想要的答案！✨");
</script>

<template>
  <div 
    class="perspective-1000 w-full h-40 cursor-pointer" 
    @mouseenter="isFlipped = true" 
    @mouseleave="isFlipped = false"
    @click="isFlipped = !isFlipped"
  >
    <div 
      class="relative w-full h-full transition-all duration-700 transform-style-3d shadow-xl rounded-3xl"
      :class="{ 'rotate-y-180': isFlipped }"
    >
      <!-- 正面 (Front) -->
      <div class="absolute inset-0 backface-hidden bg-white border border-gray-100 rounded-3xl flex flex-col items-center justify-center p-6 text-center">
        <div class="w-10 h-10 bg-rose-50 text-rose-500 rounded-full flex items-center justify-center mb-3">
          <span class="font-black text-lg">?</span>
        </div>
        <div class="text-sm font-bold text-stone-800 leading-tight">{{ front }}</div>
        <div class="mt-3 text-[9px] text-stone-400 tracking-widest uppercase">Hover to reveal</div>
      </div>

      <!-- 背面 (Back) -->
      <div class="absolute inset-0 backface-hidden bg-rose-500 text-white rounded-3xl flex flex-col items-center justify-center p-6 text-center rotate-y-180">
        <div class="text-xs font-bold mb-2 opacity-80 uppercase tracking-tighter">The Secret</div>
        <div class="text-sm font-black leading-relaxed">{{ back }}</div>
        <div class="absolute bottom-4 right-4 opacity-20 text-4xl">✨</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.perspective-1000 { perspective: 1000px; }
.transform-style-3d { transform-style: preserve-3d; }
.backface-hidden { backface-visibility: hidden; }
.rotate-y-180 { transform: rotateY(180deg); }
</style>
