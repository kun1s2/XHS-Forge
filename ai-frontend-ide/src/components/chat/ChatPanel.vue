<template>
  <div class="flex h-full flex-col bg-[#17181a] text-gray-200">
    <div class="border-b border-[#2b2d31] bg-[linear-gradient(180deg,_rgba(27,28,31,0.98),_rgba(23,24,26,0.96))] px-5 py-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-[#39404a] bg-[#20242b] px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-blue-300">创作对话</span>
            <span class="text-[10px] text-gray-500">左侧只负责聊天、素材和局部编辑</span>
          </div>
          <div class="text-[15px] font-bold text-gray-100">和 Agent 一起打磨当前笔记</div>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <select
            v-model="creatorPersona"
            class="rounded-full border border-[#353840] bg-[#1d2026] px-3 py-1.5 text-[11px] text-blue-300 outline-none transition-all hover:border-blue-500/50"
          >
            <option value="硬核数码博主">📸 硬核数码博主</option>
            <option value="毒舌美妆专家">💄 毒舌美妆专家</option>
            <option value="温柔探店达人">🍰 温柔探店达人</option>
            <option value="深夜感性诗人">🌙 深夜感性诗人</option>
          </select>

          <div class="inline-flex items-center gap-2 rounded-full border border-[#32353c] bg-[#1d2026] px-3 py-1.5 text-[11px] text-gray-300">
            <span class="inline-flex h-2.5 w-2.5 rounded-full" :class="wsStatus === 'connected' ? 'bg-emerald-400' : wsStatus === 'connecting' ? 'bg-amber-400 animate-pulse' : 'bg-rose-400'"></span>
            <span>{{ wsStatus === 'connected' ? '已连接' : wsStatus === 'connecting' ? '连接中' : '未连接' }}</span>
          </div>
        </div>
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <span class="rounded-full border border-[#30343b] bg-[#1b1d22] px-3 py-1 text-[10px] text-gray-400">
          当前节点 {{ nodeMap[currentNode] || currentNode || '待命' }}
        </span>
        <span
          v-if="pendingFactConflictCount > 0"
          class="rounded-full border border-amber-800/30 bg-amber-950/10 px-3 py-1 text-[10px] text-amber-300"
        >
          待确认事实 {{ pendingFactConflictCount }}
        </span>
        <span
          v-if="currentCoverUrl"
          class="rounded-full border border-[#30343b] bg-[#1b1d22] px-3 py-1 text-[10px] text-gray-400"
        >
          已设置当前封面
        </span>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-5 py-5 custom-scrollbar" ref="msgListRef">
      <div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
        <div
          v-if="interactionMode === 'edit' && selectedComponentId"
          class="rounded-[24px] border border-blue-900/30 bg-[linear-gradient(180deg,_rgba(18,24,38,0.98),_rgba(12,17,28,0.96))] p-4 shadow-[0_18px_40px_rgba(0,0,0,0.16)]"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="rounded-full border border-blue-800/40 bg-blue-950/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-blue-300">编辑助手</span>
                <span class="text-[11px] text-gray-500">{{ selectedEditingGuidance.selectionModeLabel }}</span>
                <span class="rounded-full border border-[#334155] bg-[#152033] px-2 py-0.5 text-[10px] font-semibold text-blue-200">编辑模式</span>
              </div>
              <div class="text-[14px] font-bold text-gray-100">{{ selectedSelectionLabel }}</div>
              <div class="text-[11px] leading-relaxed text-gray-400">{{ selectedEditingGuidance.semanticRoleHint }}</div>
            </div>
            <button
              @click="setSelectedComponent(null, null)"
              class="rounded-full border border-[#334155] bg-[#182132] px-3 py-1 text-[11px] text-gray-300 transition-colors hover:text-white"
            >
              结束局部编辑
            </button>
          </div>

          <div v-if="selectedEditingGuidance.editableTargets.length > 0" class="mt-3 flex flex-wrap gap-2">
            <span
              v-for="target in selectedEditingGuidance.editableTargets"
              :key="target"
              class="rounded-full border border-[#334155] bg-[#162033] px-2.5 py-1 text-[10px] text-blue-200"
            >
              {{ target }}
            </span>
          </div>

          <div v-if="selectedDirectActions.length > 0" class="mt-4">
            <div class="mb-2 flex items-center gap-2">
              <span class="rounded-full border border-emerald-800/40 bg-emerald-950/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">精准修改</span>
              <span class="text-[10px] text-gray-500">点击即执行，不需要再手写描述</span>
            </div>
            <div class="grid gap-2 sm:grid-cols-2">
              <button
                v-for="action in selectedDirectActions"
                :key="action.label"
                @click="runSelectedDirectAction(action.prompt)"
                class="rounded-2xl border border-[#274a3f] bg-[#0f1a17] px-3 py-3 text-left transition-all hover:border-emerald-500/40 hover:bg-[#13231e]"
              >
                <div class="text-[11px] font-semibold text-emerald-200">{{ action.label }}</div>
                <div class="mt-1 text-[10px] leading-relaxed text-gray-400">{{ action.prompt }}</div>
              </button>
            </div>
          </div>

          <div v-if="selectedQuickActions.length > 0" class="mt-4 flex flex-wrap gap-2">
            <button
              v-for="action in selectedQuickActions"
              :key="action.label"
              @click="applySelectedQuickAction(action.prompt)"
              class="rounded-full border border-[#334155] bg-[#111827] px-3 py-1.5 text-[11px] text-gray-200 transition-all hover:border-blue-500/50 hover:text-blue-300"
            >
              {{ action.label }}
            </button>
          </div>

          <div v-if="selectedPromptRecipes.length > 0" class="mt-4 grid gap-2">
            <button
              v-for="recipe in selectedPromptRecipes"
              :key="recipe.label"
              @click="applySelectedQuickAction(recipe.prompt)"
              class="rounded-2xl border border-[#2f3b52] bg-[#111827]/85 px-3 py-3 text-left transition-all hover:border-blue-500/50 hover:bg-[#152139]"
            >
              <div class="text-[11px] font-semibold text-blue-200">{{ recipe.label }}</div>
              <div class="mt-1 text-[10px] leading-relaxed text-gray-400">{{ recipe.prompt }}</div>
            </button>
          </div>
        </div>

        <div
          v-if="documentAssets && documentAssets.length > 0"
          class="rounded-[24px] border border-[#2d3138] bg-[#1b1d22] p-4"
        >
          <div>
            <div class="flex items-center justify-between gap-3">
              <div>
                <div class="text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">当前素材</div>
                <div class="mt-1 text-[13px] font-semibold text-gray-100">当前线程素材池</div>
              </div>
              <div class="text-[10px] text-gray-500">{{ documentAssets.length }} 张素材</div>
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <div
                v-for="(asset, idx) in documentAssets.slice(0, 6)"
                :key="asset.url + idx"
                class="relative h-14 w-14 overflow-hidden rounded-2xl border border-[#353840] bg-[#111317]"
              >
                <img :src="asset.url" class="h-full w-full object-cover" alt="" />
                <span
                  v-if="asset.url === currentCoverUrl"
                  class="absolute left-1 top-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[9px] font-bold text-white"
                >
                  封面
                </span>
              </div>
            </div>
          </div>
        </div>

        <template v-for="msg in messages" :key="msg.id">
          <div v-if="msg.role === 'user'" class="flex justify-end">
            <div class="max-w-[86%] rounded-[24px] rounded-br-md bg-[linear-gradient(180deg,_#2563eb,_#1d4ed8)] px-4 py-3 text-sm text-white shadow-[0_14px_30px_rgba(37,99,235,0.18)]">
              <div v-if="msg.imageUrls && msg.imageUrls.length > 0" class="mb-2 flex flex-wrap gap-2">
                <img
                  v-for="(url, idx) in msg.imageUrls"
                  :key="idx"
                  :src="url"
                  class="h-16 w-16 rounded-xl border border-blue-300/30 object-cover"
                  alt=""
                />
              </div>
              <div class="leading-relaxed">{{ msg.content }}</div>
              <div class="mt-2 flex justify-end gap-2" v-if="msg.checkpointId && msg.messageKind !== 'checkpoint_decision'">
                <button
                  @click="handleHistoryRollback(msg.checkpointId!)"
                  class="rounded-full border border-white/20 bg-white/10 px-2.5 py-1 text-[10px] text-white/85 transition-colors hover:bg-white/15"
                >
                  回到这里
                </button>
                <button
                  @click="handleHistoryBranch(msg.checkpointId!)"
                  class="rounded-full border border-white/20 bg-white/5 px-2.5 py-1 text-[10px] text-white/80 transition-colors hover:bg-white/10"
                >
                  从这里分支
                </button>
              </div>
            </div>
          </div>

          <div v-else class="flex justify-start">
            <div class="w-full max-w-[92%]">
              <div v-if="msg.thoughts && msg.thoughts.length > 0" class="mb-2 space-y-2">
                <details
                  v-for="(thought, idx) in msg.thoughts"
                  :key="idx"
                  class="rounded-2xl border border-[#2f3440] bg-[#1a1d24]"
                >
                  <summary class="cursor-pointer list-none px-3 py-2 text-[11px] text-gray-400 hover:text-blue-300">
                    🧠 {{ thought.node }} 已完成处理
                  </summary>
                  <div class="border-t border-[#2f3440] px-3 py-3 text-[11px] leading-relaxed text-gray-500">
                    {{ thought.text }}
                  </div>
                </details>
              </div>

              <div class="rounded-[24px] rounded-bl-md border border-[#2f3440] bg-[#1b1d22] px-4 py-3 shadow-[0_14px_30px_rgba(0,0,0,0.16)]">
                <div class="flex items-center justify-between gap-3">
                  <div class="text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">Agent 回复</div>
                  <span v-if="msg.streaming" class="text-[10px] text-blue-400 animate-pulse">生成中</span>
                </div>
                <div class="mt-2 text-sm leading-relaxed text-gray-200 whitespace-pre-wrap">
                  <span v-if="!msg.content && msg.streaming" class="italic text-gray-500">正在思考文案...</span>
                  <Typewriter :text="msg.content" :active="msg.streaming" :speed="10" />
                </div>
                <ConversationCheckpointCard
                  v-if="msg.actionRequired"
                  :action="msg.actionRequired"
                  @select="handleCheckpointOptionSelect(msg.actionRequired, $event)"
                />
              </div>
            </div>
          </div>
        </template>

        <div v-if="thoughtText || currentNode" class="rounded-2xl border border-blue-900/25 bg-blue-950/10 px-4 py-3 text-[11px] text-blue-200">
          <div class="flex items-center gap-2 font-semibold">
            <span class="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-blue-400"></span>
            <span>{{ thoughtText || (nodeMap[currentNode] || currentNode) }}</span>
          </div>
          <div v-if="nodeStreamOutput" class="mt-2 max-h-[160px] overflow-y-auto whitespace-pre-wrap rounded-xl border border-[#243042] bg-[#111827]/70 px-3 py-2 font-mono text-[10px] leading-relaxed text-blue-300 custom-scrollbar">
            <Typewriter :text="nodeStreamOutput" :active="true" :speed="5" />
          </div>
        </div>
      </div>
    </div>

    <div class="border-t border-[#2b2d31] bg-[linear-gradient(180deg,_rgba(27,28,31,0.98),_rgba(23,24,26,1))] px-5 py-4">
      <div class="mx-auto w-full max-w-3xl">
        <div v-if="pendingImages.some(p => p.status === 'uploading')" class="mb-3 flex flex-wrap gap-2 rounded-2xl border border-[#2f3440] bg-[#1b1d22] p-3">
          <div v-for="(img, idx) in pendingImages.filter(p => p.status === 'uploading')" :key="idx" class="relative">
            <img :src="img.preview" class="h-14 w-14 rounded-xl border border-[#3a3f49] object-cover" alt="" />
            <div class="absolute inset-0 flex items-center justify-center rounded-xl bg-black/50">
              <svg class="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            </div>
          </div>
        </div>

        <div class="rounded-[24px] border border-[#2f3440] bg-[#1b1d22] p-3 shadow-[0_14px_30px_rgba(0,0,0,0.16)]">
          <div class="flex items-end gap-3">
            <input type="file" ref="fileInput" accept="image/*" multiple class="hidden" @change="handleFileSelect" />
            <button
              @click="triggerFileInput"
              class="mb-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[#374151] bg-[#111317] text-gray-400 transition-colors hover:text-white"
              title="上传图片"
            >
              <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
            </button>

            <div class="relative flex-1">
              <textarea
                v-model="composerDraft"
                @keydown.enter.prevent="handleSend"
                :placeholder="composerPlaceholder"
                class="min-h-[56px] w-full resize-none rounded-[20px] border border-[#353840] bg-[#111317] px-4 py-3 pr-14 text-sm text-gray-200 outline-none transition-all placeholder:text-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              ></textarea>

              <button
                @click="handleSend"
                :disabled="(!composerDraft.trim() && imageAssets.length === 0) || isUploading || currentNode !== ''"
                class="absolute bottom-2 right-2 flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white transition-colors hover:bg-blue-500 disabled:bg-[#30343b] disabled:text-gray-500"
              >
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
              </button>
            </div>
          </div>
        </div>
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
import ConversationCheckpointCard from './ConversationCheckpointCard.vue'
import type { ConversationCheckpointAction, ConversationCheckpointOption } from '../../types/chat'
import { buildEditingGuidance } from './chatEditingGuidance'

