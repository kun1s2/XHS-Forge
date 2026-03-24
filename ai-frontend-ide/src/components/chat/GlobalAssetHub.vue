<template>
  <div class="mx-auto w-full max-w-6xl space-y-4 rounded-[26px] border border-[#333] bg-[#1e1e1e] p-5 text-gray-200 shadow-[0_18px_40px_rgba(0,0,0,0.22)] lg:p-6">
    <div class="flex flex-wrap items-start justify-between gap-3 border-b border-[#333] pb-4">
      <div class="space-y-2">
        <div class="flex items-center gap-2">
          <span class="rounded-full border border-violet-800/30 bg-violet-950/20 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-violet-300">Global Hub</span>
          <span class="rounded-full border border-violet-800/30 bg-violet-950/20 px-2 py-0.5 text-[10px] font-semibold text-violet-200">独立于回滚 / 分支</span>
        </div>
        <div class="text-[15px] font-bold text-gray-100">全局资产中心</div>
        <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">
          这里只管理正式知识、长期资料、Demo 资料包和评估资产。当前会话待审知识与本轮诊断已经从这里剥离。
        </p>
      </div>
      <div class="grid min-w-[260px] grid-cols-3 gap-2 text-[10px]">
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">正式知识</div>
          <div class="mt-1 text-[13px] font-bold text-violet-300">{{ persistentGroups.length }}</div>
        </div>
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">待确认冲突</div>
          <div class="mt-1 text-[13px] font-bold text-amber-300">{{ reviewQueue.length }}</div>
        </div>
        <div class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2.5">
          <div class="uppercase tracking-wider text-gray-500">Demo / Eval</div>
          <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ demoPacks.length }}/{{ evalSets.length }}</div>
        </div>
      </div>
    </div>

    <section class="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <div class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">长期资料入库</div>
            <div class="mt-1 text-[13px] font-semibold text-gray-100">把资料直接沉淀到全局资产层</div>
          </div>
          <div class="rounded-full border border-violet-500/30 bg-violet-950/20 px-3 py-1.5 text-[10px] text-violet-100">
            当前固定写入：长期知识库
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          <button
            v-for="mode in uploadModes"
            :key="mode.value"
            class="rounded-full border px-3 py-1 text-[10px] font-bold transition-all"
            :class="uploadMode === mode.value ? 'border-violet-500/40 bg-violet-950/30 text-violet-100' : 'border-[#334155] bg-[#111827] text-gray-400 hover:text-gray-200'"
            @click="uploadMode = mode.value"
          >
            {{ mode.label }}
          </button>
        </div>

        <div class="mt-4 grid gap-3">
          <input v-model="entityHint" type="text" placeholder="实体提示，例如：华为 Mate 60 / 小米 14 / iPhone 15" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
          <input v-model="sceneHint" type="text" placeholder="场景提示，例如：seeding / digital_decision" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />

          <div v-if="uploadMode === 'file'" class="grid gap-2">
            <input ref="fileInputRef" type="file" class="rounded-2xl border border-dashed border-[#334155] bg-[#111827] px-3 py-3 text-[12px] text-gray-300 file:mr-3 file:rounded-full file:border-0 file:bg-violet-950/40 file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:text-violet-200" />
            <button class="rounded-full border border-violet-500/40 bg-violet-950/30 px-3 py-2 text-[11px] text-violet-100 hover:border-violet-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy" @click="handleFileUpload">
              {{ busy ? '正在解析...' : '上传文件并入长期资产' }}
            </button>
          </div>

          <div v-else-if="uploadMode === 'text'" class="grid gap-2">
            <input v-model="textTitle" type="text" placeholder="文本标题，例如：Mate 60 参数摘要" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
            <textarea v-model="textPayload" rows="5" placeholder="直接粘贴资料内容、表格文本或你自己的笔记…" class="min-h-[140px] rounded-2xl border border-[#334155] bg-[#111827] px-3 py-3 text-[12px] leading-relaxed text-gray-200 outline-none placeholder:text-gray-600"></textarea>
            <button class="rounded-full border border-violet-500/40 bg-violet-950/30 px-3 py-2 text-[11px] text-violet-100 hover:border-violet-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy || !textTitle.trim() || !textPayload.trim()" @click="handleTextUpload">
              {{ busy ? '正在解析...' : '粘贴文本并入长期资产' }}
            </button>
          </div>

          <div v-else class="grid gap-2">
            <input v-model="urlPayload" type="url" placeholder="输入公开网页或在线文档链接" class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] text-gray-200 outline-none placeholder:text-gray-600" />
            <button class="rounded-full border border-violet-500/40 bg-violet-950/30 px-3 py-2 text-[11px] text-violet-100 hover:border-violet-400 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500" :disabled="busy || !urlPayload.trim()" @click="handleUrlUpload">
              {{ busy ? '正在抓取...' : '抓取链接并入长期资产' }}
            </button>
          </div>
        </div>

        <div v-if="uploadMessage" class="mt-3 rounded-2xl border border-emerald-800/30 bg-emerald-950/10 px-3 py-2 text-[11px] leading-relaxed text-emerald-200">
          {{ uploadMessage }}
        </div>
      </div>

      <div class="rounded-[22px] border border-[#334155] bg-[#0f172a] p-4">
        <div class="text-[11px] font-black uppercase tracking-[0.18em] text-gray-500">Demo / Eval 资产</div>
        <div class="mt-1 text-[13px] font-semibold text-gray-100">导入可控资料包或查看评估集</div>
        <div class="mt-3 flex items-center gap-2">
          <span class="text-[10px] text-gray-500">导入目标</span>
          <select v-model="demoScope" class="rounded-xl border border-[#334155] bg-[#111827] px-3 py-2 text-[11px] text-gray-200 outline-none">
            <option value="session">当前会话</option>
            <option value="persistent">长期知识库</option>
          </select>
        </div>
        <div class="mt-3 grid gap-2">
          <button
            v-for="pack in demoPacks"
            :key="String(pack.pack_id || pack.title)"
            class="rounded-2xl border border-[#334155] bg-[#111827] px-3 py-3 text-left transition-colors hover:border-[#4b5563]"
            :disabled="busy"
            @click="handleDemoImport(String(pack.pack_id || ''))"
          >
            <div class="text-[12px] font-semibold text-gray-100">{{ pack.title }}</div>
            <div class="mt-1 text-[10px] text-gray-500">{{ pack.scenario }} · {{ Array.isArray(pack.documents) ? pack.documents.length : 0 }} 份资料</div>
          </button>
        </div>
        <div v-if="evalSets.length" class="mt-3 rounded-2xl border border-[#334155] bg-[#111827] px-3 py-3 text-[11px] leading-relaxed text-gray-400">
          已挂载 {{ evalSets.length }} 组 golden eval set，用于区分 retrieval fail 和 generation fail。
        </div>
      </div>
    </section>

    <section class="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
      <KnowledgeGroupSection title="正式知识库" badge="全局级" tone="violet" :groups="persistentGroups" empty-text="长期知识库里还没有已沉淀的知识。" />

      <section class="rounded-[22px] border border-[#4b1d1d] bg-[rgba(48,16,16,0.55)] p-4">
        <div class="text-[11px] font-black uppercase tracking-[0.18em] text-amber-300">待确认区</div>
        <div class="mt-3 grid gap-3">
          <div
            v-for="(item, idx) in reviewQueue"
            :key="item.group_id || idx"
            class="rounded-2xl border border-[#5b2b2b] bg-[#1f1515] p-3"
          >
            <div class="text-[12px] font-semibold text-gray-100">{{ item.group_id || '冲突知识' }}</div>
            <div class="mt-2 grid gap-2 text-[11px] text-gray-300">
              <div>旧值：{{ item.old_record?.value || item.old_record?.summary || '—' }}</div>
              <div>新值：{{ item.new_record?.value || item.new_record?.summary || '—' }}</div>
              <div class="text-amber-300">推荐版本：{{ item.recommended_record_id || '需要你判断' }}</div>
            </div>
          </div>
          <div v-if="!reviewQueue.length" class="rounded-2xl border border-[#333] bg-[#111827] px-3 py-3 text-[11px] text-gray-400">
            当前没有待确认的长期知识冲突。
          </div>
        </div>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import type { KnowledgeGroup } from '../../types/chat'
