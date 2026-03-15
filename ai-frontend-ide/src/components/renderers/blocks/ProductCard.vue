<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver" class="relative overflow-hidden transition-all duration-300">
    
    <!-- 1. 骨架屏状态：当数据正在抓取中 -->
    <div v-if="isLoading" class="flex bg-gray-50 rounded-xl p-3 items-center border border-gray-100/50 animate-pulse">
      <div class="w-16 h-16 rounded-lg bg-gray-200 mr-3"></div>
      <div class="flex-1 space-y-2">
        <div class="h-3 bg-gray-200 rounded-full w-3/4"></div>
        <div class="h-2 bg-gray-200 rounded-full w-1/2"></div>
        <div class="h-4 bg-gray-200 rounded-full w-1/4"></div>
      </div>
      <div class="w-16 h-8 rounded-full bg-gray-200 ml-3"></div>
    </div>

    <!-- 2. 真实数据状态 -->
    <div v-else class="flex bg-gray-50 rounded-xl p-3 items-center border border-gray-100/50 hover:bg-white transition-colors duration-300 group">
      <img v-if="props.data?.image_url" :src="props.data.image_url" class="w-16 h-16 object-cover rounded-lg mr-3 shadow-sm border border-gray-200/50 group-hover:scale-105 transition-transform duration-500" />
      <div class="flex-1 min-w-0">
        <!-- 商品名称 -->
        <div class="text-sm text-gray-800 line-clamp-2 mb-1.5 font-bold tracking-tight">{{ props.data?.title || props.data?.desc || '宝藏好物' }}</div>
        
        <!-- 评分系统 -->
        <div v-if="props.data?.rating" class="flex items-center gap-1 mb-1">
          <div class="relative flex text-[10px]">
            <div class="flex text-gray-300">
              <span v-for="i in 5" :key="i">★</span>
            </div>
            <div 
              class="absolute top-0 left-0 flex overflow-hidden whitespace-nowrap"
              :style="{ width: (props.data.rating / 5 * 100) + '%', color: 'var(--primary-vibe, #ff2442)' }"
            >
              <span v-for="i in 5" :key="i">★</span>
            </div>
          </div>
          <span class="text-[9px] font-bold text-gray-400">{{ props.data.rating }}</span>
        </div>

        <div class="text-[#ff2442] font-bold text-base" :style="{ color: 'var(--primary-vibe, #ff2442)' }">{{ props.data?.price || '正在核价...' }}</div>
      </div>
      
      <button 
        class="ml-3 shrink-0 transition-all duration-300 text-white text-xs px-4 py-2 rounded-full font-medium shadow-sm hover:brightness-110 active:scale-95"
        :style="{ backgroundColor: 'var(--primary-vibe, #ff2442)' }"
      >
        去看看
      </button>
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

const emit = defineEmits(['select', 'hover'])

// 判断是否处于 Loading 状态：如果标题是默认的“宝藏好物”或为空，且正在通过搜索增强数据
const isLoading = computed(() => {
  const title = props.data?.title
  return !title || title === '宝藏好物' || title === '商品名称'
})

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}
</script>
