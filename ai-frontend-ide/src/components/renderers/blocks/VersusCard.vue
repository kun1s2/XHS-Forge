<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  node: any
  data: {
    title?: string
    pros?: { summary?: string; details?: string; points?: string[]; fit_for?: string }
    cons?: { summary?: string; details?: string; points?: string[]; fit_for?: string }
    proText?: string
    conText?: string
    decision_hint?: string
    risk_note?: string
  }
  recentChange?: { fields?: string[] } | null
}>()
const recentFields = computed(() => new Set((props.recentChange?.fields || []).map((item) => String(item))))
const localHighlightStyle = (active: boolean) => active
  ? {
      borderColor: 'rgba(251,191,36,0.48)',
      boxShadow: '0 0 0 1px rgba(251,191,36,0.18), 0 16px 34px rgba(251,191,36,0.12)',
      transform: 'translateY(-1px)',
    }
  : {}

const title = computed(() => props.data.title || '两种选择，拉开的是体验方向')
const proSummary = computed(() => props.data.pros?.summary || props.data.proText || '更适合偏好主推荐路线的人')
const conSummary = computed(() => props.data.cons?.summary || props.data.conText || '更适合优先看边界和代价的人')

const splitToBullets = (value?: string) =>
  String(value || '')
    .split(/[。\n；;!?！？]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)

const proBullets = computed(() => {
  const bullets = Array.isArray(props.data.pros?.points) && props.data.pros?.points?.length
    ? props.data.pros.points.map((item) => String(item).trim()).filter(Boolean).slice(0, 3)
    : splitToBullets(props.data.pros?.details)
  return bullets.length ? bullets : ['更容易快速建立好感', '适合承接主推荐理由', '适合放在先亮结论的路线里']
})

const conBullets = computed(() => {
  const bullets = Array.isArray(props.data.cons?.points) && props.data.cons?.points?.length
    ? props.data.cons.points.map((item) => String(item).trim()).filter(Boolean).slice(0, 3)
    : splitToBullets(props.data.cons?.details)
  return bullets.length ? bullets : ['更适合把代价和边界说清楚', '适合提醒可能的妥协点', '适合作为反方路线补充']
})

const verdict = computed(() => {
  if (props.data.decision_hint) return props.data.decision_hint
  return '这不是单纯优缺点堆砌，而是两条使用路线的分流。'
})

const proAudience = computed(() => props.data.pros?.fit_for || '更适合看重第一眼好感、核心亮点和主推荐理由的人。')
const conAudience = computed(() => props.data.cons?.fit_for || '更适合看重长期边界、现实代价和使用妥协点的人。')
const riskNote = computed(() => props.data.risk_note || '如果两边都写成大段长文，这张卡就会失去“帮用户做决定”的价值。')

const rootRef = ref<HTMLElement | null>(null)
const layoutMode = ref<'stack' | 'split'>('stack')
let observer: ResizeObserver | null = null

const syncLayoutMode = () => {
  const width = rootRef.value?.clientWidth || 0
  layoutMode.value = width >= 760 ? 'split' : 'stack'
}

onMounted(() => {
  syncLayoutMode()
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => syncLayoutMode())
    if (rootRef.value) observer.observe(rootRef.value)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
})
</script>

