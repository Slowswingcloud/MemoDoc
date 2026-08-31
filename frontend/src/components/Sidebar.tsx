import { Button, Empty, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useStore } from '../store'

export default function Sidebar() {
  const sessions = useStore((s) => s.sessions)
  const current = useStore((s) => s.currentSessionId)
  const newSession = useStore((s) => s.newSession)
  const switchSession = useStore((s) => s.switchSession)
  const deleteSession = useStore((s) => s.deleteSession)

  return (
    <aside className="app-sidebar">
      <div className="sidebar-head">
        <Button type="primary" block icon={<PlusOutlined />} onClick={() => newSession()}>
          新对话
        </Button>
      </div>
      <div className="session-list">
        {sessions.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无会话"
            style={{ marginTop: 48 }}
          />
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`session-item ${s.id === current ? 'active' : ''}`}
            onClick={() => switchSession(s.id)}
          >
            <span className="session-title">{s.title}</span>
            <span className="session-time">{fmt(s.updated_at)}</span>
            <Tooltip title="删除会话">
              <DeleteOutlined
                style={{ color: '#c0c5d6' }}
                onClick={(e) => {
                  e.stopPropagation()
                  deleteSession(s.id)
                }}
              />
            </Tooltip>
          </div>
        ))}
      </div>
    </aside>
  )
}

function fmt(ts: number): string {
  if (!ts) return ''
  const d = dayjs(ts * 1000)
  return d.isSame(dayjs(), 'day') ? d.format('HH:mm') : d.format('MM-DD')
}
