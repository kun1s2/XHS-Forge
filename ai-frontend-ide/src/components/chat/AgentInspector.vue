<script setup lang="ts">
import { ref, computed } from 'vue';
import { useChatStore } from '../../stores/useChatStore';

const chatStore = useChatStore();
const activeTab = ref<'meta' | 'dsl' | 'rag' | 'patch'>('meta');

// 递归 JSON 树组件 (内部局部定义)
const JsonTree = {
  name: 'JsonTree',
  props: ['data', 'label'],
  template: `
    <div class="pl-3 border-l border-[#333] my-1">
      <details class="group" open>
        <summary class="cursor-pointer text-[11px] hover:text-blue-400 transition-colors list-none flex items-center gap-1">
          <span class="w-3 h-3 text-[8px] opacity-40 transition-transform group-open:rotate-90">▶</span>
          <span class="font-bold text-gray-500">{{ label }}:</span>
          <span v-if="!isObject(data)" class="text-blue-300 font-mono">{{ formatValue(data) }}</span>
          <span v-else class="text-[9px] opacity-30 italic">{ Object }</span>
        </summary>
        <div v-if="isObject(data)" class="pl-2 space-y-0.5 mt-1">
          <JsonTree v-for="(val, key) in data" :key="key" :data="val" :label="key" />
        </div>
      </details>
    </div>
  `,
  methods: {
    isObject: (val: any) => val !== null && typeof val === 'object',
    formatValue: (val: any) => typeof val === 'string' ? `"${val}"` : val
  }
};

const tabs = [
  { id: 'meta', name: '🧠 灵感架构', icon: '⚡' },
  { id: 'dsl', name: '📄 实时 DSL', icon: '🛠️' },
  { id: 'rag', name: '📚 检索记忆', icon: '🔍' },
  { id: 'patch', name: '🩹 视觉补丁', icon: '💉' }
];

const metaInfo = computed(() => [
  { label: '创作者人设', value: chatStore.creatorPersona || '默认博主', color: 'text-yellow-400' },
  { label: '意图路由', value: chatStore.currentNode || 'IDLE', color: 'text-pink-400' },
  { label: 'Checkpoint', value: chatStore.activeCheckpointId?.slice(0, 8) || 'NONE', color: 'text-gray-500' }
]);
</script>

