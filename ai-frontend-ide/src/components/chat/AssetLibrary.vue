<template>
  <section class="rounded-2xl border border-[#343434] bg-[#202022] p-3">
    <div class="mb-3 flex items-center gap-2">
      <span class="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8ab4ff]">Assets</span>
      <div class="h-px flex-1 bg-gradient-to-r from-[#8ab4ff]/40 to-transparent"></div>
      <span class="text-[10px] text-gray-500">素材库</span>
    </div>

    <div class="flex gap-2">
      <input
        v-model="query"
        type="text"
        placeholder="搜索真实图片素材..."
        class="flex-1 rounded-xl border border-[#3a3a3a] bg-[#171719] px-3 py-2 text-[12px] text-gray-200 outline-none focus:border-blue-500"
        @keydown.enter.prevent="handleSearch"
      />
      <button
        class="rounded-xl bg-[#2d6cdf] px-3 py-2 text-[12px] font-semibold text-white transition-all hover:bg-[#255ed0] disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="assetSearchLoading"
        @click="handleSearch"
      >
        {{ assetSearchLoading ? '搜索中' : '搜图' }}
      </button>
    </div>

    <div v-if="currentCoverUrl" class="mt-4 overflow-hidden rounded-2xl border border-[#3c3c3c] bg-[#171719]">
      <div class="flex items-center justify-between border-b border-[#303030] px-3 py-2">
        <span class="text-[10px] font-bold uppercase tracking-[0.18em] text-[#ff8a65]">当前封面</span>
        <span class="rounded-full border border-[#5a3f39] bg-[#2a1917] px-2 py-0.5 text-[9px] text-[#ff8a65]">Active Cover</span>
      </div>
      <img :src="currentCoverUrl" class="h-40 w-full object-cover" alt="" />
    </div>

    <div v-if="currentAssets.length > 0" class="mt-4">
      <p class="mb-2 text-[10px] uppercase tracking-[0.18em] text-gray-500">当前资产</p>
      <div class="grid grid-cols-2 gap-2">
        <article
          v-for="asset in currentAssets.slice(0, 4)"
          :key="asset.url"
          class="overflow-hidden rounded-xl border bg-[#171719]"
          :class="asset.url === currentCoverUrl ? 'border-[#ff8a65] ring-1 ring-[#ff8a65]/40' : 'border-[#363636]'"
        >
          <img :src="asset.url" class="h-24 w-full object-cover" alt="" />
          <div class="p-2">
            <div class="mb-1 flex items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-1">
                <span class="rounded-full border border-[#444] px-2 py-0.5 text-[9px] text-gray-400">
                  {{ asset.source_type || 'asset' }}
                </span>
                <span
                  v-if="asset.url === currentCoverUrl"
                  class="rounded-full border border-[#5a3f39] bg-[#2a1917] px-2 py-0.5 text-[9px] text-[#ff8a65]"
                >
                  当前封面
                </span>
              </div>
              <button
                class="text-[10px] transition-colors"
                :class="asset.url === currentCoverUrl ? 'text-[#ff8a65]' : 'text-blue-400 hover:text-blue-300'"
                @click="$emit('cover', asset)"
              >
                {{ asset.url === currentCoverUrl ? '已设为封面' : '设为封面' }}
              </button>
            </div>
            <p class="line-clamp-2 text-[10px] leading-4 text-gray-500">{{ asset.desc }}</p>
          </div>
        </article>
      </div>
    </div>

    <div v-if="searchResults.length > 0" class="mt-4">
      <p class="mb-2 text-[10px] uppercase tracking-[0.18em] text-gray-500">搜索结果</p>
      <div class="grid grid-cols-2 gap-2">
        <article
          v-for="asset in searchResults.slice(0, 6)"
          :key="asset.url"
          class="overflow-hidden rounded-xl border bg-[#171719]"
          :class="asset.url === currentCoverUrl ? 'border-[#ff8a65] ring-1 ring-[#ff8a65]/40' : 'border-[#363636]'"
        >
          <img :src="asset.url" class="h-24 w-full object-cover" alt="" />
          <div class="p-2">
            <div class="mb-1 flex flex-wrap items-center gap-1">
              <span
                v-if="importedAssetUrls.includes(asset.url)"
                class="rounded-full border border-[#1c4a36] bg-[#10271f] px-2 py-0.5 text-[9px] text-[#7fe0a6]"
              >
                已入资产池
              </span>
              <span
                v-if="asset.url === currentCoverUrl"
                class="rounded-full border border-[#5a3f39] bg-[#2a1917] px-2 py-0.5 text-[9px] text-[#ff8a65]"
              >
                当前封面
              </span>
            </div>
            <p class="line-clamp-2 min-h-[32px] text-[10px] leading-4 text-gray-500">{{ asset.desc }}</p>
            <div class="mt-2 flex items-center gap-2">
              <button
                class="flex-1 rounded-lg border px-2 py-1 text-[10px] transition-all"
                :class="importedAssetUrls.includes(asset.url) ? 'border-[#1c4a36] bg-[#10271f] text-[#7fe0a6]' : 'border-[#444] text-gray-300 hover:border-blue-500 hover:text-blue-400'"
                @click="$emit('import', asset)"
              >
                {{ importedAssetUrls.includes(asset.url) ? '已入资产池' : '收进资产池' }}
              </button>
              <button
                class="flex-1 rounded-lg px-2 py-1 text-[10px] font-semibold text-white transition-all"
                :class="asset.url === currentCoverUrl ? 'bg-[#ff8a65]' : 'bg-[#ff2442] hover:bg-[#e2213d]'"
                @click="$emit('cover', asset)"
              >
                {{ asset.url === currentCoverUrl ? '当前封面' : '设为封面' }}
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
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

const handleSearch = () => {
  emit('search', query.value)
}
</script>
