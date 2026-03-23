<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { resolveNodeStyles } from '../../utils/StyleDictionary';
import { resolveResponsiveLayout, getCurrentBreakpoint } from '../../utils/LayoutSolver';
import { useChatStore } from '../../stores/useChatStore';
import componentManifestJson from '../../config/componentManifest.json';

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
import ProgressBarSpec from './blocks/ProgressBarSpec.vue';
import QuoteBlock from './blocks/QuoteBlock.vue';
import TimelineBlock from './blocks/TimelineBlock.vue';

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
  WeatherPolaroid,
  ProgressBarSpec,
  QuoteBlock,
  TimelineBlock
};

const componentManifest = (componentManifestJson as { components?: Array<Record<string, any>> }).components || [];
const supportedTypes = new Set(componentManifest.map((item) => String(item.type || "")));

const props = defineProps<{
  node: { id: string; component_type: string; props?: Record<string, any>; style?: Record<string, any> };
  index: number;
  interactive?: boolean;
  selectionEnabled?: boolean;
}>();

const chatStore = useChatStore();
const { selectedComponentId, selectedParagraphIndex } = storeToRefs(chatStore);

const wrapperRef = ref<HTMLElement | null>(null);
const containerWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1280);
let resizeObserver: ResizeObserver | null = null;

const syncContainerWidth = () => {
  const measuredWidth = wrapperRef.value?.getBoundingClientRect().width || window.innerWidth || 1280;
  containerWidth.value = Math.max(320, Math.round(measuredWidth));
};

onMounted(() => {
  syncContainerWidth();
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => syncContainerWidth());
    if (wrapperRef.value) resizeObserver.observe(wrapperRef.value);
  }
  window.addEventListener('resize', syncContainerWidth);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  window.removeEventListener('resize', syncContainerWidth);
});

const breakpoint = computed(() => getCurrentBreakpoint(containerWidth.value));

// 语义样式解析
const componentStyle = computed(() => {
  const authored = (props.node?.style || {}) as Record<string, any>;
  return {
    css_classes: authored.css_classes || '',
    inline_styles: authored.inline_styles || {},
  };
});

const computedClasses = computed(() => {
  try {
    const nodeProps = props.node?.props || {};
    const baseStyles = resolveNodeStyles(nodeProps);
    const layoutStyles = resolveResponsiveLayout(nodeProps.col_span || 1, breakpoint.value);
    const authoredStyles = componentStyle.value?.css_classes || '';
    return `${baseStyles} ${layoutStyles} ${authoredStyles}`.trim();
  } catch (e) {
    console.error("样式解析失败:", e);
    return "";
  }
});

const transitionDelay = computed(() => `${(props.index || 0) * 50}ms`); 
const isInteractive = computed(() => props.interactive !== false);
const isSelectionEnabled = computed(() => props.selectionEnabled === true);
const isSelected = computed(() => isSelectionEnabled.value && selectedComponentId.value === props.node?.id);
const selectedParagraph = computed(() => {
  if (!isSelectionEnabled.value || props.node?.component_type !== 'StoryText' || selectedComponentId.value !== props.node?.id) {
    return null;
  }
  return typeof selectedParagraphIndex.value === 'number' ? selectedParagraphIndex.value : null;
});
const wrapperClasses = computed(() => [
  'w-full transition-all duration-700 animate-fade-up',
  isSelectionEnabled.value ? 'cursor-crosshair' : 'cursor-default',
  computedClasses.value,
  isSelected.value ? 'ring-2 ring-[var(--primary-vibe)] ring-offset-2 ring-offset-white/60 rounded-[28px] shadow-[0_0_0_1px_rgba(255,36,66,0.12)]' : '',
]);

const handleSelect = (event?: MouseEvent) => {
  if (!isSelectionEnabled.value) return;
  event?.stopPropagation();
  if (props.node?.id) {
    chatStore.setSelectedComponent(props.node.id, null);
  }
};

const handleSelectPayload = (payload?: string | { compId?: string; paragraphIndex?: number | null }, event?: MouseEvent) => {
  if (!isSelectionEnabled.value) return;
  event?.stopPropagation();
  if (typeof payload === 'string') {
    chatStore.setSelectedComponent(payload, null);
    return;
  }
  const compId = payload?.compId || props.node?.id;
  if (compId) {
    chatStore.setSelectedComponent(compId, typeof payload?.paragraphIndex === 'number' ? payload.paragraphIndex : null);
  }
};

