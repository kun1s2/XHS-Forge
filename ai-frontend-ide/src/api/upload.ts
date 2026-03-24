/**
 * 图片上传到 OSS，与旧项目 frontend/src/api/upload.js 及后端 POST /upload/image 对齐。
 * 后端：multipart/form-data 字段名 file，响应 { url: string, thumbnail_url?: string }。
 */

const getBaseUrl = (): string => {
  const u = import.meta.env.VITE_API_BASE_URL
  if (u && typeof u === 'string') return u.replace(/\/$/, '')
  // 开发时默认连本机后端（与 ws 一致）；生产请配置 VITE_API_BASE_URL 或同源代理
  if (import.meta.env.DEV) return 'http://127.0.0.1:8000'
  return ''
}

/**
 * 上传单张图片到 OSS，返回可访问 URL。
 * @param file 图片文件
 * @returns 原图 URL（或 thumbnail_url 若后端返回且需省 token 可改用该字段）
 */
export async function uploadImage(file: File): Promise<{ url: string }> {
  const base = getBaseUrl()
  const form = new FormData()
  form.append('file', file)

  const url = base ? `${base}/upload/image` : '/upload/image'
  const res = await fetch(url, {
    method: 'POST',
    body: form,
    // 不设 Content-Type，由浏览器自动带 multipart/form-data; boundary=...
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: string }).detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  const data = (await res.json()) as { url?: string; thumbnail_url?: string }
  const imageUrl = data.url ?? data.thumbnail_url
  if (!imageUrl) throw new Error('后端未返回 url')
  return { url: imageUrl }
}

/**
 * 批量上传图片，返回 URL 列表（顺序与 files 一致）。
 * 后端：POST /upload/images，字段名 files，响应 { urls: string[] }。
 */
export async function uploadImages(files: File[]): Promise<{ urls: string[] }> {
  if (!files?.length) return { urls: [] }

  const base = getBaseUrl()
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }

  const url = base ? `${base}/upload/images` : '/upload/images'
  const res = await fetch(url, {
    method: 'POST',
    body: form,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: string }).detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }

  const data = (await res.json()) as { urls?: string[] }
  if (!Array.isArray(data.urls)) throw new Error('后端未返回 urls 数组')
  return { urls: data.urls }
}

type KnowledgeScope = 'session' | 'persistent'

type KnowledgeUploadBase = {
  threadId: string
  kbScope?: KnowledgeScope
  entityHint?: string
  sceneHint?: string
}

async function parseJsonOrThrow(res: Response) {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (data as { detail?: string }).detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data as Record<string, unknown>
}

export async function uploadKnowledgeFile(
  file: File,
  options: KnowledgeUploadBase,
): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const form = new FormData()
  form.append('file', file)
  form.append('thread_id', options.threadId)
  form.append('kb_scope', options.kbScope || 'session')
  form.append('entity_hint', options.entityHint || '')
  form.append('scene_hint', options.sceneHint || '')
  const res = await fetch(base ? `${base}/upload/knowledge/file` : '/upload/knowledge/file', {
    method: 'POST',
    body: form,
  })
  return parseJsonOrThrow(res)
}

export async function uploadKnowledgeText(
  payload: KnowledgeUploadBase & { title: string; text: string },
): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/text` : '/upload/knowledge/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: payload.threadId,
      kb_scope: payload.kbScope || 'session',
      entity_hint: payload.entityHint || '',
      scene_hint: payload.sceneHint || '',
      title: payload.title,
      text: payload.text,
    }),
  })
  return parseJsonOrThrow(res)
}

export async function uploadKnowledgeUrl(
  payload: KnowledgeUploadBase & { url: string },
): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/url` : '/upload/knowledge/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: payload.threadId,
      kb_scope: payload.kbScope || 'session',
      entity_hint: payload.entityHint || '',
      scene_hint: payload.sceneHint || '',
      url: payload.url,
    }),
  })
  return parseJsonOrThrow(res)
}

export async function listKnowledgeDemoPacks(): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/demo-packs` : '/upload/knowledge/demo-packs')
  return parseJsonOrThrow(res)
}

export async function listKnowledgeEvalSets(): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/eval-sets` : '/upload/knowledge/eval-sets')
  return parseJsonOrThrow(res)
}

export async function fetchGlobalKnowledgeOverview(): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/global-overview` : '/upload/knowledge/global-overview')
  return parseJsonOrThrow(res)
}

export async function importKnowledgeDemoPack(
  payload: KnowledgeUploadBase & { packId: string },
): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/demo-pack` : '/upload/knowledge/demo-pack', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: payload.threadId,
      kb_scope: payload.kbScope || 'session',
      pack_id: payload.packId,
    }),
  })
  return parseJsonOrThrow(res)
}

export async function promoteKnowledgeToPersistent(payload: {
  threadId: string
  recordIds?: string[]
  normalizedEntity?: string
  fieldOrTopic?: string
}): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/promote` : '/upload/knowledge/promote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: payload.threadId,
      record_ids: payload.recordIds || [],
      normalized_entity: payload.normalizedEntity || null,
      field_or_topic: payload.fieldOrTopic || null,
    }),
  })
  return parseJsonOrThrow(res)
}

export async function reviewKnowledgeCandidates(payload: {
  threadId: string
  decision: string
  recordIds?: string[]
  normalizedEntity?: string
  fieldOrTopic?: string
}): Promise<Record<string, unknown>> {
  const base = getBaseUrl()
  const res = await fetch(base ? `${base}/upload/knowledge/review` : '/upload/knowledge/review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: payload.threadId,
      decision: payload.decision,
      record_ids: payload.recordIds || [],
      normalized_entity: payload.normalizedEntity || null,
      field_or_topic: payload.fieldOrTopic || null,
    }),
  })
  return parseJsonOrThrow(res)
}
