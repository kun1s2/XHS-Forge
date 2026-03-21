// src/stores/useChatStore.ts
// Main workspace store: persistent state, websocket/workspace sync, and user actions.
// Pure protocol pickers and derived-data helpers live in `chatStoreDerivations.ts`
// so this file stays focused on orchestration rather than data-shaping details.
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type {
  AgentBackends,
  AgentMeta,
  BenchmarkOverview,
  ChatMessage,
  ImageAsset,
  InspectorSummary,
  NoteDocument,
  NoteDocumentAsset,
  NoteDocumentBlock,
  PlannerOutput,
  PlannerPolicy,
  RetrievedKnowledge,
  ShowcaseProfile,
  TurnTrace,
  WSEvent,
} from '../types/chat'
import {
  buildAssistantResultText,
  dedupeImageAssets,
  getConfiguredApiBase,
  getDocumentBlockById,
  getDocumentPayloadById,
  getDocumentBlocks,
  getPendingFactConflictCount,
  getPreferredBlockById,
  getPreferredCoverUrl,
  getPreferredPatchTracks,
  getPreferredPayloadById,
  getPreferredRenderPageData,
  getPreferredRenderStyleData,
  getPreferredScenarioTags,
  normalizeShowcaseProfile,
  pickAgentBackends,
  pickCheckpointId,
  pickImageAssets,
  pickInspectorSummary,
  pickNodePrompts,
  pickNoteDocument,
  pickOssUrl,
  pickPlannerOutput,
  pickPlannerPolicy,
  pickSourceCode,
  pickTurnTrace,
  resolveComparablePage,
  toWsBase,
} from './chatStoreDerivations'
import { reportFrontendObservation } from '../utils/frontendReport'

// 生成简单的 UUID
const generateId = () => Math.random().toString(36).substring(2, 15)

type SnapshotPart = {
  type?: string
  text?: string
  image_url?: { url?: string }
  [key: string]: unknown
}

const nodeMap: Record<string, string> = {
  'intent_node': '意图解析',
  'research_agent': '全网搜索',
  'enrichment_agent': '地理/热度增强',
  'content_node': '文案创作',
  'style_node': '视觉渲染',
  'structure_node': '结构布局',
  'asset_node': '素材调度'
}

const showcaseEnabled = import.meta.env.VITE_ENABLE_SHOWCASE === 'true'
const THREAD_STORAGE_KEY = 'xhs_forge_active_thread'

const reportUiAction = (threadId: string, eventType: string, message: string, payload: Record<string, unknown> = {}) => {
  void reportFrontendObservation({
    thread_id: threadId || '',
    event_type: eventType,
    message,
    payload,
  })
}

