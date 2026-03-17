<script setup lang="ts">
import { defineProps, computed } from 'vue';

const props = defineProps<{
  node: any;
  pageData: any;
}>();

const nodeData = computed(() => props.pageData[props.node.id] || {});
</script>

<template>
  <div class="p-4 transform -rotate-1">
    <div class="relative inline-block">
      <!-- 底部高亮笔迹模拟 -->
      <div class="absolute -bottom-1 -left-1 w-full h-3 bg-rose-100/40 -z-10 rounded-full"></div>
      <p class="text-stone-700 font-serif italic text-[15px] leading-relaxed tracking-wide">
        {{ nodeData.text || nodeData.content || '碎碎念...' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
/* 模拟手写感字体，若系统未安装特定字体则降级为衬线体 */
.font-serif {
  font-family: 'Caveat', 'Georgia', 'Times New Roman', serif;
}
</style>
