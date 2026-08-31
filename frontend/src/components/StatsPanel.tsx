import { useEffect } from 'react'
import { Empty, Statistic, Row, Col } from 'antd'
import { useStore } from '../store'

export default function StatsPanel() {
  const stats = useStore((s) => s.stats)
  const loadStats = useStore((s) => s.loadStats)

  useEffect(() => {
    loadStats()
  }, [])

  if (!stats.length) {
    return (
      <div style={{ padding: 24 }}>
        <Empty
          description="暂无学习画像数据——让学生先使用「复习问答」几轮，再回来查看班级薄弱点"
          style={{ marginTop: 64 }}
        />
      </div>
    )
  }

  const max = stats[0].count
  const totalStudents = new Set(stats.map((s) => s.students)).size

  return (
    <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
      <h3 style={{ marginTop: 0, marginBottom: 16 }}>📊 班级薄弱知识点统计</h3>
      <Row gutter={16} style={{ marginBottom: 20 }}>
        <Col span={12}>
          <Statistic title="薄弱点条目" value={stats.length} />
        </Col>
        <Col span={12}>
          <Statistic title="涉及学生" value={totalStudents} suffix="人" />
        </Col>
      </Row>
      {stats.map((s, i) => (
        <div className="stat-row" key={i}>
          <div className="stat-label">
            <span>
              {s.subject} · {s.content}
            </span>
            <span style={{ color: 'var(--primary)', fontWeight: 600 }}>
              {s.count} 次 · {s.students} 人
            </span>
          </div>
          <div className="stat-bar">
            <div className="stat-bar-fill" style={{ width: `${(s.count / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}
