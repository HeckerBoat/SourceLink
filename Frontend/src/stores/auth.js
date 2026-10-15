import { defineStore } from 'pinia'

import http from '@/api/http'

const USER_KEY = 'sl_user'
const DEVICE_KEY = 'sl_device_id'

function ensureDeviceId() {
  let id = localStorage.getItem(DEVICE_KEY)
  if (!id) {
    id = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `d-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem(DEVICE_KEY, id)
  }
  return id
}

// 真实登录态由服务端 Cookie 会话判定；localStorage 仅缓存用户信息用于首屏渲染
export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.user),
    isAdmin: (state) => Boolean(state.user && state.user.is_admin),
    displayName: (state) => {
      if (!state.user) return ''
      return state.user.username || state.user.phone || state.user.email || ''
    },
  },
  actions: {
    deviceId() {
      return ensureDeviceId()
    },
    setAuth(user) {
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    setUser(user) {
      this.setAuth(user)
    },
    // 启动时与服务端同步登录态：Cookie 会话无效则清空本地缓存
    async fetchMe() {
      try {
        const user = await http.get('/auth/me')
        this.setAuth(user)
      } catch {
        this.user = null
        localStorage.removeItem(USER_KEY)
      }
    },
    async logout() {
      try {
        await http.post('/auth/logout')
      } catch {
        // 会话可能已过期，本地照常清理
      }
      this.user = null
      localStorage.removeItem(USER_KEY)
    },
  },
})
