<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    quote?: string;
    author?: string;
  };
}>();
</script>

<template>
  <div class="px-8 py-6 relative group animate-in fade-in zoom-in duration-700">
    <!-- 装饰性大引号 -->
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
  </div>
</template>
