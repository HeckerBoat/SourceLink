<template>
  <div class="auth-page">
    <el-card class="auth-card">
      <div class="auth-brand">
        <span class="logo"><el-icon><Link /></el-icon></span>
        <span class="title">注册账号</span>
      </div>
      <p class="auth-subtitle">短信验证码或邮箱验证码，任选一种验证通过即可注册</p>

      <el-tabs v-model="form.channel" stretch>
        <el-tab-pane v-if="site.smsEnabled" label="手机号注册" name="sms">
          <el-input v-model="form.target" placeholder="请输入手机号" :prefix-icon="Iphone" clearable />
        </el-tab-pane>
        <el-tab-pane v-if="site.emailEnabled" label="邮箱注册" name="email">
          <el-input v-model="form.target" placeholder="请输入邮箱地址" :prefix-icon="Message" clearable />
        </el-tab-pane>
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @submit.prevent>
        <el-form-item label="验证码" prop="code">
          <div style="display: flex; gap: 10px; width: 100%">
            <el-input v-model="form.code" placeholder="请输入 6 位验证码" :prefix-icon="Key" maxlength="6" />
            <el-button :disabled="countdown > 0" :loading="sending" style="width: 128px" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="6-64 位密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item v-if="!captchaPassed" label="滑动验证">
          <div class="captcha-slot">
            <SliderCaptcha ref="captchaRef" @verified="onCaptchaVerified" />
          </div>
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="onSubmit">注 册</el-button>
      </el-form>

      <div class="auth-footer">
        已有账号？<router-link to="/login">返回登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { Iphone, Key, Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import SliderCaptcha from '@/components/SliderCaptcha.vue'
import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const router = useRouter()
const auth = useAuthStore()
const site = useSiteStore()

site.loadPublicConfig().then(() => {
  // 默认渠道被管理员关闭时，自动切到可用渠道
  if (!site.smsEnabled && site.emailEnabled) form.channel = 'email'
  else if (site.smsEnabled && !site.emailEnabled) form.channel = 'sms'
})

const formRef = ref()
const captchaRef = ref()
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
const captchaTicket = ref('')
const captchaPassed = ref(false) // 滑动验证通过后从前端去掉验证码组件（需求 7）
let timer = null

const form = reactive({
  channel: 'sms',
  target: '',
  code: '',
  password: '',
  confirm: '',
})

const validateConfirm = (_rule, value, callback) => {
  if (value !== form.password) callback(new Error('两次输入的密码不一致'))
  else callback()
}

const rules = {
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6-64 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

function onCaptchaVerified(ticket) {
  captchaTicket.value = ticket
  captchaPassed.value = true // 验证成功，去掉验证码组件
}

async function onSendCode() {
  if (!form.target.trim()) {
    ElMessage.warning(form.channel === 'sms' ? '请输入手机号' : '请输入邮箱地址')
    return
  }
  sending.value = true
  try {
    await http.post('/verification/send', { target: form.target.trim(), channel: form.channel })
    ElMessage.success('验证码已发送，请注意查收')
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    sending.value = false
  }
}

async function onSubmit() {
  await formRef.value.validate()
  if (!captchaTicket.value) {
    ElMessage.warning('请先拖动滑块完成滑动验证')
    return
  }
  loading.value = true
  try {
    const data = await http.post('/auth/register', {
      channel: form.channel,
      target: form.target.trim(),
      code: form.code.trim(),
      password: form.password,
      captcha_ticket: captchaTicket.value,
      device_id: auth.deviceId(),
    })
    auth.setAuth(data.user)
    ElMessage.success('注册成功')
    router.push('/')
  } catch {
    // 失败后滑动验证凭证已消费，刷新重试
    captchaTicket.value = ''
    captchaPassed.value = false
    captchaRef.value?.reset()
  } finally {
    loading.value = false
  }
}

onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<style scoped>
.captcha-slot {
  width: 100%;
}
</style>
