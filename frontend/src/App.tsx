import { useEffect, useState } from 'react'
import { Segmented, Select, Tabs } from 'antd'
import { useStore, STUDENTS } from './store'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import SourcesPanel from './components/SourcesPanel'
import ProfilePanel from './components/ProfilePanel'
import DocLibrary from './components/DocLibrary'
import StatsPanel from './components/StatsPanel'

export default function App() {
  const role = useStore((s) => s.role)
  const studentName = useStore((s) => s.studentName)
  const setRole = useStore((s) => s.setRole)
  const setStudentName = useStore((s) => s.setStudentName)

  useEffect(() => {
    useStore.getState().loadSessions()
  }, [])

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">📚</span>
          MemoDoc 学习助手
        </div>
        <div className="header-right">
          {role === 'student' && (
            <Select
              value={studentName}
              onChange={setStudentName}
              style={{ width: 110 }}
              options={STUDENTS.map((n) => ({ label: `👤 ${n}`, value: n }))}
            />
          )}
          <Segmented
            value={role}
            onChange={(v) => setRole(v as 'student' | 'teacher')}
            options={[
              { label: '🧑‍🎓 学生', value: 'student' },
              { label: '👩‍🏫 教师', value: 'teacher' },
            ]}
          />
        </div>
      </header>

      <div className="app-body">
        <Sidebar />
        <main className="app-main">{role === 'student' ? <ChatPanel /> : <TeacherMain />}</main>
        <aside className="app-right">
          <SourcesPanel />
          {role === 'student' && <ProfilePanel />}
        </aside>
      </div>
    </div>
  )
}

function TeacherMain() {
  const [tab, setTab] = useState('chat')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div
        style={{
          padding: '8px 20px 0',
          background: '#fff',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            { key: 'chat', label: '💬 课件问答' },
            { key: 'docs', label: '📚 资料库管理' },
            { key: 'stats', label: '📊 班级统计' },
          ]}
        />
      </div>
      {tab === 'chat' && <ChatPanel />}
      {tab === 'docs' && <DocLibrary />}
      {tab === 'stats' && <StatsPanel />}
    </div>
  )
}
