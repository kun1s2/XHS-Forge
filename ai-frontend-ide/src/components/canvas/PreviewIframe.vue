<template>
  <div class="flex flex-col h-full relative bg-[#1e1e1e] border-l border-[#333]">
    <div class="h-14 bg-[#252526] border-b border-[#333] flex items-center px-4 shrink-0 justify-between z-10 shadow-sm">

      <div class="flex gap-1 bg-[#1e1e1e] p-1 rounded-lg border border-[#333]">
        <button
          @click="viewMode = 'preview'"
          :class="{'bg-[#333] text-gray-100 shadow': viewMode === 'preview', 'text-gray-500 hover:text-gray-300': viewMode !== 'preview'}"
          class="px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5"
        >
          <span>👁️</span> 预览视图
        </button>
        <button
          @click="viewMode = 'code'"
          :class="{'bg-[#333] text-gray-100 shadow': viewMode === 'code', 'text-gray-500 hover:text-gray-300': viewMode !== 'code'}"
          class="px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5"
        >
          <span>💻</span> 源码模式
        </button>
        <button
          @click="viewMode = 'prompts'"
          :class="{'bg-[#333] text-gray-100 shadow': viewMode === 'prompts', 'text-gray-500 hover:text-gray-300': viewMode !== 'prompts'}"
          class="px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5"
        >
          <span>🧪</span> 提示词检查
        </button>
        <button
          @click="viewMode = 'state'"
          :class="{'bg-[#333] text-gray-100 shadow': viewMode === 'state', 'text-gray-500 hover:text-gray-300': viewMode !== 'state'}"
          class="px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5"
        >
          <span>🧠</span> Agent 状态
        </button>
      </div>

      <div class="flex items-center">
        <button
          v-if="viewMode === 'code' && sourceCode"
          @click="copyCode"
          class="flex items-center gap-1 text-xs px-3 py-1.5 rounded-md bg-blue-600/20 text-blue-400 border border-blue-900/50 hover:bg-blue-600/40 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
          {{ isCopied ? '已复制！' : '复制代码' }}
        </button>
        <div v-else-if="viewMode === 'preview'" class="text-xs text-gray-500 max-w-[300px] truncate bg-[#1e1e1e] px-3 py-1.5 rounded border border-[#333]">
          🔒 {{ previewUrl ? 'Dynamic JSON Renderer' : '等待渲染...' }}
        </div>
      </div>
    </div>

    <div class="flex-1 relative overflow-hidden bg-[#141414] flex">

      <div v-show="viewMode === 'preview'" class="w-full h-full overflow-y-auto bg-[#141414] flex items-start justify-center custom-scrollbar">
        <DynamicRenderer v-if="pageData && Object.keys(pageData).length > 0" class="shadow-2xl my-8 border border-[#333]/50 rounded-xl" />
        <div v-else class="absolute inset-0 flex flex-col items-center justify-center text-gray-600 bg-[#141414]">
          <div class="w-20 h-20 rounded-full bg-[#1e1e1e] border border-[#333] flex items-center justify-center mb-6 shadow-inner">
            <span class="text-4xl animate-pulse">🎨</span>
          </div>
          <p class="font-bold text-sm tracking-widest uppercase opacity-40">Ready for Creation</p>
          <p class="text-[10px] mt-2 opacity-30 italic">Waiting for Agent to generate UI structure...</p>
        </div>
      </div>

      <div
        v-show="viewMode === 'code'"
        class="w-full h-full bg-[#1e1e1e] overflow-auto p-6 text-gray-300 font-mono text-sm leading-relaxed"
      >
        <div v-if="sourceCode" class="w-full h-full">
          <pre class="whitespace-pre-wrap break-all selection:bg-blue-900 selection:text-white">{{ sourceCode }}</pre>
        </div>
        <div v-else class="w-full h-full flex items-center justify-center text-gray-600">
          <p>暂无源码生成，请先在聊天框下达指令。</p>
        </div>
      </div>

      <div
        v-show="viewMode === 'prompts'"
        class="w-full h-full bg-[#1e1e1e] overflow-auto p-6 text-gray-300 font-mono text-sm leading-relaxed"
      >
        <div v-if="Object.keys(nodePrompts).length > 0" class="flex flex-col gap-10">
          <div v-for="(messages, node) in nodePrompts" :key="node" class="flex flex-col gap-4">
            <!-- 节点标题头 -->
            <div class="flex items-center gap-2 text-blue-400 font-bold border-b border-[#333] pb-2 uppercase tracking-widest">
              <span class="bg-blue-900/30 px-2 py-0.5 rounded text-[10px]">AGENT NODE</span>
              <span>{{ node }}</span>
            </div>
            
            <!-- 颗粒化消息列表 -->
            <div class="flex flex-col gap-4">
              <div v-for="(msg, mIdx) in (Array.isArray(messages) ? (messages as any[]) : [{role: 'info', content: messages}])" :key="mIdx" class="group relative flex flex-col gap-2 bg-[#252526] rounded-lg border border-[#333] p-4 hover:border-[#444] transition-colors">
                
                <!-- 消息角色标签与复制按钮 -->
                <div class="flex items-center justify-between">
                  <span 
                    class="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase"
                    :class="{
                      'bg-purple-900/40 text-purple-400': msg.role === 'system',
                      'bg-green-900/40 text-green-400': msg.role === 'human' || msg.role === 'user',
                      'bg-gray-700 text-gray-400': msg.role !== 'system' && msg.role !== 'human' && msg.role !== 'user'
                    }"
                  >
                    {{ msg.role }}
                  </span>
                  
                  <!-- ✨ 独立复制按钮 -->
                  <button 
                    @click="copyIndividualPrompt(msg.content, node + mIdx)" 
                    class="text-[10px] flex items-center gap-1.5 transition-all"
                    :class="copiedSubNode === (node + mIdx) ? 'text-green-400' : 'text-gray-500 hover:text-white opacity-0 group-hover:opacity-100'"
                  >
                    <template v-if="copiedSubNode === (node + mIdx)">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                      已复制！
                    </template>
                    <template v-else>
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                      复制此条
                    </template>
                  </button>
                </div>

                <!-- 消息内容 -->
                <pre class="whitespace-pre-wrap text-gray-400 text-xs leading-normal font-mono select-text">{{ msg.content }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-600 gap-4">
          <span class="text-4xl opacity-20">🔎</span>
          <p>暂无提示词快照，请先让 Agent 执行任务。</p>
        </div>
      </div>

      <!-- ✨ 哨兵白盒化：Agent 决策状态看板 -->
      <div
        v-show="viewMode === 'state'"
        class="w-full h-full bg-[#1e1e1e] overflow-auto p-8"
      >
        <div class="max-w-4xl mx-auto">
          <AgentInspector />
        </div>
      </div>

      <div
        v-if="viewMode === 'preview' && hoveredComponentId && pageData[hoveredComponentId]"
        class="absolute right-4 top-4 w-72 bg-[#1e1e1e]/95 backdrop-blur shadow-2xl rounded-xl border border-[#333] p-4 z-50 pointer-events-none transition-all"
      >
        <div class="text-xs font-bold text-blue-400 mb-2 pb-2 border-b border-[#333] flex items-center justify-between">
          <span>🔍 {{ hoveredComponentId }}</span>
          <span class="text-gray-500">{{ (pageData[hoveredComponentId] as Record<string, unknown>)?.type }}</span>
        </div>
        <pre class="text-[10px] text-green-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">{{ JSON.stringify(pageData[hoveredComponentId], null, 2) }}</pre>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import DynamicRenderer from '../renderers/DynamicRenderer.vue'
import AgentInspector from '../chat/AgentInspector.vue'

const chatStore = useChatStore()
const { previewUrl, pageData, nodePrompts, hoveredComponentId, sourceCode } = storeToRefs(chatStore)

// 控制当前视图是预览、代码、提示词检查器还是 Agent 状态
const viewMode = ref<'preview' | 'code' | 'prompts' | 'state'>('preview')
const isCopied = ref(false)
const copiedSubNode = ref<string | null>(null) // 追踪当前被复制的单条提示词 ID

// 一键复制代码
const copyCode = async () => {
  if (!sourceCode.value) return
  try {
    await navigator.clipboard.writeText(sourceCode.value)
    isCopied.value = true
    setTimeout(() => { isCopied.value = false }, 2000)
  } catch (err) {
    console.error('复制失败:', err)
    alert('复制失败，请手动选择复制')
  }
}

// ✨ 独立复制单条提示词
const copyIndividualPrompt = async (text: string, subNodeId: string) => {
  try {
    await navigator.clipboard.writeText(text)
    copiedSubNode.value = subNodeId
    setTimeout(() => { copiedSubNode.value = null }, 2000)
  } catch (err) {
    console.error('复制失败:', err)
  }
}

// 监听 iframe 传来的 hover/select 事件 (现在不通过 iframe，但保留以便兼容)
const handleMessage = (event: MessageEvent) => {
  if (!event.data) return
  if (event.data.type === 'SELECT_REGION') {
    chatStore.setSelectedComponent(event.data.id)
  } else if (event.data.type === 'HOVER_REGION') {
    hoveredComponentId.value = event.data.id
  } else if (event.data.type === 'UNHOVER_REGION') {
    hoveredComponentId.value = null
  }
}

onMounted(() => window.addEventListener('message', handleMessage))
onUnmounted(() => window.removeEventListener('message', handleMessage))
</script>
