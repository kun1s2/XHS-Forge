<template>
  <div
    :id="compId"
    :class="[cssClasses]"
    :style="inlineStyles"
    class="group relative mb-4 w-full overflow-hidden rounded-[32px] border"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="pointer-events-none absolute inset-0 z-[1] opacity-80" :style="ambientGlowStyle"></div>
    <div class="absolute inset-0 pointer-events-none z-10" :style="overlayStyle"></div>

    <div class="absolute left-4 top-4 z-20 flex items-center gap-2">
      <div
        class="rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-[0.22em]"
        :style="badgeStyle"
      >
        封面
      </div>
      <div
        v-if="imageList.length > 1"
        class="rounded-full px-2.5 py-1 text-[10px] font-bold"
        :style="counterStyle"
      >
        {{ currentIdx + 1 }}/{{ imageList.length }}
      </div>
    </div>

    <div
      v-if="!hasImages"
      class="flex aspect-[4/5] min-h-[320px] w-full flex-col items-center justify-center animate-pulse sm:min-h-[360px] lg:aspect-[16/10] lg:min-h-[380px]"
      :style="fallbackStyle"
    >
      <div class="mb-3 h-12 w-12" :style="iconStyle">
        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          ></path>
        </svg>
      </div>
      <div class="text-xs font-medium" :style="textStyle">等待封面图片接入...</div>
    </div>

    <template v-else>
      <div class="relative aspect-[4/5] min-h-[320px] overflow-hidden sm:min-h-[360px] lg:aspect-[16/10] lg:min-h-[380px]" :style="railStyle">
        <div class="flex h-full transition-transform duration-700 ease-out" :style="trackStyle">
          <div
            v-for="(img, idx) in imageList"
            :key="`${img}-${idx}`"
            class="relative h-full w-full shrink-0"
          >
            <img
              :src="img"
              :alt="slideHeadline(idx)"
              class="h-full w-full object-cover"
            />
            <div
              class="absolute inset-x-0 bottom-0 z-10 px-5 pb-5 pt-20"
              :style="slideInfoStyle"
            >
              <div class="max-w-[82%]">
                <div class="text-[10px] font-black uppercase tracking-[0.22em] text-white/72">
                  {{ imageList.length > 1 ? '封面组图' : '封面图' }}
                </div>
                <div class="mt-2 text-base font-black leading-tight text-white sm:text-lg">
                  {{ slideHeadline(idx) }}
                </div>
                <div class="mt-2 text-[12px] leading-relaxed text-white/82">
                  {{ slideCaption(idx) }}
                </div>
                <div
                  v-if="imageSourceLabel(idx)"
                  class="mt-3 inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold text-white/82"
                  :style="{ borderColor: 'rgba(255,255,255,0.16)', background: 'rgba(15,23,42,0.16)' }"
                >
                  {{ imageSourceLabel(idx) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <button
          v-if="imageList.length > 1"
          type="button"
          class="absolute left-4 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border transition-all duration-300 group-hover:scale-100 md:scale-95"
          :style="navButtonStyle"
          @click="prev"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
          </svg>
        </button>

        <button
          v-if="imageList.length > 1"
          type="button"
          class="absolute right-4 top-1/2 z-20 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border transition-all duration-300 group-hover:scale-100 md:scale-95"
          :style="navButtonStyle"
          @click="next"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
          </svg>
        </button>
      </div>

      <div
        v-if="imageList.length > 1"
        class="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 rounded-full px-3 py-2"
        :style="indicatorShellStyle"
      >
        <button
          v-for="(_, idx) in imageList"
          :key="`indicator-${idx}`"
          type="button"
          class="h-2.5 rounded-full transition-all duration-300"
          :style="indicatorStyle(idx)"
          @click="goTo(idx)"
        ></button>
      </div>

      <div class="border-t px-5 py-4" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg)' }">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div class="max-w-2xl">
            <div class="text-sm font-bold leading-relaxed" :style="{ color: 'var(--text-color)' }">
              {{ slideHeadline(currentIdx) }}
            </div>
            <div class="mt-1 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
              {{ deckSummary }}
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="chip in deckChips"
              :key="chip"
              class="rounded-full border px-2.5 py-1 text-[10px] font-semibold"
              :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
            >
              {{ chip }}
            </span>
          </div>
        </div>

        <div
          v-if="imageList.length > 1"
          class="mt-4 grid gap-2 sm:grid-cols-3"
        >
          <button
            v-for="(img, idx) in imageList.slice(0, 3)"
            :key="`thumb-${idx}`"
            type="button"
            class="group relative overflow-hidden rounded-[20px] border transition-all duration-300 hover:-translate-y-0.5"
            :style="{ borderColor: currentIdx === idx ? 'var(--primary-vibe)' : 'var(--card-border)', background: 'var(--card-bg-soft)' }"
            @click="goTo(idx)"
          >
            <div class="aspect-[4/3] overflow-hidden">
              <img :src="img" :alt="`cover-thumb-${idx}`" class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]" />
            </div>
            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent px-3 pb-3 pt-10 text-left">
              <div class="text-[9px] font-black uppercase tracking-[0.2em] text-white/70">图 {{ idx + 1 }}</div>
              <div class="mt-1 text-[11px] font-bold leading-tight text-white">{{ imageSourceLabel(idx) }}</div>
            </div>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  compId: string
  data: any
  style: any
}>()

const currentIdx = ref(0)
const isHovered = ref(false)
let autoplayTimer: ReturnType<typeof setInterval> | null = null
const isVisualLab = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('visual_lab') === '1'

