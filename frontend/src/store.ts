// 全局状态（zustand）
import { create } from 'zustand'
import { api, chatStream } from './api'
import type {
  ChatMessage,
  CheckStatus,
  DocItem,
  MemoryFact,
  ProfileItem,
  Role,
  Session,
  SourceItem,
  StatItem,
} from './types'

export const STUDENTS = ['张三', '李四', '王五']

interface DocFilter {
  course?: string
  docType?: string
}

interface AppState {
  role: Role
  studentName: string

  sessions: Session[]
  currentSessionId: string | null
  messages: ChatMessage[]

  sources: SourceItem[]
  checks: Record<number, CheckStatus>
  streaming: boolean
  inputText: string

  profile: ProfileItem[]
  memories: MemoryFact[]
  stats: StatItem[]
  docs: DocItem[]
  courses: string[]
  docFilter: DocFilter

  setRole: (r: Role) => void
  setStudentName: (n: string) => void
  loadSessions: () => Promise<void>
  newSession: () => Promise<void>
  switchSession: (sid: string) => Promise<void>
  deleteSession: (sid: string) => Promise<void>
  send: (question: string) => Promise<void>

  loadProfile: () => Promise<void>
  loadStats: () => Promise<void>
  loadDocs: () => Promise<void>
  setDocFilter: (course?: string, docType?: string) => void
  upload: (files: File[], course: string, docType: string) => Promise<{ results: { ok: boolean }[] }>
  deleteDoc: (name: string) => Promise<void>
  clearChat: () => void
}

export const useStore = create<AppState>((set, get) => ({
  role: 'student',
  studentName: '张三',

  sessions: [],
  currentSessionId: null,
  messages: [],

  sources: [],
  checks: {},
  streaming: false,
  inputText: '',

  profile: [],
  memories: [],
  stats: [],
  docs: [],
  courses: [],
  docFilter: {},

  async setRole(r) {
    set({ role: r, currentSessionId: null, messages: [], sources: [], checks: {} })
    await get().loadSessions()
    if (r === 'teacher') get().loadStats()
    if (r === 'student') get().loadProfile()
  },

  async setStudentName(n) {
    set({ studentName: n, currentSessionId: null, messages: [], sources: [], checks: {} })
    await get().loadSessions()
    get().loadProfile()
  },

  async loadSessions() {
    const { role } = get()
    const sessions = await api.sessions(role)
    set({ sessions })
    if (!get().currentSessionId && sessions.length) {
      get().switchSession(sessions[0].id)
    }
  },

  async newSession() {
    const { role } = get()
    const { session_id } = await api.newSession(role)
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

  async send(question) {
    if (get().streaming || !question.trim()) return
    const { role, studentName, currentSessionId } = get()
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
        role,
        user_id: role === 'teacher' ? 'tea' : studentName,
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
          if (get().role === 'student') get().loadProfile()
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

  async loadProfile() {
    const profile = await api.profile(get().studentName)
    const memories = await api.memories(get().studentName)
    set({ profile, memories })
  },

  async loadStats() {
    const stats = await api.stats()
    set({ stats })
  },

  async loadDocs() {
    const { docFilter } = get()
    const docs = await api.documents(docFilter.course, docFilter.docType)
    const courses = await api.courses()
    set({ docs, courses })
  },

  setDocFilter(course, docType) {
    set({ docFilter: { course, docType } })
    get().loadDocs()
  },

  async upload(files, course, docType) {
    const res = await api.upload(files, course, docType)
    get().loadDocs()
    return res
  },

  async deleteDoc(name) {
    await api.deleteDocument(name)
    get().loadDocs()
  },

  clearChat() {
    set({ messages: [], sources: [], checks: {} })
  },
}))
