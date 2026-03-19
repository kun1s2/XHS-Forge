/** WS 协议与消息类型定义 */

/** 全局图库资产：url + 语义描述，同步到后端 state，生成的页面必须全部使用 */
export interface ImageAsset {
  url: string
  desc: string
  source_type?: string
  query?: string
  primary_color?: string
  accent_color?: string
}

export interface ShowcaseProfile {
  id: string
  scenarioId: string
  title: string
  persona: string
  whyThisMatters: string
  highlightFeatures: string[]
  talkingPoints: string[]
  demoScript: ShowcaseDemoStep[]
  starterPrompt: string
  editPrompt: string
  themePrompt: string
  branchPrompt: string
}

export interface ShowcaseDemoStep {
  label: string
  goal: string
  action: 'start' | 'fill'
  prompt: string
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
  /** ✨ 思维链实时透传记录 */
  thoughts?: { node: string; text: string; streaming?: boolean }[]
}

export interface WSEvent {
  /** 新版协议：使用 event 和 data */
  event?: 'token' | 'thought' | 'thought_process' | 'turn_end' | 'error' | 'action_required'
  data?: any
  
  /** 旧版协议兼容 (可选) */
  type?: 'middleware' | 'token' | 'tool_call' | 'turn_end' | 'error'
  node?: string
  content?: string
  checkpoint_id?: string
  checkpointId?: string
  oss_url?: string
  ossUrl?: string
  message?: string
  image_assets?: ImageAsset[]
  imageAssets?: ImageAsset[]
  page_data?: Record<string, unknown>
  pageData?: Record<string, unknown>
  noteData?: Record<string, unknown>
  style_data?: Record<string, unknown>
  styleData?: Record<string, unknown>
  node_prompts?: Record<string, string>
  nodePrompts?: Record<string, string>
  source_code?: string
  sourceCode?: string
  htmlPreview?: string
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
