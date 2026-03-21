<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  node: any
  data: {
    title?: string
    pros?: { summary?: string; details?: string }
    cons?: { summary?: string; details?: string }
    proText?: string
    conText?: string
  }
}>()

const title = computed(() => props.data.title || '两种选择，拉开的是体验方向')
const proSummary = computed(() => props.data.pros?.summary || props.data.proText || '真香：优势点')
const conSummary = computed(() => props.data.cons?.summary || props.data.conText || '避雷：下头点')

const splitToBullets = (value?: string) =>
  String(value || '')
    .split(/[。\n；;!?！？]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3)

const proBullets = computed(() => {
  const bullets = splitToBullets(props.data.pros?.details)
  return bullets.length ? bullets : ['适合想快速抓住亮点的人', '表达偏正向，适合首轮种草', '适合作为主推荐路径']
})
const conBullets = computed(() => {
  const bullets = splitToBullets(props.data.cons?.details)
  return bullets.length ? bullets : ['把问题说透，适合冷静比较', '更容易暴露短板和妥协点', '适合作为风险提醒或反方意见']
})

const verdict = computed(() => {
  if (title.value.includes('华为') || title.value.includes('Mate')) return '这不是简单优缺点堆砌，而是体验路线的分流。'
  return '把结论、理由和风险拆开说，才像真正的对比卡。'
})

const comparisonTakeaway = computed(() => {
  if (proBullets.value.length >= conBullets.value.length) {
    return '更适合先亮结论，再告诉用户代价和边界。'
  }
  return '更适合先说风险，再引出为什么仍然有人会选它。'
})
</script>

<template>
  <div class="w-full animate-in fade-in zoom-in duration-500">
    <div class="rounded-[30px] border p-5 md:p-6" :style="{ background: 'var(--card-bg)', borderColor: 'var(--card-border)', boxShadow: 'var(--card-shadow)' }">
      <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div class="max-w-2xl">
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">Opinion Clash</div>
          <h3 class="mt-2 text-xl font-black leading-tight md:text-2xl" :style="{ color: 'var(--text-color)' }">{{ title }}</h3>
          <p class="mt-2 text-sm leading-relaxed" :style="{ color: 'var(--text-muted)' }">{{ verdict }}</p>
        </div>
        <div class="inline-flex w-fit items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }">
          <span class="inline-block h-2 w-2 rounded-full" :style="{ background: 'var(--primary-vibe)' }"></span>
          红黑对抗块已升级成“摘要 + 要点”结构
        </div>
      </div>

      <div class="mt-5 grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-stretch">
        <section
          class="rounded-[26px] border p-5"
          :style="{ background: 'linear-gradient(180deg, color-mix(in srgb, var(--pro-color) 88%, white 12%) 0%, color-mix(in srgb, var(--pro-color) 70%, #020617 30%) 100%)', borderColor: 'rgba(255,255,255,0.14)' }"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.24em] text-white/70">Pro Side</div>
              <div class="mt-2 text-lg font-black leading-tight text-white">{{ proSummary }}</div>
            </div>
            <div class="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.22em] text-white/75" :style="{ borderColor: 'rgba(255,255,255,0.2)' }">真香</div>
          </div>
          <ul class="mt-4 space-y-2.5">
            <li
              v-for="bullet in proBullets"
              :key="bullet"
              class="flex items-start gap-2 rounded-2xl bg-white/10 px-3 py-2.5 text-[13px] leading-relaxed text-white/88"
            >
              <span class="mt-1 inline-block h-2 w-2 rounded-full bg-white/90"></span>
              <span>{{ bullet }}</span>
            </li>
          </ul>
        </section>

        <div class="hidden items-center justify-center md:flex">
          <div
            class="flex h-16 w-16 items-center justify-center rounded-full border-[6px] text-sm font-black italic tracking-tight"
            :style="{ background: 'rgba(255,255,255,0.96)', color: 'var(--text-color)', borderColor: 'rgba(248,250,252,0.9)', boxShadow: '0 18px 44px rgba(15,23,42,0.18)' }"
          >
            VS
          </div>
        </div>

        <section
          class="rounded-[26px] border p-5"
          :style="{ background: 'linear-gradient(180deg, color-mix(in srgb, var(--con-color) 86%, white 14%) 0%, color-mix(in srgb, var(--con-color) 72%, #020617 28%) 100%)', borderColor: 'rgba(255,255,255,0.14)' }"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.24em] text-white/70">Risk Side</div>
              <div class="mt-2 text-lg font-black leading-tight text-white">{{ conSummary }}</div>
            </div>
            <div class="rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.22em] text-white/75" :style="{ borderColor: 'rgba(255,255,255,0.2)' }">避雷</div>
          </div>
          <ul class="mt-4 space-y-2.5">
            <li
              v-for="bullet in conBullets"
              :key="bullet"
              class="flex items-start gap-2 rounded-2xl bg-white/8 px-3 py-2.5 text-[13px] leading-relaxed text-white/84"
            >
              <span class="mt-1 inline-block h-2 w-2 rounded-full bg-white/70"></span>
              <span>{{ bullet }}</span>
            </li>
          </ul>
        </section>
      </div>

      <div class="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div class="rounded-[24px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Comparison Reading</div>
          <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
            {{ comparisonTakeaway }}
          </div>
          <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            这类积木适合承接两种路线、两种选择，或者一正一反的意见冲突，不应该退化成左右两坨长文字。
          </div>
        </div>
        <div class="rounded-[24px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Best Use</div>
          <div class="mt-2 space-y-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            <div>适合做：路线对比 / 观点冲突 / 选择分流</div>
            <div>不适合做：大段正文堆砌或参数清单搬运</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
