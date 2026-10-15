import axios from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'sl_token'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    // 会话滑动续期：后端在令牌剩余不足一半时通过该头下发新令牌
    const fresh = response.headers?.['x-refresh-token']
    if (fresh) {
      localStorage.setItem(TOKEN_KEY, fresh)
    }
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return body.data
      }
      // 4011：需要滑动验证码（新设备登录），由页面自行处理，不弹全局错误
      if (body.code !== 4011) {
        ElMessage.error(body.msg || '请求失败')
      }
      const err = new Error(body.msg || '请求失败')
      err.code = body.code
      err.data = body.data
      return Promise.reject(err)
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.msg
    if (status === 401) {
      ElMessage.error(msg || '登录已失效，请重新登录')
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('sl_user')
      if (!location.hash.startsWith('#/login')) {
        location.hash = '#/login'
      }
    } else {
      ElMessage.error(msg || '网络异常，请稍后重试')
    }
    return Promise.reject(error)
  },
)

export default http