const chatStore = useChatStore()
const {
  messages,
  wsStatus,
  currentNode,
  thoughtText,
  nodeStreamOutput,
  selectedComponentId,
  selectedParagraphIndex,
  imageAssets,
  documentAssets,
  creatorPersona,
  composerDraft,
  pendingFactConflictCount,
  interactionMode,
  selectedBlock,
  selectedPayload,
  currentCoverUrl,
} = storeToRefs(chatStore)
const { setSelectedComponent, addPendingUploadAsset } = chatStore
const msgListRef = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const handleCheckpointOptionSelect = (
  action: ConversationCheckpointAction,
  option: ConversationCheckpointOption,
) => {
  chatStore.submitCheckpointDecision(action, option)
}

const handleHistoryRollback = async (checkpointId: string) => {
  await chatStore.rollbackTo(checkpointId)
}

const handleHistoryBranch = async (checkpointId: string) => {
  await chatStore.branchFromCheckpoint(checkpointId)
}

const selectedEditingGuidance = computed(() =>
  buildEditingGuidance({
    block: selectedBlock.value,
    payload: (selectedPayload.value || {}) as Record<string, unknown>,
    selectedParagraphIndex: selectedParagraphIndex.value,
    pendingFactConflictCount: pendingFactConflictCount.value,
  })
)

