<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <div class="auth-brand">
        <span class="logo"><el-icon><Link /></el-icon></span>
        <span class="title">{{ site.siteName }}</span>
      </div>
      <p class="auth-subtitle">商业化虚拟资源托管平台 · 请登录后查看资源</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @submit.prevent>
        <el-form-item label="账号" prop="account">
          <el-input v-model="form.account" placeholder="用户名 / 手机号 / 邮箱" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="onSubmit">登 录</el-button>
      </el-form>

      <template v-if="needCaptcha">
        <el-alert
          class="captcha-alert"
          type="warning"
          :closable="false"
          show-icon
          title="检测到新设备登录，请完成滑动验证后自动重试"
        />
        <div class="captcha-slot">
          <SliderCaptcha ref="captchaRef" @verified="onCaptchaVerified" />
        </div>
      </template>

      <div class="auth-footer">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import SliderCaptcha from '@/components/SliderCaptcha.vue'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const site = useSiteStore()

site.loadPublicConfig()

const formRef = ref()
const captchaRef = ref()
const loading = ref(false)
const needCaptcha = ref(false)
const captchaTicket = ref('')
const form = reactive({ account: '', password: '' })
const rules = {
  account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function onCaptchaVerified(ticket) {
  captchaTicket.value = ticket
  doLogin()
}

async function onSubmit() {
  await formRef.value.validate()
  // 新设备场景下滑动验证通过后会自动调用 doLogin；避免重复提交
  if (needCaptcha.value && !captchaTicket.value) {
    ElMessage.warning('请先完成滑动验证')
    return
  }
  await doLogin()
}

async function doLogin() {
  loading.value = true
  try {
    const data = await http.post('/auth/login', {
      account: form.account,
      password: form.password,
      device_id: auth.deviceId(),
      captcha_ticket: captchaTicket.value,
    })
    auth.setAuth(data.token, data.user)
    needCaptcha.value = false
    captchaTicket.value = ''
    ElMessage.success('登录成功')
    const redirect = route.query.redirect
    if (redirect && typeof redirect === 'string' && !redirect.startsWith('/login')) {
      router.push(redirect)
    } else {
      router.push(data.user.is_admin ? '/admin/resources' : '/')
    }
  } catch (err) {
    if (err?.code === 4011) {
      needCaptcha.value = true
    } else {
      // 密码错误等其他失败：已通过的滑动验证可能已消费，重置重试
      if (needCaptcha.value) {
        captchaTicket.value = ''
        captchaRef.value?.reset()
      }
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.captcha-alert {
  margin: 4px 0 12px;
}

.captcha-slot {
  margin-bottom: 16px;
}
</style>
