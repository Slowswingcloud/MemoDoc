import { useState } from 'react'
import { Button, Form, Input, Segmented, Tabs, message } from 'antd'
import { LockOutlined, ReadOutlined, UserOutlined } from '@ant-design/icons'
import { useStore } from '../store'

export default function AuthPage() {
  const login = useStore((s) => s.login)
  const register = useStore((s) => s.register)
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [role, setRole] = useState<'user' | 'admin'>('user')
  const [loading, setLoading] = useState(false)

  const submit = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(values.username, values.password)
        message.success('登录成功')
      } else {
        await register(values.username, values.password, role)
        message.success('注册成功，已自动登录')
      }
    } catch (e) {
      message.error((e as Error).message || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-logo">📚</div>
          <h1>MemoDoc</h1>
          <p className="auth-slogan">带长期记忆的文档问答</p>
          <ul className="auth-features">
            <li>· 引用可追溯，点击直接打开源文件</li>
            <li>· 跨会话记住你，越用越懂你</li>
            <li>· 混合检索 + 重排，答案可核查</li>
          </ul>
        </div>
        <div className="auth-form-wrap">
          <Tabs
            activeKey={mode}
            onChange={(k) => setMode(k as 'login' | 'register')}
            centered
            items={[
              { key: 'login', label: '登录' },
              { key: 'register', label: '注册' },
            ]}
          />
          <Form layout="vertical" onFinish={submit} requiredMark={false}>
            <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
              <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码（至少 6 位）" size="large" />
            </Form.Item>
            {mode === 'register' && (
              <Form.Item label="注册身份">
                <Segmented
                  block
                  value={role}
                  onChange={(v) => setRole(v as 'user' | 'admin')}
                  options={[
                    { label: '👤 普通用户', value: 'user' },
                    { label: '🛡️ 管理员', value: 'admin' },
                  ]}
                />
              </Form.Item>
            )}
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>
              {mode === 'login' ? '登 录' : '注 册'}
            </Button>
          </Form>
          {mode === 'login' && (
            <div className="auth-tip">
              <ReadOutlined /> 首次使用？默认管理员 admin / admin123（可登录后自行注册新账号）
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
