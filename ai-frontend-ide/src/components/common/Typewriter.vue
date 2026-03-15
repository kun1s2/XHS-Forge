<template>
  <div class="relative inline-block font-mono leading-relaxed">
    <span class="whitespace-pre-wrap">{{ displayedText }}</span>
    <span v-if="active" class="ml-1 inline-block w-1.5 h-4 bg-blue-500 animate-pulse align-middle"></span>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  text: string
  active?: boolean
  speed?: number
}>()

const displayedText = ref('')
const currentIndex = ref(0)

const type = () => {
  if (currentIndex.value < props.text.length) {
    displayedText.value += props.text[currentIndex.value]
    currentIndex.value++
    setTimeout(type, props.speed || 30)
  }
}

// 如果文本是流式追加的（来自 LLM），我们需要观察变化
watch(() => props.text, (newText) => {
  // 如果新文本长度大于当前已显示的，则继续追加
  if (newText.length > displayedText.value.length) {
    const nextChars = newText.slice(displayedText.value.length)
    displayedText.value += nextChars
    currentIndex.value = displayedText.value.length
  } else if (newText === '') {
    // 重置
    displayedText.value = ''
    currentIndex.value = 0
  }
}, { immediate: true })

onMounted(() => {
  if (props.text && displayedText.value === '') {
    type()
  }
})
</script>

<style scoped>
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
.animate-pulse {
  animation: pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
