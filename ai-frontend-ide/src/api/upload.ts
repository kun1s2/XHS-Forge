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
