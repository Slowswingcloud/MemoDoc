import { useEffect, useState } from 'react'
import {
  Button,
  Input,
  Popconfirm,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Upload,
  message,
  type UploadFile,
} from 'antd'
import { ReloadOutlined, UploadOutlined } from '@ant-design/icons'
import { useStore } from '../store'
import type { DocItem } from '../types'

const DOC_TYPES = ['课件', '作业题', '往年题', '错题']

export default function DocLibrary() {
  const docs = useStore((s) => s.docs)
  const courses = useStore((s) => s.courses)
  const docFilter = useStore((s) => s.docFilter)
  const loadDocs = useStore((s) => s.loadDocs)
  const setDocFilter = useStore((s) => s.setDocFilter)
  const upload = useStore((s) => s.upload)
  const deleteDoc = useStore((s) => s.deleteDoc)

  const [course, setCourse] = useState('软件工程')
  const [docType, setDocType] = useState('课件')
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    loadDocs()
  }, [])

  const doUpload = async (): Promise<void> => {
    const files = fileList
      .map((f) => f.originFileObj)
      .filter((f): f is File => f instanceof File)
    if (!files.length) return message.warning('请先选择文件')
    setUploading(true)
    const { results } = await upload(files, course.trim() || '默认课程', docType)
    setUploading(false)
    setFileList([])
    const ok = results.filter((r) => r.ok).length
    message.success(`上传完成：${ok} 成功，${results.length - ok} 失败`)
  }

  const columns = [
    { title: '文档', dataIndex: 'name', ellipsis: true },
    {
      title: '课程',
      dataIndex: 'course',
      width: 120,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '类型',
      dataIndex: 'doc_type',
      width: 90,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    { title: '块数', dataIndex: 'chunks', width: 70, align: 'center' as const },
    {
      title: '操作',
      width: 90,
      render: (_: unknown, r: DocItem) => (
        <Popconfirm title={`删除《${r.name}》？`} onConfirm={() => deleteDoc(r.name)}>
          <Button danger size="small">
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
      <Space direction="vertical" style={{ width: '100%' }} size={16}>
        {/* 上传区（左上角） */}
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
              style={{ width: 160 }}
              placeholder="课程名称"
              value={course}
              onChange={(e) => setCourse(e.target.value)}
            />
            <Select
              style={{ width: 110 }}
              value={docType}
              onChange={setDocType}
              options={DOC_TYPES.map((t) => ({ label: t, value: t }))}
            />
            <Button type="primary" loading={uploading} onClick={doUpload}>
              上传并索引
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadDocs}>
              刷新
            </Button>
          </Space>
        </div>

        {/* 过滤 + 统计 */}
        <Space wrap>
          <Select
            allowClear
            placeholder="按课程过滤"
            style={{ width: 170 }}
            value={docFilter.course}
            onChange={(v) => setDocFilter(v, docFilter.docType)}
            options={courses.map((c) => ({ label: c, value: c }))}
          />
          <Select
            allowClear
            placeholder="按类型过滤"
            style={{ width: 150 }}
            value={docFilter.docType}
            onChange={(v) => setDocFilter(docFilter.course, v)}
            options={DOC_TYPES.map((t) => ({ label: t, value: t }))}
          />
          <Statistic title="文档数" value={docs.length} style={{ marginLeft: 12 }} />
        </Space>

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
