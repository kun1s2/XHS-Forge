// src/stores/useChatStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, ImageAsset, ShowcaseProfile, WSEvent } from '../types/chat'

// 生成简单的 UUID
const generateId = () => Math.random().toString(36).substring(2, 15)

const nodeMap: Record<string, string> = {
  'intent_node': '意图解析',
  'research_agent': '全网搜索',
  'enrichment_agent': '地理/热度增强',
  'content_node': '文案创作',
  'style_node': '视觉渲染',
  'structure_node': '结构布局',
  'asset_node': '素材调度'
}

const pickCheckpointId = (data: Record<string, any>) => data.checkpoint_id ?? data.checkpointId ?? null
const pickOssUrl = (data: Record<string, any>) => data.oss_url ?? data.ossUrl ?? null
const pickPageData = (data: Record<string, any>) => data.page_data ?? data.pageData ?? data.noteData ?? {}
const pickStyleData = (data: Record<string, any>) => data.style_data ?? data.styleData ?? {}
const pickNodePrompts = (data: Record<string, any>) => data.node_prompts ?? data.nodePrompts ?? {}
const pickImageAssets = (data: Record<string, any>) => data.image_assets ?? data.imageAssets ?? []
const pickSourceCode = (data: Record<string, any>) => data.source_code ?? data.sourceCode ?? data.htmlPreview ?? ''
const showcaseEnabled = import.meta.env.VITE_ENABLE_SHOWCASE === 'true'
const DEFAULT_ASSISTANT_RESULT_TEXT = '页面已更新，可以在右侧预览继续查看和编辑。'
const THREAD_STORAGE_KEY = 'xhs_forge_active_thread'

const componentLabelMap: Record<string, string> = {
  CoverSwiper: '封面轮播',
  VersusCard: '对比卡',
  PollBlock: '投票卡',
  RadarChartBlock: '雷达图',
  ProductSpecCard: '参数卡',
  StoryText: '正文区',
  TitleBlock: '标题块',
  LocationBlock: '地点卡',
  WeatherPolaroid: '氛围图卡',
}

const dedupeImageAssets = (assets: ImageAsset[]) => {
  const deduped = new Map<string, ImageAsset>()
  for (const asset of assets || []) {
    if (!asset?.url) continue
    const existing = deduped.get(asset.url)
    deduped.set(asset.url, {
      ...(existing || {}),
      ...asset,
      desc: asset.desc || existing?.desc || '素材图',
    })
  }
  return Array.from(deduped.values())
}

const normalizeSnapshotMessages = (rawMessages: Array<Record<string, any>> = []) =>
  rawMessages.map((msg) => {
    if (msg.role !== 'user') return { ...msg, content: String(msg.content || '') }
    if (Array.isArray(msg.content)) {
      const text = msg.content
        .filter((part: Record<string, any>) => part?.type === 'text' && part?.text)
        .map((part: Record<string, any>) => String(part.text))
        .join('')
      const imageUrls = msg.content
        .filter((part: Record<string, any>) => part?.type === 'image_url' && part?.image_url?.url)
        .map((part: Record<string, any>) => String(part.image_url.url))
      return { ...msg, content: text, imageUrls }
    }
    return { ...msg, content: String(msg.content || '') }
  })

const hydrateSnapshotMessages = (
  snapshotMessages: ChatMessage[],
  existingMessages: ChatMessage[],
) => {
  const usedIndexes = new Set<number>()

  return snapshotMessages.map((msg) => {
    const matchIndex = existingMessages.findIndex((existing, idx) => {
      if (usedIndexes.has(idx)) return false
      if (existing.role !== msg.role) return false
      if ((existing.content || '') && (msg.content || '') && existing.content !== msg.content) return false
      return true
    })

    if (matchIndex === -1) {
      return {
        ...msg,
        id: generateId(),
        timestamp: msg.timestamp || Date.now(),
      }
    }

    usedIndexes.add(matchIndex)
    const existing = existingMessages[matchIndex]
    return {
      ...existing,
      ...msg,
      id: existing.id || msg.id || generateId(),
      timestamp: existing.timestamp || msg.timestamp || Date.now(),
      imageUrls: msg.imageUrls || existing.imageUrls,
      thoughts: existing.thoughts,
      checkpointId: existing.checkpointId,
      ossUrl: existing.ossUrl,
      pageData: existing.pageData,
      styleData: existing.styleData,
      nodePrompts: existing.nodePrompts,
      imageAssets: existing.imageAssets,
      sourceCode: existing.sourceCode,
      streaming: false,
    } satisfies ChatMessage
  })
}

