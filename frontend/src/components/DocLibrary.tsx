import { useEffect, useState } from 'react'
import {
  Button,
  Input,
  Popconfirm,
  Space,
  Statistic,
  Table,
  Tag,
  Upload,
  message,
  type UploadFile,
} from 'antd'
import {
  DeleteOutlined,
  DownloadOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { useStore } from '../store'
import { api } from '../api'
import type { DocItem } from '../types'

export default function DocLibrary() {
  const user = useStore((s) => s.user)
  const docs = useStore((s) => s.docs)
  const loadDocs = useStore((s) => s.loadDocs)
  const upload = useStore((s) => s.upload)
  const deleteDoc = useStore((s) => s.deleteDoc)
  const addDocTag = useStore((s) => s.addDocTag)
  const removeDocTag = useStore((s) => s.removeDocTag)

  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [tagInput, setTagInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [addingFor, setAddingFor] = useState<string | null>(null)
  const [newTag, setNewTag] = useState('')

  useEffect(() => {
    loadDocs()
  }, [])

  const doUpload = async (): Promise<void> => {
    const files = fileList
      .map((f) => f.originFileObj)
      .filter((f): f is File => f instanceof File)
    if (!files.length) return message.warning('请先选择文件')
    const tags = tagInput
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean)
    setUploading(true)
    const { results } = await upload(files, tags)
    setUploading(false)
    setFileList([])
    setTagInput('')
    const ok = results.filter((r) => r.ok).length
    message.success(`上传完成：${ok} 成功，${results.length - ok} 失败`)
  }

  const canDelete = (doc: DocItem): boolean =>
    user?.role === 'admin' || doc.owner === user?.username

  const openSource = async (doc: DocItem): Promise<void> => {
    if (!doc.source) return message.warning('该文档没有源文件路径')
    const r = await api.openFile(doc.source)
    r.ok ? message.success(r.message) : message.error(r.message)
  }

  const download = async (name: string): Promise<void> => {
    try {
      await api.download(name)
      message.success('已开始下载')
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  const columns = [
    { title: '文档', dataIndex: 'name', ellipsis: true },
    {
      title: '标签',
      key: 'tags',
      render: (_: unknown, doc: DocItem) => (
        <Space size={4} wrap>
          {(doc.tags || []).map((t) => (
            <Tag
              key={t}
              closable
              onClose={(e) => {
                e.preventDefault()
                removeDocTag(doc.name, t)
              }}
            >
              {t}
            </Tag>
          ))}
          {addingFor === doc.name ? (
            <Input
              size="small"
              style={{ width: 90 }}
              autoFocus
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              onPressEnter={() => {
                const t = newTag.trim()
                if (t) addDocTag(doc.name, t)
                setAddingFor(null)
                setNewTag('')
              }}
              onBlur={() => {
                setAddingFor(null)
                setNewTag('')
              }}
            />
          ) : (
            <Button
              size="small"
              type="text"
              onClick={() => {
                setAddingFor(doc.name)
                setNewTag('')
              }}
            >
              +
            </Button>
          )}
        </Space>
      ),
    },
    {
      title: '上传者',
      dataIndex: 'owner',
      width: 100,
      render: (v: string) => (v ? <Tag>{v}</Tag> : <span style={{ color: '#bbb' }}>—</span>),
    },
    { title: '块数', dataIndex: 'chunks', width: 70, align: 'center' as const },
    {
      title: '操作',
      width: 190,
      render: (_: unknown, doc: DocItem) => (
        <Space size={4}>
          <Button size="small" icon={<DownloadOutlined />} onClick={() => download(doc.name)}>
            下载
          </Button>
          {doc.source && (
            <Button size="small" icon={<FolderOpenOutlined />} onClick={() => openSource(doc)} />
          )}
          {canDelete(doc) && (
            <Popconfirm title={`删除《${doc.name}》？`} onConfirm={() => deleteDoc(doc.name)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        {/* 上传区 */}
        <div
          style={{
            background: '#fff',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: 16,
            boxShadow: 'var(--shadow)',
          }}
        >
          <Space wrap>
            <Upload
              multiple
              beforeUpload={() => false}
              fileList={fileList}
              onChange={({ fileList }) => setFileList(fileList)}
            >
              <Button icon={<UploadOutlined />}>选择文件（可多选）</Button>
            </Upload>
            <Input
              style={{ width: 220 }}
              placeholder="标签（逗号分隔，留空则自动打标签）"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
            />
            <Button type="primary" loading={uploading} onClick={doUpload}>
              上传并索引
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadDocs}>
              刷新
            </Button>
          </Space>
        </div>

        <Statistic title="文件总数" value={docs.length} />

        <Table
          rowKey="name"
          size="small"
          columns={columns}
          dataSource={docs}
          pagination={{ pageSize: 8 }}
        />
      </Space>
    </div>
  )
}
