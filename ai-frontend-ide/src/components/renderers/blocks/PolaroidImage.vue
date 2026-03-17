<script setup lang="ts">
import { defineProps, computed } from 'vue';

const props = defineProps<{
  node: any;
  pageData: any;
}>();

const nodeData = computed(() => props.pageData[props.node.id] || {});
</script>

<template>
  <div class="bg-white p-3 pb-10 shadow-[0_10px_30px_rgba(0,0,0,0.12)] border border-gray-100 flex flex-col gap-3 group overflow-hidden">
    <div class="relative aspect-square overflow-hidden bg-gray-50">
      <img 
        v-if="nodeData.image_url" 
        :src="nodeData.image_url" 
        class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" 
      />
      <div v-else class="w-full h-full flex items-center justify-center text-gray-300">
        📷 记录美好瞬间
      </div>
      <!-- 拍立得闪光感 -->
      <div class="absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-white/20 pointer-events-none"></div>
    </div>
    
    <div class="px-1 italic text-stone-600 font-serif text-[13px] leading-tight text-center">
      {{ nodeData.caption || '记录于 2026' }}
    </div>
  </div>
</template>
