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

      <template v-if="needCaptcha && !captchaPassed">
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
        <span>还没有账号？<router-link to="/register">立即注册</router-link></span>
        <el-link type="primary" :underline="false" @click="forgotVisible = true">忘记密码？</el-link>
      </div>
    </el-card>

    <el-dialog v-model="forgotVisible" title="忘记密码" width="min(440px, 94vw)" @closed="resetForgot">
      <p class="forgot-tip">输入注册时使用的邮箱，通过邮箱验证码验证后即可重置密码。</p>
      <el-form ref="forgotFormRef" :model="forgotForm" :rules="forgotRules" label-position="top" @submit.prevent>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="forgotForm.email" placeholder="请输入注册邮箱" :prefix-icon="Message" clearable />
        </el-form-item>
        <el-form-item label="验证码" prop="code">
          <div style="display: flex; gap: 10px; width: 100%">
            <el-input v-model="forgotForm.code" placeholder="请输入 6 位验证码" :prefix-icon="Key" maxlength="6" />
            <el-button :disabled="forgotCountdown > 0" :loading="forgotSending" style="width: 128px" @click="onForgotSend">
              {{ forgotCountdown > 0 ? `${forgotCountdown}s 后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码" prop="password">
          <el-input v-model="forgotForm.password" type="password" placeholder="6-64 位新密码" :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm">
          <el-input v-model="forgotForm.confirm" type="password" placeholder="请再次输入新密码" :prefix-icon="Lock" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="forgotVisible = false">取 消</el-button>
        <el-button type="primary" :loading="forgotLoading" @click="onForgotSubmit">重置密码</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Key, Lock, Message, User } from '@element-plus/icons-vue'
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
const captchaPassed = ref(false) // 滑动验证通过后移除验证码组件（需求 7）
const captchaTicket = ref('')
const form = reactive({ account: '', password: '' })
const rules = {
  account: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function onCaptchaVerified(ticket) {
  captchaTicket.value = ticket
  captchaPassed.value = true // 验证成功，前端去掉验证码组件
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
    auth.setAuth(data.user)
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
      captchaPassed.value = false
    } else {
      // 密码错误等其他失败：已通过的滑动验证可能已消费，重置重试
      if (needCaptcha.value) {
        captchaTicket.value = ''
        captchaPassed.value = false
        captchaRef.value?.reset()
      }
    }
  } finally {
    loading.value = false
  }
}

// ---------------- 忘记密码（需求 4） ----------------

const forgotVisible = ref(false)
const forgotFormRef = ref()
const forgotSending = ref(false)
const forgotLoading = ref(false)
const forgotCountdown = ref(0)
let forgotTimer = null

const forgotForm = reactive({ email: '', code: '', password: '', confirm: '' })

const validateForgotConfirm = (_rule, value, callback) => {
  if (value !== forgotForm.password) callback(new Error('两次输入的密码不一致'))
  else callback()
}

const forgotRules = {
  email: [
    { required: true, message: '请输入注册邮箱', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6-64 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateForgotConfirm, trigger: 'blur' },
  ],
}

async function onForgotSend() {
  try {
    await forgotFormRef.value.validateField('email')
  } catch {
    return
  }
  forgotSending.value = true
  try {
    await http.post('/verification/send', {
      target: forgotForm.email.trim(),
      channel: 'email',
      purpose: 'reset_password',
    })
    ElMessage.success('验证码已发送，请注意查收')
    forgotCountdown.value = 60
    forgotTimer = setInterval(() => {
      forgotCountdown.value -= 1
      if (forgotCountdown.value <= 0) clearInterval(forgotTimer)
    }, 1000)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    forgotSending.value = false
  }
}

async function onForgotSubmit() {
  await forgotFormRef.value.validate()
  forgotLoading.value = true
  try {
    await http.post('/auth/forgot-password', {
      email: forgotForm.email.trim(),
      code: forgotForm.code.trim(),
      password: forgotForm.password,
    })
    ElMessage.success('密码已重置，请使用新密码登录')
    forgotVisible.value = false
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    forgotLoading.value = false
  }
}

function resetForgot() {
  forgotForm.email = ''
  forgotForm.code = ''
  forgotForm.password = ''
  forgotForm.confirm = ''
  forgotCountdown.value = 0
  if (forgotTimer) clearInterval(forgotTimer)
}

onBeforeUnmount(() => forgotTimer && clearInterval(forgotTimer))
</script>

<style scoped>
.captcha-alert {
  margin: 4px 0 12px;
}

.captcha-slot {
  margin-bottom: 16px;
}

.auth-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.forgot-tip {
  margin: 0 0 14px;
  font-size: 13px;
  color: var(--sl-text-sub, #909399);
  line-height: 1.6;
}
</style>
