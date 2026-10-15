<template>
  <div class="page-container">
    <div class="panel-title">用户管理</div>

    <div class="table-toolbar">
      <el-input
        v-model="keyword"
        placeholder="按用户名 / 手机号 / 邮箱精确搜索"
        clearable
        style="max-width: 320px"
        @keyup.enter="load"
        @clear="load"
      >
        <template #append>
          <el-button @click="load">搜索</el-button>
        </template>
      </el-input>
      <el-button type="primary" @click="openCreate">新建用户</el-button>
    </div>

    <div class="table-scroll">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">{{ row.username || '—' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="130">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_admin ? 'danger' : 'info'" size="small">{{ row.is_admin ? '管理员' : '用户' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'warning'" size="small">{{ row.is_active ? '正常' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" min-width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <template v-if="!row.is_admin">
              <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button text type="danger" size="small" @click="onDelete(row)">删除</el-button>
            </template>
            <span v-else style="color: var(--sl-text-sub, #909399); font-size: 12px">内置账户</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新建用户'" width="min(520px, 94vw)" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="选填，字母 / 数字 / 下划线" clearable />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填，绑定后可用手机号登录" maxlength="11" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填，绑定后可用邮箱登录" clearable />
        </el-form-item>
        <el-form-item :label="editing ? '重置密码（留空则不修改）' : '初始密码'" prop="password">
          <el-input v-model="form.password" type="password" placeholder="6-64 位密码" show-password clearable />
        </el-form-item>
        <el-form-item v-if="editing" label="账户状态">
          <el-switch v-model="form.is_active" active-text="正常" inactive-text="停用" />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="用户名、手机号、邮箱至少保留一项作为登录账号" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '@/api/http'
import { formatTime } from '@/utils/format'

const PHONE_PATTERN = /^1[3-9]\d{9}$/
const EMAIL_PATTERN = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

const users = ref([])
const loading = ref(false)
const keyword = ref('')

const dialogVisible = ref(false)
const editing = ref(null)
const saving = ref(false)
const formRef = ref()
const form = reactive({ username: '', phone: '', email: '', password: '', is_active: true })

const validateAccount = (_rule, _value, callback) => {
  if (!form.username.trim() && !form.phone.trim() && !form.email.trim()) {
    callback(new Error('用户名、手机号、邮箱至少填写一项'))
  } else {
    callback()
  }
}
const validatePhone = (_rule, value, callback) => {
  if (value && !PHONE_PATTERN.test(value.trim())) callback(new Error('手机号格式不正确'))
  else callback()
}
const validateEmail = (_rule, value, callback) => {
  if (value && !EMAIL_PATTERN.test(value.trim())) callback(new Error('邮箱格式不正确'))
  else callback()
}
const validatePassword = (_rule, value, callback) => {
  if (!editing.value && !value) callback(new Error('请设置初始密码'))
  else if (value && (value.length < 6 || value.length > 64)) callback(new Error('密码长度需为 6-64 位'))
  else callback()
}

const formRules = {
  username: [{ validator: validateAccount, trigger: 'blur' }],
  phone: [{ validator: validatePhone, trigger: 'blur' }],
  email: [{ validator: validateEmail, trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    users.value = await http.get('/admin/users', { params: { keyword: keyword.value.trim() } })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  form.username = row.username || ''
  form.phone = row.phone || ''
  form.email = row.email || ''
  form.password = ''
  form.is_active = row.is_active
  dialogVisible.value = true
}

function resetForm() {
  form.username = ''
  form.phone = ''
  form.email = ''
  form.password = ''
  form.is_active = true
  editing.value = null
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      username: form.username.trim(),
      phone: form.phone.trim(),
      email: form.email.trim(),
    }
    if (form.password) payload.password = form.password
    if (editing.value) {
      payload.is_active = form.is_active
      await http.put(`/admin/users/${editing.value.id}`, payload)
      ElMessage.success('用户已更新')
    } else {
      await http.post('/admin/users', { ...payload, password: form.password })
      ElMessage.success('用户已创建')
    }
    dialogVisible.value = false
    load()
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username || row.phone || row.email}」吗？其登录会话与可信设备将一并清除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await http.delete(`/admin/users/${row.id}`)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.table-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.table-scroll {
  overflow-x: auto;
}
</style>
