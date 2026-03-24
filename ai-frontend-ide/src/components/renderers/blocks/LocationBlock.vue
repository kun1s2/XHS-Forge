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
      
      <!-- ✨ 中间文字：展示地点名称与推荐说明 -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-1.5 mb-0.5">
          <div class="text-[14px] font-bold truncate" :style="{ color: 'var(--text-color)' }">{{ props.data?.poi_name || props.data?.location || '未知地点' }}</div>
          <div v-if="hasCoordinates" class="px-1 py-0.5 bg-green-100 text-green-600 text-[9px] rounded font-bold uppercase tracking-tighter">已确认</div>
          <div v-else class="px-1 py-0.5 bg-sky-50 text-sky-600 text-[9px] rounded font-bold uppercase tracking-tighter">推荐</div>
        </div>
        <div class="text-[11px] truncate leading-tight" :style="{ color: 'var(--text-muted)' }">
          {{ props.data?.location || '点击查看详情' }}
        </div>
      </div>

      <!-- ✨ 右侧箭头 -->
      <div class="group-hover:translate-x-0.5 transition-all flex items-center" :style="arrowStyle">
        <span class="mr-2 hidden text-[10px] font-bold sm:inline">{{ actionCopy }}</span>
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
        </svg>
      </div>
    </div>

    <FactBindingFooter :node="node" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  compId: string
  node: any
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
const mode = computed(() => String(props.data?.mode || 'recommended'))

const hasCoordinates = computed(() => mode.value === 'confirmed' && props.data?.lat !== undefined && props.data?.lng !== undefined)
const actionCopy = computed(() => (mode.value === 'confirmed' ? '打开地图' : '查看推荐位置'))

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
  
  const name = props.data?.poi_name || props.data?.location
  
  if (hasCoordinates.value) {
    const url = `https://www.amap.com/search?query=${encodeURIComponent(name)}&city=auto`
    window.open(url, '_blank')
  } else if (name) {
    const url = `https://www.amap.com/search?query=${encodeURIComponent(name)}&city=auto`
    window.open(url, '_blank')
  }
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}
</script>
