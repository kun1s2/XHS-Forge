<script setup lang="ts">
import { defineProps, computed } from 'vue';
import { resolveNodeStyles } from '../../utils/StyleDictionary';
import { resolveResponsiveLayout, getCurrentBreakpoint } from '../../utils/LayoutSolver';

// 1. 导入所有原子组件（大动脉接通）
import CollageContainer from './blocks/CollageContainer.vue';
import PolaroidImage from './blocks/PolaroidImage.vue';
import HandwrittenText from './blocks/HandwrittenText.vue';
import CoverSwiper from './blocks/CoverSwiper.vue';
import TitleBlock from './blocks/TitleBlock.vue';
import StoryText from './blocks/StoryText.vue';
import ProductCard from './blocks/ProductCard.vue';
import TagList from './blocks/TagList.vue';
import InteractionsBar from './blocks/InteractionsBar.vue';
import ProductSpecCard from './blocks/ProductSpecCard.vue';
import LocationBlock from './blocks/LocationBlock.vue';
import VersusCard from './blocks/VersusCard.vue';
import FlipCard from './blocks/FlipCard.vue';
import GiftBox from './blocks/GiftBox.vue';

// 2. 建立组件注册表
const componentMap: Record<string, any> = {
  CollageContainer, 
  PolaroidImage, 
  HandwrittenText,
  CoverSwiper, 
  TitleBlock, 
  StoryText, 
  ProductCard, 
  TagList, 
  InteractionsBar,
  ProductSpecCard,
  LocationBlock,
  VersusCard,
  FlipCard,
  GiftBox
};

const windowWidth = window.innerWidth;
const breakpoint = getCurrentBreakpoint(windowWidth);

interface UINode {
  id: string;
  component_type: string;
  props: Record<string, any>;
  children?: UINode[];
}

const props = defineProps<{
  node: UINode;
  index: number;
  pageData: Record<string, any>;
}>();

// 语义样式解析
const computedClasses = computed(() => {
  const baseStyles = resolveNodeStyles(props.node.props);
  const layoutStyles = resolveResponsiveLayout(props.node.props.col_span || 1, breakpoint);
  return `${baseStyles} ${layoutStyles}`.trim();
});

const transitionDelay = computed(() => `${props.index * 100}ms`);
const nodeData = computed(() => props.pageData[props.node.id] || {});

// 动态组件解析逻辑
const resolveComp = (type: string) => componentMap[type] || null;
</script>

<template>
  <div 
    :id="node.id"
    :data-comp-id="node.id"
    :class="['relative transition-all', computedClasses]"
    :style="{ transitionDelay }"
  >
    <!-- 1. 布局容器递归分支 -->
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

    <!-- 2. 动态业务组件分发（核心大动脉） -->
    <template v-else-if="resolveComp(node.component_type)">
      <component 
        :is="resolveComp(node.component_type)"
        :comp-id="node.id"
        :node="node"
        :data="nodeData"
        :pageData="pageData"
        :style="{ css_classes: computedClasses }"
      >
        <!-- ✨ 4.0 增强：支持业务组件内部嵌套子节点 (如 GiftBox 容器) -->
        <XForgeRenderer 
          v-for="(child, idx) in node.children" 
          :key="child.id" 
          :node="child" 
          :index="idx" 
          :pageData="pageData" 
        />
      </component>
    </template>

    <!-- 3. 报错兜底（不再有 opacity-50 滤镜干扰） -->
    <template v-else>
      <div class="p-4 border-2 border-dashed border-red-400 bg-red-50 text-red-600 rounded-lg text-sm font-bold">
        🚨 组件未注册: {{ node.component_type }}
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 确保动画类名在全局生效 */
.animate-fade-up {
  animation: fadeUp 0.6s ease-out forwards;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
