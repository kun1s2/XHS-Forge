<template>
  <section v-if="profiles.length > 0" class="border-b border-[#2f2f2f] bg-[#202022]">
    <div class="px-4 pt-3 pb-3">
      <div class="flex items-center gap-3">
        <button
          class="inline-flex items-center gap-2 rounded-full border border-[#4b3a34] bg-[linear-gradient(135deg,rgba(255,138,101,0.18),rgba(255,138,101,0.04))] px-3 py-1.5 text-[11px] font-semibold text-[#ffb29b] transition-all hover:border-[#ff8a65]/60 hover:text-white"
          @click="expanded = !expanded"
        >
          <span>🎬</span>
          <span>Showcase</span>
          <span class="rounded-full bg-black/20 px-1.5 py-0.5 text-[9px] font-bold text-[#ffd6c8]">{{ profiles.length }}</span>
          <span class="text-[10px] text-[#ffcab9]">{{ expanded ? '收起' : '展开' }}</span>
        </button>

        <div class="min-w-0 flex-1 overflow-x-auto no-scrollbar">
          <div class="flex items-center gap-2 pr-2">
            <button
              v-for="profile in profiles"
              :key="profile.id"
              class="group inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] transition-all"
              :class="selectedProfileId === profile.id
                ? 'border-[#ff8a65]/70 bg-[#ff8a65]/12 text-[#ffd9cc]'
                : 'border-[#3a3a3a] bg-[#171719] text-gray-300 hover:border-[#ff8a65]/50 hover:text-white'"
              @click="handleQuickPick(profile)"
            >
              <span class="font-medium">{{ profile.title }}</span>
              <span class="rounded-full border border-white/10 bg-black/20 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.12em] text-gray-400 group-hover:text-gray-200">
                {{ profile.scenarioId }}
              </span>
            </button>
          </div>
        </div>

        <button
          v-if="selectedProfile"
          class="shrink-0 rounded-full bg-[#ff2442] px-3 py-1.5 text-[11px] font-semibold text-white transition-all hover:bg-[#e2213d]"
          @click="$emit('start', selectedProfile)"
        >
          启动当前场景
        </button>
      </div>

      <div v-if="selectedProfile" class="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
        <span class="rounded-full border border-[#343434] bg-[#171719] px-2.5 py-1 text-[#ffb29b]">
          推荐人设: {{ selectedProfile.persona }}
        </span>
        <span
          v-for="feature in selectedProfile.highlightFeatures.slice(0, expanded ? 4 : 2)"
          :key="feature"
          class="rounded-full border border-[#343434] bg-[#171719] px-2.5 py-1"
        >
          {{ feature }}
        </span>
      </div>
    </div>

    <div v-if="expanded && selectedProfile" class="border-t border-[#2f2f2f] bg-[radial-gradient(circle_at_top,rgba(255,138,101,0.08),transparent_55%),#1a1a1c] px-4 py-4">
      <div class="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <article class="rounded-2xl border border-[#353535] bg-[linear-gradient(160deg,#2a2a2d_0%,#1c1c1f_100%)] p-4 shadow-[0_16px_40px_rgba(0,0,0,0.22)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-sm font-semibold text-gray-100 leading-snug">{{ selectedProfile.title }}</h2>
              <p class="mt-1 text-[12px] leading-5 text-gray-400">
                {{ selectedProfile.whyThisMatters }}
              </p>
            </div>
            <span class="rounded-full border border-[#444] bg-[#151516] px-2 py-1 text-[10px] text-gray-400">
              {{ selectedProfile.scenarioId }}
            </span>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="feature in selectedProfile.highlightFeatures"
              :key="feature"
              class="rounded-full bg-[#151516] px-2.5 py-1 text-[10px] text-gray-300 border border-[#3a3a3a]"
            >
              {{ feature }}
            </span>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <button
              class="rounded-xl bg-[#ff2442] px-3 py-2 text-[12px] font-semibold text-white transition-all hover:bg-[#e2213d]"
              @click="$emit('start', selectedProfile)"
            >
              一键演示
            </button>
            <button
              class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
              @click="$emit('use-prompt', selectedProfile.editPrompt, selectedProfile.persona)"
            >
              改文案
            </button>
            <button
              class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
              @click="$emit('use-prompt', selectedProfile.themePrompt, selectedProfile.persona)"
            >
              改主题
            </button>
            <button
              class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
              @click="$emit('use-prompt', selectedProfile.branchPrompt, selectedProfile.persona)"
            >
              分叉
            </button>
          </div>
        </article>

        <div class="grid gap-4">
          <div class="rounded-2xl border border-[#383838] bg-[#171719]/80">
            <div class="flex items-center justify-between border-b border-[#343434] px-3 py-2 text-[11px] font-medium text-gray-300">
              <span>演示脚本</span>
              <span class="text-[10px] text-gray-500">按步骤触发</span>
            </div>
            <div class="space-y-2 px-3 py-3">
              <div
                v-for="step in selectedProfile.demoScript"
                :key="`${selectedProfile.id}-${step.label}`"
                class="rounded-xl border border-[#313131] bg-[#141416] px-3 py-2"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="text-[10px] uppercase tracking-[0.18em] text-[#ff8a65]">{{ step.label }}</p>
                    <p class="mt-1 text-[12px] text-gray-200">{{ step.goal }}</p>
                  </div>
                  <button
                    class="shrink-0 rounded-lg border border-[#454545] bg-[#1b1b1d] px-2.5 py-1.5 text-[11px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
                    @click="handleStep(selectedProfile, step)"
                  >
                    {{ step.action === 'start' ? '启动' : '填入' }}
                  </button>
                </div>
                <p class="mt-2 text-[11px] leading-5 text-gray-500">
                  {{ step.prompt }}
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-[#313131] bg-[#141416] px-3 py-3">
            <p class="text-[10px] uppercase tracking-[0.18em] text-[#8ab4ff]">Talking Points</p>
            <ul class="mt-2 space-y-2">
              <li
                v-for="point in selectedProfile.talkingPoints"
                :key="point"
                class="text-[11px] leading-5 text-gray-400"
              >
                {{ point }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ShowcaseDemoStep, ShowcaseProfile } from '../../types/chat'

const props = defineProps<{
  profiles: ShowcaseProfile[]
}>()

const emit = defineEmits<{
  start: [profile: ShowcaseProfile]
  'use-prompt': [prompt: string, persona: string]
}>()

const expanded = ref(false)
const selectedProfileId = ref('')

const selectedProfile = computed(() => {
  const profiles = props.profiles || []
  if (!profiles.length) return null
  return profiles.find((profile) => profile.id === selectedProfileId.value) || profiles[0]
})

const handleQuickPick = (profile: ShowcaseProfile) => {
  selectedProfileId.value = profile.id
}

const handleStep = (profile: ShowcaseProfile, step: ShowcaseDemoStep) => {
  if (step.action === 'start') {
    emit('start', profile)
    return
  }
  emit('use-prompt', step.prompt, profile.persona)
}
</script>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}

.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
