<script setup lang="ts">
import { computed, ref } from 'vue'
import FactBindingFooter from './FactBindingFooter.vue'

const props = defineProps<{
  node: any
  data: {
    mode?: string
    title?: string
    metrics?: Array<{ label: string; value: number; reason?: string; confidence?: string; evidence?: string }>
    dimensions?: string[]
    scores?: number[]
  }
  style?: any
}>()

const activeIndex = ref<number | null>(null)
const cardMode = computed(() => String(props.data.mode || 'judgment_summary'))

const normalizedMetrics = computed(() => {
  if (Array.isArray(props.data.metrics) && props.data.metrics.length) {
    return props.data.metrics.map((item) => ({
      label: String(item.label || '维度'),
      value: Math.max(0, Math.min(100, Number(item.value) || 0)),
      reason: String(item.reason || ''),
      confidence: String(item.confidence || 'medium'),
      evidence: String(item.evidence || ''),
    }))
  }
  if (Array.isArray(props.data.dimensions) && Array.isArray(props.data.scores) && props.data.dimensions.length) {
    return props.data.dimensions.map((label, idx) => ({
      label: String(label || `维度 ${idx + 1}`),
      value: Math.max(0, Math.min(100, Number(props.data.scores[idx]) || 0)),
      reason: '',
      confidence: 'medium',
      evidence: '',
    }))
  }
  return [
    { label: '性能', value: 85, reason: '高负载场景下仍然能维持稳定体验。', confidence: 'medium', evidence: '综合体验反馈' },
    { label: '续航', value: 70, reason: '够用，但不是它最具决定性的优势。', confidence: 'medium', evidence: '日常续航表现' },
    { label: '颜值', value: 95, reason: '第一眼观感足够强，容易形成记忆点。', confidence: 'medium', evidence: '外观与手感反馈' },
    { label: '便携', value: 80, reason: '尺寸和重量还在可接受范围内。', confidence: 'medium', evidence: '握持体验' },
    { label: '性价比', value: 65, reason: '更适合讲取舍，不适合写成绝对优势。', confidence: 'low', evidence: '价格与体验权衡' },
  ]
})

const title = computed(() => props.data.title || (cardMode.value === 'scored_evidence' ? '重点维度对比' : '判断摘要'))
const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const cardStyle = computed(() => ({
  background: 'var(--card-bg)',
  borderColor: 'var(--card-border)',
  boxShadow: 'var(--card-shadow)',
  ...inlineStyles.value,
}))

const sides = computed(() => normalizedMetrics.value.length)
const radius = 86
const center = 110

const strongestMetric = computed(() => [...normalizedMetrics.value].sort((a, b) => b.value - a.value)[0])
const weakestMetric = computed(() => [...normalizedMetrics.value].sort((a, b) => a.value - b.value)[0])
const averageScore = computed(() => {
  if (!normalizedMetrics.value.length) return 0
  return Math.round(normalizedMetrics.value.reduce((sum, item) => sum + item.value, 0) / normalizedMetrics.value.length)
})
const activeMetric = computed(() => {
  if (activeIndex.value === null) return null
  return normalizedMetrics.value[activeIndex.value] || null
})
const interpretation = computed(() => {
  const metric = activeMetric.value || strongestMetric.value
  if (!metric) return '当前还没有足够的维度数据。'
  if (metric.reason) return metric.reason
  if (metric.value >= 85) return `${metric.label} 已经形成明显优势，适合放进标题下或结论区承接。`
  if (metric.value >= 70) return `${metric.label} 表现稳定，适合写成“放心用”或“没有明显短板”。`
  return `${metric.label} 更像提醒项，适合在正文里用更克制的表达解释取舍。`
})

const scoreBand = computed(() => {
  if (cardMode.value !== 'scored_evidence') return '当前更适合做倾向判断'
  if (averageScore.value >= 85) return '优势比较明确'
  if (averageScore.value >= 70) return '整体比较均衡'
  return '更适合保守解读'
})

const evidenceChips = computed(() => [
  `${strongestMetric.value?.label || '主维度'} 领先`,
  `${weakestMetric.value?.label || '风险维度'} 需要补强`,
  `均值 ${averageScore.value}`,
])

const confidenceLabel = (confidence?: string) => {
  if (confidence === 'high') return '高可信'
  if (confidence === 'low') return '保守表达'
  return '常规判断'
}

const polygonPoints = computed(() =>
  normalizedMetrics.value
    .map((metric, idx) => {
      const angle = (Math.PI * 2 * idx) / sides.value - Math.PI / 2
      const x = center + radius * (metric.value / 100) * Math.cos(angle)
      const y = center + radius * (metric.value / 100) * Math.sin(angle)
      return `${x},${y}`
    })
    .join(' ')
)

const gridLines = computed(() =>
  [0.25, 0.5, 0.75, 1].map((scale) =>
    normalizedMetrics.value
      .map((_, idx) => {
        const angle = (Math.PI * 2 * idx) / sides.value - Math.PI / 2
        const x = center + radius * scale * Math.cos(angle)
        const y = center + radius * scale * Math.sin(angle)
        return `${x},${y}`
      })
      .join(' ')
  )
)

