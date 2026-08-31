import { Empty, Button, message } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import { useStore } from '../store'
import { api } from '../api'

const TAG_CLASS: Record<string, string> = {
  learning: 'learning',
  identity: 'identity',
  preference: 'preference',
}
const TAG_TEXT: Record<string, string> = {
  learning: '薄弱点',
  identity: '身份',
  preference: '偏好',
}

export default function ProfilePanel() {
  const memories = useStore((s) => s.memories)
  const studentName = useStore((s) => s.studentName)

  const clear = async (): Promise<void> => {
    await api.clearMemories(studentName)
    useStore.getState().loadProfile()
    message.success('已清空记忆')
  }

  return (
    <div className="panel-block">
      <div className="panel-title" style={{ justifyContent: 'space-between' }}>
        <span>🧠 学习画像 · {studentName}</span>
        <Button size="small" type="text" icon={<DeleteOutlined />} onClick={clear} />
      </div>
      {memories.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="提问后，系统会记住你的薄弱点"
          style={{ marginTop: 24 }}
        />
      ) : (
        memories.map((m, i) => {
          const type = m.meta?.type || 'preference'
          return (
            <div className="profile-card" key={i}>
              <span className={`profile-tag ${TAG_CLASS[type] || 'preference'}`}>
                {TAG_TEXT[type] || '偏好'} · {m.meta?.subject || '其他'}
              </span>
              <div className="profile-content">{m.content}</div>
            </div>
          )
        })
      )}
    </div>
  )
}
