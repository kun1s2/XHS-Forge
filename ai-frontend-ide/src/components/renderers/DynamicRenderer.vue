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
    <div class="w-full px-4 pt-4 flex flex-col min-h-[80vh]" :style="{ gap: 'var(--spacing-md)' }">
      <TransitionGroup name="list" tag="div" class="flex flex-col w-full" :style="{ gap: 'var(--spacing-md)' }">
        <!-- 1. 骨架屏：当正在执行节点且没有页面数据时 -->
        <template v-if="pageOrder.length === 0 && currentNode">
          <div v-for="i in 3" :key="'skeleton-' + i" class="space-y-4 w-full bg-white p-4 rounded-2xl shadow-sm border border-gray-50">
            <div class="h-48 bg-gray-100 rounded-xl animate-pulse"></div>
            <div class="h-6 bg-gray-100 rounded-full w-3/4 animate-pulse"></div>
            <div class="space-y-2">
              <div class="h-3 bg-gray-100 rounded-full animate-pulse"></div>
              <div class="h-3 bg-gray-100 rounded-full animate-pulse"></div>
              <div class="h-3 bg-gray-100 rounded-full w-5/6 animate-pulse"></div>
            </div>
          </div>
        </template>

        <!-- 2. 真实内容渲染 -->
        <template v-for="compId in pageOrder" :key="compId">
          <div 
            class="relative transition-all duration-300 rounded-xl hover:shadow-md"
            :class="{
              'ring-2 ring-[#ff2442] ring-offset-2 z-20 shadow-xl': selectedComponentId === compId,
              'outline-dashed outline-2 outline-[#ff2442]/40 outline-offset-[-2px] cursor-pointer': hoveredComponentId === compId && selectedComponentId !== compId
            }"
          >
            <component
              v-if="getComponentType(compId)"
              :is="getComponentType(compId)"
              :comp-id="compId"
              :data="getComponentData(compId)"
              :style="getComponentStyle(compId)"
              @select="handleSelect"
              @hover="handleHover"
              @mouseleave="handleMouseLeave"
            />
            
            <!-- ✨ 选中状态标识 -->
            <div v-if="selectedComponentId === compId" class="absolute -top-3 -right-1 bg-[#ff2442] text-white text-[10px] px-2 py-0.5 rounded-full shadow-md z-30 font-bold">
              已锁定待修改
            </div>
          </div>
        </template>
      </TransitionGroup>
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
import CoverSwiper from './blocks/CoverSwiper.vue'
import TitleBlock from './blocks/TitleBlock.vue'
import StoryText from './blocks/StoryText.vue'
import ProductCard from './blocks/ProductCard.vue'
import TagList from './blocks/TagList.vue'
import LocationBlock from './blocks/LocationBlock.vue'
import ProductSpecCard from './blocks/ProductSpecCard.vue'
import InteractionsBar from './blocks/InteractionsBar.vue'
import { useChatStore } from '../../stores/useChatStore'
import { storeToRefs } from 'pinia'

const chatStore = useChatStore()
const { pageData, styleData, hoveredComponentId, selectedComponentId } = storeToRefs(chatStore)

// Component Registry
const componentsMap: Record<string, any> = {
  CoverSwiper,
  TitleBlock,
  StoryText,
  ProductCard,
  TagList,
  LocationBlock,
  ProductSpecCard,
  InteractionsBar
}

const globalStyles = computed(() => {
  // ✨ 黄金比例间距系统默认值
  const defaultSpacing = {
    '--spacing-sm': '16px',
    '--spacing-md': '24px',
    '--spacing-lg': '40px'
  }
  const vars = { ...defaultSpacing, ...(styleData.value?.global_vars || {}) }
  const styleStr = Object.entries(vars).map(([k, v]) => `${k}: ${v}`).join(';')
  return styleStr
})

const pageOrder = computed(() => {
  return pageData.value?.page_order || []
})

const getComponentData = (compId: string): Record<string, any> => {
  return (pageData.value?.[compId] as Record<string, any>) || {}
}

const getComponentStyle = (compId: string): Record<string, any> => {
  return (styleData.value?.[compId] as Record<string, any>) || {} 
}

const getComponentType = (compId: string) => {
  const typeStr = getComponentData(compId)?.type as string | undefined
  return typeStr ? componentsMap[typeStr] : null
}

const handleSelect = (id: string) => {
  chatStore.setSelectedComponent(id)
}

const handleHover = (id: string) => {
  chatStore.setHoveredComponent(id)
}

const handleMouseLeave = () => {
  chatStore.setHoveredComponent(null)
}
</script>

<style scoped>
.mobile-container {
  width: 100%;
  max-width: 420px;
  background-color: #ffffff;
  min-height: 100vh;
  box-shadow: 0 0 20px rgba(0,0,0,0.05);
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