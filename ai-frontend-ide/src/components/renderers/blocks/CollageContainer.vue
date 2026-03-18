<script setup lang="ts">

const props = defineProps<{
  node: any;
  pageData: any;
}>();

// 简单的伪随机旋转算法，基于 ID 字符确保渲染一致性
const getRotation = (id: string) => {
  const charCode = id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const rotations = ['-rotate-1', 'rotate-1', '-rotate-2', 'rotate-2', '-rotate-3', 'rotate-3'];
  return rotations[charCode % rotations.length];
};

const getOffset = (idx: number) => {
  const offsets = ['ml-0', 'ml-4', '-ml-2', 'mt-4', '-mt-2'];
  return offsets[idx % offsets.length];
};
</script>

<template>
  <div class="relative w-full py-8 px-4 flex flex-col items-center">
    <div 
      v-for="(child, idx) in node.children" 
      :key="child.id"
      :class="['w-full max-w-[320px] transition-transform hover:scale-105 hover:z-30 duration-500', getRotation(child.id), getOffset(idx)]"
      :style="{ zIndex: 10 + idx }"
    >
      <!-- ✨ 哨兵修复：调用全局注册的渲染引擎 -->
      <XForgeRenderer 
        :node="child" 
        :index="idx" 
        :pageData="pageData" 
      />
    </div>
  </div>
</template>
