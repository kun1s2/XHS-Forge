const getHttpBase = () => {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (configured && typeof configured === 'string') {
    return configured.replace(/\/$/, '')
  }
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8000'
  }
  return ''
}

export const reportFrontendObservation = async (payload: Record<string, unknown>) => {
  const base = getHttpBase()
  if (!base) return
  try {
    await fetch(`${base}/workspace/frontend-observe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    // 静默失败，避免观测链反向打爆主链。
  }
}
