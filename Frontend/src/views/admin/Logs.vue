<template>
  <h2 class="panel-title">访问记录</h2>

  <div class="toolbar">
    <span style="color: var(--sl-text-sub); font-size: 13px">最近 100 条资源解锁尝试（含失败记录）</span>
    <div class="toolbar-actions">
      <el-button type="danger" plain :disabled="!logs.length" @click="onClearAll">
        <el-icon style="margin-right: 4px"><Delete /></el-icon>清空全部
      </el-button>
      <el-button @click="load">
        <el-icon style="margin-right: 4px"><Refresh /></el-icon>刷新
      </el-button>
    </div>
  </div>

  <el-table :data="logs" v-loading="loading" border stripe>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="时间" width="180">
      <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
    </el-table-column>
    <el-table-column prop="user_account" label="用户" min-width="160" show-overflow-tooltip />
    <el-table-column prop="resource_name" label="资源块" min-width="180" show-overflow-tooltip />
    <el-table-column label="结果" width="110">
      <template #default="{ row }">
        <el-tag :type="row.success ? 'success' : 'danger'" size="small">
          {{ row.success ? '解锁成功' : '密码错误' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="90" fixed="right">
      <template #default="{ row }">
        <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '@/api/http'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const logs = ref([])

async function load() {
  loading.value = true
  try {
    logs.value = await http.get('/admin/logs')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除该条访问记录（#${row.id}）吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await http.delete(`/admin/logs/${row.id}`)
    ElMessage.success('删除成功')
    await load()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

async function onClearAll() {
  try {
    await ElMessageBox.confirm(`确定清空全部 ${logs.value.length} 条访问记录吗？此操作不可恢复。`, '清空确认', {
      type: 'warning',
      confirmButtonText: '全部清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const data = await http.delete('/admin/logs')
    ElMessage.success(`已清空 ${data?.deleted ?? 0} 条访问记录`)
    await load()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar-actions {
  display: flex;
  gap: 8px;
}
</style>
