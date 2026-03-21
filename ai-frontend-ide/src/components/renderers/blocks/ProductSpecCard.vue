<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" class="rounded-2xl p-4 border">
    <!-- 头部：标题与装饰 -->
    <div class="flex items-center gap-2 mb-4">
      <div class="w-1.5 h-4 rounded-full bg-[var(--primary-vibe,#ff2442)]"></div>
      <h3 class="text-sm font-bold uppercase tracking-widest" :style="{ color: 'var(--text-color)' }">Product Specs</h3>
    </div>

    <!-- 内容区：骨架屏 vs 真实数据 -->
    <div class="grid grid-cols-1 gap-2.5">
      <!-- 骨架屏：当没有参数数据时显示 -->
      <template v-if="!props.data?.core_features || props.data.core_features.length === 0">
        <div v-for="i in 4" :key="i" class="flex items-center gap-3 p-2.5 rounded-xl bg-gray-50/50 animate-pulse">
          <div class="w-4 h-4 rounded-md bg-gray-200"></div>
          <div class="h-3 bg-gray-200 rounded-full flex-1"></div>
        </div>
      </template>

      <!-- 真实数据 -->
      <template v-else>
        <div 
          v-for="(feature, idx) in props.data.core_features" 
          :key="idx"
          :class="featureRowClass(feature)"
        >
          <div class="relative flex w-full items-start gap-3 group/feature">
            <span :class="featureIconClass(feature)">
              <template v-if="isCautionFeature(feature)">⚠️</template>
              <template v-else-if="isVerifiedFeature(feature)">已确认</template>
              <svg v-else class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>
            </span>
            <span :class="featureTextClass(feature)" :style="featureTextStyle(feature)">{{ normalizeFeatureText(feature) }}</span>
            <div
              v-if="featureHint(feature, idx)"
              class="pointer-events-none absolute -top-2 right-0 hidden max-w-[220px] translate-y-[-100%] rounded-lg border border-[#334155] bg-[#111827] px-3 py-2 text-[10px] leading-relaxed text-slate-200 shadow-xl group-hover/feature:block"
            >
              <div class="font-semibold text-slate-100">{{ featureHint(feature, idx) }}</div>
              <div v-if="featureFactFields(idx).length" class="mt-1 text-slate-400">绑定字段: {{ featureFactFields(idx).join(' / ') }}</div>
              <div v-if="featureSources(idx).length" class="mt-1 text-slate-400">来源: {{ featureSources(idx).join(' / ') }}</div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  compId: string
  data: any
  style: any
}>()

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const featureMeta = computed(() => Array.isArray(props.data?.feature_meta) ? props.data.feature_meta : [])

const FACT_FIELD_LABELS: Record<string, string> = {
  battery_capacity: '电池容量',
  price: '价格',
}

const VERIFIED_FEATURE_PREFIX = '__verified__'

const normalizeFeatureText = (feature: string) => String(feature || '').replace(VERIFIED_FEATURE_PREFIX, '')

const isVerifiedFeature = (feature: string) => String(feature || '').startsWith(VERIFIED_FEATURE_PREFIX)

const isCautionFeature = (feature: string) => /多版本说法|官方页|人工确认|待确认/.test(String(feature || ''))

const featureRowClass = (feature: string) => [
  'flex items-start gap-3 p-2.5 rounded-xl border transition-all group',
  isCautionFeature(feature)
    ? 'bg-amber-50/80 border-amber-200/80 hover:border-amber-300'
    : isVerifiedFeature(feature)
      ? 'bg-emerald-50/80 border-emerald-200/80 hover:border-emerald-300'
      : 'bg-transparent border-transparent hover:border-[var(--primary-vibe-light)]',
]

const featureIconClass = (feature: string) =>
  isCautionFeature(feature)
    ? 'mt-0.5 text-[12px] leading-none'
    : isVerifiedFeature(feature)
      ? 'mt-0.5 text-[10px] font-bold text-emerald-700'
      : 'text-[var(--primary-vibe,#ff2442)] mt-0.5 group-hover:scale-110 transition-transform'

const featureTextClass = (feature: string) =>
  isCautionFeature(feature)
    ? 'text-[13px] text-amber-900 leading-tight font-medium'
    : isVerifiedFeature(feature)
      ? 'text-[13px] text-emerald-900 leading-tight font-medium'
      : 'text-[13px] leading-tight font-medium'

const featureTextStyle = (feature: string) =>
  isCautionFeature(feature)
    ? { color: '#78350f' }
    : isVerifiedFeature(feature)
      ? { color: '#065f46' }
      : { color: 'var(--text-color)' }

const featureSources = (idx: number) => Array.isArray(featureMeta.value?.[idx]?.sources) ? featureMeta.value[idx].sources : []
const featureHint = (feature: string, idx: number) => String(featureMeta.value?.[idx]?.hint || '')
const featureFactFields = (idx: number) => {
  const meta = featureMeta.value?.[idx] || {}
  const raw = []
  if (meta?.field) raw.push(String(meta.field))
  if (Array.isArray(meta?.fields)) raw.push(...meta.fields.map((item: unknown) => String(item)))
  return Array.from(new Set(raw.filter(Boolean))).map((field) => FACT_FIELD_LABELS[field] || field)
}
</script>

<style scoped>
/* 可以在这里添加一些细微的动效 */
</style>
