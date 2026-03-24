<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver">
    <div
      v-for="(section, idx) in sections"
      :key="idx"
      class="group/paragraph relative mb-4 cursor-pointer rounded-[24px] border px-4 py-4 transition-all"
      :style="sectionCardStyle(idx, section.kind)"
      @mouseenter="hoveredParagraph = idx"
      @mouseleave="hoveredParagraph = null"
    >
      <div class="flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="rounded-full border px-2.5 py-1 text-[10px] font-black tracking-[0.18em]" :class="paragraphMetaPillClass(section.kind)">
            {{ section.label || `第${idx + 1}段` }}
          </span>
          <span
            v-if="section.summary"
            class="rounded-full border px-2.5 py-1 text-[10px] font-semibold"
            :style="{ borderColor: 'var(--card-border)', background: 'rgba(255,255,255,0.78)', color: 'var(--text-muted)' }"
          >
            {{ section.summary }}
          </span>
        </div>

        <div
          class="rounded-[18px] px-3 py-3 text-[15px] leading-relaxed whitespace-pre-wrap transition-all"
          :style="paragraphTextStyle(idx)"
          :class="selectedParagraph === idx ? 'ring-2 ring-[var(--primary-vibe)]/60 bg-[var(--primary-vibe)]/5' : 'bg-white/60'"
          @click.stop="handleParagraphClick(idx, $event)"
        >
          {{ section.paragraph }}
        </div>

        <SourceDrilldownPanel
          v-if="section.sourceItems.length || section.sources.length || section.confidence || section.fields.length || section.hint"
          context-label="段落依据"
          trigger-label="查看段落依据"
          :sources="section.sources"
          :source-items="section.sourceItems"
          :fields="section.fields"
          :confidence="section.confidence"
          :hint="section.hint"
        />

      </div>
    </div>

    <FactBindingFooter :node="node" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import FactBindingFooter from './FactBindingFooter.vue'
import SourceDrilldownPanel from './SourceDrilldownPanel.vue'

type ParagraphMeta = {
  kind?: string
  hint?: string
  sources?: string[]
  source_items?: Array<{ label?: string; url?: string; source_scope?: string }>
  fields?: string[]
  confidence?: string
}

type StorySection = {
  label: string
  role: string
  paragraph: string
  summary?: string
  hint?: string
  sources?: string[]
  sourceItems: Array<{ label: string; url?: string; source_scope?: string }>
  fields?: string[]
  kind?: string
  confidence?: string
  roleHint: string
}

const props = defineProps<{
  compId: string
  node: any
  data: any
  style: any
  selectedParagraph?: number | null
  recentChange?: { fields?: string[]; paragraph_indices?: number[] } | null
}>()

const emit = defineEmits(['select', 'hover'])

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const paragraphs = computed(() => props.data?.paragraphs || [])
const paragraphMeta = computed<ParagraphMeta[]>(() => Array.isArray(props.data?.paragraph_meta) ? props.data.paragraph_meta : [])
const selectedParagraph = computed(() => props.selectedParagraph ?? null)
const hoveredParagraph = ref<number | null>(null)
const changedParagraphIndices = computed(() => new Set((props.recentChange?.paragraph_indices || []).map((value) => Number(value))))

const roleHintByRole = (role?: string | null) => {
  if (role === 'summary') return '适合承接最先给读者的判断。'
  if (role === 'verified') return '适合放已确认事实，不要写得像情绪段落。'
  if (role === 'caution') return '适合解释边界和不确定项。'
  if (role === 'selling_point') return '适合把最容易打动人的理由收紧。'
  return '适合承接正文，但不要退化成没有层次的大段文案。'
}

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

