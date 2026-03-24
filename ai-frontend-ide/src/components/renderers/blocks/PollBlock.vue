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
    option_cards?: Array<{ label?: string; stance?: string; vote_hint?: string; why_it_matters?: string }>
    explanation?: string
    vote_counts?: number[]
  }
  style?: any
  recentChange?: { fields?: string[] } | null
}>()
const recentFields = computed(() => new Set((props.recentChange?.fields || []).map((item) => String(item))))
const highlightBoxStyle = (active: boolean) => active
  ? {
      borderColor: 'rgba(251,191,36,0.58)',
      background: 'linear-gradient(180deg, rgba(255,251,235,0.98) 0%, rgba(255,255,255,0.92) 100%)',
      boxShadow: '0 0 0 1px rgba(251,191,36,0.18), 0 16px 32px rgba(251,191,36,0.12)',
    }
  : {}

const question = computed(() => props.data.question || '你更站哪一边？')
const optionCards = computed(() => {
  if (Array.isArray(props.data.option_cards) && props.data.option_cards.length) {
    return props.data.option_cards.map((item, idx) => ({
      label: String(item?.label || item?.option || `选项 ${idx + 1}`),
      stance: String(item?.stance || `立场 ${idx + 1}`),
      voteHint: String(item?.vote_hint || ''),
      whyItMatters: String(item?.why_it_matters || ''),
    }))
  }
  const rawOptions = [props.data.option_a, props.data.option_b, props.data.option_c].filter(Boolean)
  return rawOptions.map((option, idx) => ({
    label: String(option),
    stance: idx === 0 ? '主推理由' : idx === 1 ? '现实代价' : `立场 ${idx + 1}`,
    voteHint: idx === 0 ? '更适合承接第一购买理由。' : idx === 1 ? '更适合承接现实妥协点。' : '适合承接轻量互动表达。',
    whyItMatters: idx === 0 ? '让用户快速表达“我就是被这个点打动”。' : idx === 1 ? '把真正会犹豫的点显性化。' : '补一个额外偏好维度。',
  }))
})

const options = computed(() => {
  if (Array.isArray(props.data.options) && props.data.options.length) return props.data.options
  return optionCards.value.map((item) => item.label)
})

const selectedOption = ref<number | null>(null)
const voteCounts = ref<number[]>([])

watch(options, () => {
  selectedOption.value = null
  if (Array.isArray(props.data.vote_counts) && props.data.vote_counts.length === options.value.length) {
    voteCounts.value = props.data.vote_counts.map((item) => Number(item || 0))
    return
  }
  const seedBase = `${question.value}|${options.value.join('|')}`.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  voteCounts.value = options.value.map((_, idx) => 32 + ((seedBase + idx * 17) % 41))
}, { immediate: true })

const cssClasses = computed(() => props.style?.css_classes || '')
const inlineStyles = computed(() => props.style?.inline_styles || {})
const cardStyle = computed(() => ({
  background: 'linear-gradient(145deg, var(--card-bg, rgba(255,255,255,0.95)) 0%, var(--card-bg-soft, rgba(255,255,255,0.78)) 100%)',
  borderColor: 'var(--card-border)',
  boxShadow: 'var(--card-shadow)',
}))

const handleVote = (idx: number) => {
  const previous = selectedOption.value
  if (previous !== null && voteCounts.value[previous] > 0) {
    voteCounts.value[previous] -= 1
  }
  selectedOption.value = idx
  voteCounts.value[idx] = (voteCounts.value[idx] || 0) + 1
}

const selectedCard = computed(() => {
  if (selectedOption.value === null) return null
  return optionCards.value[selectedOption.value] || null
})

const totalVotes = computed(() => voteCounts.value.reduce((sum, item) => sum + Number(item || 0), 0))

const optionMetrics = computed(() => {
  const total = totalVotes.value || 1
  return options.value.map((label, idx) => {
    const count = Number(voteCounts.value[idx] || 0)
    const percent = Math.round((count / total) * 100)
    return {
      label,
      count,
      percent,
    }
  })
})

const leadingOption = computed(() => {
  if (!optionMetrics.value.length) return null
  return optionMetrics.value.reduce((best, current) => (current.count > best.count ? current : best), optionMetrics.value[0])
})

const participationSummary = computed(() => {
  if (selectedOption.value === null || !selectedCard.value) {
    return '点一下表达你的倾向，系统会立刻给出当前投票分布。'
  }
  const currentMetric = optionMetrics.value[selectedOption.value]
  return `你刚刚把「${selectedCard.value.label}」的占比推到了 ${currentMetric?.percent || 0}% ，当前总参与 ${totalVotes.value} 人。`
})
</script>

