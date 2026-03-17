<template>
  <div class="flex h-screen w-screen bg-[#F8F8F8] overflow-hidden font-sans text-[#333]">
    
    <!-- 左侧会话管理侧边栏 -->
    <aside 
      class="bg-white border-r border-gray-200 flex flex-col transition-all duration-300 ease-in-out relative z-30 shadow-sm"
      :class="chatStore.isSidebarOpen ? 'w-64' : 'w-0 overflow-hidden'"
    >
      <!-- 顶部新建按钮 -->
      <div class="p-4 flex-shrink-0">
        <button 
          @click="chatStore.createNewSession"
          class="w-full py-2.5 px-4 bg-[#FF2442] hover:bg-[#D91F39] text-white rounded-xl flex items-center justify-center gap-2 transition-all font-semibold text-sm shadow-md active:scale-95"
        >
          <span class="text-xl leading-none">+</span> 新建种草页面
        </button>
      </div>

      <!-- 会话历史列表 -->
      <div class="flex-1 overflow-y-auto px-3 space-y-1.5 py-2 custom-scrollbar">
        <div 
          v-for="session in chatStore.sessions" 
          :key="session.thread_id"
          @click="chatStore.switchSession(session.thread_id)"
          :class="[
            'group relative p-3 rounded-xl cursor-pointer transition-all border border-transparent',
            chatStore.threadId === session.thread_id 
              ? 'bg-[#FF2442]/5 border-[#FF2442]/10 text-[#FF2442]' 
              : 'hover:bg-gray-50 text-gray-600'
          ]"
        >
          <div class="flex flex-col gap-1">
            <div class="text-sm font-bold truncate pr-4">
              {{ session.title }}
            </div>
            <div class="text-[10px] opacity-50 flex justify-between items-center">
              <span>{{ session.thread_id.slice(7, 15) }}</span>
              <span>{{ formatDate(session.updated_at) }}</span>
            </div>
          </div>
          <!-- 选中指示条 -->
          <div 
            v-if="chatStore.threadId === session.thread_id"
            class="absolute left-0 top-3 bottom-3 w-1 bg-[#FF2442] rounded-r-full"
          ></div>
        </div>
      </div>

      <!-- 底部用户信息 -->
      <div class="p-4 border-t border-gray-50 bg-gray-50/50 flex items-center gap-3">
        <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-[#FF2442] to-[#FF7E8D] shadow-inner flex items-center justify-center text-white text-[10px] font-bold">XF</div>
        <div class="flex flex-col">
          <span class="text-xs font-bold text-gray-700">X-Forge Pro</span>
          <span class="text-[9px] text-green-500 font-medium">● 引擎已就绪</span>
        </div>
      </div>
    </aside>

    <!-- 主交互区域：对话框 -->
    <div 
      class="w-[420px] bg-white border-r border-gray-200 flex flex-col z-20 shadow-sm relative transition-all duration-300"
      :class="{ 'border-l': !chatStore.isSidebarOpen }"
    >
      <!-- 侧边栏折叠开关 -->
      <button 
        @click="chatStore.isSidebarOpen = !chatStore.isSidebarOpen"
        class="absolute -left-3 top-1/2 -translate-y-1/2 z-40 w-6 h-12 bg-white border border-gray-200 rounded-full flex items-center justify-center hover:bg-gray-50 shadow-sm transition-transform hover:scale-110 group"
      >
        <span class="text-[10px] text-gray-400 group-hover:text-[#FF2442]">{{ chatStore.isSidebarOpen ? '◀' : '▶' }}</span>
      </button>
      
      <ChatPanel />
    </div>

    <!-- 右侧画布：预览 -->
    <div class="flex-1 flex flex-col relative bg-[#F0F2F5]">
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
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`
}

onMounted(() => {
  // 挂载时，先拉取会话列表
  chatStore.fetchSessions()
})
</script>

<style>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #E5E7EB;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #D1D5DB;
}
</style>
