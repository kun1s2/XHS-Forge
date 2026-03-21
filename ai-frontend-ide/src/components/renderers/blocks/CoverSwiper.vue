<template>
  <div
    :id="compId"
    :class="[cssClasses]"
    :style="inlineStyles"
    class="group relative mb-4 w-full overflow-hidden rounded-[32px] border"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="absolute inset-0 pointer-events-none z-10" :style="overlayStyle"></div>

    <div class="absolute left-4 top-4 z-20 flex items-center gap-2">
      <div
        class="rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-[0.22em]"
        :style="badgeStyle"
      >
        Cover Story
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
      class="flex h-[400px] w-full flex-col items-center justify-center animate-pulse"
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
      <div class="text-xs font-medium" :style="textStyle">AI 正在构思精美封面...</div>
    </div>

    <template v-else>
      <div class="relative h-[400px] overflow-hidden" :style="railStyle">
        <div class="flex h-full transition-transform duration-700 ease-out" :style="trackStyle">
          <div
            v-for="(img, idx) in imageList"
            :key="`${img}-${idx}`"
            class="relative h-full w-full shrink-0"
          >
            <img
              :src="img"
              :alt="`cover-${idx}`"
              class="h-full w-full object-cover"
            />
            <div
              class="absolute inset-x-0 bottom-0 z-10 flex items-end justify-between gap-4 px-5 pb-5 pt-16"
              :style="slideInfoStyle"
            >
              <div class="max-w-[75%]">
                <div class="text-[10px] font-black uppercase tracking-[0.22em] text-white/70">Hero Visual</div>
                <div class="mt-1 text-sm font-black leading-tight text-white">
                  {{ slideHeadline(idx) }}
                </div>
                <div class="mt-1 text-[11px] leading-relaxed text-white/78">
                  {{ slideCaption(idx) }}
                </div>
              </div>
              <div
                class="hidden rounded-2xl border px-3 py-2 text-right text-[10px] font-medium text-white/80 md:block"
                :style="metaCardStyle"
              >
                <div class="font-black uppercase tracking-[0.18em] text-white">Preview</div>
                <div class="mt-1 text-white/70">适合做首屏强视觉封面</div>
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
        <div class="flex flex-col gap-4">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div class="max-w-2xl">
              <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Hero Media</div>
              <div class="mt-1 text-sm font-bold leading-relaxed" :style="{ color: 'var(--text-color)' }">
                {{ slideHeadline(currentIdx) }}
              </div>
              <div class="mt-1 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
                {{ deckSummary }}
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span class="rounded-full border px-2.5 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }">
                  {{ imageList.length > 1 ? '多视角封面叙事' : '单张强视觉封面' }}
                </span>
                <span class="rounded-full border px-2.5 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)', color: 'var(--primary-vibe)' }">
                  {{ imageList.length > 1 ? '自动切换 + 手动切换' : '首屏重心已锁定' }}
                </span>
              </div>
            </div>
            <div class="rounded-[20px] border px-3 py-3 md:min-w-[240px]" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
              <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Current Frame</div>
              <div class="mt-1 text-sm font-bold" :style="{ color: 'var(--text-color)' }">{{ imageSourceLabel(currentIdx) }}</div>
              <div class="mt-1 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
                {{ slideCaption(currentIdx) }}
              </div>
            </div>
          </div>

          <div
            v-if="imageList.length > 1"
            class="grid gap-2 sm:grid-cols-3"
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
                <div class="text-[9px] font-black uppercase tracking-[0.2em] text-white/70">Frame {{ idx + 1 }}</div>
                <div class="mt-1 text-[11px] font-bold leading-tight text-white">{{ imageSourceLabel(idx) }}</div>
              </div>
            </button>
          </div>
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

const imageList = computed<string[]>(() => {
  const urls = props.data?.image_urls || []
  if (urls.length === 0 && props.data?.image_url) return [props.data.image_url]
  return urls.filter(Boolean)
})

const hasImages = computed(() => imageList.value.length > 0)
const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})

