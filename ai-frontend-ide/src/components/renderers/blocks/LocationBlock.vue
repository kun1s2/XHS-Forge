<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver">
    <div class="flex items-center gap-3 px-3 py-3 rounded-2xl border transition-all cursor-pointer group" :style="shellStyle">
      <!-- ✨ 左侧图标：带呼吸感的背景 -->
      <div 
        class="w-10 h-10 rounded-full flex items-center justify-center shadow-inner shrink-0"
        :style="{ backgroundColor: 'var(--primary-vibe-light, rgba(255, 36, 66, 0.1))' }"
      >
        <span class="text-xl" :style="{ color: 'var(--primary-vibe, #ff2442)' }">📍</span>
      </div>
      
      <!-- ✨ 中间文字：展示真实 POI 名称与地址 -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-1.5 mb-0.5">
          <div class="text-[14px] font-bold truncate" :style="{ color: 'var(--text-color)' }">{{ props.data?.poi_name || props.data?.location || '未知地点' }}</div>
          <!-- ✨ 如果有坐标，显示“已校准”小标签 -->
          <div v-if="hasCoordinates" class="px-1 py-0.5 bg-green-100 text-green-600 text-[9px] rounded font-bold uppercase tracking-tighter">GPS</div>
        </div>
        <div class="text-[11px] truncate leading-tight" :style="{ color: 'var(--text-muted)' }">
          {{ props.data?.location || '点击查看详情' }}
        </div>
      </div>

      <!-- ✨ 右侧箭头 -->
      <div class="group-hover:translate-x-0.5 transition-all" :style="arrowStyle">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
        </svg>
      </div>
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

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const shellStyle = computed(() => ({
  background: 'var(--card-bg)',
  borderColor: 'var(--card-border)',
  boxShadow: 'var(--card-shadow)',
}))
const arrowStyle = computed(() => ({ color: 'var(--text-muted)' }))

const hasCoordinates = computed(() => props.data?.lat !== undefined && props.data?.lng !== undefined)

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
  
  const name = props.data?.poi_name || props.data?.location
  
  if (hasCoordinates.value) {
    // ✨ 真实跳转：打开高德地图搜索页
    const url = `https://www.amap.com/search?query=${encodeURIComponent(name)}&city=auto`
    window.open(url, '_blank')
  } else {
    // 降级：仅弹窗
    alert(`正在调起地图准备导航至：${name || '该地点'}`)
  }
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}
</script>