const handleQuickAction = (payload?: { compId?: string; paragraphIndex?: number | null; prompt?: string }) => {
  if (!isSelectionEnabled.value) return;
  const compId = payload?.compId || props.node?.id;
  if (compId) {
    chatStore.setSelectedComponent(compId, typeof payload?.paragraphIndex === 'number' ? payload.paragraphIndex : null);
  }
  if (payload?.prompt) {
    chatStore.setComposerDraft(payload.prompt);
  }
};

const handleHover = () => {
  if (!isSelectionEnabled.value) return;
  if (props.node?.id) {
    chatStore.setHoveredComponent(props.node.id);
  }
};

const handleUnhover = () => {
  if (!isSelectionEnabled.value) return;
  if (selectedComponentId.value !== props.node?.id) {
    chatStore.setHoveredComponent(null);
  }
};
const nodeData = computed(() => {
  const rawData = ((props.node?.props || {}) as Record<string, any>);
  const type = props.node?.component_type;

  if (type === 'RadarChartBlock' && !rawData.metrics && Array.isArray(rawData.dimensions) && Array.isArray(rawData.scores)) {
    return {
      ...rawData,
      metrics: rawData.dimensions.map((label: string, idx: number) => ({
        label,
        value: Number(rawData.scores?.[idx] ?? 0),
      })),
    };
  }

  if (type === 'PollBlock' && !rawData.options) {
    const options = [rawData.option_a, rawData.option_b].filter(Boolean);
    return {
      ...rawData,
      options,
    };
  }

  return rawData;
});

// 动态组件解析逻辑 (大小写不敏感匹配)
const resolveComp = (type: string) => {
  if (!type || !supportedTypes.has(type)) return null;
  if (componentMap[type]) return componentMap[type];
  const lowerType = type.toLowerCase();
  const entry = Object.entries(componentMap).find(([name]) => name.toLowerCase() === lowerType);
  return entry ? entry[1] : null;
};
</script>

<template>
  <div 
    ref="wrapperRef"
    :id="node.id"
    :data-comp-id="node.id"
    :class="['relative', wrapperClasses]"
    :style="{ transitionDelay, ...(componentStyle.inline_styles || {}) }"
    @click="handleSelect"
    @mouseenter="handleHover"
    @mouseleave="handleUnhover"
  >
    <button
      v-if="isSelectionEnabled"
      type="button"
      data-selection-overlay
      class="absolute inset-0 z-10 rounded-[28px] border border-transparent bg-transparent transition-all hover:border-[var(--primary-vibe)]/40 hover:bg-[var(--primary-vibe)]/5"
      :class="isSelected ? 'border-[var(--primary-vibe)]/50 bg-[var(--primary-vibe)]/5' : ''"
      @click.stop="handleSelect"
      aria-label="选择当前积木"
    />
    <div
      v-if="isSelectionEnabled"
      class="pointer-events-none absolute left-3 top-3 z-20 rounded-full border px-2 py-0.5 text-[9px] font-black uppercase tracking-[0.16em]"
      :style="{
        borderColor: isSelected ? 'color-mix(in srgb, var(--primary-vibe) 60%, white 40%)' : 'rgba(148,163,184,0.28)',
        background: isSelected ? 'color-mix(in srgb, var(--primary-vibe) 12%, white 88%)' : 'rgba(255,255,255,0.82)',
        color: isSelected ? 'var(--primary-vibe)' : 'var(--text-muted)',
      }"
    >
      {{ isSelected ? '已选中' : '点击选择' }}
    </div>
    <template v-if="resolveComp(node.component_type)">
      <component 
        :is="resolveComp(node.component_type)"
        :comp-id="node.id"
        :node="node"
        :data="nodeData"
        :style="{ css_classes: computedClasses, inline_styles: componentStyle.inline_styles || {} }"
        :selectedParagraph="selectedParagraph"
        @select="handleSelectPayload"
        @quick-action="handleQuickAction"
        @hover="handleHover"
      />
    </template>

    <template v-else>
      <div class="m-2 p-4 border-2 border-dashed border-amber-400 bg-amber-50 rounded-2xl flex flex-col gap-2 opacity-50">
        <div class="flex items-center gap-2 text-amber-700 font-bold text-[8px] uppercase">
          <span>⚠️ Component Not Ready</span>
        </div>
        <div class="text-[9px] text-amber-600/80 font-mono break-all bg-white/50 p-2 rounded-lg">
          [幻觉拦截] 待开发区块: <{{ node.component_type }}>
        </div>
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
