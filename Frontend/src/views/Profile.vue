<template>
  <div class="page-container profile-page">
    <div class="panel-title">我的</div>

    <el-card class="profile-card" shadow="never" v-loading="loading">
      <div class="info-row">
        <span class="info-label">用户名</span>
        <span>{{ auth.user?.username || '未设置' }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">邮箱</span>
        <span>
          {{ auth.user?.email || '未绑定' }}
          <el-tag v-if="auth.user?.email" size="small" type="success" style="margin-left: 8px">已绑定</el-tag>
        </span>
      </div>
      <div class="info-row">
        <span class="info-label">手机号</span>
        <span>
          {{ auth.user?.phone || '未绑定' }}
          <el-tag v-if="auth.user?.phone" size="small" type="success" style="margin-left: 8px">已绑定</el-tag>
        </span>
      </div>
      <div class="info-row">
        <span class="info-label">注册时间</span>
        <span>{{ formatTime(auth.user?.created_at) }}</span>
      </div>
    </el-card>

    <el-card v-if="!auth.user?.email" class="profile-card" shadow="never">
      <div class="bind-title">绑定邮箱</div>
      <div class="bind-tip">输入邮箱发送验证码，验证通过即可绑定；绑定后可使用邮箱登录账号。</div>
      <el-form class="bind-form" @submit.prevent>
        <el-form-item :error="emailError">
          <el-input
            v-model="email"
            clearable
            placeholder="请输入邮箱地址"
            @input="emailError = ''"
          >
            <template #prefix>
              <el-icon><Message /></el-icon>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <el-form class="bind-form" style="margin-top: 12px" @submit.prevent>
        <el-form-item :error="emailCodeError">
          <el-input
            v-model="emailCode"
            maxlength="6"
            clearable
            placeholder="请输入 6 位验证码"
            @input="emailCodeError = ''"
          >
            <template #prefix>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-button :disabled="countdown > 0" :loading="sending" @click="onSendEmailCode">
          {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
        </el-button>
        <el-button type="primary" :loading="bindingEmail" @click="onBindEmail">确认绑定</el-button>
      </el-form>
    </el-card>

    <el-card class="profile-card" shadow="never">
      <div class="bind-title">{{ auth.user?.phone ? '更换手机号' : '绑定手机号' }}</div>
      <div class="bind-tip">无需短信验证码，格式校验通过即可绑定；绑定后可使用手机号登录账号。</div>
      <el-form class="bind-form" @submit.prevent>
        <el-form-item :error="phoneError">
          <el-input
            v-model="phone"
            maxlength="11"
            clearable
            placeholder="请输入 11 位手机号"
            @input="phoneError = ''"
          >
            <template #prefix>
              <el-icon><Iphone /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-button type="primary" :loading="binding" @click="onBind">
          {{ auth.user?.phone ? '确认更换' : '确认绑定' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const PHONE_PATTERN = /^1[3-9]\d{9}$/
const EMAIL_PATTERN = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

const auth = useAuthStore()
const phone = ref('')
const phoneError = ref('')
const binding = ref(false)
const loading = ref(false)
const email = ref('')
const emailCode = ref('')
const emailError = ref('')
const emailCodeError = ref('')
const sending = ref(false)
const bindingEmail = ref(false)
const countdown = ref(0)
let timer = null

// 进入页面同步一次最新用户信息（手机号绑定状态等）
async function loadMe() {
  loading.value = true
  try {
    const user = await http.get('/auth/me')
    auth.setUser(user)
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function onBind() {
  const value = phone.value.trim()
  if (!PHONE_PATTERN.test(value)) {
    phoneError.value = '手机号格式不正确'
    return
  }
  binding.value = true
  try {
    const user = await http.post('/auth/bind-phone', { phone: value })
    auth.setUser(user)
    phone.value = ''
    ElMessage.success('手机号绑定成功，之后可使用该手机号登录')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    binding.value = false
  }
}

async function onSendEmailCode() {
  const value = email.value.trim()
  if (!EMAIL_PATTERN.test(value)) {
    emailError.value = '邮箱格式不正确'
    return
  }
  sending.value = true
  try {
    await http.post('/verification/send', { target: value, channel: 'email', purpose: 'bind_email' })
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

async function onBindEmail() {
  const value = email.value.trim()
  if (!EMAIL_PATTERN.test(value)) {
    emailError.value = '邮箱格式不正确'
    return
  }
  if (!emailCode.value.trim()) {
    emailCodeError.value = '请输入验证码'
    return
  }
  bindingEmail.value = true
  try {
    const user = await http.post('/auth/bind-email', { email: value, code: emailCode.value.trim() })
    auth.setUser(user)
    email.value = ''
    emailCode.value = ''
    ElMessage.success('邮箱绑定成功，之后可使用该邮箱登录')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    bindingEmail.value = false
  }
}

onMounted(loadMe)
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<style scoped>
.profile-page {
  max-width: 640px;
}

.profile-card {
  border-radius: var(--sl-radius);
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--sl-border, #ebeef5);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  width: 72px;
  flex-shrink: 0;
  color: var(--sl-text-sub);
}

.bind-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 6px;
}

.bind-tip {
  font-size: 12px;
  color: var(--sl-text-sub);
  margin-bottom: 14px;
  line-height: 1.6;
}

.bind-form {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.bind-form :deep(.el-form-item) {
  flex: 1;
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .bind-form {
    flex-direction: column;
  }

  .bind-form :deep(.el-form-item),
  .bind-form .el-button {
    width: 100%;
  }
}
</style>