import {
  fetchGlobalKnowledgeOverview,
  importKnowledgeDemoPack,
  uploadKnowledgeFile,
  uploadKnowledgeText,
  uploadKnowledgeUrl,
} from '../../api/upload'
import KnowledgeGroupSection from './KnowledgeWorkbenchSection.vue'

const chatStore = useChatStore()
const { threadId } = storeToRefs(chatStore)

const uploadModes = [
  { value: 'file', label: '上传文件' },
  { value: 'text', label: '粘贴文本' },
  { value: 'url', label: '抓取链接' },
]

const uploadMode = ref<'file' | 'text' | 'url'>('file')
const demoScope = ref<'session' | 'persistent'>('persistent')
const entityHint = ref('')
const sceneHint = ref('')
const textTitle = ref('')
const textPayload = ref('')
const urlPayload = ref('')
const uploadMessage = ref('')
const busy = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const demoPacks = ref<Array<Record<string, unknown>>>([])
const evalSets = ref<Array<Record<string, unknown>>>([])
const persistentSnapshot = ref<Record<string, any>>({})

const persistentGroups = computed<KnowledgeGroup[]>(
  () => (persistentSnapshot.value?.groups || []) as KnowledgeGroup[],
)
const reviewQueue = computed<Array<Record<string, any>>>(
  () => (persistentSnapshot.value?.review_queue || []) as Array<Record<string, any>>,
)

