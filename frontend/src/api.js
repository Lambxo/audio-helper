// Axios 请求封装。
// 本轮只封装 /health；录音上传、识别、提取、搜索、播报等接口
// 会在实现对应后端功能的轮次中依次补充，不在此提前实现。
import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://localhost:8003',
})

/**
 * 调用后端健康检查接口。
 * @returns {Promise<{request_id: string, data: {status: string}}>}
 */
export async function checkHealth() {
  const response = await apiClient.get('/health')
  return response.data
}

export default apiClient