<template>
  <div ref="rootRef" class="w-full animate-in fade-in zoom-in duration-500">
    <div
      class="relative overflow-hidden rounded-[30px] border p-5 lg:p-6"
      :style="{ background: 'var(--card-bg)', borderColor: 'var(--card-border)', boxShadow: 'var(--card-shadow)' }"
    >
      <div
        class="pointer-events-none absolute inset-0 opacity-90"
        :style="{ background: 'radial-gradient(circle at top left, color-mix(in srgb, var(--primary-vibe) 14%, white 86%) 0%, transparent 34%), radial-gradient(circle at bottom right, rgba(15,23,42,0.05) 0%, transparent 42%)' }"
      ></div>

      <div class="relative flex flex-col gap-3 rounded-[24px] p-2 lg:flex-row lg:items-end lg:justify-between" :style="localHighlightStyle(recentFields.has('title'))">
        <div class="max-w-2xl">
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">路线对比</div>
          <h3 class="mt-2 text-xl font-black leading-tight lg:text-2xl" :style="{ color: 'var(--text-color)' }">{{ title }}</h3>
          <p class="mt-2 text-sm leading-relaxed" :style="{ color: 'var(--text-muted)' }">{{ verdict }}</p>
        </div>
        <div
          class="inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold"
          :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
        >
          <span class="inline-block h-2 w-2 rounded-full" :style="{ background: 'var(--primary-vibe)' }"></span>
          适合承接“我该怎么选”
        </div>
      </div>

      <div
        class="mt-5"
        :class="layoutMode === 'split'
          ? 'grid grid-cols-[minmax(0,1fr)_52px_minmax(0,1fr)] items-center gap-4'
          : 'space-y-4'"
      >
        <section
          class="rounded-[26px] border p-5"
          :style="{ background: 'linear-gradient(180deg, color-mix(in srgb, var(--pro-color) 88%, white 12%) 0%, color-mix(in srgb, var(--pro-color) 70%, #020617 30%) 100%)', borderColor: 'rgba(255,255,255,0.14)', ...localHighlightStyle(recentFields.has('pros')) }"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.24em] text-white/70">主推路线</div>
              <div class="mt-2 text-lg font-black leading-tight text-white">{{ proSummary }}</div>
            </div>
            <div class="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.22em] text-white/75" :style="{ borderColor: 'rgba(255,255,255,0.2)' }">
              倾向选它
            </div>
          </div>

          <ul class="mt-4 space-y-2.5">
            <li
              v-for="bullet in proBullets"
              :key="bullet"
              class="flex items-start gap-2 rounded-2xl bg-white/10 px-3 py-2.5 text-[12px] leading-relaxed text-white/88 sm:text-[13px]"
            >
              <span class="mt-1 inline-block h-2 w-2 rounded-full bg-white/90"></span>
              <span>{{ bullet }}</span>
            </li>
          </ul>

          <div class="mt-4 rounded-[20px] border border-white/15 bg-white/8 px-3 py-3">
            <div class="text-[10px] font-black uppercase tracking-[0.18em] text-white/68">更适合谁</div>
            <div class="mt-2 text-[12px] leading-relaxed text-white/84">{{ proAudience }}</div>
          </div>
        </section>

        <div class="flex items-center justify-center" :class="layoutMode === 'split' ? 'self-center' : ''">
          <div
            class="flex h-12 w-12 items-center justify-center rounded-full border-[5px] text-xs font-black italic tracking-tight"
            :style="{ background: 'rgba(255,255,255,0.96)', color: 'var(--text-color)', borderColor: 'rgba(248,250,252,0.9)', boxShadow: '0 16px 34px rgba(15,23,42,0.14)' }"
          >
            VS
          </div>
        </div>

        <section
          class="rounded-[26px] border p-5"
          :style="{ background: 'linear-gradient(180deg, color-mix(in srgb, var(--con-color) 86%, white 14%) 0%, color-mix(in srgb, var(--con-color) 72%, #020617 28%) 100%)', borderColor: 'rgba(255,255,255,0.14)', ...localHighlightStyle(recentFields.has('cons')) }"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.24em] text-white/70">保守路线</div>
              <div class="mt-2 text-lg font-black leading-tight text-white">{{ conSummary }}</div>
            </div>
            <div class="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.22em] text-white/75" :style="{ borderColor: 'rgba(255,255,255,0.2)' }">
              先看边界
            </div>
          </div>

          <ul class="mt-4 space-y-2.5">
            <li
              v-for="bullet in conBullets"
              :key="bullet"
              class="flex items-start gap-2 rounded-2xl bg-white/8 px-3 py-2.5 text-[12px] leading-relaxed text-white/84 sm:text-[13px]"
            >
              <span class="mt-1 inline-block h-2 w-2 rounded-full bg-white/70"></span>
              <span>{{ bullet }}</span>
            </li>
          </ul>

          <div class="mt-4 rounded-[20px] border border-white/15 bg-white/8 px-3 py-3">
            <div class="text-[10px] font-black uppercase tracking-[0.18em] text-white/68">更适合谁</div>
            <div class="mt-2 text-[12px] leading-relaxed text-white/84">{{ conAudience }}</div>
          </div>
        </section>
      </div>

      <div class="mt-4 rounded-[24px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', ...localHighlightStyle(recentFields.has('decision')) }">
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">怎么选</div>
        <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
          先看哪一边更接近你的使用路线，再看自己能不能接受对应的代价。
        </div>
        <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">{{ riskNote }}</div>
      </div>

      <FactBindingFooter :node="node" />
    </div>
  </div>
</template>
