<template>
  <div class="min-h-full rounded-[26px] border border-[#333] bg-[#1e1e1e] text-gray-200 shadow-[0_18px_40px_rgba(0,0,0,0.22)] overflow-hidden">
    <div class="border-b border-[#333] bg-[radial-gradient(circle_at_top_left,_rgba(125,211,252,0.10),_transparent_35%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] px-5 py-4 lg:px-6">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="space-y-1.5">
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-sky-700/30 bg-sky-950/20 px-2 py-0.5 text-[9px] font-bold text-sky-300">Block Gallery</span>
            <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">单积木真实样例 + 场景整页样例</span>
          </div>
          <div class="text-[14px] font-bold text-gray-100">积木大全</div>
          <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">
            先看单积木的数据结构和观感，再看整页样例里的比例、主题和前后块节奏。这里的样例都直接走真实渲染器，不是静态截图。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="rounded-full border border-[#3a3a3a] bg-black/10 px-3 py-1 text-[10px] font-bold text-gray-300 transition hover:border-sky-700/30 hover:text-sky-300"
            @click="refreshOverview"
          >
            刷新样例
          </button>
        </div>
      </div>
    </div>

    <div class="grid min-h-[780px] grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside class="border-r border-[#333] bg-[#19191b] px-4 py-4">
        <div class="rounded-2xl border border-[#333] bg-[#141414] p-1">
          <button
            type="button"
            class="w-1/2 rounded-xl px-3 py-2 text-[11px] font-bold transition"
            :class="catalogMode === 'components' ? 'bg-sky-950/30 text-sky-300' : 'text-gray-500 hover:text-gray-200'"
            @click="catalogMode = 'components'"
          >
            单积木
          </button>
          <button
            type="button"
            class="w-1/2 rounded-xl px-3 py-2 text-[11px] font-bold transition"
            :class="catalogMode === 'scenarios' ? 'bg-violet-950/30 text-violet-300' : 'text-gray-500 hover:text-gray-200'"
            @click="catalogMode = 'scenarios'"
          >
            整页场景
          </button>
        </div>

        <div class="mt-4 space-y-2">
          <button
            v-for="entry in entryList"
            :key="entry.id"
            type="button"
            class="block w-full rounded-[18px] border px-3 py-3 text-left transition-all duration-200 hover:-translate-y-0.5"
            :class="entry.id === activeEntryId ? entry.activeClass : entry.idleClass"
            @click="activeEntryId = entry.id"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-[11px] font-bold" :class="entry.id === activeEntryId ? entry.activeBadgeClass : 'text-gray-500'">
                {{ entry.kicker }}
              </div>
              <span class="rounded-full border px-2 py-0.5 text-[9px] font-bold" :class="entry.id === activeEntryId ? entry.activePillClass : 'border-[#3a3a3a] text-gray-500'">
                {{ entry.semantic }}
              </span>
            </div>
            <div class="mt-2 text-[13px] font-bold text-gray-100">{{ entry.title }}</div>
            <div class="mt-2 text-[11px] leading-relaxed text-gray-500">{{ entry.summary }}</div>
          </button>
        </div>

        <div class="mt-5 rounded-[18px] border border-[#333] bg-[#141414] p-3">
          <div class="text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">使用建议</div>
          <ul class="mt-3 space-y-2 text-[11px] leading-relaxed text-gray-400">
            <li v-for="(item, idx) in recommendations" :key="`${idx}-${item}`">{{ idx + 1 }}. {{ item }}</li>
          </ul>
        </div>
      </aside>

      <main class="bg-[#141414] px-4 py-4 lg:px-5">
        <div v-if="activeFixture" class="space-y-4">
          <div class="rounded-[22px] border border-[#333] bg-[linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(29,29,29,1))] p-4">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-1.5">
                <div class="flex items-center gap-2">
                  <span class="rounded-full border border-[#3a3a3a] bg-black/10 px-2 py-0.5 text-[9px] font-bold text-gray-400">{{ activeMeta.kicker }}</span>
                  <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">{{ activeMeta.semantic }}</span>
                </div>
                <div class="text-[15px] font-bold text-gray-100">{{ activeMeta.title }}</div>
                <p class="max-w-3xl text-[12px] leading-relaxed text-gray-500">{{ activeMeta.description }}</p>
              </div>
              <div class="grid min-w-[220px] grid-cols-2 gap-2">
                <div class="rounded-2xl border border-[#333] bg-[#1b1b1d] px-3 py-2.5">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">Blocks</div>
                  <div class="mt-1 text-[13px] font-bold text-gray-100">{{ blockCount }}</div>
                </div>
                <div class="rounded-2xl border border-[#333] bg-[#1b1b1d] px-3 py-2.5">
                  <div class="text-[9px] uppercase tracking-wider text-gray-500">Scenarios</div>
                  <div class="mt-1 text-[13px] font-bold text-gray-100">{{ scenarioSummary }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 gap-4">
            <section class="rounded-[24px] border border-[#333] bg-[#0f0f10] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <div class="mb-4 flex items-center justify-between">
                <div>
                  <div class="text-[10px] uppercase tracking-[0.16em] text-gray-500">Live Preview</div>
                  <div class="mt-1 text-[13px] font-bold text-gray-100">真实渲染预览</div>
                </div>
                <div class="text-[10px] text-gray-500">与正式块渲染器共用一套组件</div>
              </div>

              <div class="mx-auto w-full max-w-6xl">
                <div data-gallery-preview-shell class="gallery-preview-shell pb-[92px] shadow-[0_32px_80px_rgba(0,0,0,0.32)]" :style="globalStyles">
                  <div class="sticky top-0 z-40 flex items-center justify-between border-b px-4 py-3 backdrop-blur-md" :style="topBarStyle">
                    <div class="flex h-8 w-8 items-center justify-center rounded-full text-xl" :style="iconButtonStyle">←</div>
                    <div class="flex gap-5 text-[15px]">
                      <span :style="mutedTabStyle">发现</span>
                      <span :style="mutedTabStyle">附近</span>
                      <span class="border-b-2 pb-1 font-semibold" :style="activeTabStyle">样例</span>
                    </div>
                    <div class="flex h-8 w-8 items-center justify-center rounded-full text-xl" :style="iconButtonStyle">🔍</div>
                  </div>

                  <div class="flex w-full flex-col gap-6 px-4 pt-4">
                    <XForgeRenderer
                      v-for="(block, idx) in renderBlocks"
                      :key="block.id"
                      :node="block"
                      :index="idx"
                      :interactive="false"
                    />
                  </div>

                  <div class="absolute inset-x-0 bottom-0 z-40 flex items-center justify-between border-t px-4 py-2.5 backdrop-blur-md" :style="bottomBarStyle">
                    <div class="mr-4 flex-1 rounded-full border px-4 py-2 text-[13px]" :style="composerStyle">这块放在真实页面里会长这样...</div>
                    <div class="flex gap-5 text-xl" :style="actionBarStyle">
                      <span>🤍</span>
                      <span>⭐</span>
                      <span>💬</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <aside class="space-y-4">
              <section class="rounded-[24px] border border-[#333] bg-[#1b1b1d] p-4">
                <div class="text-[10px] uppercase tracking-[0.16em] text-gray-500">Fixture Data</div>
                <div class="mt-1 text-[13px] font-bold text-gray-100">样例结构摘要</div>
                <div class="mt-3 grid grid-cols-1 gap-2">
                  <div class="rounded-2xl border border-[#333] bg-[#141414] px-3 py-3">
                    <div class="text-[10px] uppercase tracking-wider text-gray-500">标题</div>
                    <div class="mt-1 text-[12px] font-medium text-gray-200">{{ activeFixture.title }}</div>
                  </div>
                  <div class="rounded-2xl border border-[#333] bg-[#141414] px-3 py-3">
                    <div class="text-[10px] uppercase tracking-wider text-gray-500">说明</div>
                    <div class="mt-1 text-[12px] leading-relaxed text-gray-400">{{ activeFixture.description || '该样例用于观察块的真实比例、信息节奏与主题一致性。' }}</div>
                  </div>
                </div>
              </section>

              <section class="rounded-[24px] border border-[#333] bg-[#1b1b1d] p-4">
                <div class="text-[10px] uppercase tracking-[0.16em] text-gray-500">Block Outline</div>
                <div class="mt-1 text-[13px] font-bold text-gray-100">区块顺序</div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="block in outlineBlocks"
                    :key="block.id"
                    class="rounded-2xl border border-[#333] bg-[#141414] px-3 py-3"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <div class="text-[12px] font-bold text-gray-200">{{ block.type }}</div>
                      <span class="rounded-full border border-[#3a3a3a] px-2 py-0.5 text-[9px] font-bold text-gray-500">{{ block.id }}</span>
                    </div>
                    <div class="mt-1 text-[11px] text-gray-500">{{ block.semantic_role || 'general' }}</div>
                  </div>
                </div>
              </section>
            </aside>
          </div>
        </div>

        <div v-else class="flex min-h-[520px] items-center justify-center rounded-[24px] border border-dashed border-[#333] bg-[#151517] text-center text-gray-500">
          暂无可展示的积木样例。
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import XForgeRenderer from '../renderers/XForgeRenderer.vue'
import type {
  BlockGalleryComponentGuide,
  BlockGalleryFixture,
  BlockGalleryOverview,
  BlockGalleryScenarioGuide,
  NoteDocument,
} from '../../types/chat'

type CatalogMode = 'components' | 'scenarios'

type GalleryEntry = {
  id: string
  title: string
  summary: string
  kicker: string
  semantic: string
  activeClass: string
  idleClass: string
  activeBadgeClass: string
  activePillClass: string
}

const chatStore = useChatStore()
const { blockGalleryOverview } = storeToRefs(chatStore)

const catalogMode = ref<CatalogMode>('components')
const activeEntryId = ref('')

const overview = computed<BlockGalleryOverview>(() => blockGalleryOverview.value || {})
const componentEntries = computed<BlockGalleryComponentGuide[]>(() => overview.value.components || [])
const scenarioEntries = computed<BlockGalleryScenarioGuide[]>(() => overview.value.scenarios || [])
const recommendations = computed(() => overview.value.recommendations || [])

const entryList = computed<GalleryEntry[]>(() => {
  if (catalogMode.value === 'components') {
    return componentEntries.value.map((item) => ({
      id: item.component_type,
      title: item.label,
      summary: item.summary || '查看这个积木在真实内容里的结构化长相。',
      kicker: item.component_type,
      semantic: item.semantic_role || 'general',
      activeClass: 'border-sky-700/30 bg-sky-950/20',
      idleClass: 'border-[#333] bg-[#141414]',
      activeBadgeClass: 'text-sky-300',
      activePillClass: 'border-sky-700/30 text-sky-300',
    }))
  }
  return scenarioEntries.value.map((item) => ({
    id: item.scenario_id,
    title: item.title,
    summary: item.description || '查看这套积木放回真实页面后的比例、节奏和主题一致性。',
    kicker: item.scenario_id,
    semantic: 'scenario',
    activeClass: 'border-violet-700/30 bg-violet-950/20',
    idleClass: 'border-[#333] bg-[#141414]',
    activeBadgeClass: 'text-violet-300',
    activePillClass: 'border-violet-700/30 text-violet-300',
  }))
})

const ensureActiveEntry = () => {
  const list = entryList.value
  if (list.length === 0) {
    activeEntryId.value = ''
    return
  }
  if (!list.some((entry) => entry.id === activeEntryId.value)) {
    activeEntryId.value = list[0].id
  }
}

watch([catalogMode, componentEntries, scenarioEntries], ensureActiveEntry, { immediate: true })

const activeComponent = computed<BlockGalleryComponentGuide | null>(() => {
  if (catalogMode.value !== 'components') return null
  return componentEntries.value.find((item) => item.component_type === activeEntryId.value) || null
})

const activeScenario = computed<BlockGalleryScenarioGuide | null>(() => {
  if (catalogMode.value !== 'scenarios') return null
  return scenarioEntries.value.find((item) => item.scenario_id === activeEntryId.value) || null
})

const activeFixture = computed<BlockGalleryFixture | null>(() => activeComponent.value?.fixture || activeScenario.value?.fixture || null)
const activeMeta = computed(() => ({
  kicker: catalogMode.value === 'components' ? activeComponent.value?.component_type || 'component' : activeScenario.value?.scenario_id || 'scenario',
  semantic: catalogMode.value === 'components' ? activeComponent.value?.semantic_role || 'general' : 'scenario',
  title: catalogMode.value === 'components' ? activeComponent.value?.label || activeFixture.value?.title || '' : activeScenario.value?.title || activeFixture.value?.title || '',
  description:
    (catalogMode.value === 'components'
      ? activeComponent.value?.summary
      : activeScenario.value?.description) ||
    activeFixture.value?.description ||
    '',
}))

const activeDocument = computed<NoteDocument>(() => activeFixture.value?.note_document || {})
const blockCount = computed(() => activeDocument.value.blocks?.length || 0)
const scenarioSummary = computed(() => {
  const scenarios = activeDocument.value.document_meta?.scenarios
  return Array.isArray(scenarios) && scenarios.length > 0 ? scenarios.join(' / ') : 'general'
})
const outlineBlocks = computed(() => (activeDocument.value.blocks || []).map((block) => ({
  id: block.id,
  type: block.type,
  semantic_role: block.semantic_role,
})))
const renderBlocks = computed(() =>
  (activeDocument.value.blocks || []).map((block) => ({
    id: block.id,
    component_type: block.type,
    props: block.props || {},
    style: block.style || {},
  }))
)

const globalVars = computed(() => ({
  '--spacing-sm': '16px',
  '--spacing-md': '24px',
  '--spacing-lg': '40px',
  '--bg-color': '#ffffff',
  '--bg-gradient': 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
  '--chrome-bg': 'rgba(255,255,255,0.92)',
  '--chrome-border': 'rgba(148,163,184,0.16)',
  '--card-bg': 'rgba(255,255,255,0.92)',
  '--card-bg-soft': 'rgba(255,255,255,0.78)',
  '--card-border': 'rgba(148,163,184,0.16)',
  '--text-color': '#0f172a',
  '--text-muted': '#64748b',
  '--primary-vibe': '#ff2442',
  '--primary-vibe-light': 'rgba(255,36,66,0.12)',
  ...((activeDocument.value.theme?.global_vars || {}) as Record<string, string>),
  ...((activeDocument.value.theme?.page_theme || {}) as Record<string, string>),
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
  background: 'var(--card-bg-soft)',
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
  background: 'var(--card-bg-soft)',
  borderColor: 'var(--card-border)',
  color: 'var(--text-muted)',
}))
const actionBarStyle = computed(() => ({
  color: 'var(--text-muted)',
}))

const refreshOverview = async () => {
  await chatStore.fetchBlockGalleryOverview()
}

onMounted(() => {
  if ((overview.value.components || []).length === 0 && (overview.value.scenarios || []).length === 0) {
    void refreshOverview()
  }
})
</script>

<style scoped>
.gallery-preview-shell {
  width: 100%;
  max-width: min(100%, 580px);
  min-height: 100%;
  background-color: var(--bg-color);
  background-image: var(--bg-gradient);
  border-radius: 24px;
  box-shadow: 0 10px 50px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow-x: hidden;
  margin: 0 auto;
}
</style>
