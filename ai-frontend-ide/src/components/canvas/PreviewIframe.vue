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
          <span
            v-if="pendingFactConflictCount > 0"
            class="ml-1 inline-flex min-w-[18px] items-center justify-center rounded-full border border-amber-700/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-300"
          >
            {{ pendingFactConflictCount }}
          </span>
        </button>
        <button
          @click="viewMode = 'assets'"
          :class="{'bg-[#333] text-gray-100 shadow': viewMode === 'assets', 'text-gray-500 hover:text-gray-300': viewMode !== 'assets'}"
          class="px-4 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5"
        >
          <span>🖼️</span> 素材库
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

      <div v-show="viewMode === 'preview'" class="w-full h-full overflow-y-auto bg-[#141414] p-3 lg:p-4 custom-scrollbar">
        <div class="mx-auto w-full max-w-6xl">
          <div v-if="hasRenderableDocument" class="rounded-[28px] border border-[#333] bg-[#1b1b1d] p-3 shadow-[0_18px_40px_rgba(0,0,0,0.22)] lg:p-4">
            <!-- ✨ 4.0 重构修复：依赖 blocks 列表而非旧的 root 树 -->
            <DynamicRenderer class="shadow-2xl border border-[#333]/50 rounded-xl" />
          </div>
          <div v-else class="rounded-[28px] border border-[#333] bg-[#1b1b1d] px-6 py-16 text-gray-600 shadow-[0_18px_40px_rgba(0,0,0,0.22)]">
            <div class="flex flex-col items-center justify-center text-center">
              <div class="mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-[#333] bg-[#1e1e1e] shadow-inner">
                <span class="text-4xl animate-pulse">🎨</span>
              </div>
              <p class="font-bold text-sm tracking-widest uppercase opacity-40">Ready for Creation</p>
              <p class="mt-2 text-[10px] opacity-30 italic">Waiting for Agent to generate UI structure...</p>
            </div>
          </div>
        </div>
      </div>

      <div
        v-show="viewMode === 'code'"
        class="w-full h-full bg-[#141414] overflow-auto p-3 lg:p-4"
      >
        <div v-if="sourceCode" class="mx-auto h-full w-full max-w-6xl rounded-[26px] border border-[#333] bg-[#1e1e1e] p-5 text-gray-300 font-mono text-sm leading-relaxed shadow-[0_18px_40px_rgba(0,0,0,0.22)] lg:p-6">
          <pre class="whitespace-pre-wrap break-all selection:bg-blue-900 selection:text-white">{{ sourceCode }}</pre>
        </div>
        <div v-else class="mx-auto flex h-[calc(100vh-220px)] w-full max-w-6xl items-center justify-center rounded-[26px] border border-[#333] bg-[#1e1e1e] text-gray-600 shadow-[0_18px_40px_rgba(0,0,0,0.22)]">
          <p>暂无源码生成，请先在聊天框下达指令。</p>
        </div>
      </div>

      <div
        v-show="viewMode === 'prompts'"
        class="w-full h-full bg-[#141414] overflow-auto p-3 lg:p-4"
      >
        <div class="mx-auto w-full max-w-6xl rounded-[26px] border border-[#333] bg-[#1e1e1e] p-5 text-gray-300 shadow-[0_18px_40px_rgba(0,0,0,0.22)] lg:p-6">
          <div class="flex flex-wrap items-start justify-between gap-4 border-b border-[#333] pb-4">
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <span class="rounded-full border border-[#2f456d] bg-[#162033] px-2 py-0.5 text-[9px] font-bold text-[#8ab4ff]">Prompt Lab</span>
                <span class="text-[10px] uppercase tracking-[0.18em] text-gray-500">系统提示词追踪</span>
              </div>
              <div class="text-[14px] font-bold text-gray-100">查看本轮真正参与决策的提示词快照</div>
              <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">面板现在优先展示 `planner / note_editor / intent` 的 prompt snapshot。如果某个关键节点没有覆盖，你会在下面直接看到缺口。</p>
            </div>
            <div class="grid min-w-[240px] grid-cols-2 gap-2 sm:min-w-[320px]">
              <div class="rounded-2xl border border-cyan-800/20 bg-cyan-950/10 px-3 py-2.5">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">节点数</div>
                <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ promptNodeCount }}</div>
              </div>
              <div class="rounded-2xl border border-violet-800/20 bg-violet-950/10 px-3 py-2.5">
                <div class="text-[9px] uppercase tracking-wider text-gray-500">消息条数</div>
                <div class="mt-1 text-[13px] font-bold text-violet-300">{{ promptMessageCount }}</div>
              </div>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <button
              class="rounded-full border px-3 py-1 text-[10px] font-bold transition-all"
              :class="showPromptSystemOnly ? 'border-cyan-700/30 bg-cyan-950/20 text-cyan-300' : 'border-[#3a3a3a] bg-black/10 text-gray-400 hover:text-gray-200'"
              @click="showPromptSystemOnly = !showPromptSystemOnly"
            >
              {{ showPromptSystemOnly ? '只看 System · 开' : '只看 System' }}
            </button>
            <button
              class="rounded-full border px-3 py-1 text-[10px] font-bold transition-all"
              :class="showPromptKeyNodesOnly ? 'border-violet-700/30 bg-violet-950/20 text-violet-300' : 'border-[#3a3a3a] bg-black/10 text-gray-400 hover:text-gray-200'"
              @click="showPromptKeyNodesOnly = !showPromptKeyNodesOnly"
            >
              {{ showPromptKeyNodesOnly ? '只看关键节点 · 开' : '只看关键节点' }}
            </button>
            <button
              class="rounded-full border px-3 py-1 text-[10px] font-bold transition-all"
              :class="copiedPromptBundle ? 'border-emerald-700/30 bg-emerald-950/20 text-emerald-300' : 'border-[#3a3a3a] bg-black/10 text-gray-400 hover:text-gray-200'"
              @click="copyPromptBundle"
            >
              {{ copiedPromptBundle ? '已复制整轮 Prompt' : '复制整轮 Prompt Bundle' }}
            </button>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="item in promptCoverage"
              :key="item.node"
              class="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-[10px] font-bold"
              :class="item.present ? 'border-emerald-700/30 bg-emerald-950/20 text-emerald-300' : 'border-amber-700/30 bg-amber-950/20 text-amber-300'"
            >
              <span>{{ item.present ? '●' : '○' }}</span>
              <span>{{ humanizePromptNode(item.node) }}</span>
            </span>
          </div>

          <div v-if="filteredPromptEntries.length > 0" class="mt-6 flex flex-col gap-6">
            <article v-for="entry in filteredPromptEntries" :key="entry.node" class="rounded-[22px] border border-[#333] bg-[linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(29,29,29,1))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] lg:p-5">
              <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[#333]/80 pb-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="rounded-full border border-[#2f456d] bg-[#162033] px-2 py-0.5 text-[9px] font-bold text-[#8ab4ff]">{{ humanizePromptNode(entry.node) }}</span>
                    <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">{{ entry.node }}</span>
                  </div>
                  <div class="text-[11px] text-gray-500">共 {{ entry.messages.length }} 条 prompt / snapshot 消息</div>
                </div>
              </div>
              <div class="mt-4 flex flex-col gap-4">
                <div v-for="(msg, mIdx) in entry.messages" :key="mIdx" class="group relative flex flex-col gap-2 rounded-xl border border-[#333] bg-[#252526] p-4 transition-colors hover:border-[#444]">
                  <div class="flex items-center justify-between gap-3">
                    <span
                      class="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                      :class="{
                        'bg-purple-900/40 text-purple-400': msg.role === 'system',
                        'bg-green-900/40 text-green-400': msg.role === 'human' || msg.role === 'user',
                        'bg-cyan-900/40 text-cyan-300': msg.role === 'assistant',
                        'bg-gray-700 text-gray-400': msg.role !== 'system' && msg.role !== 'human' && msg.role !== 'user' && msg.role !== 'assistant'
                      }"
                    >
                      {{ msg.role || 'info' }}
                    </span>
                    <button
                      @click="copyIndividualPrompt(String(msg.content || ''), entry.node + mIdx)"
                      class="flex items-center gap-1.5 text-[10px] transition-all"
                      :class="copiedSubNode === (entry.node + mIdx) ? 'text-green-400' : 'text-gray-500 hover:text-white opacity-0 group-hover:opacity-100'"
                    >
                      <template v-if="copiedSubNode === (entry.node + mIdx)">
                        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        已复制！
                      </template>
                      <template v-else>
                        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        复制此条
                      </template>
                    </button>
                  </div>
                  <pre class="max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/10 p-3 font-mono text-[11px] leading-relaxed text-gray-300">{{ String(msg.content || '') }}</pre>
                </div>
              </div>
            </article>
          </div>
          <div v-else class="mt-8 flex h-[calc(100vh-260px)] w-full flex-col items-center justify-center gap-4 text-center text-gray-600">
            <span class="text-4xl opacity-20">🧪</span>
            <div class="text-[13px] font-bold text-gray-300">当前还没有可展示的提示词快照</div>
            <p class="max-w-lg text-[11px] leading-relaxed text-gray-500">如果你刚完成了一轮生成或编辑，但这里仍然是空的，优先检查这轮是否真的命中了 `planner` 或 `note_editor`，或者你开启了筛选后把所有消息都过滤掉了。</p>
          </div>
        </div>
      </div>

      <div
        v-show="viewMode === 'state'"
        class="w-full h-full bg-[#141414] overflow-auto p-3 lg:p-4"
      >
        <div class="mx-auto w-full max-w-6xl min-h-full">
          <AgentInspector />
        </div>
      </div>

      <div
        v-show="viewMode === 'assets'"
        class="w-full h-full bg-[#141414] overflow-auto p-3 lg:p-4"
      >
        <div class="mx-auto w-full max-w-6xl min-h-full">
          <AssetLibrary
            :current-assets="documentAssets"
            :search-results="searchedAssets"
            :asset-search-loading="assetSearchLoading"
            :current-cover-url="currentCoverUrl"
            :imported-asset-urls="importedAssetUrls"
            @search="searchAssets"
            @import="importAsset"
            @cover="setAsCover"
          />
        </div>
      </div>

      <div
        v-if="viewMode === 'preview' && hoveredComponentId && hoveredComponentPayload"
        class="absolute right-4 top-4 w-72 bg-[#1e1e1e]/95 backdrop-blur shadow-2xl rounded-xl border border-[#333] p-4 z-50 pointer-events-none transition-all"
      >
        <div class="text-xs font-bold text-blue-400 mb-2 pb-2 border-b border-[#333] flex items-center justify-between">
          <span>🔍 {{ hoveredComponentId }}</span>
          <span class="text-gray-500">{{ (hoveredComponentPayload as Record<string, unknown>)?.type }}</span>
        </div>
        <pre class="text-[10px] text-green-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">{{ JSON.stringify(hoveredComponentPayload, null, 2) }}</pre>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import DynamicRenderer from '../renderers/DynamicRenderer.vue'
import AgentInspector from '../chat/AgentInspector.vue'
import AssetLibrary from '../chat/AssetLibrary.vue'
import type { NoteDocument } from '../../types/chat'

type PromptMessage = {
  role?: string
  content?: string
  [key: string]: unknown
}

const chatStore = useChatStore()
const { getPreferredPayloadById } = chatStore
const { previewUrl, renderPageData, nodePrompts, hoveredComponentId, sourceCode, searchedAssets, assetSearchLoading, pendingFactConflictCount, noteDocument, documentAssets, currentCoverUrl, hasRenderableDocument } = storeToRefs(chatStore)

// 控制当前视图是预览、代码、提示词检查器还是 Agent 状态
const viewMode = ref<'preview' | 'code' | 'prompts' | 'state' | 'assets'>('preview')
const isCopied = ref(false)
const copiedSubNode = ref<string | null>(null) // 追踪当前被复制的单条提示词 ID
const copiedPromptBundle = ref(false)
const showPromptSystemOnly = ref(false)
const showPromptKeyNodesOnly = ref(false)

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

const copyPromptBundle = async () => {
  try {
    await navigator.clipboard.writeText(promptBundleText.value)
    copiedPromptBundle.value = true
    setTimeout(() => { copiedPromptBundle.value = false }, 1800)
  } catch (err) {
    console.error('复制整轮 prompt 失败:', err)
  }
}

const searchAssets = async (query: string) => {
  await chatStore.searchAssetImages(query)
}

const importAsset = async (asset: { url: string; desc: string; source_type?: string; query?: string }) => {
  await chatStore.importAssetToLibrary(asset)
}

const setAsCover = async (asset: { url: string; desc: string; source_type?: string; query?: string }) => {
  await chatStore.setAssetAsCover(asset)
}


const hoveredComponentPayload = computed(() => {
  if (!hoveredComponentId.value) return null
  const payload = getPreferredPayloadById(
    (noteDocument.value as NoteDocument | undefined) || {},
    hoveredComponentId.value,
  )
  return Object.keys(payload).length > 0 ? payload : null
})

const importedAssetUrls = computed(() => documentAssets.value.map(asset => asset.url))

const normalizePromptMessages = (messages: unknown): PromptMessage[] => {
  if (Array.isArray(messages)) return messages as PromptMessage[]
  if (messages && typeof messages === 'object') return [messages as PromptMessage]
  if (typeof messages === 'string' && messages.trim()) return [{ role: 'info', content: messages }]
  return []
}

const promptEntries = computed(() =>
  Object.entries((nodePrompts.value || {}) as Record<string, unknown>).map(([node, messages]) => ({
    node,
    messages: normalizePromptMessages(messages),
  }))
)
const promptExpectedNodes = ['planner_agent', 'note_editor', 'intent_agent', 'structure_node', 'component_builder', 'patch_doctor', 'enrichment_agent']
const promptCoverage = computed(() => {
  const present = new Set(promptEntries.value.map(entry => entry.node))
  return promptExpectedNodes.map((node) => ({
    node,
    present: present.has(node),
  }))
})
const filteredPromptEntries = computed(() => {
  return promptEntries.value
    .filter((entry) => !showPromptKeyNodesOnly.value || promptExpectedNodes.includes(entry.node))
    .map((entry) => ({
      ...entry,
      messages: entry.messages.filter((msg) => !showPromptSystemOnly.value || msg.role === 'system'),
    }))
    .filter((entry) => entry.messages.length > 0)
})
const promptNodeCount = computed(() => filteredPromptEntries.value.length)
const promptMessageCount = computed(() => filteredPromptEntries.value.reduce((sum, entry) => sum + entry.messages.length, 0))
const promptBundleText = computed(() =>
  filteredPromptEntries.value
    .map((entry) => {
      const header = `## ${humanizePromptNode(entry.node)} (${entry.node})`
      const body = entry.messages
        .map((msg) => `[${String(msg.role || 'info').toUpperCase()}]\n${String(msg.content || '')}`)
        .join('\n\n')
      return `${header}\n${body}`
    })
    .join('\n\n====\n\n')
)
const humanizePromptNode = (node: string) => ({
  planner_agent: '策略规划',
  note_editor: '编辑主脑',
  intent_agent: '意图网关',
  structure_node: '结构布局',
}[node] || node)

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
