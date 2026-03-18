<script setup lang="ts">
import { ref } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    hint?: string;
  };
}>();

const isOpen = ref(false);
const isExploding = ref(false);

const handleOpen = () => {
  if (!isOpen.value) {
    isExploding.value = true;
    setTimeout(() => {
      isOpen.value = true;
      isExploding.value = false;
    }, 600);
  }
};
</script>

<template>
  <div class="relative w-full flex flex-col items-center justify-center min-h-[12rem] my-4">
    <!-- 1. 礼物盒形态 -->
    <div 
      v-if="!isOpen" 
      @click="handleOpen"
      :class="['group cursor-pointer transition-all duration-500', isExploding ? 'scale-150 blur-sm opacity-0' : 'scale-100']"
    >
      <div class="text-7xl animate-bounce group-hover:scale-110 transition-transform">🎁</div>
      <div class="mt-4 bg-rose-500 text-white px-4 py-1.5 rounded-full text-xs font-bold shadow-lg animate-pulse">
        {{ data.hint || "点击开启惊喜" }}
      </div>
    </div>

    <!-- 2. 爆炸特效层 (CSS Confetti) -->
    <div v-if="isExploding" class="absolute inset-0 pointer-events-none flex items-center justify-center">
      <div class="w-4 h-4 bg-yellow-400 rounded-full animate-ping absolute"></div>
      <div class="w-4 h-4 bg-rose-400 rounded-full animate-ping absolute delay-75"></div>
      <div class="w-4 h-4 bg-blue-400 rounded-full animate-ping absolute delay-150"></div>
      <span class="text-4xl animate-bounce">🎉✨🎊</span>
    </div>

    <!-- 3. 展开后的子内容 (Slot) -->
    <Transition name="fade-scale">
      <div v-if="isOpen" class="w-full flex flex-col gap-4 animate-in fade-in zoom-in duration-700">
        <div class="flex items-center gap-2 mb-2 px-2">
          <span class="text-lg">✨</span>
          <span class="text-xs font-black text-rose-500 uppercase tracking-widest">Surprise Unboxed</span>
          <div class="flex-1 h-[1px] bg-rose-100"></div>
        </div>
        
        <!-- 核心槽位：承载 AST 树中的子节点 -->
        <div class="w-full">
          <slot />
        </div>

        <button 
          @click="isOpen = false" 
          class="mt-4 self-center text-[10px] text-stone-400 underline decoration-dotted underline-offset-4 hover:text-rose-500 transition-colors"
        >
          重新封印惊喜
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-scale-enter-active {
  transition: all 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.fade-scale-enter-from {
  opacity: 0;
  transform: scale(0.8) translateY(20px);
}
</style>
