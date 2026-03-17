// src/stores/useChatStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, ImageAsset, WSEvent } from '../types/chat'

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
  const imageAssets = ref<ImageAsset[]>([])
  const pageData = ref<Record<string, unknown>>({})
  const styleData = ref<Record<string, unknown>>({})
  const sourceCode = ref<string>('')
  const nodePrompts = ref<Record<string, string>>({})
  const hoveredComponentId = ref<string | null>(null)
  const activeCheckpointId = ref<string | null>(null)
  const creatorPersona = ref<string>("硬核数码博主")

  let ws: WebSocket | null = null

  // === Actions (动作) ===

  const getBaseUrl = (protocol: 'http' | 'ws' = 'http') => {
    // 假设后端始终在 8000 端口
    const host = `${window.location.hostname}:8000`
    return protocol === 'ws' ? `ws://${host}` : `http://${host}`
  }

  const fetchSessions = async () => {
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/workspace/sessions`)
      const data = await res.json()
      sessions.value = data.sessions || []
      
      if (sessions.value.length > 0) {
        if (!threadId.value) {
          await switchSession(sessions.value[0].thread_id)
        }
      } else {
        createNewSession()
      }
    } catch (e) {
      console.error('获取会话列表失败:', e)
      if (!threadId.value) createNewSession()
    }
  }

  const switchSession = async (newThreadId: string) => {
    if (threadId.value === newThreadId && wsStatus.value === 'connected') return
    
    if (ws) {
      ws.onclose = null 
      ws.close()
      ws = null
    }
    
    threadId.value = newThreadId
    wsStatus.value = 'disconnected'
    
    try {
      const baseUrl = getBaseUrl('http')
      const res = await fetch(`${baseUrl}/${newThreadId}`)
      const data = await res.json()
      
      messages.value = data.messages?.main || []
      pageData.value = data.data_dsl || {}
      styleData.value = data.style_dsl || {}
      previewUrl.value = data.oss_url || null
      sourceCode.value = data.source_code || ''
      activeCheckpointId.value = data.checkpoints?.[0]?.checkpoint_id || null
      
      connectWebSocket()
    } catch (e) {
      console.error('切换会话失败:', e)
      connectWebSocket()
    }
  }

  const createNewSession = () => {
    const newId = `thread_${generateId()}`
    threadId.value = newId
    messages.value = []
    pageData.value = {}
    styleData.value = {}
    previewUrl.value = null
    
    sessions.value.unshift({
      thread_id: newId,
      title: '新的种草页面',
      updated_at: new Date().toISOString()
    })
    
    connectWebSocket()
  }

  const setSelectedComponent = (id: string | null) => {
    selectedComponentId.value = id
  }

  const setCreatorPersona = (persona: string) => {
    creatorPersona.value = persona
  }

  const setHoveredComponent = (id: string | null) => {
    hoveredComponentId.value = id
  }

  const addImageAsset = (asset: ImageAsset) => {
    imageAssets.value = [...imageAssets.value, asset]
  }

  const removeImageAsset = (index: number) => {
    imageAssets.value = imageAssets.value.filter((_, i) => i !== index)
  }

  const setImageAssets = (list: ImageAsset[]) => {
    imageAssets.value = [...list]
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
        break

      case 'thought':
        thoughtText.value = data
        nodeStreamOutput.value = ''
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
        currentNode.value = ''
        thoughtText.value = ''
        nodeStreamOutput.value = ''
        if (isAssistant) {
          lastMsg.streaming = false
          lastMsg.checkpointId = data.checkpoint_id
          lastMsg.ossUrl = data.oss_url
          lastMsg.pageData = data.page_data
          lastMsg.styleData = data.style_data
          lastMsg.nodePrompts = data.node_prompts
          lastMsg.imageAssets = data.image_assets
          lastMsg.sourceCode = data.source_code
          activeCheckpointId.value = data.checkpoint_id ?? null
        }
        if (data.oss_url) previewUrl.value = data.oss_url
        if (data.page_data) pageData.value = data.page_data
        if (data.style_data) styleData.value = data.style_data
        if (data.node_prompts) nodePrompts.value = data.node_prompts
        if (data.image_assets) imageAssets.value = data.image_assets
        if (data.source_code !== undefined) sourceCode.value = data.source_code
        break

      case 'action_required':
        if (isAssistant) {
          lastMsg.streaming = false
          lastMsg.content += `\n\n📢 ${data.message}`
        }
        break

      case 'error':
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

  const sendMessage = (content: string) => {
    const assets = imageAssets.value
    if ((!content.trim() && assets.length === 0) || wsStatus.value !== 'connected') return

    const currentUrls = assets.map(a => a.url)

    messages.value.push({
      id: generateId(),
      role: 'user',
      content,
      imageUrls: currentUrls,
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
        image_urls: currentUrls
      }))
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
    imageAssets,
    pageData,
    styleData,
    nodePrompts,
    hoveredComponentId,
    activeCheckpointId,
    sourceCode,
    creatorPersona,
    thoughtText,
    isSidebarOpen,
    sessions,
    setSelectedComponent,
    setCreatorPersona,
    setHoveredComponent,
    addImageAsset,
    removeImageAsset,
    setImageAssets,
    connectWebSocket,
    rollbackTo,
    sendMessage,
    fetchSessions,
    switchSession,
    createNewSession
  }
})