const refreshKnowledge = async () => {
  await loadGlobalOverview()
}

const loadGlobalOverview = async () => {
  try {
    const result = await fetchGlobalKnowledgeOverview()
    persistentSnapshot.value = ((result.persistent_kb || {}) as Record<string, any>)
    demoPacks.value = Array.isArray(result.demo_packs) ? (result.demo_packs as Array<Record<string, unknown>>) : []
    evalSets.value = Array.isArray(result.eval_sets) ? (result.eval_sets as Array<Record<string, unknown>>) : []
  } catch (error) {
    console.error('加载全局知识概览失败:', error)
  }
}

const withBusy = async (runner: () => Promise<void>) => {
  if (!threadId.value) {
    uploadMessage.value = '请先创建或打开一个会话，再管理全局资产。'
    return
  }
  busy.value = true
  uploadMessage.value = ''
  try {
    await runner()
    await refreshKnowledge()
  } catch (error) {
    console.error(error)
    uploadMessage.value = error instanceof Error ? error.message : '全局资产操作失败，请稍后重试。'
  } finally {
    busy.value = false
  }
}

const buildBasePayload = () => ({
  threadId: threadId.value,
  kbScope: 'persistent' as const,
  entityHint: entityHint.value.trim(),
  sceneHint: sceneHint.value.trim() || 'seeding',
})

const handleFileUpload = async () => {
  const file = fileInputRef.value?.files?.[0]
  if (!file) {
    uploadMessage.value = '请先选择一份资料文件。'
    return
  }
  await withBusy(async () => {
    const result = await uploadKnowledgeFile(file, buildBasePayload())
    uploadMessage.value = `已导入 ${String((result.document as Record<string, unknown> | undefined)?.title || file.name)}，资料已沉淀到长期知识层，并把候选事实送入当前会话待审区。`
    if (fileInputRef.value) fileInputRef.value.value = ''
  })
}

const handleTextUpload = async () => {
  await withBusy(async () => {
    await uploadKnowledgeText({
      ...buildBasePayload(),
      title: textTitle.value,
      text: textPayload.value,
    })
    uploadMessage.value = '文本资料已写入长期知识层；候选事实会在当前会话里等待确认。'
    textTitle.value = ''
    textPayload.value = ''
  })
}

const handleUrlUpload = async () => {
  await withBusy(async () => {
    await uploadKnowledgeUrl({
      ...buildBasePayload(),
      url: urlPayload.value,
    })
    uploadMessage.value = '链接资料已抓取并写入长期知识层；候选事实会在当前会话里等待确认。'
    urlPayload.value = ''
  })
}

const handleDemoImport = async (packId: string) => {
  await withBusy(async () => {
    await importKnowledgeDemoPack({
      threadId: String(threadId.value || ''),
      kbScope: demoScope.value,
      packId,
    })
    if (demoScope.value === 'session' && threadId.value) {
      await chatStore.fetchAgentMeta()
    }
    uploadMessage.value = demoScope.value === 'session'
      ? 'Demo 资料包已导入当前会话，并进入待审知识区。'
      : 'Demo 资料包已导入长期知识库；候选事实已送入当前会话待审区。'
  })
}

onMounted(() => {
  void refreshKnowledge()
})
</script>
