<template>
  <div
    v-if="hasMetadata"
    class="rounded-[18px] border px-3 py-3"
    :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.68)' }"
    @click.stop
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.18em]"
          :style="{ borderColor: 'var(--card-border)', color: 'var(--text-muted)' }"
        >
          {{ contextLabel }}
        </span>
        <span
          v-if="sourceCount"
          class="rounded-full border px-2 py-0.5 text-[9px] font-semibold"
          :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
        >
          来源 {{ sourceCount }}
        </span>
        <span
          v-if="confidenceLabel"
          class="rounded-full border px-2 py-0.5 text-[9px] font-semibold"
          :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: confidenceColor }"
        >
          置信度 {{ confidenceLabel }}
        </span>
      </div>

      <button
        type="button"
        class="rounded-full border px-2.5 py-1 text-[10px] font-semibold transition-colors hover:text-[var(--primary-vibe)]"
        :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.76)', color: 'var(--text-muted)' }"
        @click.stop="expanded = !expanded"
      >
        {{ expanded ? '收起来源' : triggerLabel }}
      </button>
    </div>

    <div v-if="expanded" class="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div class="rounded-[16px] border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.72)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">绑定说明</div>
        <div class="mt-2 flex flex-wrap gap-2">
          <span
            v-for="field in normalizedFields"
            :key="field"
            class="rounded-full border px-2 py-1 text-[10px] font-semibold"
            :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
          >
            {{ field }}
          </span>
          <span
            v-if="!normalizedFields.length"
            class="rounded-full border px-2 py-1 text-[10px] font-semibold"
            :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
          >
            当前没有明确绑定字段
          </span>
        </div>
        <div v-if="hintText" class="mt-3 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
          {{ hintText }}
        </div>
      </div>

      <div class="rounded-[16px] border px-3 py-3" :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.72)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">来源链接</div>
        <div class="mt-2 flex flex-col gap-2">
          <div
            v-for="(item, idx) in normalizedSourceItems"
            :key="`${item.label}-${item.url || idx}`"
            class="rounded-[14px] border px-3 py-2"
            :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <a
                v-if="item.url"
                :href="item.url"
                target="_blank"
                rel="noreferrer noopener"
                class="text-[11px] font-semibold transition-colors hover:text-[var(--primary-vibe)]"
                :style="{ color: 'var(--text-color)' }"
                @click.stop
              >
                {{ item.label }}
              </a>
              <span v-else class="text-[11px] font-semibold" :style="{ color: 'var(--text-color)' }">
                {{ item.label }}
              </span>
              <span
                v-if="item.source_scope"
                class="rounded-full border px-2 py-0.5 text-[9px] font-semibold"
                :style="{ borderColor: 'var(--card-border)', color: 'var(--text-muted)' }"
              >
                {{ sourceScopeLabel(item.source_scope) }}
              </span>
            </div>
            <div v-if="item.url" class="mt-1 text-[10px] break-all" :style="{ color: 'var(--text-muted)' }">
              {{ item.url }}
            </div>
          </div>

          <div
            v-if="!normalizedSourceItems.length"
            class="rounded-[14px] border px-3 py-2 text-[11px] font-medium"
            :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
          >
            暂无可展开来源
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

type SourceItem = {
  label?: string
  url?: string
  source_scope?: string
}

const props = defineProps<{
  contextLabel: string
  triggerLabel: string
  sources?: string[]
  sourceItems?: SourceItem[]
  fields?: string[]
  confidence?: string
  hint?: string
}>()

const expanded = ref(false)

const normalizedFields = computed(() =>
  Array.from(
    new Set(
      (Array.isArray(props.fields) ? props.fields : [])
        .map((field) => String(field || '').trim())
        .filter(Boolean)
    )
  )
)

const normalizedSourceItems = computed(() => {
  const explicit = Array.isArray(props.sourceItems)
    ? props.sourceItems
        .map((item) => ({
          label: String(item?.label || '').trim(),
          url: String(item?.url || '').trim() || undefined,
          source_scope: String(item?.source_scope || '').trim() || undefined,
        }))
        .filter((item) => item.label)
    : []

  if (explicit.length) return explicit

  return (Array.isArray(props.sources) ? props.sources : [])
    .map((source) => String(source || '').trim())
    .filter(Boolean)
    .map((label) => ({ label }))
})

const hintText = computed(() => String(props.hint || '').trim())
const sourceCount = computed(() => normalizedSourceItems.value.length)

const confidenceLabel = computed(() => {
  const value = String(props.confidence || '').trim()
  if (value === 'high') return '高'
  if (value === 'low') return '低'
  if (value) return '中'
  return ''
})

const confidenceColor = computed(() => {
  const value = String(props.confidence || '').trim()
  if (value === 'high') return '#047857'
  if (value === 'low') return '#b45309'
  return 'var(--text-muted)'
})

const hasMetadata = computed(
  () =>
    normalizedSourceItems.value.length > 0 ||
    normalizedFields.value.length > 0 ||
    !!confidenceLabel.value ||
    !!hintText.value
)

const sourceScopeLabel = (scope?: string) => {
  if (scope === 'official') return '官方来源'
  if (scope === 'review') return '评测来源'
  if (scope === 'user') return '用户来源'
  return scope || '来源'
}
</script>