const getBlockList = (page?: Record<string, any> | null) =>
  (Array.isArray(page?.blocks) ? page?.blocks : []) as Array<Record<string, any>>

const getBlockTypeById = (page: Record<string, any> | null | undefined, blockId: string) => {
  const block = getBlockList(page).find(item => item?.id === blockId)
  return String(block?.component_type || '')
}

const getCoverUrl = (page?: Record<string, any> | null) => {
  const coverBlock = getBlockList(page).find(block => block?.component_type === 'CoverSwiper')
  if (!coverBlock?.id) return ''
  const payload = (page || {})[coverBlock.id] as Record<string, any> | undefined
  return String(payload?.image_urls?.[0] || payload?.image_url || '')
}

const hasBlockType = (page: Record<string, any> | null | undefined, componentType: string) =>
  getBlockList(page).some(block => String(block?.component_type || '') === componentType)

const getThemeSignature = (page?: Record<string, any> | null) =>
  JSON.stringify((page?.page_theme || {}) as Record<string, any>)

const pickContentSignature = (payload: Record<string, any> | null | undefined) => {
  if (!payload) return ''
  if (Array.isArray(payload.paragraphs)) return JSON.stringify(payload.paragraphs)
  if (typeof payload.question === 'string') return `${payload.question}|${payload.option_a || ''}|${payload.option_b || ''}`
  if (typeof payload.proText === 'string' || typeof payload.conText === 'string') return `${payload.proText || ''}|${payload.conText || ''}`
  if (typeof payload.title === 'string') return payload.title
  return ''
}

const buildAssistantResultText = (page: Record<string, any>, previousPage?: Record<string, any> | null, userText = '') => {
  const blocks = getBlockList(page)
  if (!blocks.length) return DEFAULT_ASSISTANT_RESULT_TEXT

  const currentTypes = blocks
    .map((block: Record<string, any>) => String(block?.component_type || ''))
    .filter(Boolean)
  const currentLabels = currentTypes
    .map(type => componentLabelMap[type] || type)
    .filter(Boolean)

  const previousBlocks = getBlockList(previousPage)
  const previousTypes = previousBlocks
    .map((block: Record<string, any>) => String(block?.component_type || ''))
    .filter(Boolean)

  const currentIds = blocks.map(block => String(block?.id || '')).filter(Boolean)
  const previousIds = previousBlocks.map(block => String(block?.id || '')).filter(Boolean)
  const addedIds = currentIds.filter(id => !previousIds.includes(id))
  const removedIds = previousIds.filter(id => !currentIds.includes(id))

  for (const id of currentIds) {
    if (!previousIds.includes(id)) continue
    const previousType = getBlockTypeById(previousPage || {}, id)
    const currentType = getBlockTypeById(page, id)
    if (previousType && currentType && previousType !== currentType) {
      return `页面已更新，已将${componentLabelMap[previousType] || previousType}替换为${componentLabelMap[currentType] || currentType}。`
    }
  }

  const previousCoverUrl = getCoverUrl(previousPage)
  const currentCoverUrl = getCoverUrl(page)
  if (currentCoverUrl && currentCoverUrl !== previousCoverUrl) {
    return previousCoverUrl
      ? `页面已更新，封面图已替换，当前共 ${blocks.length} 个区块。`
      : `页面已更新，已添加封面图，当前共 ${blocks.length} 个区块。`
  }

  if (removedIds.length) {
    const removedType = getBlockTypeById(previousPage || {}, removedIds[0])
    const stillHasSameType = removedType ? hasBlockType(page, removedType) : false
    if (!stillHasSameType) {
      return `页面已更新，删除了${componentLabelMap[removedType] || removedType || '一个区块'}，当前共 ${blocks.length} 个区块。`
    }
  }

  if (getThemeSignature(page) !== getThemeSignature(previousPage)) {
    if (/(灰蓝|主题|风格|配色|色调)/.test(userText)) {
      return `页面已更新，已按你的要求切换页面主题，当前共 ${blocks.length} 个区块。`
    }
    return `页面已更新，已切换页面主题，当前共 ${blocks.length} 个区块。`
  }

  for (const id of currentIds) {
    if (!previousIds.includes(id)) continue
    const prevPayload = (previousPage || {})[id] as Record<string, any> | undefined
    const nextPayload = (page || {})[id] as Record<string, any> | undefined
    const prevSig = pickContentSignature(prevPayload)
    const nextSig = pickContentSignature(nextPayload)
    if (prevSig && nextSig && prevSig !== nextSig) {
      const blockType = getBlockTypeById(page, id)
      if (/(毒舌|尖锐|重写|润色|改写|文案)/.test(userText)) {
        return `页面已更新，已按你的要求调整${componentLabelMap[blockType] || blockType || '区块'}的文案内容。`
      }
      return `页面已更新，已调整${componentLabelMap[blockType] || blockType || '区块'}的文案内容。`
    }
  }

  const addedType = addedIds.length
    ? getBlockTypeById(page, addedIds[0])
    : currentTypes.find(type => !previousTypes.includes(type))
  if (addedType) {
    return `页面已更新，新增了${componentLabelMap[addedType] || addedType}，当前共 ${blocks.length} 个区块。`
  }

  const firstTwo = currentLabels.slice(0, 2).join('、')
  if (firstTwo) {
    return `页面已更新，当前共 ${blocks.length} 个区块，包含 ${firstTwo}。`
  }

  return `页面已更新，当前共 ${blocks.length} 个区块。`
}

