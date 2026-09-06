import { useEffect, useState } from 'react'
import { checkHealth } from './api.js'

// 本轮只做一件事：页面加载时调用后端 /health，验证前后端联通、
// 端口与 CORS 配置是否正确。录音、识别等业务功能后续轮次再加入。
function App() {
  const [status, setStatus] = useState('checking')
  const [requestId, setRequestId] = useState('')

  useEffect(() => {
    let isMounted = true

    checkHealth()
      .then((body) => {
        if (!isMounted) return
        setStatus(body?.data?.status === 'ok' ? 'connected' : 'unexpected')
        setRequestId(body?.request_id ?? '')
      })
      .catch(() => {
        if (!isMounted) return
        setStatus('failed')
      })

    return () => {
      isMounted = false
    }
  }, [])

  const statusText = {
    checking: '正在检查后端连接...',
    connected: '后端连接正常 ✅',
    unexpected: '后端返回了非预期内容 ⚠️',
    failed: '无法连接后端 ❌（请确认后端已启动，且端口/CORS配置正确）',
  }[status]

  return (
    <main style={{ padding: '2rem', maxWidth: 640, margin: '0 auto' }}>
      <h1>语音约碰面地点</h1>
      <p>{statusText}</p>
      {requestId && <p style={{ color: '#666' }}>request_id：{requestId}</p>}
    </main>
  )
}

export default App
