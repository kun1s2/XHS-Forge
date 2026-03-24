<template>
  <div class="mt-3 rounded-[22px] border border-[#2f3d59] bg-[linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(17,24,39,0.96))] p-4">
    <div class="flex flex-wrap items-center gap-2">
      <span class="rounded-full border border-blue-900/40 bg-blue-950/30 px-2 py-0.5 text-[10px] font-black uppercase tracking-[0.18em] text-blue-300">
        Agent 协作
      </span>
      <span
        v-if="action.blocking"
        class="rounded-full border border-amber-800/40 bg-amber-950/20 px-2 py-0.5 text-[10px] font-semibold text-amber-200"
      >
        需要先确认
      </span>
    </div>

    <div class="mt-3 text-[14px] font-bold text-gray-100">{{ action.title }}</div>
    <div v-if="action.summary" class="mt-1 text-[12px] leading-relaxed text-gray-400">{{ action.summary }}</div>
    <div
      v-if="action.proposal_summary || action.recommended_reason"
      class="mt-3 rounded-2xl border border-[#334155] bg-[#0f172a] p-3"
    >
      <div v-if="action.proposal_summary" class="text-[11px] leading-relaxed text-gray-200">{{ action.proposal_summary }}</div>
      <div v-if="action.recommended_reason" class="mt-2 text-[10px] leading-relaxed text-blue-200">
        推荐原因：{{ action.recommended_reason }}
      </div>
    </div>

    <div
      v-if="showTruthForm"
      class="mt-4 rounded-2xl border border-[#334155] bg-[#0f172a] p-3"
    >
      <div class="text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">补充真实信息</div>
      <div v-if="action.input_schema?.helper_text" class="mt-2 text-[11px] leading-relaxed text-gray-400">
        {{ action.input_schema.helper_text }}
      </div>

      <div class="mt-3 grid gap-3">
        <label
          v-for="field in action.input_schema?.fields || []"
          :key="field.id"
          class="grid gap-1.5"
        >
          <span class="text-[11px] font-semibold text-gray-200">{{ field.label }}</span>
          <input
            v-if="field.type === 'text'"
            v-model="truthForm[field.id]"
            :placeholder="field.placeholder || ''"
            class="w-full rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] leading-relaxed text-gray-200 outline-none transition-colors placeholder:text-gray-600 focus:border-blue-500/50"
          />
          <textarea
            v-else-if="!field.type || field.type === 'textarea'"
            v-model="truthForm[field.id]"
            rows="2"
            :placeholder="field.placeholder || ''"
            class="min-h-[72px] w-full resize-y rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] leading-relaxed text-gray-200 outline-none transition-colors placeholder:text-gray-600 focus:border-blue-500/50"
          />
          <div v-else class="grid gap-2">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in field.options || []"
                :key="`${field.id}-${option.value}`"
                type="button"
                class="rounded-full border px-3 py-1.5 text-[11px] transition-all"
                :class="isFieldOptionActive(field.id, field.type, option.value)
                  ? 'border-blue-500/50 bg-blue-950/30 text-blue-100'
                  : 'border-[#334155] bg-[#111827] text-gray-300 hover:border-[#475569]'"
                @click="selectFieldOption(field.id, field.type, option.value)"
              >
                <span>{{ option.label }}</span>
                <span
                  v-if="option.recommended"
                  class="ml-2 rounded-full border border-blue-800/40 bg-blue-950/30 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-blue-200"
                >
                  推荐
                </span>
              </button>
            </div>
            <input
              v-if="field.allow_custom"
              v-model="truthCustomForm[field.id]"
              :placeholder="field.custom_placeholder || '其他补充...'"
              class="w-full rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] leading-relaxed text-gray-200 outline-none transition-colors placeholder:text-gray-600 focus:border-blue-500/50"
            />
          </div>
        </label>
      </div>

      <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div class="text-[10px] text-gray-500">不确定的项可以留空，系统会只按你填的内容继续。</div>
        <button
          @click="submitTruthFacts"
          :disabled="!hasTruthFacts"
          class="rounded-full border border-blue-500/40 bg-blue-950/30 px-3 py-1.5 text-[11px] text-blue-100 transition-all hover:border-blue-400 hover:bg-blue-950/40 disabled:border-[#334155] disabled:bg-[#111827] disabled:text-gray-500"
        >
          {{ action.input_schema?.submit_label || '按这些信息继续' }}
        </button>
      </div>
    </div>

    <div
      v-if="action.other_allowed"
      class="mt-4 rounded-2xl border border-[#334155] bg-[#0f172a] p-3"
    >
      <div class="text-[10px] font-black uppercase tracking-[0.18em] text-gray-500">其他补充</div>
      <textarea
        v-model="customNote"
        rows="2"
        :placeholder="action.other_placeholder || '如果推荐方案还不够贴合，你也可以补一句说明'"
        class="mt-2 min-h-[72px] w-full resize-y rounded-2xl border border-[#334155] bg-[#111827] px-3 py-2 text-[12px] leading-relaxed text-gray-200 outline-none transition-colors placeholder:text-gray-600 focus:border-blue-500/50"
      />
    </div>

    <div class="mt-4 grid gap-2">
      <button
        v-for="option in action.options"
        :key="option.value"
        @click="$emit('select', option, customNotePayload)"
        class="rounded-2xl border px-3 py-3 text-left transition-all"
        :class="option.recommended || action.recommended_option === option.value
          ? 'border-blue-500/50 bg-blue-950/20 hover:border-blue-400 hover:bg-blue-950/30'
          : 'border-[#334155] bg-[#0f172a] hover:border-[#4b5563] hover:bg-[#131c2f]'"
      >
        <div class="flex items-start gap-3">
          <div
            v-if="option.asset_url"
            class="h-14 w-14 shrink-0 overflow-hidden rounded-2xl border border-[#334155] bg-[#0b1220]"
          >
            <img :src="option.asset_url" alt="" class="h-full w-full object-cover" loading="lazy" />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <div class="text-[12px] font-semibold text-gray-100">{{ option.label }}</div>
              <span
                v-if="option.recommended || action.recommended_option === option.value"
                class="rounded-full border border-blue-800/40 bg-blue-950/30 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em] text-blue-200"
              >
                推荐
              </span>
            </div>
            <div v-if="option.description" class="mt-1 text-[11px] leading-relaxed text-gray-400">{{ option.description }}</div>
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ConversationCheckpointAction, ConversationCheckpointInputField, ConversationCheckpointOption } from '../../types/chat'

