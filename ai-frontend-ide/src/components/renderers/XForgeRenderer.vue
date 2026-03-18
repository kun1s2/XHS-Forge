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
import RadarChartBlock from './blocks/RadarChartBlock.vue';
import PollBlock from './blocks/PollBlock.vue';
import WeatherPolaroid from './blocks/WeatherPolaroid.vue';

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
  GiftBox,
  RadarChartBlock,
  PollBlock,
  WeatherPolaroid
};

const windowWidth = window.innerWidth;
const breakpoint = getCurrentBreakpoint(windowWidth);

interface UIBlock {
  id: string;
  component_type: string;
  props?: Record<string, any>;
}

const props = defineProps<{
  node: UIBlock;
  index: number;
  pageData: Record<string, any>;
}>();

// 语义样式解析
const computedClasses = computed(() => {
  const nodeProps = props.node.props || {};
  const baseStyles = resolveNodeStyles(nodeProps);
  const layoutStyles = resolveResponsiveLayout(nodeProps.col_span || 1, breakpoint);
  return `${baseStyles} ${layoutStyles}`.trim();
});

const transitionDelay = computed(() => `${props.index * 50}ms`); // 加快进场速度
const nodeData = computed(() => props.pageData[props.node.id] || {});

// 动态组件解析逻辑
const resolveComp = (type: string) => componentMap[type] || null;
</script>

<template>
  <div 
    :id="node.id"
    :data-comp-id="node.id"
    :class="['w-full transition-all duration-700 animate-fade-up', computedClasses]"
    :style="{ transitionDelay }"
  >
    <!-- 1. 动态业务组件分发（扁平区块流模式） -->
    <template v-if="resolveComp(node.component_type)">
      <component 
        :is="resolveComp(node.component_type)"
        :comp-id="node.id"
        :node="node"
        :data="nodeData"
        :pageData="pageData"
        :style="{ css_classes: computedClasses }"
      />
    </template>

    <!-- 2. 🚨 哨兵防弹衣：未知组件优雅降级 (Error Boundary) -->
    <template v-else>
      <div class="m-2 p-4 border-2 border-dashed border-amber-400 bg-amber-50 rounded-2xl flex flex-col gap-2">
        <div class="flex items-center gap-2 text-amber-700 font-bold text-xs uppercase tracking-tighter">
          <span>⚠️</span>
          <span>Block Not Registered</span>
        </div>
        <div class="text-[10px] text-amber-600/80 font-mono break-all bg-white/50 p-2 rounded-lg">
          [幻觉拦截] 尝试渲染未定义的区块: <{{ node.component_type }}>
        </div>
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
