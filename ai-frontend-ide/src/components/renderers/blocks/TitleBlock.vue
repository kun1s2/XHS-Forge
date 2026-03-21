<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver">
    <div class="rounded-[28px] px-4 py-1.5" :style="shellStyle">
      <h1 class="text-xl font-bold leading-snug border-l-4 pl-3" :style="titleStyle">
        {{ props.data?.title || '' }}
      </h1>
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
  background: 'transparent',
}))
const titleStyle = computed(() => ({
  color: 'var(--text-color, #111827)',
  borderColor: 'var(--primary-vibe, #ff2442)',
}))

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}
</script>
