import { useEffect, useState } from 'react'
import { Table, Tag } from 'antd'
import dayjs from 'dayjs'
import { api } from '../api'

interface UserRow {
  username: string
  role: string
  created_at: number
}

export default function AdminUsers() {
  const [users, setUsers] = useState<UserRow[]>([])

  useEffect(() => {
    api
      .users()
      .then(setUsers)
      .catch(() => setUsers([]))
  }, [])

  const columns = [
    { title: '用户名', dataIndex: 'username' },
    {
      title: '角色',
      dataIndex: 'role',
      render: (v: string) => (
        <Tag color={v === 'admin' ? 'gold' : 'blue'}>{v === 'admin' ? '🛡️ 管理员' : '👤 用户'}</Tag>
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      render: (v: number) => (v ? dayjs(v * 1000).format('YYYY-MM-DD HH:mm') : '—'),
    },
  ]

  return (
    <div style={{ padding: 20 }}>
      <h3 style={{ marginTop: 0, marginBottom: 16 }}>👥 注册用户</h3>
      <Table rowKey="username" size="small" columns={columns} dataSource={users} pagination={false} />
    </div>
  )
}
