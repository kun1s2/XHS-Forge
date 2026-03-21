<template>
  <section class="rounded-[28px] border border-[#343434] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_35%),linear-gradient(180deg,_rgba(32,32,34,0.98),_rgba(25,25,27,1))] p-4 lg:p-5 shadow-[0_18px_50px_rgba(0,0,0,0.24)]">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div class="space-y-2">
        <div class="flex items-center gap-2">
          <span class="text-[10px] font-bold uppercase tracking-[0.24em] text-[#8ab4ff]">Assets</span>
          <div class="h-px w-20 bg-gradient-to-r from-[#8ab4ff]/50 to-transparent"></div>
          <span class="rounded-full border border-[#2f456d] bg-[#162033] px-2 py-0.5 text-[9px] font-bold text-[#8ab4ff]">素材工作台</span>
        </div>
        <div class="text-[15px] font-bold text-gray-100">当前线程的图片资产与封面管理</div>
        <p class="max-w-2xl text-[11px] leading-relaxed text-gray-500">
          这里优先展示当前封面、资产池和联网搜图结果。你可以把图片收入资产池、设为封面，并查看这张图已经绑定到哪些区块。
        </p>
      </div>

      <div class="grid min-w-[220px] grid-cols-2 gap-2 sm:min-w-[320px]">
        <div class="rounded-2xl border border-cyan-800/20 bg-cyan-950/10 px-3 py-2.5">
          <div class="text-[9px] uppercase tracking-wider text-gray-500">当前资产</div>
          <div class="mt-1 text-[13px] font-bold text-cyan-300">{{ currentAssets.length }}</div>
        </div>
        <div class="rounded-2xl border border-emerald-800/20 bg-emerald-950/10 px-3 py-2.5">
          <div class="text-[9px] uppercase tracking-wider text-gray-500">已绑定区块</div>
          <div class="mt-1 text-[13px] font-bold text-emerald-300">{{ boundAssetCount }}</div>
        </div>
        <div class="rounded-2xl border border-amber-800/20 bg-amber-950/10 px-3 py-2.5">
          <div class="text-[9px] uppercase tracking-wider text-gray-500">当前封面</div>
          <div class="mt-1 text-[13px] font-bold text-amber-300">{{ currentCoverAsset ? '已设置' : '未设置' }}</div>
        </div>
        <div class="rounded-2xl border border-violet-800/20 bg-violet-950/10 px-3 py-2.5">
          <div class="text-[9px] uppercase tracking-wider text-gray-500">搜索结果</div>
          <div class="mt-1 text-[13px] font-bold text-violet-300">{{ searchResults.length }}</div>
        </div>
      </div>
    </div>

    <div class="mt-5 rounded-[24px] border border-[#3a3a3a] bg-[#171719]/90 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] lg:p-4">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div class="flex-1">
          <label class="mb-2 block text-[10px] font-bold uppercase tracking-[0.18em] text-gray-500">联网搜图</label>
          <input
            v-model="query"
            type="text"
            placeholder="搜索真实图片素材，比如：华为 Mate 60 真机图"
            class="w-full rounded-2xl border border-[#3a3a3a] bg-[#111113] px-4 py-3 text-[13px] text-gray-100 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15"
            @keydown.enter.prevent="handleSearch"
          />
        </div>
        <button
          class="rounded-2xl bg-[#2d6cdf] px-5 py-3 text-[13px] font-semibold text-white shadow-lg transition-all hover:bg-[#255ed0] hover:shadow-blue-900/30 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="assetSearchLoading"
          @click="handleSearch"
        >
          {{ assetSearchLoading ? '搜索中...' : '搜索图片' }}
        </button>
      </div>
      <p class="mt-2 text-[10px] leading-relaxed text-gray-500">
        搜索结果只会进入当前线程，不会污染其他会话。建议先把满意的图片收入资产池，再决定是否设为封面。
      </p>
    </div>

    <div v-if="currentCoverAsset" class="mt-5 overflow-hidden rounded-[26px] border border-[#3c3c3c] bg-[#171719] shadow-[0_18px_40px_rgba(0,0,0,0.24)]">
      <div class="grid gap-0 lg:grid-cols-[1.4fr_1fr]">
        <div class="relative min-h-[260px] bg-[#121214]">
          <img :src="currentCoverAsset.url" class="h-full w-full object-cover" alt="当前封面" />
          <div class="absolute inset-0 bg-gradient-to-t from-black/65 via-black/10 to-transparent"></div>
          <div class="absolute bottom-0 left-0 right-0 p-4">
            <div class="flex flex-wrap items-center gap-2">
              <span class="rounded-full border border-[#5a3f39] bg-[#2a1917]/90 px-2.5 py-1 text-[9px] font-bold text-[#ff8a65]">当前封面</span>
              <span v-if="currentCoverAsset.source_type" class="rounded-full border border-[#444] bg-black/20 px-2.5 py-1 text-[9px] text-gray-200">
                {{ currentCoverAsset.source_type }}
              </span>
              <span v-if="currentCoverAsset.role" class="rounded-full border border-[#2f456d] bg-[#162033]/90 px-2.5 py-1 text-[9px] font-bold text-[#8ab4ff]">
                {{ humanizeAssetRole(currentCoverAsset.role) }}
              </span>
            </div>
            <p class="mt-3 max-w-xl text-[12px] font-semibold leading-relaxed text-white/90">
              {{ currentCoverAsset.desc || '这张图片当前被当作页面封面使用。' }}
            </p>
          </div>
        </div>
        <div class="flex flex-col justify-between gap-4 border-t border-[#303030] p-4 lg:border-l lg:border-t-0">
          <div class="space-y-3">
            <div>
              <div class="text-[10px] uppercase tracking-[0.18em] text-gray-500">封面说明</div>
              <div class="mt-2 text-[12px] leading-relaxed text-gray-300">
                {{ currentCoverAsset.source_reason || '封面会在页面预览里优先展示，并影响用户第一眼的观感。' }}
              </div>
            </div>
            <div>
              <div class="text-[10px] uppercase tracking-[0.18em] text-gray-500">区块绑定</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span
                  v-for="blockId in currentCoverAsset.used_by_blocks || []"
                  :key="blockId"
                  class="rounded-full border border-[#2f456d] bg-[#162033] px-2.5 py-1 text-[9px] font-bold text-[#8ab4ff]"
                >
                  {{ blockId }}
                </span>
                <span v-if="!(currentCoverAsset.used_by_blocks || []).length" class="text-[10px] text-gray-500">当前没有显式区块绑定，主要作为页面封面。</span>
              </div>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              class="flex-1 rounded-2xl border border-[#5a3f39] bg-[#2a1917] px-3 py-2 text-[11px] font-bold text-[#ff8a65]"
              @click="$emit('cover', currentCoverAsset)"
            >
              当前已是封面
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-6 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-gray-500">当前资产</div>
          <div class="mt-1 text-[12px] font-bold text-gray-100">当前线程里可复用的素材</div>
        </div>
        <span class="rounded-full border border-[#3a3a3a] bg-black/10 px-3 py-1 text-[10px] text-gray-400">{{ currentAssets.length }} items</span>
      </div>

      <div v-if="currentAssets.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="asset in currentAssets"
          :key="asset.url"
          class="overflow-hidden rounded-[24px] border bg-[#171719] shadow-[0_14px_34px_rgba(0,0,0,0.22)] transition-all hover:-translate-y-0.5 hover:border-[#4a4a4a]"
          :class="asset.url === currentCoverUrl ? 'border-[#ff8a65] ring-1 ring-[#ff8a65]/40' : 'border-[#363636]'"
        >
          <div class="relative aspect-[4/3] overflow-hidden bg-[#101012]">
            <img :src="asset.url" class="h-full w-full object-cover transition duration-300 hover:scale-[1.02]" alt="素材图" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent"></div>
            <div class="absolute left-3 top-3 flex flex-wrap gap-1.5">
              <span class="rounded-full border border-[#444] bg-black/35 px-2 py-0.5 text-[9px] text-gray-200">
                {{ asset.source_type || 'asset' }}
              </span>
              <span
                v-if="asset.url === currentCoverUrl"
                class="rounded-full border border-[#5a3f39] bg-[#2a1917] px-2 py-0.5 text-[9px] font-bold text-[#ff8a65]"
              >
                当前封面
              </span>
              <span
                v-if="asset.role"
                class="rounded-full border border-[#2f456d] bg-[#162033] px-2 py-0.5 text-[9px] font-bold text-[#8ab4ff]"
              >
                {{ humanizeAssetRole(asset.role) }}
              </span>
              <span
                v-if="asset.locked"
                class="rounded-full border border-amber-700/30 bg-amber-950/20 px-2 py-0.5 text-[9px] font-bold text-amber-300"
              >
                已锁定
              </span>
            </div>
          </div>
          <div class="space-y-3 p-4">
            <div>
              <p class="line-clamp-2 text-[12px] font-semibold leading-5 text-gray-100">{{ asset.desc || '未命名素材' }}</p>
              <p v-if="asset.source_reason" class="mt-2 text-[10px] leading-relaxed text-gray-500">{{ asset.source_reason }}</p>
            </div>
            <div>
              <div class="text-[9px] uppercase tracking-[0.16em] text-gray-500">绑定区块</div>
              <div class="mt-2 flex min-h-[24px] flex-wrap gap-1.5">
                <span
                  v-for="blockId in asset.used_by_blocks || []"
                  :key="blockId"
                  class="rounded-full border border-[#2f456d] bg-[#162033] px-2 py-0.5 text-[9px] font-bold text-[#8ab4ff]"
                >
                  {{ blockId }}
                </span>
                <span v-if="!(asset.used_by_blocks || []).length" class="text-[10px] text-gray-500">暂未绑定区块</span>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                class="flex-1 rounded-2xl border px-3 py-2 text-[11px] font-semibold transition-all"
                :class="asset.url === currentCoverUrl ? 'border-[#5a3f39] bg-[#2a1917] text-[#ff8a65]' : 'border-[#444] text-gray-200 hover:border-[#ff8a65] hover:text-[#ff8a65]'"
                @click="$emit('cover', asset)"
              >
                {{ asset.url === currentCoverUrl ? '当前封面' : '设为封面' }}
              </button>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="rounded-2xl border border-dashed border-[#3a3a3a] bg-black/10 px-5 py-8 text-center">
        <div class="text-3xl">🗂️</div>
        <div class="mt-3 text-[12px] font-bold text-gray-200">当前还没有收进资产池的图片</div>
        <p class="mt-2 text-[10px] leading-relaxed text-gray-500">先搜图或上传新图，再把满意的素材收入资产池，后续编辑会更稳定地复用它们。</p>
      </div>
    </div>

    <div class="mt-6 space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-[10px] uppercase tracking-[0.18em] text-gray-500">搜索结果</div>
          <div class="mt-1 text-[12px] font-bold text-gray-100">联网搜图结果，建议先挑选再收入资产池</div>
        </div>
        <span class="rounded-full border border-[#3a3a3a] bg-black/10 px-3 py-1 text-[10px] text-gray-400">{{ searchResults.length }} items</span>
      </div>

      <div v-if="searchResults.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="asset in searchResults"
          :key="asset.url"
          class="overflow-hidden rounded-[24px] border bg-[#171719] shadow-[0_14px_34px_rgba(0,0,0,0.22)] transition-all hover:-translate-y-0.5 hover:border-[#4a4a4a]"
          :class="asset.url === currentCoverUrl ? 'border-[#ff8a65] ring-1 ring-[#ff8a65]/40' : 'border-[#363636]'"
        >
          <div class="relative aspect-[4/3] overflow-hidden bg-[#101012]">
            <img :src="asset.url" class="h-full w-full object-cover transition duration-300 hover:scale-[1.02]" alt="搜索结果图片" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent"></div>
            <div class="absolute left-3 top-3 flex flex-wrap gap-1.5">
              <span
                v-if="importedUrlSet.has(asset.url)"
                class="rounded-full border border-[#1c4a36] bg-[#10271f] px-2 py-0.5 text-[9px] font-bold text-[#7fe0a6]"
              >
                已入资产池
              </span>
              <span
                v-if="asset.url === currentCoverUrl"
                class="rounded-full border border-[#5a3f39] bg-[#2a1917] px-2 py-0.5 text-[9px] font-bold text-[#ff8a65]"
              >
                当前封面
              </span>
            </div>
          </div>
          <div class="space-y-3 p-4">
            <div>
              <p class="line-clamp-2 min-h-[40px] text-[12px] font-semibold leading-5 text-gray-100">{{ asset.desc || '搜索结果素材' }}</p>
              <p v-if="asset.query" class="mt-2 text-[10px] text-gray-500">搜索词：{{ asset.query }}</p>
            </div>
            <div class="flex items-center gap-2">
              <button
                class="flex-1 rounded-2xl border px-3 py-2 text-[11px] font-semibold transition-all"
                :class="importedUrlSet.has(asset.url) ? 'border-[#1c4a36] bg-[#10271f] text-[#7fe0a6]' : 'border-[#444] text-gray-200 hover:border-blue-500 hover:text-blue-300'"
                @click="$emit('import', asset)"
              >
                {{ importedUrlSet.has(asset.url) ? '已入资产池' : '收进资产池' }}
              </button>
              <button
                class="flex-1 rounded-2xl px-3 py-2 text-[11px] font-semibold text-white transition-all"
                :class="asset.url === currentCoverUrl ? 'bg-[#ff8a65]' : 'bg-[#ff2442] hover:bg-[#e2213d]'"
                @click="$emit('cover', asset)"
              >
                {{ asset.url === currentCoverUrl ? '当前封面' : '设为封面' }}
              </button>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="rounded-2xl border border-dashed border-[#3a3a3a] bg-black/10 px-5 py-8 text-center">
        <div class="text-3xl">🔎</div>
        <div class="mt-3 text-[12px] font-bold text-gray-200">还没有搜索结果</div>
        <p class="mt-2 text-[10px] leading-relaxed text-gray-500">输入一个更具体的搜索词，比如产品名、场景词或“真机图 / 氛围图 / 封面图”。</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImageAsset } from '../../types/chat'

const props = defineProps<{
  currentAssets: ImageAsset[]
  searchResults: ImageAsset[]
  assetSearchLoading: boolean
  currentCoverUrl?: string | null
  importedAssetUrls: string[]
}>()

const emit = defineEmits<{
  search: [query: string]
  import: [asset: ImageAsset]
  cover: [asset: ImageAsset]
}>()

const query = ref('')

const importedUrlSet = computed(() => new Set(props.importedAssetUrls || []))
const currentCoverAsset = computed(() => props.currentAssets.find(asset => asset.url === props.currentCoverUrl) || null)
const boundAssetCount = computed(() => props.currentAssets.filter(asset => (asset.used_by_blocks || []).length > 0).length)
const humanizeAssetRole = (role?: string) => {
  if (!role) return 'asset'
  if (role === 'cover') return '封面'
  if (role === 'supporting') return '辅助图'
  if (role === 'inline') return '正文图'
  return role
}

const handleSearch = () => {
  emit('search', query.value.trim())
}
</script>
