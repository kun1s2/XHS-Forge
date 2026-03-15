<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" class="mt-2 pt-4 border-t border-gray-100 flex justify-between items-center px-1">
    <!-- 左侧：点赞、收藏、评论 -->
    <div class="flex gap-6">
      <!-- 点赞 -->
      <button @click="handleLike" class="flex items-center gap-1.5 group transition-all">
        <div class="relative">
          <svg 
            class="w-5 h-5 transition-all duration-300" 
            :class="[isLiked ? 'text-[#ff2442] fill-[#ff2442] scale-125' : 'text-gray-400 group-hover:text-gray-600']"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
          </svg>
          <!-- 💥 点赞爆炸微动效（CSS实现） -->
          <div v-if="showLikeAnim" class="absolute inset-0 bg-[#ff2442]/20 rounded-full animate-ping"></div>
        </div>
        <span class="text-xs font-bold transition-colors" :class="[isLiked ? 'text-[#ff2442]' : 'text-gray-500']">{{ displayLikes }}</span>
      </button>

      <!-- 收藏 -->
      <button @click="isCollected = !isCollected" class="flex items-center gap-1.5 group">
        <svg 
          class="w-5 h-5 transition-all" 
          :class="[isCollected ? 'text-orange-400 fill-orange-400 scale-110' : 'text-gray-400 group-hover:text-gray-600']"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.382-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
        </svg>
        <span class="text-xs font-bold text-gray-500">{{ props.data?.collects || '0' }}</span>
      </button>

      <!-- 评论 -->
      <div class="flex items-center gap-1.5 text-gray-400 group cursor-pointer">
        <svg class="w-5 h-5 group-hover:text-gray-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
        <span class="text-xs font-bold text-gray-500">{{ props.data?.comments || '0' }}</span>
      </div>
    </div>

    <!-- 右侧：分享 -->
    <button class="text-gray-400 hover:text-gray-600 transition-colors">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path></svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  compId: string
  data: any
  style: any
}>()

const isLiked = ref(false)
const isCollected = ref(false)
const showLikeAnim = ref(false)

const displayLikes = computed(() => {
  const base = props.data?.likes || '0'
  if (isLiked.value) {
    // 简单逻辑：点击后数字+1（如果是w结尾则保持）
    return base.includes('w') ? base : (parseInt(base) + 1).toString()
  }
  return base
})

const handleLike = () => {
  if (!isLiked.value) {
    showLikeAnim.value = true
    setTimeout(() => { showLikeAnim.value = false }, 500)
  }
  isLiked.value = !isLiked.value
}

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
</script>
