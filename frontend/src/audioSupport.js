// 按实际能力检测录音格式，不以浏览器名称推断。
// 优先级与已确认方案一致：WebM/Opus → WebM → Ogg/Opus。

export const PREFERRED_MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
]

export const MIN_DURATION_MS = 1000
export const MAX_DURATION_MS = 60_000
export const MAX_FILE_BYTES = 5 * 1024 * 1024

export function detectSupportedMimeType() {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
    return null
  }

  return PREFERRED_MIME_TYPES.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) ?? null
}

export function extensionForMimeType(mimeType) {
  if (!mimeType) return 'webm'
  if (mimeType.includes('ogg')) return 'ogg'
  if (mimeType.includes('webm')) return 'webm'
  return 'webm'
}

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function formatDuration(ms) {
  return `${(ms / 1000).toFixed(1)} 秒`
}