const normalizeSnapshotMessages = (rawMessages: Array<Record<string, unknown>> = []) =>
  rawMessages.map((msg) => {
    if (msg.role !== 'user') return { ...msg, content: String(msg.content || '') }
    if (Array.isArray(msg.content)) {
      const text = msg.content
        .filter((part: SnapshotPart) => part?.type === 'text' && part?.text)
        .map((part: SnapshotPart) => String(part.text))
        .join('')
      const imageUrls = msg.content
        .filter((part: SnapshotPart) => part?.type === 'image_url' && part?.image_url?.url)
        .map((part: SnapshotPart) => String(part.image_url?.url))
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
      nodePrompts: existing.nodePrompts,
      imageAssets: existing.imageAssets,
      sourceCode: existing.sourceCode,
      noteDocument: existing.noteDocument,
      plannerOutput: existing.plannerOutput,
      plannerPolicy: existing.plannerPolicy,
      agentBackends: existing.agentBackends,
      turnTrace: existing.turnTrace,
      streaming: false,
    } satisfies ChatMessage
  })
}

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
  const sourceCode = ref<string>('')
  const nodePrompts = ref<Record<string, unknown>>({})
  const noteDocument = ref<NoteDocument>({})
  const plannerOutput = ref<PlannerOutput>({})
  const plannerPolicy = ref<PlannerPolicy>({})
  const turnTrace = ref<TurnTrace>({})
  const agentBackends = ref<AgentBackends>({})
  const inspectorSummary = ref<InspectorSummary>({})
  const benchmarkOverview = ref<BenchmarkOverview>({})
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
  const agentMeta = ref<AgentMeta>({
    creator_persona: '',
    active_archetype: '',
    intent_route: '',
    retrieved_knowledge: {},
    scenarios: [],
    has_controversy: false,
    needs_disambiguation: false,
    agent_backends: {},
    turn_trace: {},
    inspector_summary: {},
  })
  const pendingFactConflictCount = computed(() =>
    getPendingFactConflictCount(agentMeta.value.retrieved_knowledge || {})
  )
  const documentBlocks = computed(() => getDocumentBlocks(noteDocument.value))
  const documentAssets = computed(() => {
    const assets = noteDocument.value?.assets
    const docAssets = Array.isArray(assets) ? (assets as NoteDocumentAsset[]) : []
    return dedupeImageAssets([...docAssets, ...imageAssets.value])
  })
  const renderPageData = computed(() => getPreferredRenderPageData(noteDocument.value))
  const renderStyleData = computed(() => getPreferredRenderStyleData(noteDocument.value))
  const scenarioTags = computed(() => getPreferredScenarioTags(
    noteDocument.value,
    plannerOutput.value,
    plannerPolicy.value,
  ))
  const patchTracks = computed(() => getPreferredPatchTracks(noteDocument.value))
  const currentCoverUrl = computed(() => getPreferredCoverUrl(
    noteDocument.value,
    documentAssets.value,
  ))
  const selectedBlock = computed(() => {
    if (!selectedComponentId.value) return null
    return getPreferredBlockById(noteDocument.value, selectedComponentId.value)
  })
  const selectedPayload = computed(() => {
    if (!selectedComponentId.value) return {}
    return getPreferredPayloadById(noteDocument.value, selectedComponentId.value)
  })
  const hasRenderableDocument = computed(() => documentBlocks.value.length > 0)

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

  const ensureAssistantResultMessage = (
    doc?: NoteDocument,
    previousDoc?: NoteDocument | null,
  ) => {
    const lastMsg = messages.value[messages.value.length - 1]
    if (!lastMsg || lastMsg.role !== 'assistant') return
    if ((lastMsg.content || '').trim()) return
    const lastUserText = [...messages.value].reverse().find(msg => msg.role === 'user')?.content || ''
    const comparablePage = resolveComparablePage(doc)
    const comparablePrev = resolveComparablePage(previousDoc)
    lastMsg.content = buildAssistantResultText(comparablePage, comparablePrev, lastUserText, agentMeta.value.retrieved_knowledge || {})
    lastMsg.streaming = false
  }

  const applyWorkspaceSnapshot = (
    data: Record<string, any>,
    options?: { preserveLocalAssistant?: boolean }
  ) => {
    const preserveLocalAssistant = options?.preserveLocalAssistant === true
    const previousNoteDocument = noteDocument.value
    const nextNoteDocument = pickNoteDocument(data)
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
    imageAssets.value = dedupeImageAssets((data.image_assets || data.imageAssets || nextNoteDocument?.assets || []) as ImageAsset[])
    nodePrompts.value = data.node_prompts || data.nodePrompts || {}
    noteDocument.value = nextNoteDocument
    plannerOutput.value = pickPlannerOutput(data)
    plannerPolicy.value = pickPlannerPolicy(data)
    turnTrace.value = pickTurnTrace(data)
    agentBackends.value = pickAgentBackends(data)
    inspectorSummary.value = pickInspectorSummary(data)
    previewUrl.value = data.oss_url || data.ossUrl || null
    sourceCode.value = data.source_code || data.sourceCode || ''
    activeCheckpointId.value = data.checkpoints?.[0]?.checkpoint_id || data.checkpoint_id || data.checkpointId || activeCheckpointId.value
    const comparableNextPage = resolveComparablePage(nextNoteDocument)
    const comparablePrevPage = resolveComparablePage(previousNoteDocument)
    if (!snapshotHasAssistant && (Object.keys(comparableNextPage || {}).length > 0 || sourceCode.value)) {
      messages.value = [
        ...messages.value,
        {
          id: generateId(),
          role: 'assistant',
          content: buildAssistantResultText(comparableNextPage, comparablePrevPage, [...messages.value].reverse().find(msg => msg.role === 'user')?.content || '', agentMeta.value.retrieved_knowledge || {}),
          timestamp: Date.now(),
        },
      ]
    }
    if (Object.keys(comparableNextPage || {}).length > 0 || sourceCode.value) {
      ensureAssistantResultMessage(nextNoteDocument, previousNoteDocument)
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
        noteDocument.value = pickNoteDocument(data.data || {})
        plannerOutput.value = pickPlannerOutput(data.data || {})
        plannerPolicy.value = pickPlannerPolicy(data.data || {})
        turnTrace.value = pickTurnTrace(data.data || {})
        agentBackends.value = pickAgentBackends(data.data || {})
        inspectorSummary.value = pickInspectorSummary(data.data || {})
      }
    } catch (e) {
      console.error('获取 Agent 状态失败:', e)
    }
  }

  const fetchBenchmarkOverview = async () => {
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/benchmark/overview`)
      const data = await res.json()
      benchmarkOverview.value = (data?.data || data || {}) as BenchmarkOverview
    } catch (e) {
      console.error('获取 benchmark 概览失败:', e)
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
        reportUiAction(threadId.value, 'workspace_rollback_component', `组件回滚: ${elementId}@${versionIndex}`, { element_id: elementId, version_index: versionIndex })
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
      void fetchBenchmarkOverview()
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
      void fetchBenchmarkOverview()
      if (!force || !ws || ws.readyState !== WebSocket.OPEN) {
        connectWebSocket()
      }
    } catch (e) {
      console.error('切换会话失败:', e)
      fetchAgentMeta()
      void fetchBenchmarkOverview()
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
    nodePrompts.value = {}
    noteDocument.value = {}
    plannerOutput.value = {}
    plannerPolicy.value = {}
    turnTrace.value = {}
    agentBackends.value = {}
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
      const currentDoc = noteDocument.value || {}
      const docAssets = Array.isArray(currentDoc.assets) ? currentDoc.assets : []
      if (!docAssets.some((existing: Record<string, any>) => existing?.url === asset.url)) {
        noteDocument.value = {
          ...currentDoc,
          assets: [
            ...docAssets,
            {
              id: asset.url,
              url: asset.url,
              desc: asset.desc || '素材图',
              source_type: asset.source_type,
              query: asset.query,
              role: asset.role || 'supporting',
              locked: !!asset.locked,
              selection_state: asset.selection_state || 'available',
              source_reason: asset.source_reason || asset.desc || '素材图',
              used_by_blocks: asset.used_by_blocks || [],
            },
          ],
        }
      }
      await switchSession(threadId.value, { force: true })
      reportUiAction(threadId.value, 'workspace_import_asset', `素材入池: ${asset.desc || asset.url}`, { asset_url: asset.url, role: asset.role || 'supporting' })
      return true
    } catch (e) {
      console.error('加入资产池失败:', e)
      return false
    }
  }

  const applyCoverAssetLocally = (asset: ImageAsset) => {
    const currentDoc = noteDocument.value || {}
    const docBlocks = getDocumentBlocks(currentDoc).map(block => ({ ...block }))
    const legacyBlocks = Array.isArray(currentPage.blocks) ? currentPage.blocks : []
    const legacyCoverBlock = legacyBlocks.find((block: Record<string, any>) => block?.component_type === 'CoverSwiper')
    let docCoverBlock = docBlocks.find(block => String(block?.type || '') === 'CoverSwiper')
    if (!docCoverBlock) {
      docCoverBlock = {
        id: String((legacyCoverBlock as Record<string, any> | undefined)?.id || `cover_local_${Math.random().toString(36).slice(2, 8)}`),
        type: 'CoverSwiper',
        content_brief: '封面',
        props: {},
        style: {},
        asset_refs: [],
        fact_bindings: [],
        order: 0,
      }
      docBlocks.unshift(docCoverBlock)
    }

    docCoverBlock.props = {
      ...((docCoverBlock.props || {}) as Record<string, any>),
      type: 'CoverSwiper',
      image_urls: [asset.url],
    }
    docCoverBlock.asset_refs = [asset.url]

    const existingAssets = Array.isArray(currentDoc.assets) ? currentDoc.assets.map((item: Record<string, any>) => ({ ...item })) : []
    const coverBlockId = String(docCoverBlock.id)
    const normalizedAssets = existingAssets
      .filter(item => item?.url)
      .map((item: Record<string, any>) => ({
        ...item,
        role: item.url === asset.url ? 'cover' : (item.role === 'cover' ? 'supporting' : item.role),
        used_by_blocks: item.url === asset.url
          ? Array.from(new Set([...(Array.isArray(item.used_by_blocks) ? item.used_by_blocks : []), coverBlockId]))
          : (Array.isArray(item.used_by_blocks) ? item.used_by_blocks.filter((id: string) => id !== coverBlockId) : []),
      }))

    if (!normalizedAssets.some((item: Record<string, any>) => item.url === asset.url)) {
      normalizedAssets.push({
        id: asset.url,
        url: asset.url,
        desc: asset.desc || '封面图',
        source_type: asset.source_type,
        query: asset.query,
        role: 'cover',
        locked: false,
        selection_state: 'available',
        source_reason: asset.source_reason || asset.desc || '封面图',
        used_by_blocks: [coverBlockId],
      })
    }

    noteDocument.value = {
      ...currentDoc,
      document_meta: {
        ...((currentDoc.document_meta || {}) as Record<string, any>),
        title: (currentDoc.document_meta as any)?.title || 'XHS-Forge Note',
      },
      blocks: docBlocks.map((block, index) => ({ ...block, order: index })),
      assets: normalizedAssets,
      ui_state: {
        ...((currentDoc.ui_state || {}) as Record<string, any>),
        selected_element_id: (currentDoc.ui_state as any)?.selected_element_id || selectedComponentId.value || null,
      },
    }
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
      reportUiAction(threadId.value, 'workspace_set_cover', `设为封面: ${asset.desc || asset.url}`, { asset_url: asset.url })
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
      reportUiAction(threadId.value, 'workspace_confirm_fact', `确认事实: ${field}=${value}`, { field, value, sources })
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
        const previousNoteDocument = noteDocument.value
        currentNode.value = ''
        thoughtText.value = ''
        nodeStreamOutput.value = ''
        const checkpointId = pickCheckpointId(data)
        const ossUrl = pickOssUrl(data)
        const nextNodePrompts = pickNodePrompts(data)
        const nextImageAssets = pickImageAssets(data)
        const nextSourceCode = pickSourceCode(data)
        const nextNoteDocument = pickNoteDocument(data)
        const nextPlannerOutput = pickPlannerOutput(data)
        const nextPlannerPolicy = pickPlannerPolicy(data)
        const nextTurnTrace = pickTurnTrace(data)
        const nextAgentBackends = pickAgentBackends(data)
        if (isAssistant) {
          lastMsg.streaming = false
          lastMsg.checkpointId = checkpointId ?? undefined
          lastMsg.ossUrl = ossUrl ?? undefined
          lastMsg.nodePrompts = nextNodePrompts
          lastMsg.imageAssets = nextImageAssets
          lastMsg.sourceCode = nextSourceCode
          lastMsg.noteDocument = nextNoteDocument
          lastMsg.plannerOutput = nextPlannerOutput
          lastMsg.plannerPolicy = nextPlannerPolicy
          lastMsg.turnTrace = nextTurnTrace
          lastMsg.agentBackends = nextAgentBackends
          activeCheckpointId.value = checkpointId
        }
        if (ossUrl) previewUrl.value = ossUrl
        nodePrompts.value = nextNodePrompts
        imageAssets.value = dedupeImageAssets(nextImageAssets)
        sourceCode.value = nextSourceCode
        noteDocument.value = nextNoteDocument
        plannerOutput.value = nextPlannerOutput
        plannerPolicy.value = nextPlannerPolicy
        turnTrace.value = nextTurnTrace
        agentBackends.value = nextAgentBackends
        const comparableNextPage = resolveComparablePage(nextNoteDocument)
        const comparablePrevPage = resolveComparablePage(previousNoteDocument)
        if ((Object.keys(comparableNextPage || {}).length > 0 || nextSourceCode) && isAssistant && !(lastMsg.content || '').trim()) {
          const lastUserText = [...messages.value].reverse().find(msg => msg.role === 'user')?.content || ''
          lastMsg.content = buildAssistantResultText(comparableNextPage, comparablePrevPage, lastUserText, agentMeta.value.retrieved_knowledge || {})
        }
        
        // ✨ 哨兵自动化：生成结束后，立即拉取 Agent 脑电图
        fetchAgentMeta()
        void fetchBenchmarkOverview()
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
    const targetDoc = (targetMsg.noteDocument || {}) as NoteDocument
    nodePrompts.value = targetMsg.nodePrompts ?? {}
    imageAssets.value = (targetMsg.imageAssets && targetMsg.imageAssets.length > 0) ? targetMsg.imageAssets : dedupeImageAssets(((targetDoc.assets || []) as ImageAsset[]))
    sourceCode.value = targetMsg.sourceCode ?? ''
    noteDocument.value = targetDoc
    plannerOutput.value = targetMsg.plannerOutput ?? {}
    plannerPolicy.value = targetMsg.plannerPolicy ?? {}
    turnTrace.value = targetMsg.turnTrace ?? {}
    agentBackends.value = targetMsg.agentBackends ?? {}
    messages.value.push({
      id: generateId(),
      role: 'system',
      content: `已回退至历史版本 (ID: ${checkpointId.slice(0,6)}...)`,
      timestamp: Date.now()
    })
  }

  const sendMessage = (content: string, options?: { imageUrls?: string[] }) => {
    const assets = documentAssets.value
    const trimmedContent = content.trim()
    const stagedImageUrls = (options?.imageUrls || pendingUploadUrls.value).filter(Boolean)

    if ((!trimmedContent && stagedImageUrls.length === 0) || wsStatus.value !== 'connected') return

    messages.value.push({
      id: generateId(),
      role: 'user',
      content: trimmedContent,
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
        content: trimmedContent,
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
    nodePrompts,
    noteDocument,
    plannerOutput,
    plannerPolicy,
    turnTrace,
    agentBackends,
    inspectorSummary,
    benchmarkOverview,
    documentBlocks,
    documentAssets,
    renderPageData,
    renderStyleData,
    scenarioTags,
    patchTracks,
    currentCoverUrl,
    selectedBlock,
    selectedPayload,
    hasRenderableDocument,
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
    pendingFactConflictCount,
    hotTrends,
    setSelectedComponent,
    setComposerDraft,
    setCreatorPersona,
    setHoveredComponent,
    addImageAsset,
    addPendingUploadAsset,
    removeImageAsset,
    setImageAssets,
    getDocumentBlockById,
    getDocumentPayloadById,
    getPreferredBlockById,
    getPreferredPayloadById,
    getPreferredScenarioTags,
    getPreferredPatchTracks,
    getPreferredCoverUrl,
    getPreferredRenderPageData,
    getPreferredRenderStyleData,
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
    fetchBenchmarkOverview,
    fetchTrends,
    trackTrend,
    rollbackComponent
  }
})
