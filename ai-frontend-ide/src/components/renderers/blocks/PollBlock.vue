<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  node: any
  data: {
    question?: string
    options?: string[]
    option_a?: string
    option_b?: string
    option_c?: string
    vote_counts?: number[]
    total_votes?: number
    explanation?: string
  }
  style?: any
}>()

const question = computed(() => props.data.question || '你更站哪一边？')
const options = computed(() => {
  if (Array.isArray(props.data.options) && props.data.options.length) return props.data.options
  return [props.data.option_a, props.data.option_b, props.data.option_c].filter(Boolean)
})

const selectedOption = ref<number | null>(null)

const seededVotes = computed(() => {
  if (Array.isArray(props.data.vote_counts) && props.data.vote_counts.length === options.value.length) {
    return props.data.vote_counts.map((value) => Math.max(1, Number(value) || 1))
  }
  return options.value.map((option, idx) => {
    const seed = Array.from(String(option)).reduce((sum, char) => sum + char.charCodeAt(0), 0) + idx * 17
    return 34 + (seed % 29)
  })
})

watch(options, () => {
  selectedOption.value = null
})

const displayedVotes = computed(() => seededVotes.value.map((count, idx) => (selectedOption.value === idx ? count + 4 : count)))
const totalVotes = computed(() => displayedVotes.value.reduce((sum, count) => sum + count, 0))
const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const cardStyle = computed(() => ({
  background: 'linear-gradient(145deg, var(--card-bg, rgba(255,255,255,0.95)) 0%, var(--card-bg-soft, rgba(255,255,255,0.78)) 100%)',
  borderColor: 'var(--card-border)',
  boxShadow: 'var(--card-shadow)',
}))

const handleVote = (idx: number) => {
  selectedOption.value = idx
}

const getPercentage = (idx: number) => {
  if (!totalVotes.value) return 0
  return Math.round((displayedVotes.value[idx] / totalVotes.value) * 100)
}

const leadingOption = computed(() => {
  if (!displayedVotes.value.length) return null
  const max = Math.max(...displayedVotes.value)
  const idx = displayedVotes.value.findIndex(value => value === max)
  if (idx === -1) return null
  return { label: options.value[idx], percent: getPercentage(idx), idx }
})

const selectedSummary = computed(() => {
  if (selectedOption.value === null) {
    return '先表达你的倾向，系统再展示这张互动卡的演示态分布。'
  }
  const label = options.value[selectedOption.value] || '当前选项'
  const percent = getPercentage(selectedOption.value)
  const leader = leadingOption.value
  if (leader && leader.idx === selectedOption.value) {
    return `你当前站在「${label}」这边，在演示态分布里也是当前最强倾向（${percent}%）。`
  }
  return `你当前选择了「${label}」，演示态分布占比约 ${percent}%。`
})

const signalTone = computed(() => {
  if (selectedOption.value === null) return '还没站队'
  return leadingOption.value?.idx === selectedOption.value ? '你命中了当前更强的倾向' : '你选择了更少数但也成立的一边'
})
</script>

<template>
  <div
    :class="['w-full rounded-[32px] border p-6 animate-in fade-in zoom-in duration-500', cssClasses]"
    :style="{ ...cardStyle, ...inlineStyles }"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="flex items-start gap-3">
        <div
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-white"
          :style="{ background: 'linear-gradient(135deg, var(--primary-vibe), color-mix(in srgb, var(--primary-vibe) 65%, white 35%))', boxShadow: '0 16px 34px var(--primary-vibe-light)' }"
        >
          ⚖
        </div>
        <div>
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">Opinion Poll</div>
          <h3 class="mt-2 text-base font-black leading-tight" :style="{ color: 'var(--text-color)' }">{{ question }}</h3>
          <p class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            {{ props.data.explanation || '它不是平台真票数，而是一张帮助用户快速站队、表达倾向的互动语义块。' }}
          </p>
        </div>
      </div>
      <div
        class="rounded-full border px-3 py-1 text-[10px] font-bold"
        :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
      >
        {{ selectedOption === null ? '点击站队' : '已记录你的倾向' }}
      </div>
    </div>

    <div class="mt-5 space-y-3">
      <button
        v-for="(opt, idx) in options"
        :key="idx"
        type="button"
        class="group relative block w-full overflow-hidden rounded-[22px] border text-left transition-all duration-300 hover:-translate-y-0.5"
        :style="{ borderColor: selectedOption === idx ? 'var(--primary-vibe)' : 'var(--card-border)', background: 'var(--card-bg-soft)' }"
        @click="handleVote(idx)"
      >
        <div
          class="absolute inset-y-0 left-0 rounded-[22px] transition-all duration-500"
          :style="{ width: selectedOption === null ? '0%' : `${getPercentage(idx)}%`, background: 'color-mix(in srgb, var(--primary-vibe) 16%, white 84%)' }"
        ></div>
        <div class="relative flex items-center justify-between gap-3 px-4 py-4">
          <div class="flex items-center gap-3">
            <div
              class="flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-black"
              :style="{
                borderColor: selectedOption === idx ? 'var(--primary-vibe)' : 'var(--card-border)',
                background: selectedOption === idx ? 'var(--primary-vibe)' : 'transparent',
                color: selectedOption === idx ? '#fff' : 'var(--text-muted)',
              }"
            >
              {{ String.fromCharCode(65 + idx) }}
            </div>
            <span class="text-sm font-bold leading-tight" :style="{ color: 'var(--text-color)' }">{{ opt }}</span>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="selectedOption !== null" class="text-[11px] font-black" :style="{ color: 'var(--primary-vibe)' }">{{ getPercentage(idx) }}%</span>
            <span
              v-if="selectedOption === idx"
              class="rounded-full px-2 py-1 text-[10px] font-black"
              :style="{ background: 'color-mix(in srgb, var(--primary-vibe) 14%, white 86%)', color: 'var(--primary-vibe)' }"
            >
              你的选择
            </span>
          </div>
        </div>
      </button>
    </div>

    <div class="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
      <div class="rounded-[22px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Interaction Signal</div>
        <div class="mt-1 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
          {{ selectedSummary }}
        </div>
        <div class="mt-2 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
          {{ selectedOption === null ? '在不同场景里，它可以承接站队、选择、偏好表达，而不是伪装成真实投票产品。' : signalTone }}
        </div>
      </div>
      <div class="rounded-[22px] border px-4 py-4" :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)' }">
        <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">Current Split</div>
        <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
          {{ selectedOption === null ? '等待你的选择' : `${totalVotes} 份演示态样本` }}
        </div>
        <div class="mt-3 space-y-2">
          <div v-for="(opt, idx) in options" :key="`mini-${idx}`">
            <div class="flex items-center justify-between gap-3 text-[11px] font-semibold" :style="{ color: 'var(--text-muted)' }">
              <span class="truncate">{{ opt }}</span>
              <span>{{ selectedOption === null ? '--' : `${getPercentage(idx)}%` }}</span>
            </div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200/60">
              <div
                class="h-full rounded-full transition-all duration-500"
                :style="{ width: selectedOption === null ? '0%' : `${getPercentage(idx)}%`, background: idx === selectedOption ? 'var(--primary-vibe)' : 'color-mix(in srgb, var(--primary-vibe) 38%, white 62%)' }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
