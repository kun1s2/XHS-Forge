<template>
  <div class="flex h-screen w-screen bg-[#1e1e1e] overflow-hidden font-sans text-gray-300">
    
    <!-- 左侧会话管理侧边栏 -->
    <aside 
      class="bg-[#252526] border-r border-[#333] flex flex-col transition-all duration-300 ease-in-out relative z-30 shadow-2xl"
      :class="chatStore.isSidebarOpen ? 'w-64' : 'w-0 overflow-hidden'"
    >
      <!-- 顶部新建按钮 -->
      <div class="p-4 flex-shrink-0 border-b border-[#333]">
        <button 
          @click="chatStore.createNewSession"
          class="w-full py-2 px-4 bg-[#FF2442] hover:bg-[#D91F39] text-white rounded-lg flex items-center justify-center gap-2 transition-all font-bold text-xs shadow-lg active:scale-95 uppercase tracking-wider"
        >
          <span class="text-lg leading-none">+</span> New Project
        </button>
      </div>

      <!-- 会话历史列表 -->
      <div class="flex-1 overflow-y-auto px-2 space-y-1 py-4 custom-scrollbar bg-[#252526]">
        <div 
          v-for="session in chatStore.sessions" 
          :key="session.thread_id"
          @click="chatStore.switchSession(session.thread_id)"
          :class="[
            'group relative p-3 rounded-md cursor-pointer transition-all border border-transparent flex flex-col gap-1',
            chatStore.threadId === session.thread_id 
              ? 'bg-[#37373d] border-[#007acc]/30 text-blue-400 shadow-inner' 
              : 'hover:bg-[#2d2d2d] text-gray-400'
          ]"
        >
          <div class="flex items-center gap-2">
            <span class="text-[10px] opacity-40">#</span>
            <div class="text-xs font-semibold truncate flex-1">
              {{ session.title }}
            </div>
          </div>
          <div class="flex justify-between items-center text-[9px] opacity-40 mt-1 font-mono">
            <span>{{ session.thread_id.slice(7, 15) }}</span>
            <span>{{ formatDate(session.updated_at) }}</span>
          </div>
          
          <div 
            v-if="chatStore.threadId === session.thread_id"
            class="absolute left-0 top-3 bottom-3 w-0.5 bg-blue-500 rounded-r-full"
          ></div>
        </div>
      </div>

      <!-- 底部系统状态 -->
      <div class="p-3 border-t border-[#333] bg-[#1e1e1e]/50 flex items-center gap-3">
        <div class="w-7 h-7 rounded bg-[#333] flex items-center justify-center text-[10px] font-bold text-gray-500 border border-[#444]">XF</div>
        <div class="flex flex-col">
          <span class="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">X-Forge Engine</span>
          <div class="flex items-center gap-1.5">
             <span class="w-1.5 h-1.5 rounded-full" :class="chatStore.wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'"></span>
             <span class="text-[9px] opacity-50">{{ chatStore.wsStatus === 'connected' ? 'ONLINE' : 'OFFLINE' }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主交互区域：对话框 -->
    <div 
      class="w-[380px] bg-[#1e1e1e] border-r border-[#333] flex flex-col z-20 shadow-xl relative transition-all duration-300"
    >
      <button 
        @click="chatStore.isSidebarOpen = !chatStore.isSidebarOpen"
        class="absolute -left-2 top-10 z-40 w-4 h-8 bg-[#333] hover:bg-[#444] rounded flex items-center justify-center shadow-md transition-all border border-[#444] group"
      >
        <span class="text-[8px] text-gray-500 group-hover:text-blue-400">{{ chatStore.isSidebarOpen ? '◀' : '▶' }}</span>
      </button>
      
      <ChatPanel />
    </div>

    <!-- 右侧画布：预览 -->
    <div class="flex-1 flex flex-col relative bg-[#090909]">
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

const formatDate = (dateStr: string) => {
  if (!dateStr) return '--:--'
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`
}

onMounted(() => {
  chatStore.fetchSessions()
})
</script>

<style>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #444;
}
</style>
