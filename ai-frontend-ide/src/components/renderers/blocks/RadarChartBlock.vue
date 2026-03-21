<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  node: any
  data: {
    title?: string
    metrics?: Array<{ label: string; value: number }>
    dimensions?: string[]
    scores?: number[]
  }
  style?: any
}>()

const activeIndex = ref<number | null>(null)

const normalizedMetrics = computed(() => {
  if (Array.isArray(props.data.metrics) && props.data.metrics.length) {
    return props.data.metrics.map((item) => ({
      label: String(item.label || '维度'),
      value: Math.max(0, Math.min(100, Number(item.value) || 0)),
    }))
  }
  if (Array.isArray(props.data.dimensions) && Array.isArray(props.data.scores) && props.data.dimensions.length) {
    return props.data.dimensions.map((label, idx) => ({
      label: String(label || `维度 ${idx + 1}`),
      value: Math.max(0, Math.min(100, Number(props.data.scores[idx]) || 0)),
    }))
  }
  return [
    { label: '性能', value: 85 },
    { label: '续航', value: 70 },
    { label: '颜值', value: 95 },
    { label: '便携', value: 80 },
    { label: '性价比', value: 65 },
  ]
})

const title = computed(() => props.data.title || '综合能力评估')
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
  if (metric.value >= 85) return `${metric.label} 已经形成明显优势，适合放进标题下或结论区承接。`
  if (metric.value >= 70) return `${metric.label} 表现稳定，适合写成“放心用”或“没有明显短板”。`
  return `${metric.label} 更像提醒项，适合在正文里用更克制的表达解释取舍。`
})

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
    :class="['w-full rounded-[30px] border p-5 md:p-6 animate-in fade-in slide-in-from-bottom-4 duration-700', cssClasses]"
    :style="cardStyle"
  >
    <div class="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">Evidence Radar</div>
        <div class="mt-2 text-xl font-black leading-tight" :style="{ color: 'var(--text-color)' }">{{ title }}</div>
        <div class="mt-2 text-sm leading-relaxed" :style="{ color: 'var(--text-muted)' }">
          不只是一个静态图形，而是把结论、短板和维度强弱说清楚。
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 md:min-w-[280px]">
        <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">最强维度</div>
          <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ strongestMetric?.label }}</div>
          <div class="text-[12px]" :style="{ color: 'var(--primary-vibe)' }">{{ strongestMetric?.value }}</div>
        </div>
        <div class="rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">补强空间</div>
          <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">{{ weakestMetric?.label }}</div>
          <div class="text-[12px]" :style="{ color: '#b45309' }">{{ weakestMetric?.value }}</div>
        </div>
        <div class="col-span-2 rounded-2xl border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">综合判断</div>
              <div class="mt-1 text-sm font-black" :style="{ color: 'var(--text-color)' }">平均表现 {{ averageScore }}</div>
            </div>
            <div class="rounded-full px-3 py-1 text-[10px] font-black" :style="{ background: 'color-mix(in srgb, var(--primary-vibe) 12%, white 88%)', color: 'var(--primary-vibe)' }">
              {{ strongestMetric?.label }} 更适合作为主要卖点
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-center">
      <div class="relative mx-auto aspect-square w-full max-w-[260px]">
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
      </div>

      <div class="space-y-3">
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
              <div class="text-lg font-black" :style="{ color: 'var(--primary-vibe)' }">{{ metric.value }}</div>
              <div class="text-[10px]" :style="{ color: 'var(--text-muted)' }">/ 100</div>
            </div>
          </div>
          <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-200/60">
            <div
              class="h-full rounded-full transition-all duration-500"
              :style="{ width: `${metric.value}%`, background: 'linear-gradient(90deg, color-mix(in srgb, var(--primary-vibe) 84%, white 16%) 0%, var(--primary-vibe) 100%)' }"
            ></div>
          </div>
        </button>
        <div class="rounded-[22px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Reading Note</div>
          <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
            {{ (activeMetric || strongestMetric)?.label || '当前维度' }}
          </div>
          <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            {{ interpretation }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
