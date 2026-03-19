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
        class="text-[15px] text-gray-800 leading-relaxed whitespace-pre-wrap rounded-xl transition-all px-3 py-2"
        :class="selectedParagraph === idx ? 'ring-2 ring-[var(--primary-vibe)]/60 bg-[var(--primary-vibe)]/5' : 'hover:bg-black/[0.03]'"
        @click.stop="handleParagraphClick(idx, $event)"
      >
        {{ p }}
      </div>

      <div
        class="absolute -top-2 left-3 flex items-center gap-2 opacity-0 translate-y-1 transition-all duration-150 pointer-events-none group-hover/paragraph:opacity-100 group-hover/paragraph:translate-y-0"
        :class="selectedParagraph === idx || hoveredParagraph === idx ? 'opacity-100 translate-y-0 pointer-events-auto' : ''"
      >
        <span class="px-2 py-0.5 rounded-full bg-white/95 border border-slate-200 text-[10px] font-bold text-slate-500 shadow-sm">
          第{{ idx + 1 }}段
        </span>
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

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
const selectedParagraph = computed(() => props.selectedParagraph ?? null)
const hoveredParagraph = ref<number | null>(null)

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
