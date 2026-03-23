<template>
  <div
    v-if="hasBindings"
    class="mt-4 rounded-[18px] border px-4 py-3"
    :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.72)' }"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.18em]" :style="{ borderColor: 'var(--card-border)', color: 'var(--text-muted)' }">
          引用信息
        </span>
        <span class="text-[11px] font-semibold" :style="{ color: 'var(--text-color)' }">这块内容引用了本轮证据</span>
      </div>
      <div class="flex flex-wrap gap-2 text-[10px] font-bold">
        <span class="rounded-full border px-2.5 py-1" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }">
          来源 {{ uniqueSources.length }}
        </span>
        <span class="rounded-full border px-2.5 py-1" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: confidenceTone.color }">
          {{ confidenceTone.label }}
        </span>
        <span class="rounded-full border px-2.5 py-1" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }">
          证据条数 {{ evidenceCount }}
        </span>
      </div>
    </div>

    <div class="mt-3 flex flex-wrap gap-2">
      <template v-if="sourceItems.length">
        <a
          v-for="source in sourceItems"
          :key="`${source.label}-${source.url}`"
          :href="source.url || undefined"
          :target="source.url ? '_blank' : undefined"
          :rel="source.url ? 'noreferrer noopener' : undefined"
          class="rounded-full border px-2 py-1 text-[10px] font-semibold transition-colors hover:text-[var(--primary-vibe)]"
          :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
        >
          {{ source.label }}
        </a>
      </template>
      <span
        v-else
        v-for="source in uniqueSources"
        :key="source"
        class="rounded-full border px-2 py-1 text-[10px] font-semibold"
        :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
      >
        {{ source }}
      </span>
      <span
        v-if="boundFieldLabels.length"
        class="rounded-full border px-2 py-1 text-[10px] font-semibold"
        :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: 'var(--text-muted)' }"
      >
        绑定字段：{{ boundFieldLabels.join(' / ') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type FactBinding = {
  field?: string
  fact_fields?: string[]
  fact_field_labels?: string[]
  kind?: string
  sources?: string[]
  source_items?: Array<{ label?: string; url?: string; source_scope?: string }>
  hint?: string
  confidence?: string
}

const props = defineProps<{
  node?: {
    fact_bindings?: FactBinding[]
  } | null
}>()

const bindings = computed<FactBinding[]>(() =>
  Array.isArray(props.node?.fact_bindings)
    ? props.node!.fact_bindings.filter((item) => item && Array.isArray(item.sources) && item.sources.length > 0)
    : []
)

const hasBindings = computed(() => bindings.value.length > 0)
const evidenceCount = computed(() => bindings.value.length)
const uniqueSources = computed(() =>
  Array.from(
    new Set(
      bindings.value.flatMap((binding) =>
        Array.isArray(binding.sources) ? binding.sources.map((source) => String(source).trim()).filter(Boolean) : []
      )
    )
  ).slice(0, 6)
)

const sourceItems = computed(() => {
  const seen = new Set<string>()
  return bindings.value
    .flatMap((binding) =>
      Array.isArray(binding.source_items)
        ? binding.source_items
            .map((item) => ({
              label: String(item?.label || '').trim(),
              url: String(item?.url || '').trim(),
              source_scope: String(item?.source_scope || '').trim(),
            }))
            .filter((item) => item.label)
        : []
    )
    .filter((item) => {
      const key = `${item.label}::${item.url}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 6)
})

const confidenceTone = computed(() => {
  const explicit = bindings.value.map((binding) => String(binding.confidence || '').trim()).find(Boolean)
  if (explicit === 'high') return { label: '置信度 高', color: '#047857' }
  if (explicit === 'low') return { label: '置信度 低', color: '#b45309' }

  const caution = bindings.value.some((binding) => String(binding.kind || '') === 'caution')
  const verified = bindings.value.some((binding) => String(binding.kind || '') === 'verified')
  if (caution) return { label: '置信度 保守', color: '#b45309' }
  if (verified || uniqueSources.value.length >= 2) return { label: '置信度 高', color: '#047857' }
  return { label: '置信度 中', color: 'var(--text-muted)' }
})

const boundFieldLabels = computed(() =>
  Array.from(
    new Set(
      bindings.value.flatMap((binding) =>
        Array.isArray(binding.fact_field_labels)
          ? binding.fact_field_labels.map((field) => String(field).trim()).filter(Boolean)
          : []
      )
    )
  )
)
</script>
