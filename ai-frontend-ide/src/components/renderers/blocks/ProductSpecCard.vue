<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" class="relative overflow-hidden rounded-[28px] border p-5">
    <div class="pointer-events-none absolute inset-0 opacity-80" :style="{ background: 'radial-gradient(circle at top left, color-mix(in srgb, var(--primary-vibe) 15%, white 85%) 0%, transparent 34%), radial-gradient(circle at bottom right, rgba(15,23,42,0.05) 0%, transparent 40%)' }"></div>

    <div class="relative flex flex-col gap-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">参数解读</div>
          <h3 class="mt-2 text-lg font-black leading-tight" :style="{ color: 'var(--text-color)' }">把关键参数翻译成购买判断</h3>
        </div>
        <div class="rounded-full border px-3 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }">
          {{ verifiedCount }} 条已确认 / {{ cautionCount }} 条需保守表达
        </div>
      </div>
    </div>

    <div class="relative mt-5 grid grid-cols-1 gap-3">
      <template v-if="!specItems.length">
        <div v-for="i in 4" :key="i" class="flex items-center gap-3 rounded-[22px] border bg-gray-50/70 px-4 py-4 animate-pulse">
          <div class="h-10 w-10 rounded-2xl bg-gray-200"></div>
          <div class="flex-1 space-y-2">
            <div class="h-3 w-24 rounded-full bg-gray-200"></div>
            <div class="h-3 w-2/3 rounded-full bg-gray-200"></div>
          </div>
        </div>
      </template>

      <article
        v-for="(item, idx) in specItems"
        :key="`${item.label}-${idx}`"
        class="rounded-[24px] border px-4 py-4 transition-all duration-200 hover:-translate-y-0.5"
        :style="rowStyle(item.status)"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-[11px] font-black" :style="badgeStyle(item.status)">
              {{ statusLabel(item.status) }}
            </div>
            <div>
              <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">{{ item.label }}</div>
              <div class="mt-1 text-base font-black leading-tight" :style="{ color: 'var(--text-color)' }">{{ item.value }}</div>
            </div>
          </div>
          <div class="rounded-full border px-2.5 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.72)', color: item.status === 'caution' ? '#b45309' : item.status === 'verified' ? '#047857' : 'var(--text-muted)' }">
            {{ item.status === 'verified' ? '已确认' : item.status === 'caution' ? '需保守' : '参考项' }}
          </div>
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
          <div class="rounded-[18px] border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.68)' }">
            <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">为什么重要</div>
            <div class="mt-2 text-[13px] leading-relaxed font-medium" :style="{ color: 'var(--text-color)' }">{{ item.decisionImpact }}</div>
            <div v-if="item.hint" class="mt-2 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">{{ item.hint }}</div>
          </div>
          <SourceDrilldownPanel
            v-if="item.sourceItems.length || item.sources.length || item.confidence || item.fields.length || item.hint"
            context-label="参数依据"
            trigger-label="查看参数依据"
            :sources="item.sources"
            :source-items="item.sourceItems"
            :fields="item.fields"
            :confidence="item.confidence"
            :hint="item.hint"
          />
          <div
            v-else
            class="rounded-[18px] border px-3 py-3 text-[11px] font-medium"
            :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.68)', color: 'var(--text-muted)' }"
          >
            暂无明确来源
          </div>
        </div>
      </article>
    </div>

    <FactBindingFooter :node="node" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FactBindingFooter from './FactBindingFooter.vue'
import SourceDrilldownPanel from './SourceDrilldownPanel.vue'

type SpecItem = {
  label: string
  value: string
  status: 'verified' | 'caution' | 'default' | string
  decisionImpact: string
  sources: string[]
  sourceItems: Array<{ label: string; url?: string; source_scope?: string }>
  fields: string[]
  confidence?: string
  hint?: string
}

const props = defineProps<{
  compId: string
  node: any
  data: any
  style: any
}>()

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const featureMeta = computed(() => Array.isArray(props.data?.feature_meta) ? props.data.feature_meta : [])

const normalizeSourceItems = (items: unknown) => {
  if (!Array.isArray(items)) return []
  return items
    .map((item) => ({
      label: String((item as Record<string, unknown>)?.label || '').trim(),
      url: String((item as Record<string, unknown>)?.url || '').trim() || undefined,
      source_scope: String((item as Record<string, unknown>)?.source_scope || '').trim() || undefined,
    }))
    .filter((item) => item.label)
}