const metricPoint = (idx: number, value: number) => {
  const angle = (Math.PI * 2 * idx) / sides.value - Math.PI / 2
  return {
    x: center + radius * (value / 100) * Math.cos(angle),
    y: center + radius * (value / 100) * Math.sin(angle),
  }
}

const metricAxis = (idx: number) => {
  const angle = (Math.PI * 2 * idx) / sides.value - Math.PI / 2
  return {
    x: center + radius * Math.cos(angle),
    y: center + radius * Math.sin(angle),
  }
}
</script>

<template>
  <div
    :class="['relative w-full overflow-hidden rounded-[30px] border p-5 md:p-6 animate-in fade-in slide-in-from-bottom-4 duration-700', cssClasses]"
    :style="cardStyle"
  >
    <div class="pointer-events-none absolute inset-0 opacity-80" :style="{ background: 'radial-gradient(circle at top left, color-mix(in srgb, var(--primary-vibe) 16%, white 84%) 0%, transparent 32%), radial-gradient(circle at bottom right, rgba(15,23,42,0.06) 0%, transparent 42%)' }"></div>
    <div class="flex flex-col gap-3">
      <div>
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">{{ cardMode === 'scored_evidence' ? '维度对比' : '重点判断' }}</div>
        <div class="mt-2 text-xl font-black leading-tight" :style="{ color: 'var(--text-color)' }">{{ title }}</div>
        <div class="mt-2 text-sm leading-relaxed" :style="{ color: 'var(--text-muted)' }">
          {{ cardMode === 'scored_evidence' ? '把关键维度放在一张图里看清楚，但不过度包装成精确评分。' : '当前更适合作为判断摘要展示，不把它包装成精确评分报告。' }}
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="chip in evidenceChips"
            :key="chip"
            class="rounded-full border px-2.5 py-1 text-[10px] font-bold"
            :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: 'var(--text-muted)' }"
          >
            {{ chip }}
          </span>
        </div>
      </div>
      <div class="grid gap-2 sm:grid-cols-2">
        <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">{{ cardMode === 'scored_evidence' ? '更值得先看' : '当前重点' }}</div>
          <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ strongestMetric?.label }}</div>
          <div class="text-[12px]" :style="{ color: 'var(--primary-vibe)' }">{{ cardMode === 'scored_evidence' ? strongestMetric?.value : '优先展开' }}</div>
        </div>
        <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">{{ cardMode === 'scored_evidence' ? '更需要留意' : '需要留意' }}</div>
          <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ weakestMetric?.label }}</div>
          <div class="text-[12px]" :style="{ color: '#b45309' }">{{ cardMode === 'scored_evidence' ? weakestMetric?.value : '谨慎表达' }}</div>
        </div>
        <div class="col-span-2 rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">整体结论</div>
              <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ cardMode === 'scored_evidence' ? `当前均值 ${averageScore}` : '当前更适合保守解读' }}</div>
            </div>
            <div class="rounded-full px-3 py-1 text-[10px] font-black" :style="{ background: 'color-mix(in srgb, var(--primary-vibe) 12%, white 88%)', color: 'var(--primary-vibe)' }">
              {{ cardMode === 'scored_evidence' ? `${strongestMetric?.label} 更适合优先讲清楚` : `${strongestMetric?.label} 更值得优先展开` }}
            </div>
          </div>
          <div class="mt-2 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            {{ scoreBand }}
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-5 md:grid-cols-[220px_minmax(0,1fr)] md:items-start">
      <div class="relative mx-auto aspect-square w-full max-w-[240px]">
        <svg viewBox="0 0 220 220" class="h-full w-full">
          <polygon
            v-for="(line, idx) in gridLines"
            :key="idx"
            :points="line"
            fill="none"
            :stroke="idx === gridLines.length - 1 ? 'rgba(148,163,184,0.4)' : 'rgba(148,163,184,0.18)'"
            stroke-width="1"
          />
          <line
            v-for="(_, idx) in normalizedMetrics"
            :key="`axis-${idx}`"
            :x1="center"
            :y1="center"
            :x2="metricAxis(idx).x"
            :y2="metricAxis(idx).y"
            stroke="rgba(148,163,184,0.22)"
            stroke-width="1"
          />
          <polygon
            :points="polygonPoints"
            fill="var(--primary-vibe)"
            fill-opacity="0.16"
            stroke="var(--primary-vibe)"
            stroke-width="2.5"
            stroke-linejoin="round"
          />
          <circle
            v-for="(metric, idx) in normalizedMetrics"
            :key="`dot-${metric.label}`"
            :cx="metricPoint(idx, metric.value).x"
            :cy="metricPoint(idx, metric.value).y"
            :r="activeIndex === idx ? 6 : 4"
            fill="white"
            stroke="var(--primary-vibe)"
            stroke-width="2"
          />
        </svg>

        <div
          v-for="(metric, idx) in normalizedMetrics"
          :key="`label-${metric.label}`"
          class="absolute text-[10px] font-black whitespace-nowrap"
          :style="{
            color: activeIndex === idx ? 'var(--text-color)' : 'var(--text-muted)',
            left: (50 + 58 * Math.cos((Math.PI * 2 * idx) / sides - Math.PI / 2)) + '%',
            top: (50 + 58 * Math.sin((Math.PI * 2 * idx) / sides - Math.PI / 2)) + '%',
            transform: 'translate(-50%, -50%)',
          }"
        >
          {{ metric.label }}
        </div>

        <div class="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div class="rounded-full border px-4 py-3 text-center backdrop-blur-md" :style="{ borderColor: 'rgba(255,255,255,0.16)', background: 'rgba(15,23,42,0.42)', boxShadow: '0 18px 36px rgba(15,23,42,0.16)' }">
            <div class="text-[9px] font-black uppercase tracking-[0.22em] text-white/60">Average</div>
            <div class="mt-1 text-[24px] font-black leading-none text-white">{{ cardMode === 'scored_evidence' ? averageScore : 'S' }}</div>
            <div class="mt-1 text-[10px] text-white/68">{{ scoreBand }}</div>
          </div>
        </div>
      </div>

      <div class="grid gap-3">
        <button
          v-for="(metric, idx) in normalizedMetrics"
          :key="metric.label"
          type="button"
          class="block w-full rounded-[22px] border px-4 py-3 text-left transition-all duration-300 hover:-translate-y-0.5"
          :style="{
            borderColor: activeIndex === idx ? 'var(--primary-vibe)' : 'var(--card-border)',
            background: activeIndex === idx ? 'color-mix(in srgb, var(--primary-vibe) 10%, white 90%)' : 'var(--card-bg-soft)',
          }"
          @mouseenter="activeIndex = idx"
          @mouseleave="activeIndex = null"
        >
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">Dimension {{ idx + 1 }}</div>
              <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ metric.label }}</div>
            </div>
            <div class="text-right">
              <div class="text-lg font-black leading-none" :style="{ color: 'var(--primary-vibe)' }">{{ metric.value }}</div>
              <div class="text-[10px]" :style="{ color: 'var(--text-muted)' }">/ 100</div>
            </div>
          </div>
          <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/60">
            <div
              class="h-full rounded-full transition-all duration-500"
              :style="{ width: `${metric.value}%`, background: 'linear-gradient(90deg, color-mix(in srgb, var(--primary-vibe) 84%, white 16%) 0%, var(--primary-vibe) 100%)' }"
            ></div>
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            <span class="rounded-full border px-2 py-1 text-[10px] font-semibold" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: metric.confidence === 'low' ? '#b45309' : metric.confidence === 'high' ? '#047857' : 'var(--text-muted)' }">
              {{ confidenceLabel(metric.confidence) }}
            </span>
            <span>{{ metric.reason || '该维度适合承接一条简洁的判断理由。' }}</span>
          </div>
          <div v-if="metric.evidence" class="mt-2 text-[11px] leading-relaxed" :style="{ color: 'var(--primary-vibe)' }">
            证据提示：{{ metric.evidence }}
          </div>
        </button>
      </div>
    </div>

    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <div class="rounded-[22px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Reading Note</div>
        <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
          {{ (activeMetric || strongestMetric)?.label || '当前维度' }}
        </div>
        <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
          {{ interpretation }}
        </div>
        <div
          v-if="(activeMetric || strongestMetric)?.evidence"
          class="mt-2 rounded-2xl border px-3 py-2 text-[11px] leading-relaxed"
          :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.72)', color: 'var(--text-muted)' }"
        >
          证据切片：{{ (activeMetric || strongestMetric)?.evidence }}
        </div>
      </div>
      <div class="rounded-[22px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Evidence Posture</div>
        <div class="mt-2 grid gap-2 sm:grid-cols-2">
          <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
              <div class="text-[9px] uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">先看这一项</div>
            <div class="mt-1 text-sm font-bold" :style="{ color: 'var(--text-color)' }">{{ strongestMetric?.label }}</div>
            <div class="mt-1 text-[11px]" :style="{ color: 'var(--primary-vibe)' }">更适合放在结论前面讲清楚</div>
          </div>
          <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
              <div class="text-[9px] uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">这项要更保守</div>
            <div class="mt-1 text-sm font-bold" :style="{ color: 'var(--text-color)' }">{{ weakestMetric?.label }}</div>
            <div class="mt-1 text-[11px]" :style="{ color: '#b45309' }">更适合用克制语气解释取舍</div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-4 rounded-[24px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
      <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">怎么看这张图</div>
          <div class="mt-1 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
            重点不是分数本身，而是看清哪些地方更强、哪些地方要保守讲
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <span class="rounded-full border px-2.5 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: 'var(--text-muted)' }">适合：快速判断 / 对比总结</span>
          <span class="rounded-full border px-2.5 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: 'var(--primary-vibe)' }">不适合：脱离依据单看分数</span>
        </div>
      </div>
    </div>

    <FactBindingFooter :node="node" />
  </div>
</template>
