<script setup lang="ts">
import { defineProps, computed } from 'vue';
import { resolveNodeStyles } from '../../utils/StyleDictionary';
import { resolveResponsiveLayout, getCurrentBreakpoint } from '../../utils/LayoutSolver';

// 引入新原子组件
import CollageContainer from './blocks/CollageContainer.vue';
import PolaroidImage from './blocks/PolaroidImage.vue';
import HandwrittenText from './blocks/HandwrittenText.vue';

// 模拟窗口宽度，实际开发中可以接入 ResizeObserver
const windowWidth = window.innerWidth;
const breakpoint = getCurrentBreakpoint(windowWidth);

interface UINode {
  id: string;
  component_type: string;
  props: Record<string, any>;
  children?: UINode[];
  content_brief?: string;
}

const props = defineProps<{
  node: UINode;
  index: number; // 用于计算动效序列延迟
  pageData: Record<string, any>; // 工兵填充的真实数据库
}>();

// 1. 语义样式解析
const computedClasses = computed(() => {
  const baseStyles = resolveNodeStyles(props.node.props);
  const layoutStyles = resolveResponsiveLayout(props.node.props.col_span || 1, breakpoint);
  return `${baseStyles} ${layoutStyles}`.trim();
});

// 2. 动效延迟计算
const transitionDelay = computed(() => {
  const baseDelay = props.index * 100;
  return `${baseDelay}ms`;
});

// 3. 提取工兵填充的真实内容
const nodeData = computed(() => props.pageData[props.node.id] || {});

</script>

<template>
  <div 
    :id="node.id"
    :data-comp-id="node.id"
    :class="['relative transition-all', computedClasses]"
    :style="{ transitionDelay }"
  >
    <!-- 1. 容器型组件渲染 -->
    <template v-if="node.component_type === 'Container'">
      <div class="flex flex-col gap-4 w-full">
        <XForgeRenderer 
          v-for="(child, idx) in node.children" 
          :key="child.id" 
          :node="child" 
          :index="idx"
          :pageData="pageData"
        />
      </div>
    </template>

    <template v-else-if="node.component_type === 'CollageContainer'">
      <CollageContainer :node="node" :pageData="pageData" />
    </template>

    <template v-else-if="node.component_type === 'BentoGrid'">
      <div :class="['grid gap-4 w-full', `grid-cols-${node.props.cols || 2}`]">
        <XForgeRenderer 
          v-for="(child, idx) in node.children" 
          :key="child.id" 
          :node="child" 
          :index="idx"
          :pageData="pageData"
        />
      </div>
    </template>

    <!-- 2. 原子业务组件渲染 -->
    <template v-else-if="node.component_type === 'TitleBlock'">
      <h1 class="text-xl font-bold leading-snug">{{ nodeData.title || '未命名标题' }}</h1>
      <p v-if="nodeData.subtitle" class="text-sm opacity-70 mt-1">{{ nodeData.subtitle }}</p>
    </template>

    <template v-else-if="node.component_type === 'StoryText'">
      <div class="space-y-2">
        <p v-for="(p, pIdx) in nodeData.paragraphs" :key="pIdx" class="text-[15px] leading-relaxed">
          {{ p }}
        </p>
      </div>
    </template>

    <template v-else-if="node.component_type === 'ProductCard'">
      <div class="flex items-center gap-3">
        <img v-if="nodeData.image_url" :src="nodeData.image_url" class="w-16 h-16 rounded-lg object-cover" />
        <div class="flex-1">
          <div class="font-bold text-sm line-clamp-1">{{ nodeData.title }}</div>
          <div class="text-rose-500 font-bold">{{ nodeData.price }}</div>
        </div>
      </div>
    </template>

    <template v-else-if="node.component_type === 'PolaroidImage'">
      <PolaroidImage :node="node" :pageData="pageData" />
    </template>

    <template v-else-if="node.component_type === 'HandwrittenText'">
      <HandwrittenText :node="node" :pageData="pageData" />
    </template>

    <!-- 3. 递归默认分支 -->
    <template v-else>
      <div class="p-2 border border-dashed border-gray-400 opacity-50">
        {{ node.component_type }}
      </div>
    </template>
  </div>
</template>

<style scoped>
.animate-fade-up {
  animation: fadeUp 0.6s ease-out forwards;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
