import { defineStore } from 'pinia'

const TOKEN_KEY = 'sl_token'
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

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
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
    setAuth(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    setUser(user) {
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    },
  },
})
