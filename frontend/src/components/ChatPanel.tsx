import { useEffect, useRef } from 'react'
import { Button, Input, Select, Tooltip } from 'antd'
import { SendOutlined, ClearOutlined } from '@ant-design/icons'
import { useStore } from '../store'
import MessageItem from './MessageItem'

const SUGGESTIONS = ['状态图怎么画？', '软件过程模型有哪些？', '需求分析有哪些步骤？']

export default function ChatPanel() {
  const messages = useStore((s) => s.messages)
  const streaming = useStore((s) => s.streaming)
  const inputText = useStore((s) => s.inputText)
  const send = useStore((s) => s.send)
  const clearChat = useStore((s) => s.clearChat)
  const allTags = useStore((s) => s.allTags)
  const selectedTags = useStore((s) => s.selectedTags)
  const setSelectedTags = useStore((s) => s.setSelectedTags)
  const loadTags = useStore((s) => s.loadTags)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadTags()
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const doSend = (text: string): void => {
    const t = text.trim()
    if (!t || streaming) return
    useStore.setState({ inputText: '' })
    send(t)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="empty-box">
            <div style={{ fontSize: 44, marginBottom: 12 }}>📖</div>
            <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 6 }}>向 MemoDoc 提问</div>
            <div style={{ fontSize: 13, marginBottom: 18 }}>
              基于文件库回答，引用可追溯，跨会话记住你
            </div>
            <div>
              {SUGGESTIONS.map((s) => (
                <Button key={s} size="small" style={{ margin: 4 }} onClick={() => doSend(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageItem key={i} msg={m} streaming={streaming && i === messages.length - 1} />
        ))}
      </div>

      {/* 检索标签过滤 */}
      {allTags.length > 0 && (
        <div style={{ padding: '8px 16px 0', background: '#fff' }}>
          <Select
            mode="multiple"
            size="small"
            style={{ width: '100%' }}
            placeholder="按标签过滤检索（可选）"
            value={selectedTags}
            onChange={setSelectedTags}
            options={allTags.map((t) => ({ label: `# ${t}`, value: t }))}
            maxTagCount="responsive"
          />
        </div>
      )}

      <div className="chat-input-bar">
        <Input.TextArea
          autoSize={{ minRows: 1, maxRows: 4 }}
          value={inputText}
          onChange={(e) => useStore.setState({ inputText: e.target.value })}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault()
              doSend(inputText)
            }
          }}
          placeholder="输入你的问题…（Shift+Enter 换行）"
          style={{ flex: 1, fontSize: 14 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={streaming}
          onClick={() => doSend(inputText)}
        >
          发送
        </Button>
        <Tooltip title="清空当前对话（记忆保留）">
          <Button icon={<ClearOutlined />} onClick={clearChat} />
        </Tooltip>
      </div>
    </div>
  )
}
