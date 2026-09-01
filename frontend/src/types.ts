// ============ 共享类型定义 ============

export type UserRole = 'user' | 'admin'

export interface User {
  username: string
  role: UserRole
}

export interface Session {
  id: string
  title: string
  updated_at: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SourceItem {
  index: number
  doc_name: string
  section: string
  source: string
  preview: string
}

export type CheckStatus = 'supported' | 'unsupported' | 'unknown'

export interface DocItem {
  name: string
  source: string
  chunks: number
  indexed_at: number
  tags: string[]
  tenant: string
  lifecycle: string
  owner: string
}

export interface MemoryFact {
  content: string
  meta: { type: string; subject: string; user_id?: string }
}

export interface UploadResult {
  name: string
  doc?: string
  chunks?: number
  mode?: string
  tags?: string[]
  ok: boolean
  error?: string
}

// SSE 事件
export type SSEEvent =
  | { type: 'sources'; items: SourceItem[] }
  | { type: 'delta'; text: string }
  | { type: 'checks'; items: { index: number; status: CheckStatus }[] }
  | { type: 'done'; session_id?: string }
  | { type: 'error'; message: string }
