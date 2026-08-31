import { Empty, message } from 'antd'
import { useStore } from '../store'
import { api } from '../api'

export default function SourcesPanel() {
  const sources = useStore((s) => s.sources)
  const checks = useStore((s) => s.checks)

  return (
    <div className="panel-block">
      <div className="panel-title">🔗 引用来源（点击打开源文件）</div>
      {sources.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="提问后显示引用来源"
          style={{ marginTop: 24 }}
        />
      ) : (
        sources.map((s) => (
          <div
            key={s.index}
            className="source-card"
            onClick={async () => {
              if (!s.source) return message.warning('该引用没有源文件')
              const r = await api.openFile(s.source)
              r.ok ? message.success(r.message) : message.error(r.message)
            }}
          >
            <div className="source-head">
              <span className="source-badge">[{s.index}]</span>
              <span className="source-section">
                {s.doc_name} · {s.section}
              </span>
            </div>
            {checks[s.index] === 'supported' && <span className="check-ok">✓ 已核查</span>}
            {checks[s.index] === 'unsupported' && <span className="check-bad">⚠ 不支持</span>}
            <div className="source-preview">{s.preview}</div>
          </div>
        ))
      )}
    </div>
  )
}