const getConfiguredApiBase = () => {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (configured && typeof configured === 'string') {
    return configured.replace(/\/$/, '')
  }
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8000'
  }
  return ''
}

const toWsBase = (httpBase: string) => {
  if (!httpBase) return ''
  if (httpBase.startsWith('https://')) return `wss://${httpBase.slice('https://'.length)}`
  if (httpBase.startsWith('http://')) return `ws://${httpBase.slice('http://'.length)}`
  return httpBase
}

const normalizeShowcaseProfile = (profile: Record<string, any>): ShowcaseProfile => ({
  id: profile.id,
  scenarioId: profile.scenario_id ?? profile.scenarioId ?? '',
  title: profile.title ?? '',
  persona: profile.persona ?? '硬核数码博主',
  whyThisMatters: profile.why_this_matters ?? profile.whyThisMatters ?? '',
  highlightFeatures: profile.highlight_features ?? profile.highlightFeatures ?? [],
  talkingPoints: profile.talking_points ?? profile.talkingPoints ?? [],
  demoScript: profile.demo_script ?? profile.demoScript ?? [],
  starterPrompt: profile.starter_prompt ?? profile.starterPrompt ?? '',
  editPrompt: profile.edit_prompt ?? profile.editPrompt ?? '',
  themePrompt: profile.theme_prompt ?? profile.themePrompt ?? '',
  branchPrompt: profile.branch_prompt ?? profile.branchPrompt ?? ''
})

