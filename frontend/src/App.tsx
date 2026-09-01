import { useEffect, useState } from 'react'
import { Avatar, Button, Tabs, Tag } from 'antd'
import { LogoutOutlined } from '@ant-design/icons'
import { useStore } from './store'
import AuthPage from './components/AuthPage'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import SourcesPanel from './components/SourcesPanel'
import DocLibrary from './components/DocLibrary'
import AdminUsers from './components/AdminUsers'

export default function App() {
  const user = useStore((s) => s.user)
  const logout = useStore((s) => s.logout)

  useEffect(() => {
    if (user) useStore.getState().loadSessions()
  }, [user?.username])

  if (!user) return <AuthPage />

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">📚</span>
          MemoDoc 文档问答
        </div>
        <div className="header-right">
          <Tag color={user.role === 'admin' ? 'gold' : 'blue'}>
            {user.role === 'admin' ? '🛡️ 管理员' : '👤 用户'}
          </Tag>
          <Avatar size={28} style={{ background: 'var(--primary)' }}>
            {user.username.slice(0, 1).toUpperCase()}
          </Avatar>
          <span style={{ fontWeight: 600 }}>{user.username}</span>
          <Button size="small" icon={<LogoutOutlined />} onClick={logout}>
            退出
          </Button>
        </div>
      </header>

      <div className="app-body">
        <Sidebar />
        <main className="app-main">
          <MainTabs />
        </main>
        <aside className="app-right">
          <SourcesPanel />
        </aside>
      </div>
    </div>
  )
}

function MainTabs() {
  const role = useStore((s) => s.user?.role)
  const [tab, setTab] = useState('chat')
  const items = [
    { key: 'chat', label: '💬 问答' },
    { key: 'docs', label: '📚 文件库' },
  ]
  if (role === 'admin') items.push({ key: 'users', label: '👥 用户管理' })
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div
        style={{
          padding: '8px 20px 0',
          background: '#fff',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <Tabs activeKey={tab} onChange={setTab} items={items} />
      </div>
      {tab === 'chat' && <ChatPanel />}
      {tab === 'docs' && <DocLibrary />}
      {tab === 'users' && <AdminUsers />}
    </div>
  )
}
