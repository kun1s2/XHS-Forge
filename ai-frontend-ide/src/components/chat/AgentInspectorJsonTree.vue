<script setup lang="ts">
const props = defineProps<{
  data: unknown
  label: string
}>()

const isObject = (val: unknown) => val !== null && typeof val === 'object'
const formatValue = (val: unknown) => typeof val === 'string' ? `"${val}"` : val
</script>

<template>
  <div class="pl-3 border-l border-[#333] my-1">
    <details class="group" open>
      <summary class="cursor-pointer text-[11px] hover:text-blue-400 transition-colors list-none flex items-center gap-1">
        <span class="w-3 h-3 text-[8px] opacity-40 transition-transform group-open:rotate-90">▶</span>
        <span class="font-bold text-gray-500">{{ props.label }}:</span>
        <span v-if="!isObject(props.data)" class="text-blue-300 font-mono">{{ formatValue(props.data) }}</span>
        <span v-else class="text-[9px] opacity-30 italic">{ Object }</span>
      </summary>
      <div v-if="isObject(props.data)" class="pl-2 space-y-0.5 mt-1">
        <AgentInspectorJsonTree
          v-for="(val, key) in props.data as Record<string, unknown>"
          :key="key"
          :data="val"
          :label="key"
        />
      </div>
    </details>
  </div>
</template>