export const useChatStore = defineStore('chat', () => {
  // === State (状态) ===
  const threadId = ref<string>('') 
  const sessions = ref<any[]>([])
  const isSidebarOpen = ref(true)
  const messages = ref<ChatMessage[]>([])
  const previewUrl = ref<string | null>(null)
  const wsStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const currentNode = ref<string>('')
  const thoughtText = ref<string>('')
  const nodeStreamOutput = ref<string>('')
  const activePanel = ref<string>('main')
  const selectedComponentId = ref<string | null>(null)
  const selectedParagraphIndex = ref<number | null>(null)
  const composerDraft = ref<string>('')
  const imageAssets = ref<ImageAsset[]>([])
  const pageData = ref<Record<string, unknown>>({})
  const styleData = ref<Record<string, unknown>>({})
  const sourceCode = ref<string>('')
  const nodePrompts = ref<Record<string, string>>({})
  const pendingUploadUrls = ref<string[]>([])
  const showcaseProfiles = ref<ShowcaseProfile[]>([])
  const searchedAssets = ref<ImageAsset[]>([])
  const assetSearchLoading = ref(false)
  const factConfirmingField = ref<string | null>(null)
  const hoveredComponentId = ref<string | null>(null)
  const activeCheckpointId = ref<string | null>(null)
  const creatorPersona = ref<string>("硬核数码博主")
  const hotTrends = ref<string[]>([]) // ✨ 哨兵新增：热词排行榜
  
  // ✨ 哨兵白盒化：Agent 决策元数据
  const agentMeta = ref({
    creator_persona: '',
    active_archetype: '',
    intent_route: '',
    retrieved_knowledge: {},
    scenarios: [],
    has_controversy: false,
    needs_disambiguation: false
  })

  let ws: WebSocket | null = null
  let renderRecoveryTimer: number | null = null

  // === Actions (动作) ===

  const persistActiveThread = (nextThreadId: string) => {
    if (!nextThreadId) return
    try {
      window.localStorage.setItem(THREAD_STORAGE_KEY, nextThreadId)
      const url = new URL(window.location.href)
      url.searchParams.set('thread', nextThreadId)
      window.history.replaceState({}, '', url.toString())
    } catch (e) {
      console.warn('持久化当前线程失败:', e)
    }
  }

  const getPreferredThreadId = () => {
    try {
      const url = new URL(window.location.href)
      const fromQuery = url.searchParams.get('thread')
      if (fromQuery) return fromQuery
      return window.localStorage.getItem(THREAD_STORAGE_KEY) || ''
    } catch {
      return ''
    }
  }

  const ensureAssistantResultMessage = (page?: Record<string, any>, previousPage?: Record<string, any> | null) => {
    const lastMsg = messages.value[messages.value.length - 1]
    if (!lastMsg || lastMsg.role !== 'assistant') return
    if ((lastMsg.content || '').trim()) return
    const lastUserText = [...messages.value].reverse().find(msg => msg.role === 'user')?.content || ''
    lastMsg.content = buildAssistantResultText(page || (pageData.value as Record<string, any>), previousPage || null, lastUserText)
    lastMsg.streaming = false
  }

  const applyWorkspaceSnapshot = (
    data: Record<string, any>,
    options?: { preserveLocalAssistant?: boolean }
  ) => {
    const preserveLocalAssistant = options?.preserveLocalAssistant === true
    const previousPage = pageData.value as Record<string, any>
    const nextPage = data.data_dsl || data.pageData || {}
    const snapshotMessages = hydrateSnapshotMessages(
      normalizeSnapshotMessages(data.messages?.main || []) as ChatMessage[],
      preserveLocalAssistant ? messages.value : []
    )
    const snapshotHasAssistant = Array.isArray(snapshotMessages)
      && snapshotMessages.some((msg: Record<string, any>) => msg.role === 'assistant' || msg.role === 'system')
    if (!preserveLocalAssistant || snapshotHasAssistant || messages.value.length === 0) {
      messages.value = snapshotMessages || []
    } else if (Array.isArray(snapshotMessages) && snapshotMessages.length > messages.value.length) {
      messages.value = snapshotMessages
    }
    pageData.value = nextPage
    styleData.value = data.style_dsl || data.styleData || {}
    imageAssets.value = dedupeImageAssets(data.image_assets || data.imageAssets || [])
    nodePrompts.value = data.node_prompts || data.nodePrompts || {}
    previewUrl.value = data.oss_url || data.ossUrl || null
    sourceCode.value = data.source_code || data.sourceCode || ''
    activeCheckpointId.value = data.checkpoints?.[0]?.checkpoint_id || data.checkpoint_id || data.checkpointId || activeCheckpointId.value
    if (!snapshotHasAssistant && (Object.keys(nextPage || {}).length > 0 || sourceCode.value)) {
      messages.value = [
        ...messages.value,
        {
          id: generateId(),
          role: 'assistant',
          content: buildAssistantResultText(nextPage, previousPage, [...messages.value].reverse().find(msg => msg.role === 'user')?.content || ''),
          timestamp: Date.now(),
        },
      ]
    }
    if (Object.keys(pageData.value || {}).length > 0 || sourceCode.value) {
      ensureAssistantResultMessage(nextPage, previousPage)
    }
  }

  const clearRenderRecoveryTimer = () => {
    if (renderRecoveryTimer !== null) {
      window.clearTimeout(renderRecoveryTimer)
      renderRecoveryTimer = null
    }
  }

  const recoverFromWorkspaceSnapshot = async () => {
    if (!threadId.value) return false
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      applyWorkspaceSnapshot(data, { preserveLocalAssistant: true })
      currentNode.value = ''
      thoughtText.value = ''
      nodeStreamOutput.value = ''
      return true
    } catch (e) {
      console.error('兜底拉取工作台快照失败:', e)
      return false
    }
  }

  const syncWorkspaceAfterTurnEnd = async () => {
    if (!threadId.value) return false
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      applyWorkspaceSnapshot(data, { preserveLocalAssistant: true })
      return true
    } catch (e) {
      console.warn('turn_end 后同步 workspace 快照失败:', e)
      return false
    }
  }

  const scheduleRenderRecovery = () => {
    clearRenderRecoveryTimer()
    renderRecoveryTimer = window.setTimeout(async () => {
      if (currentNode.value !== 'render') return
      console.warn('⚠️ render 收尾超时，尝试主动拉取 workspace 快照恢复前端')
      await recoverFromWorkspaceSnapshot()
      clearRenderRecoveryTimer()
    }, 3500)
  }

  // 拉取 Agent 内部状态 (白盒探针)
  const fetchAgentMeta = async () => {
    if (!threadId.value) return
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}/inspect`)
      const data = await res.json()
      if (data.status === 'success') {
        agentMeta.value = data.data
      }
    } catch (e) {
      console.error('获取 Agent 状态失败:', e)
    }
  }

  // ✨ 哨兵新增：主动追踪话题
  const trackTrend = async (keyword: string) => {
    try {
      const baseUrl = getBaseUrl('http')
      await fetch(`${baseUrl}/workspace/trends/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword })
      })
      await fetchTrends() // 刷新列表
    } catch (e) {
      console.error('追踪失败:', e)
    }
  }

  // ✨ 哨兵新增：原子级单组件回溯
  const rollbackComponent = async (elementId: string, versionIndex: number) => {
    if (!threadId.value) return
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}/rollback/component`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ element_id: elementId, version_index: versionIndex })
      })
      const data = await res.json()
      if (data.status === 'success') {
        // 重新拉取最新状态以同步预览
        await switchSession(threadId.value)
      }
    } catch (e) {
      console.error('原子回溯失败:', e)
    }
  }

  const getBaseUrl = (protocol: 'http' | 'ws' = 'http') => {
    const httpBase = getConfiguredApiBase()
    if (httpBase) {
      return protocol === 'ws' ? toWsBase(httpBase) : httpBase
    }
    const pageProtocol = window.location.protocol === 'https:' ? 'https' : 'http'
    const wsProtocol = pageProtocol === 'https' ? 'wss' : 'ws'
    const host = `${window.location.hostname}:8000`
    return protocol === 'ws' ? `${wsProtocol}://${host}` : `${pageProtocol}://${host}`
  }

  // ✨ 哨兵新增：从后端拉取实时热点
  const fetchTrends = async () => {
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/trends`)
      const data = await res.json()
      hotTrends.value = data.trends || []
    } catch (e) {
      console.error('获取热词失败:', e)
    }
  }

  const fetchSessions = async () => {
    try {
      fetchTrends() // ✨ 初始化时同步拉取热词
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/sessions`)
      const data = await res.json()
      sessions.value = data.sessions || []
      const preferredThreadId = getPreferredThreadId()
      
      if (sessions.value.length > 0) {
        if (!threadId.value) {
          const matched = sessions.value.find((session) => session.thread_id === preferredThreadId)
          await switchSession((matched || sessions.value[0]).thread_id)
        }
      } else {
        createNewSession()
      }
    } catch (e) {
      console.error('获取会话列表失败:', e)
      if (!threadId.value) createNewSession()
    }
  }

  const fetchShowcaseProfiles = async () => {
    if (!showcaseEnabled) {
      showcaseProfiles.value = []
      return
    }
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/showcase/profiles`)
      const data = await res.json()
      showcaseProfiles.value = (data.profiles || []).map((profile: Record<string, any>) =>
        normalizeShowcaseProfile(profile)
      )
    } catch (e) {
      console.error('获取 showcase 场景失败:', e)
    }
  }

  const switchSession = async (newThreadId: string, options?: { force?: boolean }) => {
    const force = options?.force === true
    const sameThread = threadId.value === newThreadId
    if (!force && sameThread && wsStatus.value === 'connected') return
    
    if (ws && (!force || !sameThread)) {
      ws.onclose = null 
      ws.close()
      ws = null
    }
    
    threadId.value = newThreadId
    persistActiveThread(newThreadId)
    if (!force || !sameThread) {
      wsStatus.value = 'disconnected'
    }
    currentNode.value = ''
    thoughtText.value = ''
    nodeStreamOutput.value = ''
    selectedComponentId.value = null
    selectedParagraphIndex.value = null
    
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${newThreadId}`)
      const data = await res.json()
      applyWorkspaceSnapshot(data, { preserveLocalAssistant: false })
      
      fetchAgentMeta()
      if (!force || !ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket()
      }
    } catch (e) {
      console.error('切换会话失败:', e)
      fetchAgentMeta()
      if (!force || !ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket()
      }
    }
  }

  const createNewSession = () => {
    const newId = `thread_${generateId()}`

    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }

    threadId.value = newId
    persistActiveThread(newId)
    wsStatus.value = 'disconnected'
    messages.value = []
    pageData.value = {}
    styleData.value = {}
    nodePrompts.value = {}
    previewUrl.value = null
    sourceCode.value = ''
    imageAssets.value = []
    activeCheckpointId.value = null
    selectedComponentId.value = null
    selectedParagraphIndex.value = null
    hoveredComponentId.value = null
    currentNode.value = ''
    thoughtText.value = ''
    nodeStreamOutput.value = ''
    
    sessions.value.unshift({
      thread_id: newId,
      title: '新的种草页面',
      updated_at: new Date().toISOString()
    })
    
    connectWebSocket()
  }

  const waitForWebSocketReady = async (timeoutMs = 8000) => {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
      if (wsStatus.value === 'connected' && ws && ws.readyState === WebSocket.OPEN) return true
      await new Promise(resolve => setTimeout(resolve, 120))
    }
    return false
  }

  const startShowcaseDemo = async (profile: ShowcaseProfile) => {
    if (!showcaseEnabled) return false
    setCreatorPersona(profile.persona)
    createNewSession()
    const connected = await waitForWebSocketReady()
    if (!connected) {
      console.error('Showcase 演示启动失败: WebSocket 未连接')
      return false
    }
    sendMessage(profile.starterPrompt)
    return true
  }

  const searchAssetImages = async (query: string) => {
    const finalQuery = query.trim()
    if (!threadId.value || !finalQuery) {
      searchedAssets.value = []
      return []
    }
    assetSearchLoading.value = true
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(
        `${baseUrl}/workspace/${threadId.value}/assets/search?query=${encodeURIComponent(finalQuery)}`
      )
      const data = await res.json()
      searchedAssets.value = data.results || []
      return searchedAssets.value
    } catch (e) {
      console.error('素材搜索失败:', e)
      searchedAssets.value = []
      return []
    } finally {
      assetSearchLoading.value = false
    }
  }

  const importAssetToLibrary = async (asset: ImageAsset) => {
    if (!threadId.value) return false
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}/assets/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asset)
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!imageAssets.value.some(existing => existing.url === asset.url)) {
        imageAssets.value = dedupeImageAssets([...imageAssets.value, asset])
      }
      await switchSession(threadId.value, { force: true })
      return true
    } catch (e) {
      console.error('加入资产池失败:', e)
      return false
    }
  }

  const applyCoverAssetLocally = (asset: ImageAsset) => {
    const currentPage = (pageData.value || {}) as Record<string, any>
    const blocks = Array.isArray(currentPage.blocks) ? [...currentPage.blocks] : []
    let coverBlock = blocks.find(block => block.component_type === 'CoverSwiper')
    let nextPage = { ...currentPage }

    if (!coverBlock) {
      coverBlock = {
        id: `cover_local_${Math.random().toString(36).slice(2, 8)}`,
        component_type: 'CoverSwiper',
        props: {},
      }
      blocks.unshift(coverBlock)
      nextPage = { ...nextPage, blocks }
    }

    nextPage = {
      ...nextPage,
      blocks,
      [coverBlock.id]: {
        ...(nextPage[coverBlock.id] || {}),
        type: 'CoverSwiper',
        image_urls: [asset.url],
      },
    }
    pageData.value = nextPage
  }

  const setAssetAsCover = async (asset: ImageAsset) => {
    if (!threadId.value) return false
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}/assets/cover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(asset)
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      if (!imageAssets.value.some(existing => existing.url === asset.url)) {
        imageAssets.value = dedupeImageAssets([...imageAssets.value, asset])
      }
      applyCoverAssetLocally(asset)
      await switchSession(threadId.value, { force: true })
      return true
    } catch (e) {
      console.error('设为封面失败:', e)
      return false
    }
  }

  const confirmFactValue = async (field: string, value: string, sources: string[] = []) => {
    if (!threadId.value || !field || !value) return false
    factConfirmingField.value = field
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/${threadId.value}/facts/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value, sources }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await switchSession(threadId.value, { force: true })
      await fetchAgentMeta()
      messages.value.push({
        id: generateId(),
        role: 'system',
        content: `已确认 ${field} = ${value}，后续生成会优先沿用这个事实。`,
        timestamp: Date.now(),
      })
      return true
    } catch (e) {
      console.error('确认事实失败:', e)
      return false
    } finally {
      factConfirmingField.value = null
    }
  }

  const setSelectedComponent = (id: string | null, paragraphIndex: number | null = null) => {
    selectedComponentId.value = id
    selectedParagraphIndex.value = paragraphIndex
  }

  const setComposerDraft = (value: string) => {
    composerDraft.value = value
  }

  const setCreatorPersona = (persona: string) => {
    creatorPersona.value = persona
  }

  const setHoveredComponent = (id: string | null) => {
    hoveredComponentId.value = id
  }

  const addImageAsset = (asset: ImageAsset) => {
    imageAssets.value = dedupeImageAssets([...imageAssets.value, asset])
  }

  const addPendingUploadAsset = (asset: ImageAsset) => {
    imageAssets.value = dedupeImageAssets([...imageAssets.value, asset])
    if (asset.url && !pendingUploadUrls.value.includes(asset.url)) {
      pendingUploadUrls.value = [...pendingUploadUrls.value, asset.url]
    }
  }

  const removeImageAsset = (index: number) => {
    imageAssets.value = imageAssets.value.filter((_, i) => i !== index)
  }

  const setImageAssets = (list: ImageAsset[]) => {
    imageAssets.value = dedupeImageAssets(list)
  }

  const connectWebSocket = () => {
    if (ws && ws.readyState === WebSocket.OPEN) return
    if (!threadId.value) return

    wsStatus.value = 'connecting'
    const baseUrl = getBaseUrl('ws')
    const wsUrl = `${baseUrl}/ws/chat/${threadId.value}`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      wsStatus.value = 'connected'
      console.log('🟢 WebSocket 已连接')
    }

    ws.onmessage = (event) => {
      try {
        const data: WSEvent = JSON.parse(event.data)
        handleWsEvent(data)
      } catch (e) {
        console.error('WebSocket 消息解析失败:', e)
      }
    }

    ws.onclose = () => {
      wsStatus.value = 'disconnected'
      console.log('🔴 WebSocket 已断开，尝试重连...')
      setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      ws?.close()
    }
  }

  const handleWsEvent = (wsData: WSEvent) => {
    const lastMsg = messages.value[messages.value.length - 1]
    const isAssistant = lastMsg && lastMsg.role === 'assistant'

    const eventType = wsData.event || wsData.type
    const data = wsData.data || wsData

    switch (eventType) {
      case 'middleware':
        if (currentNode.value !== wsData.node) {
           nodeStreamOutput.value = ''
        }
        currentNode.value = wsData.node || ''
        if (currentNode.value === 'render') {
          scheduleRenderRecovery()
        }
        break

      case 'thought':
        thoughtText.value = data
        nodeStreamOutput.value = ''
        if (currentNode.value === 'render' || thoughtText.value.includes('云端打包渲染')) {
          scheduleRenderRecovery()
        }
        break

      case 'thought_process':
        if (isAssistant) {
          if (!lastMsg.thoughts) lastMsg.thoughts = []
          const nodeName = data.node
          const nodeLabel = nodeMap[nodeName] || nodeName
          const existingIdx = lastMsg.thoughts.findIndex(t => t.node === nodeLabel)
          if (existingIdx !== -1) {
            lastMsg.thoughts[existingIdx] = { node: nodeLabel, text: data.content, streaming: false }
          } else {
            lastMsg.thoughts.push({ node: nodeLabel, text: data.content, streaming: false })
          }
        }
        break

      case 'token':
        const content = typeof data === 'string' ? data : (wsData.content || '')
        const sourceNode = wsData.node || currentNode.value
        
        if (sourceNode && !['content_node', 'direct_chat_node', 'rag_node'].includes(sourceNode)) {
          nodeStreamOutput.value += content
          const buffer = nodeStreamOutput.value
          const marker = '"thought_process":'
          const startIdx = buffer.indexOf(marker)
          
          if (startIdx !== -1 && isAssistant) {
            if (!lastMsg.thoughts) lastMsg.thoughts = []
            const nodeLabel = nodeMap[sourceNode] || sourceNode
            let extracted = ''
            const afterMarker = buffer.substring(startIdx + marker.length).trim()
            if (afterMarker.startsWith('"')) {
              const contentStart = afterMarker.indexOf('"') + 1
              const remaining = afterMarker.substring(contentStart)
              const match = remaining.match(/^((?:[^"\\]|\\.)*)/)
              if (match) {
                extracted = match[1].replace(/\\n/g, '\n').replace(/\\"/g, '"')
              }
            }

            if (extracted) {
              const existingIdx = lastMsg.thoughts.findIndex(t => t.node === nodeLabel)
              if (existingIdx !== -1) {
                lastMsg.thoughts[existingIdx].text = extracted
                lastMsg.thoughts[existingIdx].streaming = true
              } else {
                lastMsg.thoughts.push({ node: nodeLabel, text: extracted, streaming: true })
              }
            }
          }
        } else if (isAssistant && content) {
          lastMsg.content += content
        }
        break

      case 'turn_end':
        clearRenderRecoveryTimer()
        const previousPage = pageData.value as Record<string, any>
        currentNode.value = ''
        thoughtText.value = ''
        nodeStreamOutput.value = ''
        const checkpointId = pickCheckpointId(data)
        const ossUrl = pickOssUrl(data)
        const nextPageData = pickPageData(data)
        const nextStyleData = pickStyleData(data)
        const nextNodePrompts = pickNodePrompts(data)
        const nextImageAssets = pickImageAssets(data)
        const nextSourceCode = pickSourceCode(data)
        if (isAssistant) {
          lastMsg.streaming = false
          lastMsg.checkpointId = checkpointId ?? undefined
          lastMsg.ossUrl = ossUrl ?? undefined
          lastMsg.pageData = nextPageData
          lastMsg.styleData = nextStyleData
          lastMsg.nodePrompts = nextNodePrompts
          lastMsg.imageAssets = nextImageAssets
          lastMsg.sourceCode = nextSourceCode
          activeCheckpointId.value = checkpointId
        }
        if (ossUrl) previewUrl.value = ossUrl
        pageData.value = nextPageData
        styleData.value = nextStyleData
        nodePrompts.value = nextNodePrompts
        imageAssets.value = dedupeImageAssets(nextImageAssets)
        sourceCode.value = nextSourceCode
        if ((Object.keys(nextPageData || {}).length > 0 || nextSourceCode) && isAssistant && !(lastMsg.content || '').trim()) {
          const lastUserText = [...messages.value].reverse().find(msg => msg.role === 'user')?.content || ''
          lastMsg.content = buildAssistantResultText(nextPageData, previousPage, lastUserText)
        }
        
        // ✨ 哨兵自动化：生成结束后，立即拉取 Agent 脑电图
        fetchAgentMeta()
        window.setTimeout(() => {
          void syncWorkspaceAfterTurnEnd()
        }, 120)
        break

      case 'action_required':
        clearRenderRecoveryTimer()
        if (isAssistant) {
          lastMsg.streaming = false
          lastMsg.content += `\n\n📢 ${data.message}`
        }
        break

      case 'error':
        clearRenderRecoveryTimer()
        currentNode.value = ''
        thoughtText.value = ''
        nodeStreamOutput.value = ''
        const errMsg = typeof data === 'string' ? data : (wsData.message || '未知错误')
        if (isAssistant) {
          lastMsg.content += `\n\n[❌ 系统报错]: ${errMsg}`
          lastMsg.streaming = false
        }
        break
    }
  }

  const rollbackTo = (checkpointId: string) => {
    const idx = messages.value.findIndex(m => m.checkpointId === checkpointId)
    if (idx === -1) return
    messages.value = messages.value.slice(0, idx + 1)
    const targetMsg = messages.value[idx]
    activeCheckpointId.value = targetMsg.checkpointId ?? null
    previewUrl.value = targetMsg.ossUrl ?? null
    pageData.value = targetMsg.pageData ?? {}
    styleData.value = targetMsg.styleData ?? {}
    nodePrompts.value = targetMsg.nodePrompts ?? {}
    imageAssets.value = targetMsg.imageAssets ?? []
    sourceCode.value = targetMsg.sourceCode ?? ''
    messages.value.push({
      id: generateId(),
      role: 'system',
      content: `已回退至历史版本 (ID: ${checkpointId.slice(0,6)}...)`,
      timestamp: Date.now()
    })
  }

  const sendMessage = (content: string, options?: { imageUrls?: string[] }) => {
    const assets = imageAssets.value
    if ((!content.trim() && assets.length === 0) || wsStatus.value !== 'connected') return

    const stagedImageUrls = (options?.imageUrls || pendingUploadUrls.value).filter(Boolean)
    const currentUrls = assets.map(a => a.url)

    messages.value.push({
      id: generateId(),
      role: 'user',
      content,
      imageUrls: stagedImageUrls,
      timestamp: Date.now()
    })

    messages.value.push({
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true
    })

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        content,
        panel: activePanel.value,
        parent_checkpoint_id: activeCheckpointId.value,
        selected_element_id: selectedComponentId.value,
        creator_persona: creatorPersona.value,
        current_assets: assets,
        image_urls: stagedImageUrls
      }))
      pendingUploadUrls.value = []
    }
  }

  return {
    threadId,
    messages,
    previewUrl,
    wsStatus,
    currentNode,
    nodeStreamOutput,
    activePanel,
    selectedComponentId,
    selectedParagraphIndex,
    composerDraft,
    imageAssets,
    pageData,
    styleData,
    nodePrompts,
    hoveredComponentId,
    activeCheckpointId,
    sourceCode,
    pendingUploadUrls,
    showcaseProfiles,
    searchedAssets,
    assetSearchLoading,
    factConfirmingField,
    showcaseEnabled,
    creatorPersona,
    thoughtText,
    isSidebarOpen,
    sessions,
    agentMeta,
    hotTrends,
    setSelectedComponent,
    setComposerDraft,
    setCreatorPersona,
    setHoveredComponent,
    addImageAsset,
    addPendingUploadAsset,
    removeImageAsset,
    setImageAssets,
    connectWebSocket,
    rollbackTo,
    sendMessage,
    fetchSessions,
    fetchShowcaseProfiles,
    switchSession,
    createNewSession,
    startShowcaseDemo,
    searchAssetImages,
    importAssetToLibrary,
    setAssetAsCover,
    confirmFactValue,
    fetchAgentMeta,
    fetchTrends,
    trackTrend,
    rollbackComponent
  }
})