const selectedSelectionLabel = computed(() => selectedEditingGuidance.value.selectionLabel)
const selectedDirectActions = computed(() => selectedEditingGuidance.value.directActions)
const selectedQuickActions = computed(() => selectedEditingGuidance.value.quickActions)
const selectedPromptRecipes = computed(() => selectedEditingGuidance.value.promptRecipes)

const composerPlaceholder = computed(() =>
  selectedComponentId.value
    ? selectedEditingGuidance.value.composerPlaceholder
    : '给当前笔记下达创作或编辑指令…'
)

const applySelectedQuickAction = (prompt: string) => {
  composerDraft.value = prompt
}

const runSelectedDirectAction = (prompt: string) => {
  if (!prompt || isUploading.value || currentNode.value !== '') return
  chatStore.sendMessage(prompt)
  composerDraft.value = ''
  stagedUploadUrls.value = []
}

interface PendingImage {
  file: File
  preview: string
  ossUrl: string
  status: 'uploading' | 'success' | 'error'
}
const pendingImages = ref<PendingImage[]>([])
const stagedUploadUrls = ref<string[]>([])
const isUploading = computed(() => pendingImages.value.some(img => img.status === 'uploading'))

const nodeMap: Record<string, string> = {
  asset_processor: '理解上传图片',
  intent_agent: '意图分析大脑',
  note_editor: '内容编辑大脑',
  structure_node: '解析页面骨架',
  theme_compiler: '生成 CSS 样式',
  document_renderer: '云端打包渲染',
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
      status: 'uploading',
    }
    pendingImages.value.push(imgObj)

    try {
      const { url } = await uploadImage(file)
      imgObj.ossUrl = url
      imgObj.status = 'success'
      stagedUploadUrls.value.push(url)
      addPendingUploadAsset({ url, desc: '用户上传图片', source_type: 'upload' })
      await chatStore.importAssetToLibrary({ url, desc: '用户上传图片', source_type: 'upload' })
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
  if ((!composerDraft.value.trim() && stagedUploadUrls.value.length === 0) || isUploading.value || currentNode.value !== '') return

  chatStore.sendMessage(composerDraft.value, { imageUrls: stagedUploadUrls.value })
  stagedUploadUrls.value = []
  composerDraft.value = ''
}

const scrollToBottom = () => {
  nextTick(() => {
    if (msgListRef.value) {
      msgListRef.value.scrollTo({
        top: msgListRef.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  })
}

watch(messages, scrollToBottom, { deep: true })
watch(nodeStreamOutput, scrollToBottom)
</script>

<style scoped>
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
</style>