const imageList = computed<string[]>(() => {
  const urls = props.data?.image_urls || []
  if (urls.length === 0 && props.data?.image_url) return [props.data.image_url]
  return urls.filter(Boolean)
})

const hasImages = computed(() => imageList.value.length > 0)
const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})

const railStyle = computed(() => ({ background: 'var(--surface-hero, var(--card-bg))' }))
const ambientGlowStyle = computed(() => ({
  background:
    'radial-gradient(circle at top left, color-mix(in srgb, var(--primary-vibe) 18%, white 82%) 0%, transparent 34%), radial-gradient(circle at bottom right, rgba(15,23,42,0.08) 0%, transparent 44%)',
}))
const overlayStyle = computed(() => ({
  background:
    'linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(15,23,42,0.04) 100%)',
}))
const fallbackStyle = computed(() => ({
  background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(226,232,240,0.82) 100%)',
}))
const iconStyle = computed(() => ({ color: 'var(--primary-vibe)' }))
const textStyle = computed(() => ({ color: 'var(--text-muted)' }))
const badgeStyle = computed(() => ({
  background: 'rgba(255,255,255,0.92)',
  color: 'var(--text-color)',
}))
const counterStyle = computed(() => ({
  background: 'rgba(15,23,42,0.46)',
  color: 'rgba(255,255,255,0.92)',
}))
const slideInfoStyle = computed(() => ({
  background: 'linear-gradient(180deg, rgba(15,23,42,0) 0%, rgba(15,23,42,0.56) 100%)',
}))
const navButtonStyle = computed(() => ({
  background: 'rgba(255,255,255,0.94)',
  borderColor: 'rgba(255,255,255,0.84)',
  color: 'var(--text-color)',
  boxShadow: '0 14px 30px rgba(15,23,42,0.12)',
}))
const indicatorShellStyle = computed(() => ({
  background: 'rgba(15,23,42,0.36)',
  border: '1px solid rgba(255,255,255,0.12)',
}))

const trackStyle = computed(() => ({
  transform: `translateX(-${currentIdx.value * 100}%)`,
}))

const progressStyle = computed(() => ({
  width: `${((currentIdx.value + 1) / Math.max(imageList.value.length, 1)) * 100}%`,
  background: 'linear-gradient(90deg, color-mix(in srgb, var(--primary-vibe) 72%, white 28%) 0%, var(--primary-vibe) 100%)',
}))

const indicatorStyle = (idx: number) => ({
  width: currentIdx.value === idx ? '26px' : '10px',
  background: currentIdx.value === idx ? '#ffffff' : 'rgba(255,255,255,0.35)',
})

const rawHeadlines = computed<string[]>(() => {
  const headlines = props.data?.frame_headlines || props.data?.headlines || []
  return Array.isArray(headlines) ? headlines.map((value: unknown) => String(value || '').trim()) : []
})

const rawCaptions = computed<string[]>(() => {
  const captions = props.data?.frame_captions || props.data?.captions || []
  return Array.isArray(captions) ? captions.map((value: unknown) => String(value || '').trim()) : []
})

const sourceLabels = computed<string[]>(() => {
  const labels = props.data?.source_labels || props.data?.image_source_labels || []
  return Array.isArray(labels) ? labels.map((value: unknown) => String(value || '').trim()) : []
})

const deckSummary = computed(() => {
  if (props.data?.deck_summary) return String(props.data.deck_summary)
  if (props.data?.subtitle) return String(props.data.subtitle)
  if (imageList.value.length > 1) return `共 ${imageList.value.length} 张图，适合承接首屏氛围、补充视角和封面说明。`
  return '适合承接首屏封面和主题定调。'
})

const deckChips = computed(() => {
  const chips = Array.isArray(props.data?.deck_chips) ? props.data.deck_chips.map((value: unknown) => String(value || '').trim()).filter(Boolean) : []
  if (chips.length) return chips.slice(0, 3)
  return [
    imageList.value.length > 1 ? '多图封面' : '单图封面',
    props.data?.cover_focus || '封面已对齐当前主题',
  ]
})

const imageSourceLabel = (idx: number) => sourceLabels.value[idx] || `封面视角 ${idx + 1}`

const slideHeadline = (idx: number) => {
  return rawHeadlines.value[idx] || props.data?.title || imageSourceLabel(idx)
}

const slideCaption = (idx: number) => {
  return rawCaptions.value[idx] || props.data?.description || props.data?.subtitle || '补充当前主题的核心画面和氛围。'
}

const next = () => {
  if (!imageList.value.length) return
  currentIdx.value = (currentIdx.value + 1) % imageList.value.length
}

const prev = () => {
  if (!imageList.value.length) return
  currentIdx.value = (currentIdx.value - 1 + imageList.value.length) % imageList.value.length
}

const goTo = (idx: number) => {
  currentIdx.value = idx
}

const stopAutoplay = () => {
  if (autoplayTimer) {
    clearInterval(autoplayTimer)
    autoplayTimer = null
  }
}

const startAutoplay = () => {
  stopAutoplay()
  if (isVisualLab || imageList.value.length <= 1) return
  autoplayTimer = setInterval(() => {
    if (!isHovered.value) next()
  }, 3600)
}

watch(imageList, () => {
  currentIdx.value = 0
  startAutoplay()
})

watch(isHovered, () => {
  if (!isHovered.value) startAutoplay()
})

onMounted(() => startAutoplay())
onBeforeUnmount(() => stopAutoplay())
</script>
