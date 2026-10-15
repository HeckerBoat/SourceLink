import axios from 'axios'
import { ElMessage } from 'element-plus'

// 登录态由 HttpOnly Cookie 维持（需求 10：cookie 存储登录信息，不采用令牌校验），
// 请求只需携带 Cookie，无需手动附加任何令牌头
const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  withCredentials: true,
})

http.interceptors.response.use(
  (response) => {
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
      // 会话空闲超时或被强制下线：清除本地缓存的登录信息并跳转登录页
      ElMessage.error(msg || '登录已失效，请重新登录')
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
