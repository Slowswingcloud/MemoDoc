// API 客户端：fetch 封装 + SSE 流式问答（TypeScript）
import type {
  ChatMessage,
  CheckStatus,
  DocItem,
  MemoryFact,
  Session,
  SourceItem,
  SSEEvent,
  UploadResult,
  User,
} from './types'

let _token: string | null = null
export function setToken(t: string | null): void {
  _token = t
}
export function getToken(): string | null {
  return _token
}

function headers(json?: unknown): HeadersInit {
  const h: Record<string, string> = {}
  if (_token) h.Authorization = `Bearer ${_token}`
  if (json !== undefined) h['Content-Type'] = 'application/json'
  return h
}

async function j<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, { method, headers: headers(body), body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) {
    let detail = `${res.status}`
    try {
      const e = await res.json()
      if (e.detail) detail = e.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  // ---- 认证 ----
  register: (username: string, password: string, role: string): Promise<User> =>
    j('POST', '/api/auth/register', { username, password, role }),
  login: (username: string, password: string): Promise<{ token: string; username: string; role: string }> =>
    j('POST', '/api/auth/login', { username, password }),
  logout: (): Promise<{ ok: boolean }> => j('POST', '/api/auth/logout', {}),
  me: (): Promise<User> => j('GET', '/api/me'),
  users: (): Promise<{ username: string; role: string; created_at: number }[]> =>
    j('GET', '/api/users'),

  // ---- 会话 ----
  sessions: (): Promise<Session[]> => j('GET', '/api/sessions'),
  newSession: (): Promise<{ session_id: string }> => j('POST', '/api/sessions'),
  sessionMessages: (sid: string): Promise<{ messages: ChatMessage[] }> =>
    j('GET', `/api/sessions/${sid}`),
  deleteSession: (sid: string): Promise<{ ok: boolean }> => j('DELETE', `/api/sessions/${sid}`),

  // ---- 记忆 ----
  memories: (): Promise<MemoryFact[]> => j('GET', '/api/memories'),
  clearMemories: (): Promise<{ ok: boolean }> => j('DELETE', '/api/memories'),

  // ---- 文档库 ----
  documents: (): Promise<DocItem[]> => j('GET', '/api/documents'),
  allTags: (): Promise<string[]> => j('GET', '/api/tags'),
  deleteDocument: (name: string): Promise<{ ok: boolean }> =>
    j('DELETE', `/api/documents/${encodeURIComponent(name)}`),
  addDocTag: (name: string, tag: string): Promise<{ ok: boolean; tags: string[] }> =>
    j('POST', `/api/documents/${encodeURIComponent(name)}/tags`, { tag }),
  removeDocTag: (name: string, tag: string): Promise<{ ok: boolean; tags: string[] }> =>
    j('DELETE', `/api/documents/${encodeURIComponent(name)}/tags/${encodeURIComponent(tag)}`),

  upload: async (files: File[], tags: string[]): Promise<{ results: UploadResult[] }> => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    fd.append('tags', tags.join(','))
    const res = await fetch('/api/upload', { method: 'POST', headers: headers(), body: fd })
    if (!res.ok) throw new Error(`upload -> ${res.status}`)
    return res.json()
  },

  download: async (name: string): Promise<void> => {
    const res = await fetch(`/api/documents/${encodeURIComponent(name)}/download`, {
      headers: headers(),
    })
    if (!res.ok) throw new Error('下载失败')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  },

  openFile: (path: string): Promise<{ ok: boolean; message: string }> =>
    j('POST', '/api/open-file', { path }).catch(() => ({ ok: false, message: '打开失败' })),
}

// ---------- SSE 流式问答 ----------
export interface ChatStreamPayload {
  session_id: string
  question: string
  tags: string[]
  use_memory: boolean
}

export interface ChatStreamHandlers {
  onEvent?: (evt: SSEEvent) => void
  onDone?: () => void
  onError?: (e: Error) => void
}

export function chatStream(payload: ChatStreamPayload, handlers: ChatStreamHandlers): void {
  fetch('/api/chat', {
    method: 'POST',
    headers: headers(payload),
    body: JSON.stringify(payload),
  })
    .then((res) => {
      if (!res.ok || !res.body) throw new Error(`chat -> ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      const pump = (): void => {
        reader
          .read()
          .then(({ done, value }) => {
            if (done) {
              handlers.onDone?.()
              return
            }
            buf += decoder.decode(value, { stream: true })
            let idx: number
            while ((idx = buf.indexOf('\n\n')) >= 0) {
              const frame = buf.slice(0, idx)
              buf = buf.slice(idx + 2)
              for (const line of frame.split('\n')) {
                if (line.startsWith('data: ')) {
                  try {
                    handlers.onEvent?.(JSON.parse(line.slice(6)) as SSEEvent)
                  } catch {
                    /* ignore */
                  }
                }
              }
            }
            pump()
          })
          .catch(handlers.onError)
      }
      pump()
    })
    .catch((e: Error) => handlers.onError?.(e))
}

export type { ChatMessage, CheckStatus, SourceItem }
