<template>
  <div class="flex h-screen w-screen bg-[#1e1e1e] overflow-hidden font-sans">

    <div class="w-[400px] border-r border-[#333] flex flex-col z-20 shadow-xl relative">
      <ChatPanel />
    </div>

    <div class="flex-1 flex flex-col relative bg-gray-100">
      <PreviewIframe />
    </div>

  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import ChatPanel from './components/chat/ChatPanel.vue'
import PreviewIframe from './components/canvas/PreviewIframe.vue'
import { useChatStore } from './stores/useChatStore'

const chatStore = useChatStore()

// 挂载时，主动连接 WebSocket 引擎
onMounted(() => {
  chatStore.connectWebSocket()
})
</script>