const parseFeatureText = (feature: unknown) => {
  if (feature && typeof feature === 'object') {
    const record = feature as Record<string, unknown>
    return {
      label: String(record.label || '判断点'),
      value: String(record.value || record.text || ''),
    }
  }
  const normalized = String(feature || '').replace('__verified__', '')
  if (normalized.includes(':')) {
    const [label, ...rest] = normalized.split(':')
    return { label: label.trim(), value: rest.join(':').trim() }
  }
  return { label: '判断点', value: normalized }
}

const deriveDecisionImpact = (label: string) => {
  if (/[电池续航充电]/.test(label)) return '更直接决定日常使用的安全感和全天续航预期。'
  if (/[价格预算]/.test(label)) return '更适合承接“值不值得买”和预算边界。'
  if (/[影像拍照镜头]/.test(label)) return '更适合解释为什么这台设备会让人产生购买理由。'
  if (/[性能芯片跑分]/.test(label)) return '更适合解释重度使用和长期流畅度。'
  return '更适合作为购买判断的辅助证据，而不是孤立参数。'
}

const specItems = computed<SpecItem[]>(() => {
  if (Array.isArray(props.data?.spec_items) && props.data.spec_items.length) {
    return props.data.spec_items.map((item: any) => ({
      label: String(item?.label || '判断点'),
      value: String(item?.value || ''),
      status: String(item?.status || 'default'),
      decisionImpact: String(item?.decision_impact || deriveDecisionImpact(String(item?.label || ''))),
      sources: Array.isArray(item?.sources) ? item.sources.map((source: unknown) => String(source)) : [],
      sourceItems: normalizeSourceItems(item?.source_items),
      fields: Array.isArray(item?.fields) ? item.fields.map((field: unknown) => String(field)) : item?.field ? [String(item.field)] : [],
      confidence: String(item?.confidence || ''),
      hint: String(item?.hint || ''),
    }))
  }

  const features = Array.isArray(props.data?.core_features) ? props.data.core_features : []
  return features.map((feature: unknown, idx: number) => {
    const parsed = parseFeatureText(feature)
    const meta = featureMeta.value[idx] || {}
    return {
      label: parsed.label,
      value: parsed.value,
      status: String(meta?.kind || (typeof feature === 'string' && String(feature).startsWith('__verified__') ? 'verified' : 'default')),
      decisionImpact: String(meta?.decision_impact || deriveDecisionImpact(parsed.label)),
      sources: Array.isArray(meta?.sources) ? meta.sources.map((source: unknown) => String(source)) : [],
      sourceItems: normalizeSourceItems(meta?.source_items),
      fields: Array.isArray(meta?.fields) ? meta.fields.map((field: unknown) => String(field)) : meta?.field ? [String(meta.field)] : [],
      confidence: String(meta?.confidence || ''),
      hint: String(meta?.hint || ''),
    }
  })
})

const verifiedCount = computed(() => specItems.value.filter((item) => item.status === 'verified').length)
const cautionCount = computed(() => specItems.value.filter((item) => item.status === 'caution').length)
const statusLabel = (status: string) => {
  if (status === 'verified') return '确认'
  if (status === 'caution') return '提醒'
  return '参考'
}

const rowStyle = (status: string) => {
  if (status === 'verified') {
    return {
      borderColor: 'rgba(16,185,129,0.22)',
      background: 'linear-gradient(180deg, rgba(236,253,245,0.94) 0%, rgba(255,255,255,0.9) 100%)',
    }
  }
  if (status === 'caution') {
    return {
      borderColor: 'rgba(245,158,11,0.22)',
      background: 'linear-gradient(180deg, rgba(255,247,237,0.96) 0%, rgba(255,255,255,0.92) 100%)',
    }
  }
  return {
    borderColor: 'var(--card-border)',
    background: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.84) 100%)',
  }
}

const badgeStyle = (status: string) => {
  if (status === 'verified') return { background: 'rgba(16,185,129,0.12)', color: '#047857' }
  if (status === 'caution') return { background: 'rgba(245,158,11,0.14)', color: '#b45309' }
  return { background: 'rgba(15,23,42,0.06)', color: 'var(--text-muted)' }
}
</script>
