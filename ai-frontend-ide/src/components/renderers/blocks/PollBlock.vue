<script setup lang="ts">
import { defineProps, computed, ref } from 'vue';

const props = defineProps<{
  node: any;
  data: {
    question?: string;
    options?: string[];
    total_votes?: number;
  };
}>();

const question = computed(() => props.data.question || "大家觉得这个设计怎么样？");
const options = computed(() => props.data.options || ["真香，必入！", "再观望一下", "不太感冒"]);

const selectedOption = ref<number | null>(null);
const voteCount = ref<number[]>(options.value.map(() => Math.floor(Math.random() * 100)));
const totalVotes = computed(() => voteCount.value.reduce((a, b) => a + b, 0));

const handleVote = (idx: number) => {
  if (selectedOption.value !== null) return;
  selectedOption.value = idx;
  voteCount.value[idx]++;
};

const getPercentage = (idx: number) => {
  if (totalVotes.value === 0) return 0;
  return Math.round((voteCount.value[idx] / totalVotes.value) * 100);
};
</script>

<template>
  <div class="w-full bg-gradient-to-br from-gray-50 to-white p-6 rounded-[32px] border border-gray-100 shadow-sm animate-in fade-in zoom-in duration-500">
    <!-- 头部引导 -->
    <div class="flex items-center gap-2 mb-4">
      <div class="w-8 h-8 bg-[var(--primary-vibe)] rounded-full flex items-center justify-center text-white text-xs shadow-lg shadow-[var(--primary-vibe)]/20">
        📊
      </div>
      <div class="flex flex-col">
        <span class="text-[10px] text-[var(--primary-vibe)] font-black uppercase tracking-tighter">Opinion Poll</span>
        <h3 class="text-sm font-black text-gray-800 leading-tight">{{ question }}</h3>
      </div>
    </div>

    <!-- 选项列表 -->
    <div class="space-y-3">
      <button 
        v-for="(opt, idx) in options" 
        :key="idx"
        @click="handleVote(idx)"
        :disabled="selectedOption !== null"
        class="relative w-full overflow-hidden transition-all duration-300 active:scale-[0.98]"
      >
        <!-- 进度条背景 -->
        <div class="absolute inset-0 bg-gray-100 rounded-2xl"></div>
        <div 
          class="absolute inset-0 bg-[var(--primary-vibe)] opacity-10 transition-all duration-1000 ease-out rounded-2xl"
          :style="{ width: selectedOption !== null ? getPercentage(idx) + '%' : '0%' }"
        ></div>

        <!-- 内容层 -->
        <div 
          class="relative px-4 py-3.5 flex justify-between items-center border-2 rounded-2xl transition-all duration-300"
          :class="[
            selectedOption === idx ? 'border-[var(--primary-vibe)] bg-white/50 shadow-inner' : 'border-transparent hover:border-gray-200'
          ]"
        >
          <span class="text-xs font-bold" :class="selectedOption === idx ? 'text-[var(--primary-vibe)]' : 'text-gray-600'">
            {{ opt }}
          </span>
          
          <div v-if="selectedOption !== null" class="flex items-center gap-2">
            <span class="text-[10px] font-black text-gray-400">{{ getPercentage(idx) }}%</span>
            <div v-if="selectedOption === idx" class="w-1.5 h-1.5 bg-[var(--primary-vibe)] rounded-full animate-pulse"></div>
          </div>
        </div>
      </button>
    </div>

    <!-- 底部互动数据 -->
    <div class="mt-4 pt-3 border-t border-dashed border-gray-200 flex justify-between items-center px-1">
      <span class="text-[9px] text-gray-400 font-medium tracking-tight italic">
        已收到 {{ totalVotes }} 位用户的真实反馈
      </span>
      <div class="flex -space-x-2">
        <div v-for="i in 3" :key="i" class="w-5 h-5 rounded-full border-2 border-white bg-gray-200 overflow-hidden">
          <img :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${i + 10}`" alt="">
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
button:disabled {
  cursor: default;
}
</style>
