<template>
  <div class="min-h-full rounded-[26px] border border-[#333] bg-[#1e1e1e] shadow-[0_18px_40px_rgba(0,0,0,0.22)] overflow-hidden">
    <div class="border-b border-[#333] bg-[radial-gradient(circle_at_top_left,_rgba(255,154,62,0.14),_transparent_38%),linear-gradient(180deg,_rgba(37,37,38,0.98),_rgba(30,30,30,1))] px-5 py-4 lg:px-6">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-[#6b4724] bg-[#2c2117] px-2 py-0.5 text-[9px] font-bold text-[#ffcc8a]">Trend Desk</span>
            <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">热点与预热入口</span>
          </div>
          <div class="text-[14px] font-bold text-gray-100">把热点放到右侧工作台，变成更完整的创作入口</div>
          <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">
            这里展示的热点来自真实请求、后台追踪和缓存预热。点击热点可以直接生成，也可以先把推荐 prompt 填到左侧输入框里再继续打磨。
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="rounded-full border border-[#454545] bg-[#171719] px-3 py-1.5 text-[10px] font-bold text-gray-300 transition-all hover:border-orange-500 hover:text-orange-300"
            @click="refreshTrends"
          >
            刷新热榜
          </button>
          <span class="rounded-full border border-[#3a3a3a] bg-black/10 px-3 py-1.5 text-[10px] text-gray-400">
            {{ hotTrends.length }} 个可用话题
          </span>
        </div>
      </div>
    </div>

    <div class="grid gap-4 p-4 lg:grid-cols-[1.1fr_0.9fr] lg:p-5">
      <section class="rounded-[22px] border border-[#333] bg-[linear-gradient(180deg,_rgba(29,30,33,0.95),_rgba(22,23,25,0.98))] p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <div class="text-[10px] font-black uppercase tracking-[0.18em] text-orange-300">热点列表</div>
            <div class="mt-1 text-[13px] font-semibold text-gray-100">直接用热点触发更贴题的生成</div>
          </div>
          <div class="text-[10px] text-gray-500">优先展示推荐 prompt 和缓存状态</div>
        </div>

        <div v-if="hotTrends.length > 0" class="mt-4 grid gap-3">
          <article
            v-for="(trend, idx) in hotTrends"
            :key="trend.keyword || idx"
            class="rounded-[20px] border border-[#34363c] bg-[#181a1f] p-4 transition-all hover:border-orange-500/30 hover:bg-[#1b1e24]"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="rounded-full border border-[#6b4724] bg-[#2c2117] px-2 py-0.5 text-[9px] font-bold text-orange-300">#{{ idx + 1 }}</span>
                  <span class="rounded-full border border-[#41464f] px-2 py-0.5 text-[9px] text-gray-400">{{ scenarioLabel(trend.scenario_hint) }}</span>
                  <span class="rounded-full border border-[#41464f] px-2 py-0.5 text-[9px] text-gray-400">{{ entityTypeLabel(trend.entity_type) }}</span>
                </div>
                <div class="text-[15px] font-bold leading-snug text-gray-100">{{ trend.keyword }}</div>
                <p class="max-w-3xl text-[11px] leading-relaxed text-gray-500">
                  {{ trend.recommended_prompt || fallbackPrompt(trend) }}
                </p>
              </div>
              <div class="grid min-w-[156px] grid-cols-2 gap-2 text-[10px]">
                <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-2">
                  <div class="text-gray-500">热度</div>
                  <div class="mt-1 font-bold text-orange-300">{{ Math.round(Number(trend.score || 0)) }}</div>
                </div>
                <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-2">
                  <div class="text-gray-500">记录数</div>
                  <div class="mt-1 font-bold text-gray-200">{{ trend.record_count || 0 }}</div>
                </div>
                <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-2">
                  <div class="text-gray-500">新鲜度</div>
                  <div class="mt-1 font-bold" :class="freshnessTone(trend.freshness)">{{ freshnessLabel(trend.freshness) }}</div>
                </div>
                <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-2">
                  <div class="text-gray-500">缓存</div>
                  <div class="mt-1 font-bold" :class="cacheTone(trend.cache_freshness)">{{ cacheLabel(trend.cache_freshness) }}</div>
                </div>
              </div>
            </div>

            <div class="mt-4 flex flex-wrap items-center gap-2 text-[10px] text-gray-500">
              <span class="rounded-full border border-[#353840] bg-[#111317] px-2.5 py-1">来源 {{ sourceLabel(trend.source) }}</span>
              <span class="rounded-full border border-[#353840] bg-[#111317] px-2.5 py-1">
                {{ trend.recommended_prompt ? '已生成场景化 prompt' : '使用默认 prompt' }}
              </span>
            </div>

            <div class="mt-4 flex flex-wrap gap-2">
              <button
                class="rounded-full border border-orange-500/30 bg-orange-950/20 px-3 py-1.5 text-[11px] font-semibold text-orange-300 transition-all hover:border-orange-400 hover:bg-orange-950/35"
                @click="runTrend(trend)"
              >
                直接生成
              </button>
              <button
                class="rounded-full border border-[#40444b] bg-[#111317] px-3 py-1.5 text-[11px] font-semibold text-gray-200 transition-all hover:border-blue-500/40 hover:text-blue-300"
                @click="fillPrompt(trend)"
              >
                填到左侧输入框
              </button>
              <button
                class="rounded-full border border-[#40444b] bg-[#111317] px-3 py-1.5 text-[11px] font-semibold text-gray-200 transition-all hover:border-emerald-500/40 hover:text-emerald-300"
                @click="followTrend(trend.keyword)"
              >
                开启追踪
              </button>
            </div>
          </article>
        </div>

        <div v-else class="mt-6 rounded-[22px] border border-dashed border-[#333] bg-[#161719] px-5 py-10 text-center">
          <div class="text-[13px] font-semibold text-gray-200">当前还没有热点数据</div>
          <p class="mt-2 text-[11px] leading-relaxed text-gray-500">
            先正常生成几轮内容，或者手动开启主题追踪，这里就会长出更真实的热榜，而不是硬编码演示词。
          </p>
        </div>
      </section>

      <section class="space-y-4">
        <div class="rounded-[22px] border border-[#333] bg-[linear-gradient(180deg,_rgba(25,27,31,0.96),_rgba(20,22,25,0.98))] p-4">
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-[#314154] bg-[#182230] px-2 py-0.5 text-[9px] font-bold text-blue-300">素材联动</span>
            <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">当前线程会带着这些素材一起生成</span>
          </div>
          <div class="mt-3 grid gap-3 sm:grid-cols-2">
            <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-3">
              <div class="text-[10px] text-gray-500">素材总数</div>
              <div class="mt-1 text-[15px] font-bold text-gray-100">{{ documentAssets.length }}</div>
              <div class="mt-1 text-[10px] text-gray-500">热点触发时，这些图片会作为当前线程素材上下文一起带入。</div>
            </div>
            <div class="rounded-2xl border border-[#30343b] bg-[#111317] px-3 py-3">
              <div class="text-[10px] text-gray-500">当前封面</div>
              <div class="mt-1 text-[15px] font-bold text-gray-100">{{ currentCoverUrl ? '已设置' : '未设置' }}</div>
              <div class="mt-1 text-[10px] text-gray-500">如果你已经设了封面，热点生成会优先把它当作首屏素材来使用。</div>
            </div>
          </div>
          <div v-if="documentAssets.length > 0" class="mt-4 flex flex-wrap gap-2">
            <div
              v-for="(asset, idx) in documentAssets.slice(0, 6)"
              :key="asset.url + idx"
              class="relative h-16 w-16 overflow-hidden rounded-2xl border border-[#353840] bg-[#0f1114]"
            >
              <img :src="asset.url" class="h-full w-full object-cover" alt="" />
              <span
                v-if="asset.url === currentCoverUrl"
                class="absolute left-1 top-1 rounded-full bg-black/65 px-1.5 py-0.5 text-[9px] font-bold text-white"
              >
                封面
              </span>
            </div>
          </div>
        </div>

        <div class="rounded-[22px] border border-[#333] bg-[linear-gradient(180deg,_rgba(25,27,31,0.96),_rgba(20,22,25,0.98))] p-4">
          <div class="flex items-center gap-2">
            <span class="rounded-full border border-[#465034] bg-[#202617] px-2 py-0.5 text-[9px] font-bold text-[#b7d18a]">使用建议</span>
            <span class="text-[10px] uppercase tracking-[0.16em] text-gray-500">让热点入口更像正式创作工具</span>
          </div>
          <ul class="mt-3 space-y-2 text-[11px] leading-relaxed text-gray-400">
            <li>先在素材库里选好图，再回来点热点，这样更容易生成贴题封面。</li>
            <li>“直接生成”适合快速起稿；“填到左侧输入框”适合你再补风格、结构和限制条件。</li>
            <li>如果某个话题你打算反复演示，先点“开启追踪”，系统会在后台持续预热和补知识。</li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '../../stores/useChatStore'
import type { TrendItem } from '../../types/chat'

const chatStore = useChatStore()
const { hotTrends, documentAssets, currentCoverUrl } = storeToRefs(chatStore)

const refreshTrends = async () => {
  await chatStore.fetchTrends()
}

const fallbackPrompt = (trend: TrendItem) => `帮我围绕「${trend.keyword}」生成一篇结构清晰、信息可靠的分享笔记。`

const fillPrompt = (trend: TrendItem) => {
  chatStore.setComposerDraft(trend.recommended_prompt || fallbackPrompt(trend))
}

const runTrend = (trend: TrendItem) => {
  const prompt = trend.recommended_prompt || fallbackPrompt(trend)
  chatStore.sendMessage(prompt)
  chatStore.setWorkspaceMode('preview')
}

const followTrend = async (keyword: string) => {
  await chatStore.trackTrend(keyword)
}

const scenarioLabel = (scenario?: string) => {
  if (scenario === 'seeding') return '数码测评'
  if (scenario === 'travel') return '旅行攻略'
  if (scenario === 'daily_share') return '日常分享'
  if (scenario === 'store_review') return '探店推荐'
  return '通用话题'
}

const entityTypeLabel = (entityType?: string) => {
  if (entityType === 'digital_product') return '数码实体'
  if (entityType === 'travel_destination') return '地点实体'
  if (entityType === 'storefront') return '店铺实体'
  if (entityType === 'lifestyle_topic') return '生活方式'
  return '主题'
}

const freshnessLabel = (freshness?: string) => {
  if (freshness === 'fresh') return '新鲜'
  if (freshness === 'stale') return '待刷新'
  return '待收录'
}

const freshnessTone = (freshness?: string) => {
  if (freshness === 'fresh') return 'text-emerald-300'
  if (freshness === 'stale') return 'text-amber-300'
  return 'text-gray-300'
}

const cacheLabel = (cacheFreshness?: string) => {
  if (cacheFreshness === 'fresh') return '命中新鲜缓存'
  if (cacheFreshness === 'stale') return '命中过期缓存'
  if (cacheFreshness === 'miss') return '尚未命中'
  return '待判断'
}

const cacheTone = (cacheFreshness?: string) => {
  if (cacheFreshness === 'fresh') return 'text-emerald-300'
  if (cacheFreshness === 'stale') return 'text-amber-300'
  return 'text-gray-300'
}

const sourceLabel = (source?: string) => {
  if (source === 'manual_track') return '手动追踪'
  if (source === 'organic') return '真实请求积累'
  if (source === 'system_preload') return '系统预热'
  return source || '未知来源'
}

onMounted(() => {
  if (hotTrends.value.length === 0) {
    void refreshTrends()
  }
})
</script>
