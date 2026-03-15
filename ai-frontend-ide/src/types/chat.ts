/** WS 协议与消息类型定义 */

/** 全局图库资产：url + 语义描述，同步到后端 state，生成的页面必须全部使用 */
export interface ImageAsset {
  url: string
  desc: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
  imageUrls?: string[]
  timestamp?: number
  /** 时间胶囊：该轮结束时的世界线 */
  checkpointId?: string
  ossUrl?: string
  pageData?: Record<string, unknown>
  styleData?: Record<string, unknown>
  /** ✨ 调试用：记录该轮对话各节点的提示词输入 */
  nodePrompts?: Record<string, string>
  imageAssets?: ImageAsset[]
  /** 时间胶囊：该轮生成的 HTML 源码 */
  sourceCode?: string
}

export interface WSEvent {
  /** 新版协议：使用 event 和 data */
  event?: 'token' | 'thought' | 'turn_end' | 'error' | 'action_required'
  data?: any
  
  /** 旧版协议兼容 (可选) */
  type?: 'middleware' | 'token' | 'tool_call' | 'turn_end' | 'error'
  node?: string
  content?: string
  checkpoint_id?: string
  oss_url?: string
  message?: string
  image_assets?: ImageAsset[]
  page_data?: Record<string, unknown>
  style_data?: Record<string, unknown>
  node_prompts?: Record<string, string>
  source_code?: string
}

export interface WSPayload {
  content: string
  panel: string
  parent_checkpoint_id?: string | null
  selected_element_id?: string | null
  /** ✨ 创作者人设，同步到后端 state 影响文风 */
  creator_persona?: string | null
  /** 全局图库资产池，每次发信同步到后端 */
  current_assets?: ImageAsset[]
  /** 待打标的新图片 URL，后端塞进 pending_images 由 asset_node 识图后写入图库 */
  image_urls?: string[]
}