const sections = computed<StorySection[]>(() => {
  if (Array.isArray(props.data?.sections) && props.data.sections.length) {
    return props.data.sections.map((section: any, idx: number) => {
      const meta = paragraphMeta.value[idx] || {}
      return {
        label: String(section?.label || `第${idx + 1}段`),
        role: String(section?.role || 'body'),
        paragraph: String(section?.paragraph || paragraphs.value[idx] || ''),
        summary: String(section?.summary || ''),
        hint: String(section?.hint || meta?.hint || ''),
        sources: Array.isArray(section?.sources) ? section.sources.map((source: unknown) => String(source)) : Array.isArray(meta?.sources) ? meta.sources.map((source) => String(source)) : [],
        sourceItems: normalizeSourceItems(section?.source_items ?? meta?.source_items),
        fields: Array.isArray(section?.fields) ? section.fields.map((field: unknown) => String(field)) : Array.isArray(meta?.fields) ? meta.fields.map((field) => String(field)) : [],
        kind: String(section?.kind || meta?.kind || 'default'),
        confidence: String(section?.confidence || meta?.confidence || ''),
        roleHint: roleHintByRole(String(section?.role || 'body')),
      }
    })
  }

  return paragraphs.value.map((paragraph: string, idx: number) => {
    const meta = paragraphMeta.value[idx] || {}
    return {
      label: `第${idx + 1}段`,
      role: 'body',
      paragraph: String(paragraph || ''),
      summary: '',
      hint: String(meta?.hint || ''),
      sources: Array.isArray(meta?.sources) ? meta.sources.map((source) => String(source)) : [],
      sourceItems: normalizeSourceItems(meta?.source_items),
      fields: Array.isArray(meta?.fields) ? meta.fields.map((field) => String(field)) : [],
      kind: String(meta?.kind || 'default'),
      confidence: String(meta?.confidence || ''),
      roleHint: roleHintByRole('body'),
    }
  })
})

const paragraphMetaPillClass = (kind?: string | null) => {
  if (kind === 'verified') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (kind === 'caution') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-slate-200 bg-white/95 text-slate-500'
}

const sectionCardStyle = (idx: number, kind?: string | null) => {
  if (changedParagraphIndices.value.has(idx)) {
    return {
      borderColor: 'rgba(251,191,36,0.55)',
      background: 'linear-gradient(180deg, rgba(255,251,235,0.98) 0%, rgba(255,255,255,0.92) 100%)',
      boxShadow: '0 0 0 1px rgba(251,191,36,0.18), 0 18px 40px rgba(251,191,36,0.12)',
    }
  }
  if (selectedParagraph.value === idx) {
    return {
      borderColor: 'color-mix(in srgb, var(--primary-vibe) 35%, white 65%)',
      background: 'color-mix(in srgb, var(--primary-vibe) 6%, white 94%)',
    }
  }
  if (kind === 'verified') {
    return {
      borderColor: 'rgba(16,185,129,0.22)',
      background: 'linear-gradient(180deg, rgba(236,253,245,0.94) 0%, rgba(255,255,255,0.9) 100%)',
    }
  }
  if (kind === 'caution') {
    return {
      borderColor: 'rgba(245,158,11,0.24)',
      background: 'linear-gradient(180deg, rgba(255,247,237,0.96) 0%, rgba(255,255,255,0.92) 100%)',
    }
  }
  return {
    borderColor: 'var(--card-border)',
    background: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.84) 100%)',
  }
}

const paragraphTextStyle = (idx: number) => ({
  color: 'var(--text-color, #1f2937)',
  background: selectedParagraph.value === idx
    ? 'var(--primary-vibe-light, rgba(255,36,66,0.08))'
    : changedParagraphIndices.value.has(idx)
      ? 'rgba(255,251,235,0.88)'
      : 'rgba(255,255,255,0.72)',
})

const handleClick = (e: MouseEvent) => {
  e.stopPropagation()
  emit('select', props.compId)
}

const handleMouseOver = (e: MouseEvent) => {
  e.stopPropagation()
  emit('hover', props.compId)
}

const handleParagraphClick = (idx: number, e: MouseEvent) => {
  e.stopPropagation()
  emit('select', { compId: props.compId, paragraphIndex: idx })
}

</script>
