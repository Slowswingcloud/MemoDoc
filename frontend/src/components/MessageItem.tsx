import { message } from 'antd'
import { useStore } from '../store'
import { api } from '../api'
import type { ChatMessage } from '../types'

interface Props {
  msg: ChatMessage
  streaming: boolean
}

// 把 [1][2] 引用解析为可点击片段
function splitCites(text: string): { text?: string; n?: number }[] {
  const out: { text?: string; n?: number }[] = []
  const re = /\[(\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ text: text.slice(last, m.index) })
    out.push({ n: parseInt(m[1], 10) })
    last = m.index + m[0].length
  }
  if (last < text.length) out.push({ text: text.slice(last) })
  return out
}

export default function MessageItem({ msg, streaming }: Props) {
  const sources = useStore((s) => s.sources)
  const checks = useStore((s) => s.checks)

  if (msg.role === 'user') {
    return (
      <div className="msg-row user">
        <div className="msg-bubble">{msg.content}</div>
      </div>
    )
  }

  const parts = splitCites(msg.content)
  const bad = Object.values(checks).filter((v) => v === 'unsupported').length

  return (
    <div className="msg-row assistant">
      <div className="msg-bubble">
        {parts.map((p, i) =>
          p.n ? (
            <button
              key={i}
              className="cite-chip"
              onClick={async () => {
                const src = sources.find((s) => s.index === p.n)
                if (!src || !src.source) return message.warning('该引用没有源文件')
                const r = await api.openFile(src.source)
                r.ok ? message.success(r.message) : message.error(r.message)
              }}
            >
              {p.n}
            </button>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
        {streaming && <span className="caret" />}
        {!streaming && bad > 0 && (
          <div style={{ color: '#ef4444', fontSize: 12, marginTop: 6 }}>
            ⚠ 有 {bad} 处引用未通过核查
          </div>
        )}
      </div>
    </div>
  )
}