<template>
  <div
    :class="['relative w-full overflow-hidden rounded-[32px] border p-6 animate-in fade-in zoom-in duration-500', cssClasses]"
    :style="{ ...cardStyle, ...inlineStyles }"
  >
    <div class="pointer-events-none absolute inset-0 opacity-80" :style="{ background: 'radial-gradient(circle at top left, color-mix(in srgb, var(--primary-vibe) 16%, white 84%) 0%, transparent 30%), radial-gradient(circle at bottom right, rgba(15,23,42,0.05) 0%, transparent 38%)' }"></div>

    <div class="flex items-start justify-between gap-4 rounded-[24px] p-2" :style="highlightBoxStyle(recentFields.has('question'))">
      <div class="flex items-start gap-3">
        <div
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-white"
          :style="{ background: 'linear-gradient(135deg, var(--primary-vibe), color-mix(in srgb, var(--primary-vibe) 65%, white 35%))', boxShadow: '0 16px 34px var(--primary-vibe-light)' }"
        >
          ⚖
        </div>
        <div>
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--primary-vibe)' }">互动提问</div>
          <h3 class="mt-2 text-base font-black leading-tight" :style="{ color: 'var(--text-color)' }">{{ question }}</h3>
          <p class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
            {{ props.data.explanation || '把分歧点说透之后，再给读者一个清晰的站队入口。' }}
          </p>
        </div>
      </div>
      <div
        class="rounded-full border px-3 py-1 text-[10px] font-bold"
        :style="{ borderColor: 'var(--card-border)', background: 'var(--card-bg-soft)', color: 'var(--text-muted)' }"
      >
        {{ selectedOption === null ? '点击表达倾向' : '已记录你的选择' }}
      </div>
    </div>

    <div class="mt-5 space-y-3 rounded-[24px] p-2" :style="highlightBoxStyle(recentFields.has('options'))">
      <button
        v-for="(opt, idx) in options"
        :key="idx"
        type="button"
        class="group relative block w-full overflow-hidden rounded-[22px] border text-left transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_16px_30px_rgba(15,23,42,0.08)]"
        :style="{ borderColor: selectedOption === idx ? 'var(--primary-vibe)' : 'var(--card-border)', background: selectedOption === idx ? 'color-mix(in srgb, var(--primary-vibe) 7%, white 93%)' : 'var(--card-bg-soft)' }"
        @click="handleVote(idx)"
      >
        <div class="relative flex items-start justify-between gap-3 px-4 py-4">
          <div class="flex items-start gap-3">
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
            <div class="min-w-0">
              <div class="text-[10px] font-black uppercase tracking-[0.18em]" :style="{ color: 'var(--text-muted)' }">{{ optionCards[idx]?.stance || `立场 ${idx + 1}` }}</div>
              <div class="mt-1 text-sm font-bold leading-tight" :style="{ color: 'var(--text-color)' }">{{ opt }}</div>
              <div class="mt-1 text-[11px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
                {{ optionCards[idx]?.whyItMatters || optionCards[idx]?.voteHint || '适合承接这一边为什么成立。' }}
              </div>
              <div class="mt-3">
                <div class="flex items-center justify-between text-[10px]" :style="{ color: 'var(--text-muted)' }">
                  <span>{{ optionMetrics[idx]?.percent || 0 }}%</span>
                  <span>{{ optionMetrics[idx]?.count || 0 }} 票</span>
                </div>
                <div class="mt-1 h-2 overflow-hidden rounded-full" :style="{ background: 'rgba(15,23,42,0.08)' }">
                  <div
                    class="h-full rounded-full transition-all duration-300"
                    :style="{
                      width: `${optionMetrics[idx]?.percent || 0}%`,
                      background: selectedOption === idx
                        ? 'linear-gradient(90deg, var(--primary-vibe), color-mix(in srgb, var(--primary-vibe) 72%, white 28%))'
                        : 'linear-gradient(90deg, color-mix(in srgb, var(--primary-vibe) 40%, white 60%), color-mix(in srgb, var(--primary-vibe) 16%, white 84%))',
                    }"
                  ></div>
                </div>
              </div>
            </div>
          </div>
          <span
            v-if="selectedOption === idx"
            class="rounded-full px-2 py-1 text-[10px] font-black"
            :style="{ background: 'color-mix(in srgb, var(--primary-vibe) 14%, white 86%)', color: 'var(--primary-vibe)' }"
          >
            已选
          </span>
        </div>
      </button>
    </div>

    <div
      class="mt-5 rounded-[24px] border px-4 py-4"
      :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">投票结果</div>
          <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">
            {{ leadingOption ? `当前多数倾向：${leadingOption.label}` : '等待第一票' }}
          </div>
        </div>
        <div class="rounded-full border px-3 py-1 text-[10px] font-bold" :style="{ borderColor: 'var(--card-border)', color: 'var(--text-muted)', background: 'var(--card-bg-soft)' }">
          总投票 {{ totalVotes }}
        </div>
      </div>
      <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
        {{ participationSummary }}
      </div>
    </div>

    <div
      v-if="selectedCard"
      class="mt-5 rounded-[24px] border px-4 py-4"
      :style="{ borderColor: 'var(--card-border)', background: 'rgba(15,23,42,0.02)' }"
    >
      <div class="text-[10px] font-black uppercase tracking-[0.22em]" :style="{ color: 'var(--text-muted)' }">你的参与反馈</div>
      <div class="mt-2 text-sm font-bold" :style="{ color: 'var(--text-color)' }">{{ selectedCard.label }}</div>
      <div class="mt-2 text-[12px] leading-relaxed" :style="{ color: 'var(--text-muted)' }">
        {{ selectedCard.voteHint || selectedCard.whyItMatters || '你已经给出了这轮内容里更偏向哪一边的判断。' }}
      </div>
    </div>
  </div>
</template>