const railStyle = computed(() => ({ background: 'var(--surface-hero, var(--card-bg))' }))
const overlayStyle = computed(() => ({
  background:
    'linear-gradient(180deg, rgba(15,23,42,0.08) 0%, rgba(15,23,42,0.02) 28%, rgba(15,23,42,0.46) 100%)',
}))
const badgeStyle = computed(() => ({
  background: 'rgba(255,255,255,0.78)',
  color: 'var(--text-color)',
  border: '1px solid var(--card-border)',
  backdropFilter: 'blur(8px)',
}))
const counterStyle = computed(() => ({ background: 'rgba(15,23,42,0.45)', color: '#fff' }))
const fallbackStyle = computed(() => ({ background: 'var(--surface-hero, var(--card-bg-soft))' }))
const iconStyle = computed(() => ({ color: 'var(--text-muted)' }))
const textStyle = computed(() => ({ color: 'var(--text-muted)' }))
const slideInfoStyle = computed(() => ({
  background: 'linear-gradient(180deg, rgba(15,23,42,0) 0%, rgba(15,23,42,0.62) 100%)',
}))
const metaCardStyle = computed(() => ({
  background: 'rgba(15,23,42,0.35)',
  borderColor: 'rgba(255,255,255,0.18)',
  backdropFilter: 'blur(12px)',
}))
const navButtonStyle = computed(() => ({
  background: 'rgba(255,255,255,0.9)',
  borderColor: 'rgba(255,255,255,0.55)',
  color: 'var(--text-color)',
  boxShadow: '0 12px 32px rgba(15,23,42,0.18)',
}))
const indicatorShellStyle = computed(() => ({
  background: 'rgba(15,23,42,0.32)',
  border: '1px solid rgba(255,255,255,0.16)',
  backdropFilter: 'blur(14px)',
}))

const trackStyle = computed(() => ({
  width: `${imageList.value.length * 100}%`,
  transform: `translateX(-${currentIdx.value * (100 / Math.max(imageList.value.length, 1))}%)`,
}))

const slideHeadline = (idx: number) => {
  const title = props.data?.title || props.data?.headline
  if (title) return String(title)
  return idx === 0 ? '让首屏更像真正的作品封面' : `封面视角 ${idx + 1}`
}

const slideCaption = (idx: number) => {
  if (Array.isArray(props.data?.captions) && props.data.captions[idx]) return String(props.data.captions[idx])
  if (props.data?.caption) return String(props.data.caption)
  return '更强的视觉重心、可点击切换和自动播放，让封面不再只是静态横向图列。'
}

const imageSourceLabel = (idx: number) => {
  if (Array.isArray(props.data?.source_labels) && props.data.source_labels[idx]) return String(props.data.source_labels[idx])
  if (props.data?.source_label) return String(props.data.source_label)
  return idx === 0 ? '主视觉' : `补充视角 ${idx + 1}`
}

const deckSummary = computed(() => {
  if (imageList.value.length <= 1) return '单张强视觉封面，适合把第一印象打准。'
  return `共 ${imageList.value.length} 张图，适合承接首屏氛围、补充视角和封面说明。`
})

const goTo = (idx: number) => {
  if (!imageList.value.length) return
  currentIdx.value = (idx + imageList.value.length) % imageList.value.length
}

const next = () => goTo(currentIdx.value + 1)
const prev = () => goTo(currentIdx.value - 1)

const indicatorStyle = (idx: number) => ({
  width: currentIdx.value === idx ? '22px' : '8px',
  background: currentIdx.value === idx ? 'rgba(255,255,255,0.96)' : 'rgba(255,255,255,0.4)',
})

const stopAutoplay = () => {
  if (autoplayTimer) {
    clearInterval(autoplayTimer)
    autoplayTimer = null
  }
}

const syncAutoplay = () => {
  stopAutoplay()
  if (imageList.value.length <= 1 || isHovered.value) return
  autoplayTimer = setInterval(() => {
    next()
  }, 4200)
}

watch([imageList, isHovered], () => {
  if (currentIdx.value >= imageList.value.length) currentIdx.value = 0
  syncAutoplay()
})

onMounted(syncAutoplay)
onBeforeUnmount(stopAutoplay)
</script>
