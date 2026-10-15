<template>
  <h2 class="panel-title">站点配置</h2>

  <el-card v-loading="loading" style="max-width: 640px">
    <el-form :model="form" :label-width="isMobile ? 'auto' : '150px'" :label-position="isMobile ? 'top' : 'right'">
      <el-form-item label="站点名称">
        <el-input v-model="form.site_name" maxlength="64" show-word-limit />
      </el-form-item>
      <el-form-item label="开放注册">
        <el-switch v-model="form.register_enabled" />
        <span class="form-tip">关闭后新用户无法注册</span>
      </el-form-item>
      <el-form-item label="短信注册渠道">
        <el-switch v-model="form.sms_channel_enabled" />
        <span class="form-tip">关闭后注册页不显示手机号注册</span>
      </el-form-item>
      <el-form-item label="邮箱注册渠道">
        <el-switch v-model="form.email_channel_enabled" />
        <span class="form-tip">关闭后注册页不显示邮箱注册</span>
      </el-form-item>
      <el-form-item label="验证码有效期（秒）">
        <el-input-number v-model="form.code_ttl_seconds" :min="60" :max="1800" :step="60" />
      </el-form-item>
      <el-form-item label="重发间隔（秒）">
        <el-input-number v-model="form.code_resend_interval" :min="0" :max="600" :step="10" />
      </el-form-item>
      <el-form-item label="会话空闲失效（分钟）">
        <el-input-number v-model="form.session_idle_minutes" :min="5" :max="10080" :step="5" />
        <span class="form-tip">无操作超过该时长需重新登录，活跃用户自动续期不掉线</span>
      </el-form-item>
      <el-form-item label="资源有效期">
        <div class="ttl-row">
          <el-input-number v-model="form.resource_ttl_months" :min="0" :max="120" />
          <span class="ttl-unit">月</span>
          <el-input-number v-model="form.resource_ttl_days" :min="0" :max="3650" />
          <span class="ttl-unit">天</span>
          <el-input-number v-model="form.resource_ttl_hours" :min="0" :max="87600" />
          <span class="ttl-unit">小时</span>
        </div>
        <span class="form-tip">三项均为 0 表示永久有效；过期资源自动下架且无法上架</span>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="onSave">保存配置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-alert
    style="max-width: 640px; margin-top: 18px"
    type="info"
    :closable="false"
    title="SMTP 邮箱账号、短信厂商密钥等敏感配置在服务端 .env 文件中维护，不在页面暴露。未配置真实渠道时，验证码会直接打印在后端终端以便联调。"
  />
</template>

<script setup>
import { ref, reactive, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import { useSiteStore } from '@/stores/site'

const siteStore = useSiteStore()
const loading = ref(false)
const saving = ref(false)

// 移动端改为顶部标签布局
const mobileQuery = window.matchMedia('(max-width: 768px)')
const isMobile = ref(mobileQuery.matches)
const onMediaChange = (e) => {
  isMobile.value = e.matches
}

const form = reactive({
  site_name: '',
  register_enabled: true,
  sms_channel_enabled: true,
  email_channel_enabled: true,
  code_ttl_seconds: 300,
  code_resend_interval: 60,
  session_idle_minutes: 60,
  resource_ttl_months: 0,
  resource_ttl_days: 0,
  resource_ttl_hours: 0,
})

async function load() {
  loading.value = true
  try {
    const data = await http.get('/admin/config')
    form.site_name = data.site_name
    form.register_enabled = data.register_enabled === 'true'
    form.sms_channel_enabled = data.sms_channel_enabled === 'true'
    form.email_channel_enabled = data.email_channel_enabled === 'true'
    form.code_ttl_seconds = Number(data.code_ttl_seconds)
    form.code_resend_interval = Number(data.code_resend_interval)
    form.session_idle_minutes = Number(data.session_idle_minutes) || 60
    form.resource_ttl_months = Number(data.resource_ttl_months) || 0
    form.resource_ttl_days = Number(data.resource_ttl_days) || 0
    form.resource_ttl_hours = Number(data.resource_ttl_hours) || 0
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    await http.put('/admin/config', {
      site_name: form.site_name,
      register_enabled: form.register_enabled,
      sms_channel_enabled: form.sms_channel_enabled,
      email_channel_enabled: form.email_channel_enabled,
      code_ttl_seconds: String(form.code_ttl_seconds),
      code_resend_interval: String(form.code_resend_interval),
      session_idle_minutes: String(form.session_idle_minutes),
      resource_ttl_months: String(form.resource_ttl_months),
      resource_ttl_days: String(form.resource_ttl_days),
      resource_ttl_hours: String(form.resource_ttl_hours),
    })
    ElMessage.success('配置已保存')
    siteStore.loadPublicConfig(true)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  mobileQuery.addEventListener('change', onMediaChange)
})

onBeforeUnmount(() => mobileQuery.removeEventListener('change', onMediaChange))
</script>

<style scoped>
.form-tip {
  margin-left: 12px;
  color: var(--sl-text-sub);
  font-size: 12px;
}

.ttl-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ttl-unit {
  color: var(--sl-text-sub);
  font-size: 13px;
  min-width: 18px;
}

@media (max-width: 768px) {
  .form-tip {
    display: block;
    margin: 4px 0 0;
  }
}
</style>
