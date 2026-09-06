import { useEffect, useState } from 'react'
import { checkHealth } from './api.js'
import RecorderPanel from './components/RecorderPanel.jsx'

function App() {
  const [city, setCity] = useState('杭州')
  const [healthStatus, setHealthStatus] = useState('checking')
  const [requestId, setRequestId] = useState('')

  useEffect(() => {
    let isMounted = true

    checkHealth()
      .then((body) => {
        if (!isMounted) return
        setHealthStatus(body?.data?.status === 'ok' ? 'connected' : 'unexpected')
        setRequestId(body?.request_id ?? '')
      })
      .catch(() => {
        if (!isMounted) return
        setHealthStatus('failed')
      })

    return () => {
      isMounted = false
    }
  }, [])

  const healthText = {
    checking: '正在检查后端连接...',
    connected: '后端连接正常',
    unexpected: '后端返回了非预期内容',
    failed: '无法连接后端（录音仍可在本地使用）',
  }[healthStatus]

  return (
    <main className="page">
      <h1>语音约碰面地点</h1>

      <label className="city-field">
        城市
        <input
          value={city}
          onChange={(event) => setCity(event.target.value)}
          autoComplete="off"
        />
      </label>

      <RecorderPanel />

      <p className="health-line">
        {healthText}
        {requestId ? ` ｜ request_id：${requestId}` : ''}
      </p>
    </main>
  )
}

export default App
