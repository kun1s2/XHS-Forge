<template>
  <div class="visual-lab-root min-h-screen bg-[#111111] text-white">
    <div class="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-6 px-5 py-6 xl:flex-row">
      <aside class="w-full shrink-0 rounded-[28px] border border-white/10 bg-[#171717] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.28)] xl:w-[320px]">
        <div class="flex items-center gap-2">
          <span class="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.2em] text-emerald-300">
            Visual Lab
          </span>
          <span class="text-[10px] uppercase tracking-[0.18em] text-white/40">固定场景 / 固定视口 / 固定内容</span>
        </div>
        <h1 class="mt-4 text-2xl font-black leading-tight text-white">前端视觉回归实验室</h1>
        <p class="mt-2 text-sm leading-relaxed text-white/60">
          用固定的 `NoteDocument` 样例直接驱动真实渲染链，锁住比例、层次、主题一致性和高频积木观感。
        </p>

        <div class="mt-6 space-y-3">
          <button
            v-for="fixture in fixtures"
            :key="fixture.id"
            type="button"
            class="block w-full rounded-[22px] border px-4 py-4 text-left transition-all duration-200 hover:-translate-y-0.5"
            :class="fixture.id === activeFixture.id ? 'border-emerald-400/40 bg-emerald-500/10' : 'border-white/10 bg-white/[0.03]'"
            @click="selectFixture(fixture.id)"
          >
            <div class="text-[10px] font-black uppercase tracking-[0.18em]" :class="fixture.id === activeFixture.id ? 'text-emerald-300' : 'text-white/40'">
              {{ fixture.id }}
            </div>
            <div class="mt-2 text-sm font-bold text-white">{{ fixture.title }}</div>
            <div class="mt-2 text-[12px] leading-relaxed text-white/60">{{ fixture.description }}</div>
          </button>
        </div>

        <div class="mt-6 rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-4">
          <div class="text-[10px] font-black uppercase tracking-[0.18em] text-white/40">当前检查重点</div>
          <ul class="mt-3 space-y-2 text-[12px] leading-relaxed text-white/70">
            <li>1. 高频块不会被挤成窄长柱</li>
            <li>2. 无图时不再混入随机跑题图</li>
            <li>3. 主题、内容和块语义要一致</li>
            <li>4. 预览和导出 HTML 观感保持一致</li>
          </ul>
        </div>
      </aside>

      <main class="flex-1">
        <div class="rounded-[30px] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.10),transparent_28%),linear-gradient(180deg,#18181b_0%,#121214_100%)] p-5 shadow-[0_28px_90px_rgba(0,0,0,0.28)]">
          <div class="flex flex-col gap-3 border-b border-white/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.18em] text-emerald-300">Fixture Preview</div>
              <div class="mt-2 text-2xl font-black leading-tight text-white">{{ activeFixture.title }}</div>
              <div class="mt-2 text-sm leading-relaxed text-white/60">{{ activeFixture.description }}</div>
            </div>
            <div class="flex flex-wrap gap-2 text-[11px]">
              <span class="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-white/70">blocks {{ blockCount }}</span>
              <span class="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-white/70">scenarios {{ scenarioSummary }}</span>
              <span class="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-white/70">fixture {{ activeFixture.id }}</span>
            </div>
          </div>

          <div
            data-visual-fixture-root
            class="mt-6 rounded-[34px] border border-white/10 bg-[#0f0f10] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
          >
            <div class="mx-auto w-full max-w-[760px]">
              <div data-visual-preview-shell class="preview-shell pb-[92px] shadow-[0_32px_80px_rgba(0,0,0,0.32)]" :style="globalStyles">
                <div class="sticky top-0 z-50 flex items-center justify-between border-b px-4 py-3 backdrop-blur-md" :style="topBarStyle">
                  <div class="flex h-8 w-8 items-center justify-center rounded-full text-xl" :style="iconButtonStyle">←</div>
                  <div class="flex gap-5 text-[15px]">
                    <span :style="mutedTabStyle">发现</span>
                    <span :style="mutedTabStyle">附近</span>
                    <span class="border-b-2 pb-1 font-semibold" :style="activeTabStyle">北京</span>
                  </div>
                  <div class="flex h-8 w-8 items-center justify-center rounded-full text-xl" :style="iconButtonStyle">🔍</div>
                </div>

                <div class="flex w-full flex-col gap-6 px-4 pt-4">
                  <XForgeRenderer
                    v-for="(block, idx) in renderBlocks"
                    :key="block.id"
                    :node="block"
                    :index="idx"
                  />
                </div>

                <div class="absolute inset-x-0 bottom-0 z-50 flex items-center justify-between border-t px-4 py-2.5 backdrop-blur-md" :style="bottomBarStyle">
                  <div class="mr-4 flex-1 rounded-full border px-4 py-2 text-[13px]" :style="composerStyle">说点什么...</div>
                  <div class="flex gap-5 text-xl" :style="actionBarStyle">
                    <span>🤍</span>
                    <span>⭐</span>
                    <span>💬</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import XForgeRenderer from '../renderers/XForgeRenderer.vue'
import { getVisualFixture, visualFixtures } from '../../visualFixtures'

const fixtures = visualFixtures
const selectedFixtureId = ref(new URLSearchParams(window.location.search).get('fixture') || fixtures[0].id)

const previousRootStyles = new Map<HTMLElement, { overflow: string; height: string; width: string; minHeight: string }>()

const getVisualRootElements = () =>
  [document.documentElement, document.body, document.getElementById('app')].filter(Boolean) as HTMLElement[]

onMounted(() => {
  getVisualRootElements().forEach((element) => {
    previousRootStyles.set(element, {
      overflow: element.style.overflow,
      height: element.style.height,
      width: element.style.width,
      minHeight: element.style.minHeight,
    })
    element.style.overflow = 'auto'
    element.style.height = 'auto'
    element.style.width = '100%'
    element.style.minHeight = '100vh'
  })
})

onBeforeUnmount(() => {
  getVisualRootElements().forEach((element) => {
    const previous = previousRootStyles.get(element)
    if (!previous) return
    element.style.overflow = previous.overflow
    element.style.height = previous.height
    element.style.width = previous.width
    element.style.minHeight = previous.minHeight
  })
})

const activeFixture = computed(() => getVisualFixture(selectedFixtureId.value))

const blockCount = computed(() => activeFixture.value.noteDocument.blocks?.length || 0)
const scenarioSummary = computed(() => {
  const scenarios = activeFixture.value.noteDocument.document_meta?.scenarios
  return Array.isArray(scenarios) && scenarios.length ? scenarios.join(' / ') : 'general'
})

const renderBlocks = computed(() =>
  (activeFixture.value.noteDocument.blocks || []).map((block) => ({
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
  ...((activeFixture.value.noteDocument.theme?.global_vars || {}) as Record<string, string>),
  ...((activeFixture.value.noteDocument.theme?.page_theme || {}) as Record<string, string>),
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

const selectFixture = (fixtureId: string) => {
  selectedFixtureId.value = fixtureId
  const url = new URL(window.location.href)
  url.searchParams.set('visual_lab', '1')
  url.searchParams.set('fixture', fixtureId)
  window.history.replaceState({}, '', url.toString())
}
</script>

<style scoped>
.visual-lab-root :deep(*) {
  animation: none !important;
  transition: none !important;
  scroll-behavior: auto !important;
}

.preview-shell {
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
