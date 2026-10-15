<template>
  <h2 class="panel-title">资源块管理</h2>

  <div class="toolbar">
    <span style="color: var(--sl-text-sub); font-size: 13px">共 {{ resources.length }} 个资源块</span>
    <el-button type="primary" @click="openCreate">
      <el-icon style="margin-right: 4px"><Plus /></el-icon>新建资源块
    </el-button>
  </div>

  <el-table :data="resources" v-loading="loading" border stripe>
    <el-table-column prop="id" label="ID" width="70" />
    <el-table-column prop="name" label="资源名称" min-width="140" show-overflow-tooltip />
    <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
      <template #default="{ row }">{{ row.description || '-' }}</template>
    </el-table-column>
    <el-table-column label="网盘链接" min-width="180">
      <template #default="{ row }"><span class="link-text">{{ row.pan_url }}</span></template>
    </el-table-column>
    <el-table-column label="购买链接" min-width="180">
      <template #default="{ row }"><span class="link-text">{{ row.purchase_url }}</span></template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{ row }">
        <el-tag v-if="row.expired" type="danger" size="small">已过期</el-tag>
        <el-tag v-else :type="row.is_published ? 'success' : 'info'" size="small">
          {{ row.is_published ? '已上架' : '已下架' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="创建日期" width="110">
      <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
    </el-table-column>
    <el-table-column label="更新时间" width="160">
      <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="140" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="openEdit(row)">编辑</el-button>
        <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="dialogVisible" :title="editingId ? '编辑资源块' : '新建资源块'" width="min(560px, 94vw)" :close-on-click-modal="false">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="104px">
      <el-form-item label="资源名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入资源名称" maxlength="128" />
      </el-form-item>
      <el-form-item label="资源描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选，展示在资源卡片上" maxlength="500" />
      </el-form-item>
      <el-form-item label="网盘链接" prop="pan_url">
        <el-input v-model="form.pan_url" placeholder="https://..." />
      </el-form-item>
      <el-form-item label="购买链接" prop="purchase_url">
        <el-input v-model="form.purchase_url" placeholder="第三方购买页面 https://..." />
      </el-form-item>
      <el-form-item :label="editingId ? '重置密码' : '资源块密码'" prop="block_password">
        <el-input v-model="form.block_password" type="password" show-password :placeholder="editingId ? '留空则不修改原密码' : '用户查看资源时需输入'" />
      </el-form-item>
      <el-form-item label="是否上架">
        <el-switch v-model="form.is_published" :disabled="editingExpired" />
        <span v-if="editingExpired" style="margin-left: 8px; color: var(--el-color-danger); font-size: 12px">
          已过期资源无法上架
        </span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '@/api/http'
import { formatTime, formatDate } from '@/utils/format'

const loading = ref(false)
const saving = ref(false)
const resources = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const editingExpired = ref(false)
const formRef = ref()

const emptyForm = () => ({
  name: '',
  description: '',
  pan_url: '',
  purchase_url: '',
  block_password: '',
  is_published: true,
})
const form = reactive(emptyForm())

const urlValidator = (_rule, value, callback) => {
  if (!/^https?:\/\/.+/.test(value || '')) callback(new Error('链接必须以 http:// 或 https:// 开头'))
  else callback()
}

const rules = {
  name: [{ required: true, message: '请输入资源名称', trigger: 'blur' }],
  pan_url: [
    { required: true, message: '请输入网盘链接', trigger: 'blur' },
    { validator: urlValidator, trigger: 'blur' },
  ],
  purchase_url: [
    { required: true, message: '请输入购买链接', trigger: 'blur' },
    { validator: urlValidator, trigger: 'blur' },
  ],
  block_password: [
    {
      validator: (_rule, value, callback) => {
        if (!editingId.value && !value) callback(new Error('请设置资源块密码'))
        else if (value && value.length > 64) callback(new Error('密码最长 64 位'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

async function load() {
  loading.value = true
  try {
    resources.value = await http.get('/admin/resources')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  editingExpired.value = false
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  editingExpired.value = Boolean(row.expired)
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    pan_url: row.pan_url,
    purchase_url: row.purchase_url,
    block_password: '',
    is_published: row.is_published,
  })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value && !payload.block_password) delete payload.block_password
    if (editingId.value) {
      await http.put(`/admin/resources/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await http.post('/admin/resources', payload)
      ElMessage.success('创建成功')
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
    await ElMessageBox.confirm(`确定删除资源块「${row.name}」吗？此操作不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await http.delete(`/admin/resources/${row.id}`)
    ElMessage.success('删除成功')
    load()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

onMounted(load)
</script>
