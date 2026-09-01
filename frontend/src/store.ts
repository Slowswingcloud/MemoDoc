// 全局状态（zustand）
import { create } from 'zustand'
import { api, chatStream, setToken } from './api'
import type {
  ChatMessage,
  CheckStatus,
  DocItem,
  MemoryFact,
  Session,
  SourceItem,
  User,
} from './types'

interface AppState {
  // 认证
  user: User | null

  // 会话
  sessions: Session[]
  currentSessionId: string | null
  messages: ChatMessage[]

  // 问答
  sources: SourceItem[]
  checks: Record<number, CheckStatus>
  streaming: boolean
  inputText: string
  allTags: string[]
  selectedTags: string[]

  // 文档库
  docs: DocItem[]
  memories: MemoryFact[]

  // actions
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, role: string) => Promise<void>
  logout: () => void

  loadSessions: () => Promise<void>
  newSession: () => Promise<void>
  switchSession: (sid: string) => Promise<void>
  deleteSession: (sid: string) => Promise<void>
  send: (question: string) => Promise<void>

  loadDocs: () => Promise<void>
  loadTags: () => Promise<void>
  setSelectedTags: (tags: string[]) => void
  upload: (files: File[], tags: string[]) => Promise<{ results: { ok: boolean }[] }>
  deleteDoc: (name: string) => Promise<void>
  addDocTag: (name: string, tag: string) => Promise<void>
  removeDocTag: (name: string, tag: string) => Promise<void>

  clearChat: () => void
}

export const useStore = create<AppState>((set, get) => ({
  user: null,

  sessions: [],
  currentSessionId: null,
  messages: [],

  sources: [],
  checks: {},
  streaming: false,
  inputText: '',
  allTags: [],
  selectedTags: [],

  docs: [],
  memories: [],

  // ---------- 认证 ----------
  async login(username, password) {
    const r = await api.login(username, password)
    setToken(r.token)
    set({ user: { username: r.username, role: r.role as 'user' | 'admin' } })
    await get().loadSessions()
    get().loadDocs()
    get().loadTags()
  },

  async register(username, password, role) {
    await api.register(username, password, role)
    await get().login(username, password)
  },

  async logout() {
    try {
      await api.logout()
    } catch {
      /* ignore */
    }
    setToken(null)
    set({
      user: null,
      sessions: [],
      currentSessionId: null,
      messages: [],
      sources: [],
      checks: {},
      docs: [],
      memories: [],
    })
  },

  // ---------- 会话 ----------
  async loadSessions() {
    const sessions = await api.sessions()
    set({ sessions })
    if (!get().currentSessionId && sessions.length) {
      get().switchSession(sessions[0].id)
    }
  },

  async newSession() {
    const { session_id } = await api.newSession()
    set({ currentSessionId: session_id, messages: [], sources: [], checks: {} })
    get().loadSessions()
  },

  async switchSession(sid) {
    const { messages } = await api.sessionMessages(sid)
    set({ currentSessionId: sid, messages, sources: [], checks: {} })
  },

  async deleteSession(sid) {
    await api.deleteSession(sid)
    set({ currentSessionId: null, messages: [], sources: [], checks: {} })
    get().loadSessions()
  },

  // ---------- 问答 ----------
  async send(question) {
    if (get().streaming || !question.trim()) return
    const { currentSessionId, selectedTags } = get()
    set({
      streaming: true,
      messages: [...get().messages, { role: 'user', content: question }],
      sources: [],
      checks: {},
    })
    set({ messages: [...get().messages, { role: 'assistant', content: '' }] })

    chatStream(
      {
        session_id: currentSessionId || '',
        question,
        tags: selectedTags,
        use_memory: true,
      },
      {
        onEvent(evt) {
          const st = get()
          if (evt.type === 'sources') {
            set({ sources: evt.items })
          } else if (evt.type === 'delta') {
            const messages = st.messages.slice()
            messages[messages.length - 1] = {
              ...messages[messages.length - 1],
              content: messages[messages.length - 1].content + evt.text,
            }
            set({ messages })
          } else if (evt.type === 'checks') {
            const checks: Record<number, CheckStatus> = {}
            evt.items.forEach((c) => (checks[c.index] = c.status))
            set({ checks })
          } else if (evt.type === 'done' && evt.session_id) {
            set({ currentSessionId: evt.session_id })
          } else if (evt.type === 'error') {
            const messages = st.messages.slice()
            messages[messages.length - 1] = {
              ...messages[messages.length - 1],
              content: `⚠️ ${evt.message}`,
            }
            set({ messages })
          }
        },
        onDone() {
          set({ streaming: false })
          get().loadSessions()
        },
        onError(e) {
          const messages = get().messages.slice()
          messages[messages.length - 1] = {
            ...messages[messages.length - 1],
            content: `⚠️ 连接失败：${e.message}`,
          }
          set({ messages, streaming: false })
        },
      },
    )
  },

  // ---------- 文档库 ----------
  async loadDocs() {
    const docs = await api.documents()
    set({ docs })
  },

  async loadTags() {
    const allTags = await api.allTags()
    set({ allTags })
  },

  setSelectedTags(tags) {
    set({ selectedTags: tags })
  },

  async upload(files, tags) {
    const res = await api.upload(files, tags)
    get().loadDocs()
    get().loadTags()
    return res
  },

  async deleteDoc(name) {
    await api.deleteDocument(name)
    get().loadDocs()
    get().loadTags()
  },

  async addDocTag(name, tag) {
    await api.addDocTag(name, tag)
    get().loadDocs()
    get().loadTags()
  },

  async removeDocTag(name, tag) {
    await api.removeDocTag(name, tag)
    get().loadDocs()
    get().loadTags()
  },

  clearChat() {
    set({ messages: [], sources: [], checks: {} })
  },
}))
