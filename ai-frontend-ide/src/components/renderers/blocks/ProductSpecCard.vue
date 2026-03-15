<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100/50">
    <!-- 头部：标题与装饰 -->
    <div class="flex items-center gap-2 mb-4">
      <div class="w-1.5 h-4 rounded-full bg-[var(--primary-vibe,#ff2442)]"></div>
      <h3 class="text-sm font-bold text-gray-900 uppercase tracking-widest">Product Specs</h3>
    </div>

    <!-- 内容区：骨架屏 vs 真实数据 -->
    <div class="grid grid-cols-1 gap-2.5">
      <!-- 骨架屏：当没有参数数据时显示 -->
      <template v-if="!props.data?.core_features || props.data.core_features.length === 0">
        <div v-for="i in 4" :key="i" class="flex items-center gap-3 p-2.5 rounded-xl bg-gray-50/50 animate-pulse">
          <div class="w-4 h-4 rounded-md bg-gray-200"></div>
          <div class="h-3 bg-gray-200 rounded-full flex-1"></div>
        </div>
      </template>

      <!-- 真实数据 -->
      <template v-else>
        <div 
          v-for="(feature, idx) in props.data.core_features" 
          :key="idx"
          class="flex items-start gap-3 p-2.5 rounded-xl bg-gray-50/50 border border-transparent hover:border-[var(--primary-vibe-light)] transition-all group"
        >
          <span class="text-[var(--primary-vibe,#ff2442)] mt-0.5 group-hover:scale-110 transition-transform">
            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>
          </span>
          <span class="text-[13px] text-gray-700 leading-tight font-medium">{{ feature }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  compId: string
  data: any
  style: any
}>()

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
</script>

<style scoped>
/* 可以在这里添加一些细微的动效 */
</style>
