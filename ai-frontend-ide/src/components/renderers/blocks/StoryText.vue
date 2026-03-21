<template>
  <div :id="compId" :class="[cssClasses]" :style="inlineStyles" @click="handleClick" @mouseover="handleMouseOver">
    <div
      v-for="(p, idx) in paragraphs"
      :key="idx"
      class="group/paragraph relative mb-3 rounded-xl transition-all cursor-pointer"
      @mouseenter="hoveredParagraph = idx"
      @mouseleave="hoveredParagraph = null"
    >
      <div
        class="text-[15px] leading-relaxed whitespace-pre-wrap rounded-xl transition-all px-3 py-2" :style="paragraphTextStyle(idx)"
        :class="selectedParagraph === idx ? 'ring-2 ring-[var(--primary-vibe)]/60 bg-[var(--primary-vibe)]/5' : 'hover:bg-black/[0.03]'"
        @click.stop="handleParagraphClick(idx, $event)"
      >
        {{ p }}
      </div>

      <div
        class="absolute -top-2 left-3 flex items-start gap-2 opacity-0 translate-y-1 transition-all duration-150 pointer-events-none group-hover/paragraph:opacity-100 group-hover/paragraph:translate-y-0"
        :class="selectedParagraph === idx || hoveredParagraph === idx ? 'opacity-100 translate-y-0 pointer-events-auto' : ''"
      >
        <span class="px-2 py-0.5 rounded-full bg-white/95 border border-slate-200 text-[10px] font-bold text-slate-500 shadow-sm">
          第{{ idx + 1 }}段
        </span>
        <span
          v-if="metaFor(idx)"
          class="px-2 py-0.5 rounded-full border text-[10px] font-bold shadow-sm"
          :class="paragraphMetaPillClass(metaFor(idx)?.kind)"
        >
          {{ paragraphMetaLabel(metaFor(idx)?.kind) }}
        </span>
        <div class="flex items-start gap-2">
          <div class="flex items-center gap-1">
            <button
              class="px-2 py-0.5 rounded-full bg-white/95 border border-slate-200 text-[10px] font-semibold text-slate-700 shadow-sm hover:border-blue-400 hover:text-blue-500"
              @click.stop="emitQuickAction(idx, '把这个正文块的第' + (idx + 1) + '段简短一点，保留核心信息。')"
            >
              简短
            </button>
            <button
              class="px-2 py-0.5 rounded-full bg-white/95 border border-slate-200 text-[10px] font-semibold text-slate-700 shadow-sm hover:border-blue-400 hover:text-blue-500"
              @click.stop="emitQuickAction(idx, '重写这个正文块的第' + (idx + 1) + '段，让表达更有冲击力。')"
            >
              重写
            </button>
            <button
              class="px-2 py-0.5 rounded-full bg-white/95 border border-slate-200 text-[10px] font-semibold text-slate-700 shadow-sm hover:border-blue-400 hover:text-blue-500"
              @click.stop="emitQuickAction(idx, '把这个正文块的第' + (idx + 1) + '段改得更尖锐一点，但不要失真。')"
            >
              尖锐
            </button>
          </div>
          <div
            v-if="metaFor(idx)"
            class="max-w-[260px] rounded-2xl border bg-white/95 px-3 py-2 text-[11px] text-slate-600 shadow-lg backdrop-blur"
            :class="paragraphMetaCardClass(metaFor(idx)?.kind)"
          >
            <div class="font-semibold text-slate-800">
              {{ metaFor(idx)?.hint || paragraphMetaHint(metaFor(idx)?.kind) }}
            </div>
            <div v-if="paragraphFactFields(idx).length" class="mt-1 text-[10px] text-slate-500">
              绑定字段: {{ paragraphFactFields(idx).join(' / ') }}
            </div>
            <div v-if="metaFor(idx)?.sources?.length" class="mt-1 text-[10px] text-slate-500">
              来源: {{ metaFor(idx)?.sources?.join(' / ') }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

type ParagraphMeta = {
  kind?: string
  hint?: string
  sources?: string[]
  fields?: string[]
}

const props = defineProps<{
  compId: string
  data: any
  style: any
  selectedParagraph?: number | null
}>()

const emit = defineEmits(['select', 'hover', 'quick-action'])

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const paragraphs = computed(() => props.data?.paragraphs || [])
const paragraphMeta = computed<ParagraphMeta[]>(() => Array.isArray(props.data?.paragraph_meta) ? props.data.paragraph_meta : [])
const selectedParagraph = computed(() => props.selectedParagraph ?? null)
const hoveredParagraph = ref<number | null>(null)

const FACT_FIELD_LABELS: Record<string, string> = {
  battery_capacity: '电池容量',
  price: '价格',
}

const metaFor = (idx: number): ParagraphMeta | null => paragraphMeta.value[idx] || null

const paragraphFactFields = (idx: number) => {
  const fields = Array.isArray(metaFor(idx)?.fields) ? metaFor(idx)?.fields || [] : []
  return Array.from(new Set(fields.map((field) => String(field)).filter(Boolean))).map((field) => FACT_FIELD_LABELS[field] || field)
}

const paragraphMetaLabel = (kind?: string | null) => {
  if (kind === 'verified') return '已确认'
  if (kind === 'caution') return '保守表达'
  return '信息说明'
}

const paragraphMetaHint = (kind?: string | null) => {
  if (kind === 'verified') return '该段采用已确认事实'
  if (kind === 'caution') return '该段因参数冲突而采用保守表达'
  return '该段基于当前页面内容生成'
}

const paragraphMetaPillClass = (kind?: string | null) => {
  if (kind === 'verified') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (kind === 'caution') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-slate-200 bg-white/95 text-slate-500'
}

const paragraphMetaCardClass = (kind?: string | null) => {
  if (kind === 'verified') return 'border-emerald-200 bg-emerald-50/95'
  if (kind === 'caution') return 'border-amber-200 bg-amber-50/95'
  return 'border-slate-200 bg-white/95'
}

const paragraphTextStyle = (idx: number) => ({
  color: 'var(--text-color, #1f2937)',
  background: selectedParagraph.value === idx ? 'var(--primary-vibe-light, rgba(255,36,66,0.08))' : 'transparent',
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

const emitQuickAction = (idx: number, prompt: string) => {
  emit('quick-action', { compId: props.compId, paragraphIndex: idx, prompt })
}
</script>
