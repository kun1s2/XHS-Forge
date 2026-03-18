<template>
  <div class="mobile-container pb-20" :style="globalStyles">
    <!-- 顶部导航栏模拟 -->
    <div class="sticky top-0 z-50 bg-white/95 backdrop-blur-md px-4 py-3 flex justify-between items-center border-b border-gray-100">
      <div class="text-xl font-bold cursor-pointer hover:bg-gray-100 w-8 h-8 flex items-center justify-center rounded-full transition-colors">←</div>
      <div class="flex gap-5 text-[15px]">
        <span class="text-gray-500 font-medium">发现</span>
        <span class="text-gray-500 font-medium">附近</span>
        <span class="text-gray-900 border-b-2 border-[#ff2442] pb-1 font-semibold">北京</span>
      </div>
      <div class="text-xl cursor-pointer hover:bg-gray-100 w-8 h-8 flex items-center justify-center rounded-full transition-colors">🔍</div>
    </div>

    <!-- 动态生成的笔记内容 -->
    <div class="w-full px-4 pt-4 flex flex-col gap-6 min-h-[80vh]">
      <!-- ✨ 4.0 大重构：废弃递归 AST，拥抱扁平区块流 -->
      <XForgeRenderer 
        v-for="(block, idx) in blocks" 
        :key="block.id" 
        :node="block" 
        :index="idx"
        :pageData="pageData"
      />
      
      <!-- 骨架屏兜底 -->
      <div v-else-if="currentNode" class="space-y-4 w-full bg-white p-4 rounded-2xl shadow-sm">
        <div class="h-48 bg-gray-100 rounded-xl animate-pulse"></div>
        <div class="h-6 bg-gray-100 rounded-full w-3/4 animate-pulse"></div>
      </div>
    </div>

    <!-- 底部互动栏模拟 -->
    <div class="fixed bottom-0 w-full max-w-[420px] bg-white border-t border-gray-100 px-4 py-2.5 flex justify-between items-center z-50">
      <div class="bg-gray-100 rounded-full px-4 py-2 text-[13px] text-gray-500 flex-1 mr-4 cursor-text">说点什么...</div>
      <div class="flex gap-5 text-xl">
        <span class="cursor-pointer hover:scale-110 transition-transform">🤍</span>
        <span class="cursor-pointer hover:scale-110 transition-transform">⭐</span>
        <span class="cursor-pointer hover:scale-110 transition-transform">💬</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import XForgeRenderer from './XForgeRenderer.vue'
import { useChatStore } from '../../stores/useChatStore'
import { storeToRefs } from 'pinia'

const chatStore = useChatStore()
const { pageData, styleData, currentNode } = storeToRefs(chatStore)

// 从 DSL 结构中提取区块列表
const blocks = computed(() => {
  return (pageData.value as any)?.blocks || []
})

const globalStyles = computed(() => {
  // ✨ 哨兵纠偏：整合全量视觉变量，确保背景色、间距完全动态
  const defaultSpacing = {
    '--spacing-sm': '16px',
    '--spacing-md': '24px',
    '--spacing-lg': '40px',
    '--bg-color': '#ffffff' // 默认白
  }
  
  // 优先级：默认 < 页面主题 < 样式大脑
  const vars = { 
    ...defaultSpacing, 
    ...((pageData.value as any)?.page_theme || {}),
    ...(styleData.value?.global_vars || {})
  }
  
  return Object.entries(vars).map(([k, v]) => `${k}: ${v}`).join(';')
})
</script>

<style scoped>
.mobile-container {
  width: 100%;
  max-width: 420px;
  /* ✨ 核心修复：背景色由变量驱动，不再死板 */
  background-color: var(--bg-color);
  min-height: 100vh;
  box-shadow: 0 10px 50px rgba(0,0,0,0.1);
  position: relative;
  overflow-x: hidden;
  margin: 0 auto;
}

/* ✨ 列表过度动画 */
.list-enter-active,
.list-leave-active {
  transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.list-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
  filter: blur(10px);
}

.list-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

/* 确保移动时位置平滑 */
.list-move {
  transition: transform 0.5s ease;
}
</style>