<template>
  <div class="px-4 py-2 w-full">
    <div class="bg-red-500 text-white p-4 rounded-xl flex items-end gap-2 shadow-lg">
      <span class="text-sm">到手价 ¥</span>
      <span class="text-3xl font-black leading-none">{{ price || '99.00' }}</span>
      <span class="text-xs line-through text-red-200 ml-2">¥199.00</span>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ price?: string; }>();
</script>