<template>
  <div class="bg-[#1e1e1e] text-gray-400 p-0 rounded-xl font-sans text-xs shadow-2xl border border-[#333] w-full mb-4 overflow-hidden flex flex-col h-[400px]">
    <!-- 头部 Tabs -->
    <div class="flex border-b border-[#333] bg-[#252526] shrink-0">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="[
          'flex-1 py-2 text-[10px] font-bold border-b-2 transition-all flex items-center justify-center gap-1',
          activeTab === tab.id ? 'border-blue-500 text-blue-400 bg-[#1e1e1e]' : 'border-transparent opacity-50 hover:opacity-100 hover:bg-[#2d2d2d]'
        ]"
      >
        <span>{{ tab.icon }}</span>
        <span class="hidden sm:inline">{{ tab.name }}</span>
      </button>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#1e1e1e]">
      
      <!-- Tab 1: 灵感架构 -->
      <div v-if="activeTab === 'meta'" class="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
        <div v-for="item in metaInfo" :key="item.label" class="flex items-center justify-between border-b border-[#333]/50 pb-2">
          <span class="text-gray-500 font-medium">{{ item.label }}:</span>
          <span :class="['font-mono font-bold', item.color]">{{ item.value }}</span>
        </div>
        
        <div class="mt-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest mb-2 flex justify-between items-center">
            <span>动态追踪雷达</span>
            <span class="text-[8px] bg-orange-900/30 text-orange-500 px-1 rounded animate-pulse">Live</span>
          </div>
          <div class="bg-[#2d2d2d]/50 p-3 rounded-lg border border-[#3c3c3c] flex flex-col gap-2">
            <div class="flex items-center justify-between">
              <span class="text-[11px] text-gray-300">
                当前主体: 
                <span class="text-blue-400 font-bold ml-1">{{ (chatStore.agentMeta.retrieved_knowledge as any)?.entity_name || '未识别' }}</span>
              </span>
              <button 
                v-if="(chatStore.agentMeta.retrieved_knowledge as any)?.entity_name"
                @click="chatStore.trackTrend((chatStore.agentMeta.retrieved_knowledge as any).entity_name)"
                class="px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white text-[9px] rounded shadow-lg transition-all active:scale-95"
              >
                开启深度追踪
              </button>
            </div>
            <div class="text-[9px] text-gray-500 italic leading-tight">
              点击追踪后，后端将利用 Redis ZSet 提升权重并启动异步预热。
            </div>
          </div>
        </div>

        <div class="mt-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-widest mb-2">活跃标签</div>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="tag in (chatStore.pageData?.archetype_tags || ['general'])" :key="tag" class="bg-blue-900/20 text-blue-400 px-2 py-0.5 rounded-full border border-blue-800/30 text-[9px] font-bold uppercase tracking-tighter">
              #{{ tag }}
            </span>
          </div>
        </div>

        <div v-if="chatStore.wsStatus === 'connecting'" class="mt-4 flex items-center gap-2 bg-yellow-900/10 text-yellow-500 p-2 rounded-lg border border-yellow-900/20 text-[10px]">
          <span class="animate-spin text-lg">⚡</span>
          <span>大脑引擎正在深度初始化...</span>
        </div>
      </div>

      <!-- Tab 2: 实时 DSL -->
      <div v-if="activeTab === 'dsl'" class="animate-in fade-in duration-300 font-mono">
        <div class="text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Page Data (AST)</div>
        <JsonTree :data="chatStore.pageData" label="UI_PROJECT_STATE" />
        
        <div class="mt-6 text-[10px] text-gray-500 mb-3 border-b border-[#333] pb-1 uppercase tracking-wider">Style Library</div>
        <JsonTree :data="chatStore.styleData" label="CSS_VARS" />
      </div>

      <!-- Tab 3: 检索记忆 (RAG) -->
      <div v-if="activeTab === 'rag'" class="space-y-3 animate-in fade-in duration-300">
        <!-- ✨ 4.0 增强：舆情对冲报告可视化 -->
        <div v-if="(chatStore.agentMeta.retrieved_knowledge as any)?.battle_report" class="space-y-2 mb-4">
          <div class="flex items-center gap-2 bg-gradient-to-r from-rose-900/20 to-blue-900/20 text-rose-400 p-2 rounded-lg border border-rose-800/20">
            <span class="animate-pulse">⚔️</span>
            <span class="font-bold uppercase tracking-tighter text-[10px]">Opinion Clash Report (天平对冲引擎)</span>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <div class="bg-rose-950/20 p-2 rounded border border-rose-500/20">
              <div class="text-[8px] text-rose-500 font-bold mb-1">PROS AGENT</div>
              <div class="text-[10px] text-gray-300 leading-tight">{{ (chatStore.agentMeta.retrieved_knowledge as any).battle_report.pros?.summary }}</div>
            </div>
            <div class="bg-blue-950/20 p-2 rounded border border-blue-500/20">
              <div class="text-[8px] text-blue-500 font-bold mb-1">CONS AGENT</div>
              <div class="text-[10px] text-gray-300 leading-tight">{{ (chatStore.agentMeta.retrieved_knowledge as any).battle_report.cons?.summary }}</div>
            </div>
          </div>
        </div>

        <div v-if="!chatStore.thoughtText && !chatStore.nodeStreamOutput && !(chatStore.agentMeta.retrieved_knowledge as any)?.battle_report" class="text-center py-10 opacity-30 italic text-[10px]">
          <div class="text-3xl mb-2">🔭</div>
          等待 Agent 激活搜索引擎...
        </div>
        <div v-else class="space-y-3">
          <div class="flex items-center gap-2 bg-blue-900/10 text-blue-400 p-2 rounded-lg border border-blue-800/20">
            <span class="animate-pulse">🔎</span>
            <span class="font-bold">深度联网调研中</span>
          </div>
          <div class="bg-[#000]/30 p-3 rounded-lg border border-[#333] font-mono text-[10px] leading-relaxed text-gray-400">
             {{ chatStore.thoughtText || chatStore.nodeStreamOutput }}
          </div>
        </div>
      </div>

      <!-- Tab 4: 视觉补丁 (Tracks) -->
      <div v-if="activeTab === 'patch'" class="animate-in fade-in duration-300">
        <div v-if="chatStore.selectedComponentId" class="space-y-4">
          <div class="flex items-center gap-2 bg-pink-900/10 text-pink-500 p-2 rounded-lg border border-pink-900/20 mb-4">
            <span>🎯</span>
            <span class="font-bold uppercase tracking-tighter">选中组件: {{ chatStore.selectedComponentId }}</span>
          </div>

          <!-- ✨ 核心：生长档案时间轴 -->
          <div v-if="(chatStore.pageData.patch_tracks as any)?.[chatStore.selectedComponentId]" class="relative pl-4 border-l border-[#333] space-y-6">
            <div 
              v-for="(track, idx) in (chatStore.pageData.patch_tracks as any)[chatStore.selectedComponentId]" 
              :key="idx"
              class="relative group"
            >
              <!-- 时间轴圆点 -->
              <div class="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#1e1e1e] bg-[#444] group-hover:bg-pink-500 transition-colors shadow-[0_0_8px_rgba(0,0,0,0.5)]"></div>
              
              <div class="flex flex-col gap-1.5">
                <div class="flex justify-between items-center">
                  <span class="text-[9px] font-mono text-gray-500">{{ new Date(track.timestamp).toLocaleString() }}</span>
                  <button 
                    @click="chatStore.rollbackComponent(chatStore.selectedComponentId!, idx)"
                    class="opacity-0 group-hover:opacity-100 text-[8px] bg-pink-600/20 hover:bg-pink-600 text-pink-400 hover:text-white px-1.5 py-0.5 rounded transition-all"
                  >
                    RESTORE
                  </button>
                </div>
                <div class="bg-[#2d2d2d] p-2.5 rounded-lg border border-[#3c3c3c] group-hover:border-pink-500/30 transition-all cursor-default">
                  <div class="text-[10px] text-gray-300 font-bold mb-1 italic">"{{ track.prompt }}"</div>
                  <div class="text-[9px] text-gray-500 leading-tight">{{ track.agent_thought }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else class="text-center py-10 opacity-30 italic text-[10px]">
            <div class="text-3xl mb-2">🧬</div>
            该组件暂无手术记录
          </div>
        </div>
        <div v-else class="text-center py-10 opacity-30 italic text-[10px]">
          <div class="text-3xl mb-2">💉</div>
          请在画布选中组件以查看微调历史
        </div>
      </div>

    </div>

    <!-- 底部栏 -->
    <div class="px-4 py-2 border-t border-[#333] bg-[#252526] text-[9px] text-gray-600 flex justify-between font-mono italic shrink-0">
      <span>OBS_V2.1.0</span>
      <span class="flex items-center gap-1">
        <span class="w-1 h-1 bg-green-500 rounded-full animate-ping"></span>
        STREAM_SYNCED
      </span>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 10px;
}
</style>
