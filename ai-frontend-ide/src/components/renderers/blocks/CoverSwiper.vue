<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" class="w-full relative overflow-hidden rounded-3xl shadow-sm mb-4">
    <!-- 1. 骨架屏状态：当没有图片数据时 -->
    <div v-if="!hasImages" class="w-full h-[400px] bg-gray-100 flex flex-col items-center justify-center animate-pulse">
      <div class="w-12 h-12 text-gray-300 mb-3">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
      </div>
      <div class="text-xs text-gray-400 font-medium">AI 正在构思精美封面...</div>
    </div>

    <!-- 2. 真实数据状态 -->
    <template v-else>
      <div class="flex overflow-x-auto snap-x snap-mandatory scrollbar-hide w-full h-[400px] bg-gray-100">
        <div 
          v-for="(img, idx) in imageList" 
          :key="idx"
          class="snap-center shrink-0 w-full h-full flex-none"
        >
          <img :src="img" :alt="'cover-' + idx" class="w-full h-full object-cover transition-opacity duration-500" />
        </div>
      </div>
      <!-- 页码指示器 -->
      <div class="absolute bottom-4 right-4 bg-black/40 backdrop-blur-sm text-white text-[10px] px-2.5 py-1 rounded-full font-bold tracking-wider">
        {{ currentIdx + 1 }}/{{ imageList.length }}
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  compId: string
  data: any
  style: any
}>()

const currentIdx = ref(0)
const imageList = computed(() => {
  const urls = props.data?.image_urls || []
  if (urls.length === 0 && props.data?.image_url) return [props.data.image_url]
  return urls
})

const hasImages = computed(() => imageList.value.length > 0)
const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
</script>

<style scoped>
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