const props = defineProps<{
  action: ConversationCheckpointAction
}>()

const emit = defineEmits<{
  (event: 'select', option: ConversationCheckpointOption, overrides?: { userProvidedFacts?: Record<string, string | string[]>; customNote?: string }): void
}>()

const truthForm = reactive<Record<string, string>>({})
const truthChoiceForm = reactive<Record<string, string>>({})
const truthMultiChoiceForm = reactive<Record<string, string[]>>({})
const truthCustomForm = reactive<Record<string, string>>({})
const customNote = ref('')

watch(
  () => props.action,
  (nextAction) => {
    for (const key of Object.keys(truthForm)) delete truthForm[key]
    for (const key of Object.keys(truthChoiceForm)) delete truthChoiceForm[key]
    for (const key of Object.keys(truthMultiChoiceForm)) delete truthMultiChoiceForm[key]
    for (const key of Object.keys(truthCustomForm)) delete truthCustomForm[key]
    customNote.value = ''
    for (const field of nextAction.input_schema?.fields || []) {
      if (field.type === 'single_select') {
        const recommended = (field.options || []).find((option) => option.recommended)
        truthChoiceForm[field.id] = recommended?.value || ''
      } else if (field.type === 'multi_select') {
        truthMultiChoiceForm[field.id] = []
      } else {
        truthForm[field.id] = ''
      }
      if (field.allow_custom) truthCustomForm[field.id] = ''
    }
  },
  { immediate: true, deep: true },
)

const showTruthForm = computed(() =>
  props.action.action_type === 'truth_mode_checkpoint' && (props.action.input_schema?.fields?.length || 0) > 0,
)

const customNotePayload = computed(() => {
  const note = String(customNote.value || '').trim()
  return note ? { customNote: note } : undefined
})

const hasTruthFacts = computed(() =>
  Object.values(truthForm).some((value) => String(value || '').trim().length > 0)
  || Object.values(truthChoiceForm).some((value) => String(value || '').trim().length > 0)
  || Object.values(truthMultiChoiceForm).some((value) => Array.isArray(value) && value.length > 0)
  || Object.values(truthCustomForm).some((value) => String(value || '').trim().length > 0),
)

const isFieldOptionActive = (fieldId: string, type: ConversationCheckpointInputField['type'], value: string) => {
  if (type === 'multi_select') {
    return (truthMultiChoiceForm[fieldId] || []).includes(value)
  }
  return truthChoiceForm[fieldId] === value
}

const selectFieldOption = (fieldId: string, type: ConversationCheckpointInputField['type'], value: string) => {
  if (type === 'multi_select') {
    const current = truthMultiChoiceForm[fieldId] || []
    truthMultiChoiceForm[fieldId] = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value]
    return
  }
  truthChoiceForm[fieldId] = value
}

const submitTruthFacts = () => {
  const targetOption = props.action.options.find((option) => option.value === 'provide_user_facts')
  if (!targetOption || !hasTruthFacts.value) return
  const normalizedFacts: Record<string, string | string[]> = {}
  for (const [key, value] of Object.entries(truthForm)) {
    const normalized = String(value || '').trim()
    if (normalized) normalizedFacts[key] = normalized
  }
  for (const [key, value] of Object.entries(truthChoiceForm)) {
    const normalized = String(value || '').trim()
    if (normalized) normalizedFacts[key] = normalized
  }
  for (const [key, value] of Object.entries(truthMultiChoiceForm)) {
    const normalized = (value || []).map((item) => String(item || '').trim()).filter(Boolean)
    if (normalized.length) normalizedFacts[key] = normalized
  }
  for (const [key, value] of Object.entries(truthCustomForm)) {
    const normalized = String(value || '').trim()
    if (normalized) normalizedFacts[`${key}_custom`] = normalized
  }
  emit('select', targetOption, {
    userProvidedFacts: normalizedFacts,
    customNote: String(customNote.value || '').trim() || undefined,
  })
}
</script>
