import { useEffect, useRef, useState } from 'react'
import {
  MAX_DURATION_MS,
  MAX_FILE_BYTES,
  MIN_DURATION_MS,
  detectSupportedMimeType,
  extensionForMimeType,
  formatDuration,
  formatFileSize,
} from '../audioSupport.js'

const UNSUPPORTED_MESSAGE = '当前浏览器不支持可用的录音格式，请更换 Chrome、Edge 或 Firefox 后重试'

function releaseStream(stream) {
  if (!stream) return
  stream.getTracks().forEach((track) => track.stop())
}

function RecorderPanel() {
  const mimeType = detectSupportedMimeType()
  const [phase, setPhase] = useState('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [error, setError] = useState(mimeType ? '' : UNSUPPORTED_MESSAGE)
  const [clip, setClip] = useState(null)

  const phaseRef = useRef('idle')
  const streamRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const startedAtRef = useRef(0)
  const maxTimerRef = useRef(0)
  const tickTimerRef = useRef(0)
  const clipUrlRef = useRef('')
  const finishReasonRef = useRef('stop')
  const pointerIdRef = useRef(null)
  const unmountedRef = useRef(false)

  function setPhaseBoth(next) {
    phaseRef.current = next
    setPhase(next)
  }

  function clearTimers() {
    window.clearTimeout(maxTimerRef.current)
    window.clearInterval(tickTimerRef.current)
    maxTimerRef.current = 0
    tickTimerRef.current = 0
  }

  function dropPendingStream() {
    releaseStream(streamRef.current)
    streamRef.current = null
  }

  function replaceClip(nextClip) {
    if (clipUrlRef.current) {
      URL.revokeObjectURL(clipUrlRef.current)
      clipUrlRef.current = ''
    }
    if (nextClip) {
      clipUrlRef.current = URL.createObjectURL(nextClip.blob)
      setClip({ ...nextClip, url: clipUrlRef.current })
    } else {
      setClip(null)
    }
  }

  function finalizeClip(blob, durationMs) {
    if (finishReasonRef.current === 'cancel') {
      setError('已取消录音')
      replaceClip(null)
      return
    }

    if (durationMs < MIN_DURATION_MS || durationMs > MAX_DURATION_MS) {
      setError(`录音时长需在1—60秒之间，本次约 ${formatDuration(durationMs)}，请重新录制`)
      replaceClip(null)
      return
    }

    if (blob.size > MAX_FILE_BYTES) {
      setError('录音文件过大，请控制在5MB以内')
      replaceClip(null)
      return
    }

    if (blob.size === 0) {
      setError('录制失败，没有得到有效音频，请重试')
      replaceClip(null)
      return
    }

    setError('')
    replaceClip({
      blob,
      mimeType: blob.type || mimeType,
      size: blob.size,
      durationMs,
    })
  }

  function stopRecorderIfActive() {
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      return true
    }
    return false
  }

  function finishRecording(reason) {
    if (phaseRef.current === 'idle') return

    finishReasonRef.current = reason
    clearTimers()

    if (phaseRef.current === 'requesting') {
      setPhaseBoth('idle')
      dropPendingStream()
      if (reason === 'cancel') setError('已取消录音')
      return
    }

    const stopped = stopRecorderIfActive()
    dropPendingStream()
    if (!stopped) {
      setPhaseBoth('idle')
    }
  }

  async function startRecording() {
    if (!mimeType || phaseRef.current !== 'idle') return

    setError('')
    setElapsedMs(0)
    finishReasonRef.current = 'stop'
    chunksRef.current = []
    setPhaseBoth('requesting')

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (err) {
      if (unmountedRef.current) return
      setPhaseBoth('idle')
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setError('无法使用麦克风：浏览器拒绝了授权，请在地址栏允许麦克风后重试')
        return
      }
      setError('录制失败，请检查麦克风设备后重试')
      return
    }

    if (unmountedRef.current || phaseRef.current !== 'requesting') {
      releaseStream(stream)
      return
    }

    streamRef.current = stream

    let recorder
    try {
      recorder = new MediaRecorder(stream, { mimeType })
    } catch {
      releaseStream(stream)
      streamRef.current = null
      setPhaseBoth('idle')
      setError('录制失败，无法按当前格式开始录音')
      return
    }

    recorderRef.current = recorder

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        chunksRef.current.push(event.data)
      }
    }

    recorder.onerror = () => {
      finishReasonRef.current = 'cancel'
      setError('录制失败，请重试')
      finishRecording('cancel')
    }

    recorder.onstop = () => {
      const durationMs = Math.min(Date.now() - startedAtRef.current, MAX_DURATION_MS)
      const blob = new Blob(chunksRef.current, { type: mimeType })
      chunksRef.current = []
      recorderRef.current = null
      dropPendingStream()
      setPhaseBoth('idle')
      finalizeClip(blob, durationMs)
    }

    startedAtRef.current = Date.now()
    recorder.start()
    setPhaseBoth('recording')

    tickTimerRef.current = window.setInterval(() => {
      setElapsedMs(Math.min(Date.now() - startedAtRef.current, MAX_DURATION_MS))
    }, 100)

    maxTimerRef.current = window.setTimeout(() => {
      setElapsedMs(MAX_DURATION_MS)
      finishRecording('max')
    }, MAX_DURATION_MS)
  }

  function onPointerDown(event) {
    if (event.button !== 0 || !mimeType) return
    event.preventDefault()
    pointerIdRef.current = event.pointerId
    event.currentTarget.setPointerCapture(event.pointerId)
    startRecording()
  }

  function onPointerUp(event) {
    if (pointerIdRef.current !== null && event.pointerId !== pointerIdRef.current) return
    pointerIdRef.current = null
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    finishRecording('stop')
  }

  function onPointerCancel(event) {
    pointerIdRef.current = null
    finishRecording('cancel')
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === 'Escape' && phaseRef.current !== 'idle') {
        finishRecording('cancel')
      }
    }

    window.addEventListener('keydown', onKeyDown)
    unmountedRef.current = false
    return () => {
      unmountedRef.current = true
      window.removeEventListener('keydown', onKeyDown)
      clearTimers()
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        recorderRef.current.onstop = null
        recorderRef.current.stop()
      }
      dropPendingStream()
      if (clipUrlRef.current) URL.revokeObjectURL(clipUrlRef.current)
    }
  }, [])

  const isBusy = phase === 'requesting' || phase === 'recording'
  const downloadName = `meet-recording.${extensionForMimeType(clip?.mimeType || mimeType)}`

  return (
    <section className="recorder">
      {!mimeType && <p className="recorder-error">{UNSUPPORTED_MESSAGE}</p>}

      {mimeType && (
        <p className="recorder-meta">将使用格式：{mimeType}</p>
      )}

      <button
        type="button"
        className={`record-button ${isBusy ? 'record-button-active' : ''}`}
        disabled={!mimeType}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        onContextMenu={(event) => event.preventDefault()}
      >
        {phase === 'recording' ? `录音中 ${formatDuration(elapsedMs)}` : phase === 'requesting' ? '正在打开麦克风…' : '按住说话'}
      </button>

      <p className="recorder-hint">
        按住按钮录音，松开结束。移出按钮后松开、按 Esc 取消、或满 60 秒都会结束并释放麦克风。
      </p>

      {error && <p className="recorder-error">{error}</p>}
      {phase === 'recording' && elapsedMs >= MAX_DURATION_MS && (
        <p className="recorder-hint">已达 60 秒上限，录音已自动结束。</p>
      )}

      {clip && (
        <div className="recorder-result">
          <p>本地试听</p>
          <audio controls src={clip.url} />
          <p className="recorder-meta">
            格式 {clip.mimeType} ｜ 大小 {formatFileSize(clip.size)}（{clip.size} 字节）｜ 时长 {formatDuration(clip.durationMs)}
          </p>
          <a className="download-link" href={clip.url} download={downloadName}>
            下载录音文件（临时，供后续独立测试上传）
          </a>
        </div>
      )}
    </section>
  )
}

export default RecorderPanel
