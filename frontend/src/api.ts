export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let msg = text || res.statusText
    try { msg = JSON.parse(text).detail || msg } catch { /* 非 JSON 错误体 */ }
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
