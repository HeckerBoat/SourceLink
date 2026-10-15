import { defineStore } from 'pinia'

import http from '@/api/http'

export const useSiteStore = defineStore('site', {
  state: () => ({
    loaded: false,
    siteName: 'SourceLink 资源托管平台',
    registerEnabled: true,
    smsEnabled: true,
    emailEnabled: true,
  }),
  actions: {
    async loadPublicConfig(force = false) {
      if (this.loaded && !force) return
      const data = await http.get('/config/public')
      this.siteName = data.site_name || this.siteName
      this.registerEnabled = data.register_enabled === 'true'
      this.smsEnabled = data.sms_channel_enabled === 'true'
      this.emailEnabled = data.email_channel_enabled === 'true'
      this.loaded = true
      document.title = this.siteName
    },
  },
})
