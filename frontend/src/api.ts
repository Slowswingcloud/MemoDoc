// API 客户端：fetch 封装 + SSE 流式问答（TypeScript）
import type {
  ChatMessage,
  CheckStatus,
  DocItem,
  MemoryFact,
  ProfileItem,
  Session,
  SourceItem,
  StatItem,
  SSEEvent,
  UploadResult,
} from './types'

async function j<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${url} -> ${res.status}`)
  return res.json() as Promise<T>
}

export const api = {
  sessions: (role: string): Promise<Session[]> => j('GET', `/api/sessions?role=${role}`),
  newSession: (role: string): Promise<{ session_id: string }> =>
    j('POST', `/api/sessions?role=${role}`),
  sessionMessages: (sid: string): Promise<{ messages: ChatMessage[] }> =>
    j('GET', `/api/sessions/${sid}`),
  deleteSession: (sid: string): Promise<{ ok: boolean }> => j('DELETE', `/api/sessions/${sid}`),

  memories: (userId: string): Promise<MemoryFact[]> =>
    j('GET', `/api/memories?user_id=${encodeURIComponent(userId)}`),
  clearMemories: (userId: string): Promise<{ ok: boolean }> =>
    j('DELETE', `/api/memories?user_id=${encodeURIComponent(userId)}`),
  profile: (userId: string): Promise<ProfileItem[]> =>
    j('GET', `/api/profile?user_id=${encodeURIComponent(userId)}`),
  stats: (): Promise<StatItem[]> => j('GET', '/api/stats'),

  documents: (course?: string, docType?: string): Promise<DocItem[]> => {
    const p = new URLSearchParams()
    if (course) p.set('course', course)
    if (docType) p.set('doc_type', docType)
    return j('GET', `/api/documents?${p.toString()}`)
  },
  courses: (): Promise<string[]> => j('GET', '/api/courses'),
  deleteDocument: (name: string): Promise<{ ok: boolean }> =>
    j('DELETE', `/api/documents/${encodeURIComponent(name)}`),

  upload: async (
    files: File[],
    course: string,
    docType: string,
  ): Promise<{ results: UploadResult[] }> => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    fd.append('course', course)
    fd.append('doc_type', docType)
    const res = await fetch('/api/upload', { method: 'POST', body: fd })
    return res.json()
  },

  openFile: (path: string): Promise<{ ok: boolean; message: string }> =>
    j('POST', '/api/open-file', { path }).catch(() => ({ ok: false, message: '打开失败' })),
}

// ---------- SSE 流式问答 ----------
export interface ChatStreamPayload {
  session_id: string
  question: string
  role: string
  user_id: string
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
    headers: { 'Content-Type': 'application/json' },
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
                    /* 忽略解析失败帧 */
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

// 供 UI 使用的类型再导出
export type { CheckStatus, ChatMessage, SourceItem }
