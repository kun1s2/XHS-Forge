<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver">
    <div class="flex flex-wrap gap-2 mt-2">
      <!-- ✨ 标签文字颜色跟随图片主色调 -->
      <span 
        v-for="(tag, idx) in formattedTags" 
        :key="idx" 
        class="px-2.5 py-1 rounded-full text-[13px] font-medium cursor-pointer transition-colors bg-gray-100"
        :style="{ color: 'var(--primary-vibe, #13386c)' }"
      >
        {{ tag }}
      </span>
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

const formattedTags = computed(() => {
  const tags = props.data?.tags || []
  return tags.map((t: string) => String(t).startsWith('#') ? t : `#${t}`)
})

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}
</script>