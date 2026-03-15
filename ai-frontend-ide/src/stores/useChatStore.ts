// src/stores/useChatStore.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, ImageAsset, WSEvent } from '../types/chat'

// 生成简单的 UUID
const generateId = () => Math.random().toString(36).substring(2, 15)

export const useChatStore = defineStore('chat', () => {
  // === State (状态) ===
  const threadId = ref<string>(`thread_${generateId()}`) // 初始化一个会话ID
  const messages = ref<ChatMessage[]>([])
  const previewUrl = ref<string | null>(null) // 右侧 iframe 的预览地址
  const wsStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const currentNode = ref<string>('') // 当前正在执行的 Agent 节点名
  const thoughtText = ref<string>('') // ✨ 新增：当前 Agent 的思考描述
  const nodeStreamOutput = ref<string>('') // 用于实时预览内部节点输出流的状态
  const activePanel = ref<string>('main') // 当前面板
  const selectedComponentId = ref<string | null>(null) // 当前锁定的画布元素
  /** 全局图库资产池 */
  const imageAssets = ref<ImageAsset[]>([])
  /** turn_end 下发的页面结构 data_dsl */
  const pageData = ref<Record<string, unknown>>({})
  /** turn_end 下发的页面样式 style_dsl */
  const styleData = ref<Record<string, unknown>>({})
  /** 当前预览对应的 HTML 源码 */
  const sourceCode = ref<string>('')
  /** ✨ 新增：用于展示各节点提示词的调试状态 */
  const nodePrompts = ref<Record<string, string>>({})
  /** 当前鼠标悬浮的组件 ID */
  const hoveredComponentId = ref<string | null>(null)
  /** 当前激活的时间点 */
  const activeCheckpointId = ref<string | null>(null)
  /** ✨ 创作者人设 */
  const creatorPersona = ref<string>("硬核数码博主")

  // 内部 WebSocket 实例
  let ws: WebSocket | null = null

  // === Actions (动作) ===

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

    wsStatus.value = 'connecting'
    const wsUrl = `ws://127.0.0.1:8000/ws/chat/${threadId.value}`
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

    // 兼容新旧协议：优先取 event，其次取 type
    const eventType = wsData.event || wsData.type
    const data = wsData.data || wsData // 如果是新协议，data 在 wsData.data 里；否则就是整个 wsData

    switch (eventType) {
      case 'middleware':
        if (currentNode.value !== wsData.node) {
           nodeStreamOutput.value = ''
        }
        currentNode.value = wsData.node || ''
        break

      case 'thought':
        // ✨ 新增思考流处理
        thoughtText.value = data
        nodeStreamOutput.value = '' // 切换节点时清空流式输出预览
        break

      case 'token':
        const content = typeof data === 'string' ? data : (wsData.content || '')
        const sourceNode = wsData.node || currentNode.value
        
        if (sourceNode && !['content_node', 'direct_chat_node', 'rag_node'].includes(sourceNode)) {
            nodeStreamOutput.value += content
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
        // ✨ 处理 HITL 立场决策请求
        if (isAssistant) {
          lastMsg.streaming = false
          // 这里可以弹窗或在消息流中插入特殊卡片，目前先简单打印描述
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

    // ✨ 核心修复：提取当前资产池中的所有 URL，传递给后端进行多模态分析
    const currentUrls = assets.map(a => a.url)

    messages.value.push({
      id: generateId(),
      role: 'user',
      content,
      imageUrls: currentUrls, // 在 UI 上显示出来
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
        creator_persona: creatorPersona.value, // ✨ 同步人设到后端
        current_assets: assets,
        image_urls: currentUrls // ✨ 正确传递 URL 数组
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
    setSelectedComponent,
    setCreatorPersona,
    setHoveredComponent,
    addImageAsset,
    removeImageAsset,
    setImageAssets,
    connectWebSocket,
    rollbackTo,
    sendMessage
  }
})