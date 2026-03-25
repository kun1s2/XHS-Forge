<template>
  <div data-testid="preview-shell" class="preview-shell pb-[92px]" :style="globalStyles">
    <div class="sticky top-0 z-50 px-4 py-3 flex justify-between items-center border-b backdrop-blur-md" :style="topBarStyle">
      <div class="text-xl font-bold cursor-pointer w-8 h-8 flex items-center justify-center rounded-full transition-colors" :style="iconButtonStyle">←</div>
      <div class="flex gap-5 text-[15px]">
        <span :style="mutedTabStyle">发现</span>
        <span :style="mutedTabStyle">附近</span>
        <span class="pb-1 font-semibold border-b-2" :style="activeTabStyle">北京</span>
      </div>
      <div class="text-xl w-8 h-8 flex items-center justify-center rounded-full transition-colors" :style="iconButtonStyle">🔍</div>
    </div>

    <div class="w-full px-4 pt-4 flex flex-col gap-6 min-h-[80vh]">
      <template v-if="blocks.length > 0">
        <XForgeRenderer 
          v-for="(block, idx) in blocks" 
          :key="block.id" 
          :node="block" 
          :index="idx" 
          :interactive="true"
          :selection-enabled="previewInteractionMode === 'select'"
          :recently-changed="recentlyChangedBlockIds.includes(block.id)"
          :recent-change="recentlyChangedBlockDetails[block.id] || null"
        />
      </template>
      
      <div v-else-if="activeWorker" class="space-y-4 w-full p-4 rounded-2xl" :style="emptyCardStyle">
        <div class="h-48 rounded-xl animate-pulse" :style="skeletonStyle"></div>
        <div class="h-6 rounded-full w-3/4 animate-pulse" :style="skeletonStyle"></div>
      </div>

      <div v-else class="flex flex-col items-center justify-center py-20 opacity-40" :style="emptyStateStyle">
        <div class="text-4xl mb-2">✨</div>
        <span class="text-xs">等待灵感注入...</span>
      </div>
    </div>

    <div class="absolute inset-x-0 bottom-0 px-4 py-2.5 flex justify-between items-center z-50 border-t backdrop-blur-md" :style="bottomBarStyle">
      <div class="rounded-full px-4 py-2 text-[13px] flex-1 mr-4 cursor-text border" :style="composerStyle">说点什么...</div>
      <div class="flex gap-5 text-xl" :style="actionBarStyle">
        <span>🤍</span>
        <span>⭐</span>
        <span>💬</span>
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
const { activeWorker, renderPageData, renderStyleData, previewInteractionMode, recentlyChangedBlockIds, recentlyChangedBlockDetails } = storeToRefs(chatStore)

const blocks = computed(() => {
  return (renderPageData.value as any)?.blocks || []
})

const globalVars = computed(() => ({
  '--spacing-sm': '16px',
  '--spacing-md': '24px',
  '--spacing-lg': '40px',
  '--bg-color': '#ffffff',
  '--bg-gradient': 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
  '--chrome-bg': 'rgba(255,255,255,0.92)',
  '--chrome-border': 'rgba(148,163,184,0.16)',
  '--card-bg': 'rgba(255,255,255,0.92)',
  '--card-border': 'rgba(148,163,184,0.16)',
  '--text-color': '#0f172a',
  '--text-muted': '#64748b',
  '--primary-vibe': '#ff2442',
  '--primary-vibe-light': 'rgba(255,36,66,0.12)',
  ...((renderStyleData.value?.global_vars || {}) as Record<string, string>),
  ...(((renderPageData.value as any)?.page_theme || {}) as Record<string, string>),
}))

const globalStyles = computed(() => Object.entries(globalVars.value).map(([k, v]) => `${k}: ${v}`).join(';'))

const topBarStyle = computed(() => ({
  background: 'var(--chrome-bg)',
  borderColor: 'var(--chrome-border)',
  color: 'var(--text-color)',
}))

const bottomBarStyle = computed(() => ({
  background: 'var(--chrome-bg)',
  borderColor: 'var(--chrome-border)',
  color: 'var(--text-color)',
}))

const iconButtonStyle = computed(() => ({
  color: 'var(--text-muted)',
  background: 'var(--card-bg-soft, rgba(255,255,255,0.72))',
}))

const mutedTabStyle = computed(() => ({
  color: 'var(--text-muted)',
  fontWeight: '500',
}))

const activeTabStyle = computed(() => ({
  color: 'var(--text-color)',
  borderColor: 'var(--primary-vibe)',
}))

const composerStyle = computed(() => ({
  background: 'var(--card-bg-soft, rgba(255,255,255,0.72))',
  borderColor: 'var(--card-border)',
  color: 'var(--text-muted)',
}))

const actionBarStyle = computed(() => ({
  color: 'var(--text-muted)',
}))

const emptyCardStyle = computed(() => ({
  background: 'var(--card-bg)',
  border: '1px solid var(--card-border)',
  boxShadow: 'var(--card-shadow, 0 12px 30px rgba(15,23,42,0.06))',
}))

const skeletonStyle = computed(() => ({
  background: 'var(--card-bg-soft, rgba(255,255,255,0.72))',
}))

const emptyStateStyle = computed(() => ({
  color: 'var(--text-muted)',
}))
</script>

<style scoped>
.preview-shell {
  width: 100%;
  max-width: min(100%, 580px);
  background-color: var(--bg-color);
  background-image: var(--bg-gradient);
  min-height: 100%;
  box-shadow: 0 10px 50px rgba(0,0,0,0.1);
  border-radius: 24px;
  position: relative;
  overflow-x: hidden;
  margin: 0 auto;
}

@media (max-width: 767px) {
  .preview-shell {
    max-width: 100%;
    border-radius: 0;
  }
}

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

.list-move {
  transition: transform 0.5s ease;
}
</style>
