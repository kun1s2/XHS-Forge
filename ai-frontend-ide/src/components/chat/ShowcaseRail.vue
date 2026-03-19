<template>
  <section v-if="profiles.length > 0" class="px-4 pt-4 pb-2 border-b border-[#2f2f2f] bg-[#202022]">
    <div class="flex items-center gap-2 mb-3">
      <span class="text-[10px] font-bold uppercase tracking-[0.24em] text-[#ff8a65]">Showcase</span>
      <div class="h-px flex-1 bg-gradient-to-r from-[#ff8a65]/40 to-transparent"></div>
      <span class="text-[10px] text-gray-500">3 条演示业务线</span>
    </div>

    <div class="flex gap-3 overflow-x-auto pb-2 no-scrollbar">
      <article
        v-for="profile in profiles"
        :key="profile.id"
        class="min-w-[272px] max-w-[272px] rounded-2xl border border-[#353535] bg-[linear-gradient(160deg,#2a2a2d_0%,#1c1c1f_100%)] p-4 shadow-[0_12px_32px_rgba(0,0,0,0.18)]"
      >
        <div class="flex items-start justify-between gap-3 mb-2">
          <div>
            <h2 class="text-sm font-semibold text-gray-100 leading-snug">{{ profile.title }}</h2>
            <p class="mt-1 text-[11px] text-gray-500">推荐人设: {{ profile.persona }}</p>
          </div>
          <span class="rounded-full border border-[#444] bg-[#151516] px-2 py-1 text-[10px] text-gray-400">
            {{ profile.scenarioId }}
          </span>
        </div>

        <p class="text-[12px] leading-5 text-gray-400 min-h-[60px]">
          {{ profile.whyThisMatters }}
        </p>

        <div class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="feature in profile.highlightFeatures.slice(0, 3)"
            :key="feature"
            class="rounded-full bg-[#151516] px-2.5 py-1 text-[10px] text-gray-300 border border-[#3a3a3a]"
          >
            {{ feature }}
          </span>
        </div>

        <div class="mt-4 flex items-center gap-2">
          <button
            class="flex-1 rounded-xl bg-[#ff2442] px-3 py-2 text-[12px] font-semibold text-white transition-all hover:bg-[#e2213d]"
            @click="$emit('start', profile)"
          >
            一键演示
          </button>
          <button
            class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
            @click="$emit('use-prompt', profile.editPrompt, profile.persona)"
          >
            改文案
          </button>
          <button
            class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
            @click="$emit('use-prompt', profile.themePrompt, profile.persona)"
          >
            改主题
          </button>
          <button
            class="rounded-xl border border-[#454545] bg-[#171719] px-3 py-2 text-[12px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
            @click="$emit('use-prompt', profile.branchPrompt, profile.persona)"
          >
            分叉
          </button>
        </div>

        <details class="mt-3 rounded-xl border border-[#383838] bg-[#171719]/70">
          <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-[11px] font-medium text-gray-300">
            <span>面试手卡</span>
            <span class="text-[10px] text-gray-500">Demo Script + Talking Points</span>
          </summary>

          <div class="border-t border-[#343434] px-3 py-3">
            <div class="space-y-2">
              <div
                v-for="step in profile.demoScript"
                :key="`${profile.id}-${step.label}`"
                class="rounded-xl border border-[#313131] bg-[#141416] px-3 py-2"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="text-[10px] uppercase tracking-[0.18em] text-[#ff8a65]">{{ step.label }}</p>
                    <p class="mt-1 text-[12px] text-gray-200">{{ step.goal }}</p>
                  </div>
                  <button
                    class="shrink-0 rounded-lg border border-[#454545] bg-[#1b1b1d] px-2.5 py-1.5 text-[11px] text-gray-300 transition-all hover:border-blue-500 hover:text-blue-400"
                    @click="handleStep(profile, step)"
                  >
                    {{ step.action === 'start' ? '启动' : '填入' }}
                  </button>
                </div>
                <p class="mt-2 text-[11px] leading-5 text-gray-500">
                  {{ step.prompt }}
                </p>
              </div>
            </div>

            <div class="mt-3 rounded-xl border border-[#313131] bg-[#141416] px-3 py-3">
              <p class="text-[10px] uppercase tracking-[0.18em] text-[#8ab4ff]">Talking Points</p>
              <ul class="mt-2 space-y-2">
                <li
                  v-for="point in profile.talkingPoints"
                  :key="point"
                  class="text-[11px] leading-5 text-gray-400"
                >
                  {{ point }}
                </li>
              </ul>
            </div>
          </div>
        </details>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ShowcaseDemoStep, ShowcaseProfile } from '../../types/chat'

defineProps<{
  profiles: ShowcaseProfile[]
}>()

const emit = defineEmits<{
  start: [profile: ShowcaseProfile]
  'use-prompt': [prompt: string, persona: string]
}>()

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
