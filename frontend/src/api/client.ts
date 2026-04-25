// Tauri v2 detection: check both legacy and internal API
export const isTauri = typeof window !== 'undefined' && (
  '__TAURI__' in window ||
  '__TAURI_INTERNALS__' in window
)

export const API_BASE = isTauri ? 'http://localhost:8000' : ''

async function apiFetch<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const url = typeof input === 'string' && !input.startsWith('http')
    ? `${API_BASE}${input}`
    : input

  const isFormData = init?.body instanceof FormData
  const headers: Record<string, string> = {}
  if (!isFormData) {
    headers['Content-Type'] = 'application/json'
  }
  if (init?.headers) {
    Object.assign(headers, init.headers)
  }

  const res = await fetch(url, {
    ...init,
    headers,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }

  if (res.status === 204) {
    return undefined as unknown as T
  }

  return res.json() as Promise<T>
}

export const apiClient = {
  get: <T>(url: string) => apiFetch<T>(url, { method: 'GET' }),
  post: <T>(url: string, body?: unknown) => apiFetch<T>(url, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(url: string, form: FormData) => apiFetch<T>(url, { method: 'POST', body: form }),
  put: <T>(url: string, body?: unknown) => apiFetch<T>(url, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(url: string, body?: unknown) => apiFetch<T>(url, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(url: string) => apiFetch<T>(url, { method: 'DELETE' }),
}
