import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider
    locale={zhCN}
    theme={{
      token: {
        colorPrimary: '#4f6ef7',
        borderRadius: 10,
        fontFamily: "'PingFang SC','Microsoft YaHei','Segoe UI',system-ui,sans-serif",
      },
    }}
  >
    <App />
  </ConfigProvider>,
)
