<template>
  <div class="flex flex-col h-full bg-[#1e1e1e] text-gray-300">
    <div class="h-14 border-b border-[#333] flex items-center px-4 shrink-0 bg-[#252526] gap-3">
      <h1 class="text-sm font-bold text-gray-100 flex items-center gap-2 whitespace-nowrap">
        <span>⚡️</span> XHS-Forge
      </h1>
      
      <!-- ✨ 创作者人设切换器 -->
      <div class="flex-1 flex justify-center">
        <select 
          v-model="creatorPersona" 
          class="bg-[#1e1e1e] text-[11px] text-blue-400 border border-[#444] rounded-full px-3 py-1 outline-none focus:border-blue-500 transition-all cursor-pointer hover:bg-[#2d2d2d]"
        >
          <option value="硬核数码博主">📸 硬核数码博主</option>
          <option value="毒舌美妆专家">💄 毒舌美妆专家</option>
          <option value="温柔探店达人">🍰 温柔探店达人</option>
          <option value="深夜感性诗人">🌙 深夜感性诗人</option>
        </select>
      </div>

      <div class="flex items-center gap-3 ml-auto">
        <button 
          @click="showInspector = !showInspector"
          class="p-1.5 hover:bg-[#333] rounded transition-colors text-gray-400 hover:text-blue-400"
          :class="{ 'text-blue-400 bg-[#333]': showInspector }"
          title="切换 Agent 驾驶舱"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"></path></svg>
        </button>

        <span v-if="wsStatus === 'connected'" class="flex items-center gap-1.5 text-xs text-green-400 whitespace-nowrap">
          <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        </span>
        <span v-else class="text-xs text-red-400 whitespace-nowrap">🔴</span>
      </div>
    </div>

    <!-- ✨ Agent Inspector 驾驶舱 (可折叠) -->
    <div v-if="showInspector" class="p-4 pb-0 animate-in slide-in-from-top duration-300">
      <AgentInspector />
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar" ref="msgListRef">
      <div v-for="msg in messages" :key="msg.id" class="flex flex-col group">

        <div v-if="msg.role === 'user'" class="self-end max-w-[85%]">
          <div class="bg-blue-600 text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm shadow-md flex flex-col gap-2">
            <div v-if="msg.imageUrls && msg.imageUrls.length > 0" class="flex flex-wrap gap-2 mb-1">
              <img v-for="(url, idx) in msg.imageUrls" :key="idx" :src="url" class="w-20 h-20 object-cover rounded-lg border border-blue-400/50 shadow-sm" alt="" />
            </div>
            <span>{{ msg.content }}</span>
          </div>
          <div class="flex justify-end mt-2 opacity-0 group-hover:opacity-100 transition-opacity" v-if="msg.checkpointId">
            <button
              @click="chatStore.rollbackTo(msg.checkpointId!)"
              class="text-[11px] px-2 py-1 bg-[#333] text-gray-400 hover:text-blue-400 hover:bg-[#444] rounded flex items-center gap-1.5 transition-all"
              title="回退并在此处开辟新分支"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path></svg>
              回退到此版本
            </button>
          </div>
        </div>

        <div v-else class="self-start max-w-[90%] w-full">
          <!-- ✨ 思维链实时透传面板 -->
          <div v-if="msg.thoughts && msg.thoughts.length > 0" class="mb-2 flex flex-col gap-1.5 w-full">
            <details 
              v-for="(thought, idx) in msg.thoughts" 
              :key="idx" 
              class="group/thought border border-[#3c3c3c] rounded-lg bg-[#252526]/50 transition-all duration-200"
            >
              <summary class="flex items-center cursor-pointer p-2 text-[10px] font-medium text-gray-400 hover:text-blue-400 hover:bg-[#2d2d2d] transition-colors rounded-lg list-none">
                <span class="mr-2 opacity-70 group-open/thought:rotate-12 transition-transform">🧠</span>
                <span>{{ thought.node }} 已完成思考</span>
                <svg class="w-3 h-3 ml-auto transition-transform duration-200 group-open/thought:rotate-180 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div class="p-3 pt-1 text-[11px] text-gray-400 border-t border-[#3c3c3c]/50 leading-relaxed font-mono italic bg-[#1e1e1e]/30 rounded-b-lg">
                {{ thought.text }}
              </div>
            </details>
          </div>

          <div class="bg-[#2d2d2d] text-gray-200 px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed whitespace-pre-wrap border border-[#3c3c3c] shadow-md relative">
            <span v-if="!msg.content && msg.streaming" class="animate-pulse text-gray-500 italic">正在思考文案...</span>
            <Typewriter :text="msg.content" :active="msg.streaming" :speed="10" />
          </div>
          <div class="flex justify-start mt-2 opacity-0 group-hover:opacity-100 transition-opacity" v-if="msg.checkpointId">
            <button
              @click="chatStore.rollbackTo(msg.checkpointId!)"
              class="text-[11px] px-2 py-1 bg-[#333] text-gray-400 hover:text-blue-400 hover:bg-[#444] rounded flex items-center gap-1.5 transition-all"
              title="回退并在此处开辟新分支"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path></svg>
              回退到此版本
            </button>
          </div>
        </div>
      </div>

      <!-- Agent 运行状态播报 -->
      <div v-if="thoughtText || currentNode" class="self-start flex flex-col gap-2 mt-2 w-[90%] animate-in fade-in slide-in-from-left duration-300">
        <div class="flex items-center gap-2 text-xs text-blue-300 bg-blue-900/20 border border-blue-800/30 px-3 py-1.5 rounded-full w-max shadow-sm">
          <svg class="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <span class="font-medium">{{ thoughtText || (nodeMap[currentNode] || currentNode) }}</span>
        </div>
        
        <!-- 实时预览内部节点的流式输出 -->
        <div v-if="nodeStreamOutput" class="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 overflow-hidden shadow-inner">
          <div class="text-[10px] text-gray-500 mb-2 uppercase tracking-wider font-semibold flex justify-between">
            <span>Live Stream</span>
            <span class="animate-pulse text-blue-500">●</span>
          </div>
          <div class="text-[11px] text-blue-400/80 whitespace-pre-wrap font-mono max-h-[150px] overflow-y-auto custom-scrollbar">
            <Typewriter :text="nodeStreamOutput" :active="true" :speed="5" />
          </div>
        </div>
      </div>
    </div>

    <div class="p-4 bg-[#252526] border-t border-[#333] shrink-0">

      <div v-if="imageAssets && imageAssets.length > 0" class="mb-3">
        <h3 class="text-[11px] text-gray-500 mb-1.5 flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          全局视图资产 (Hover 查看 AI 语义)
        </h3>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="(asset, idx) in imageAssets"
            :key="asset.url + idx"
            class="relative group w-10 h-10 rounded-md border border-[#444] bg-[#1e1e1e] cursor-pointer"
          >
            <img :src="asset.url" class="w-full h-full object-cover rounded-md opacity-80 group-hover:opacity-100 transition-opacity" alt="" />
            <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50">
              <div class="bg-black/90 backdrop-blur-sm text-gray-200 text-[11px] px-2.5 py-1.5 rounded flex items-center shadow-xl border border-[#444] whitespace-nowrap max-w-[240px]">
                <span class="mr-1.5 text-blue-400 shrink-0">👁️</span>
                <span class="break-words">{{ asset.desc }}</span>
              </div>
              <div class="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-black/90"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="selectedComponentId" class="mb-2 flex items-center">
        <div class="bg-blue-900/40 border border-blue-700 text-blue-300 text-xs px-3 py-1.5 rounded-full flex items-center gap-2 shadow-sm animate-in fade-in zoom-in duration-200">
          <span>🎯 正在局部修改: <strong class="font-mono text-blue-200">{{ selectedComponentId }}</strong></span>
          <button @click="setSelectedComponent(null)" class="hover:text-white transition-colors ml-1">✖</button>
        </div>
      </div>

      <!-- 上传中 -->
      <div v-if="pendingImages.some(p => p.status === 'uploading')" class="flex flex-wrap gap-2 mb-2 p-2 bg-[#1e1e1e] rounded-lg border border-[#3c3c3c]">
        <div v-for="(img, idx) in pendingImages.filter(p => p.status === 'uploading')" :key="idx" class="relative">
          <img :src="img.preview" class="w-14 h-14 object-cover rounded-md border border-[#444]" alt="" />
          <div class="absolute inset-0 bg-black/50 flex items-center justify-center rounded-md">
            <svg class="animate-spin w-4 h-4 text-white" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          </div>
        </div>
      </div>

      <!-- ✨ 哨兵新增：实时热搜榜 (Hot Trends) -->
      <div v-if="hotTrends && hotTrends.length > 0" class="mb-3">
        <div class="flex items-center gap-2 mb-1.5 px-1">
          <span class="text-[10px] font-bold text-orange-500 uppercase tracking-wider flex items-center gap-1">
            <span class="animate-bounce">🔥</span> Hot Trends
          </span>
          <div class="h-[1px] flex-1 bg-gradient-to-r from-orange-500/30 to-transparent"></div>
        </div>
        <div class="flex gap-2 overflow-x-auto pb-1 no-scrollbar mask-fade-right">
          <button 
            v-for="(trend, idx) in hotTrends" 
            :key="idx"
            @click="quickSend(trend)"
            class="whitespace-nowrap px-3 py-1.5 bg-[#2d2d2d] hover:bg-blue-600/20 border border-[#444] hover:border-blue-500/50 rounded-full text-[11px] text-gray-400 hover:text-blue-400 transition-all flex items-center gap-1.5 group"
          >
            <span class="opacity-50 group-hover:opacity-100 text-orange-400 font-mono">#{{ idx + 1 }}</span>
            {{ trend }}
          </button>
        </div>
      </div>

      <div class="relative flex items-end gap-2">
        <input type="file" ref="fileInput" accept="image/*" multiple class="hidden" @change="handleFileSelect" />
        <button @click="triggerFileInput" class="p-2.5 text-gray-400 hover:text-white hover:bg-[#3c3c3c] rounded-lg transition-colors shrink-0 mb-1" title="上传图片">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
        </button>

        <textarea
          v-model="inputText"
          @keydown.enter.prevent="handleSend"
          placeholder="给 AI 下达指令 (Enter 发送)..."
          class="w-full bg-[#1e1e1e] text-sm text-gray-200 border border-[#3c3c3c] rounded-xl pl-4 pr-12 py-3 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none h-[52px] min-h-[52px] max-h-32 placeholder-gray-600 transition-all"
        ></textarea>

        <button
          @click="handleSend"
          :disabled="(!inputText.trim() && imageAssets.length === 0) || isUploading || currentNode !== ''"
          class="absolute right-2 bottom-2 p-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-[#3c3c3c] disabled:text-gray-500 text-white rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import { uploadImage } from '../../api/upload'
import Typewriter from '../common/Typewriter.vue'
import AgentInspector from './AgentInspector.vue'

const chatStore = useChatStore()
const { messages, wsStatus, currentNode, thoughtText, nodeStreamOutput, selectedComponentId, imageAssets, creatorPersona, hotTrends } = storeToRefs(chatStore)
const { setSelectedComponent, addImageAsset, removeImageAsset } = chatStore
const inputText = ref('')
const msgListRef = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const showInspector = ref(false)

const quickSend = (trend: string) => {
  inputText.value = `帮我针对「${trend}」做一个深度种草笔记`
  handleSend()
}

interface PendingImage {
  file: File
  preview: string
  ossUrl: string
  status: 'uploading' | 'success' | 'error'
}
const pendingImages = ref<PendingImage[]>([])
const isUploading = computed(() => pendingImages.value.some(img => img.status === 'uploading'))

const nodeMap: Record<string, string> = {
  'asset_processor': '理解上传图片',
  'intent_agent': '意图分析大脑',
  'content_node': '文案创作大脑',
  'structure_node': '解析页面骨架',
  'style_node': '生成 CSS 样式',
  'render': '云端打包渲染'
}

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = async (e: Event) => {
  const target = e.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const files = Array.from(target.files)

  for (const file of files) {
    const previewUrl = URL.createObjectURL(file)
    const imgObj: PendingImage = {
      file,
      preview: previewUrl,
      ossUrl: '',
      status: 'uploading'
    }
    pendingImages.value.push(imgObj)

    try {
      const { url } = await uploadImage(file)
      imgObj.ossUrl = url
      imgObj.status = 'success'
      addImageAsset({ url, desc: '用户上传图片' })
      URL.revokeObjectURL(previewUrl)
    } catch (error) {
      console.error('上传失败', error)
      imgObj.status = 'error'
    }
  }
  pendingImages.value = pendingImages.value.filter(p => p.status === 'uploading' || p.status === 'error')
  target.value = ''
}

const handleSend = () => {
  if ((!inputText.value.trim() && imageAssets.value.length === 0) || isUploading.value || currentNode.value !== '') return

  chatStore.sendMessage(inputText.value)
  inputText.value = ''
}

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTo({
        top: msgListRef.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}

watch(messages, scrollToBottom, { deep: true })
watch(nodeStreamOutput, scrollToBottom)
</script>

<style scoped>
.typewriter-cursor {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background-color: #3b82f6;
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.8s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
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

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.mask-fade-right {
  mask-image: linear-gradient(to right, black 85%, transparent 100%);
}
</style>
