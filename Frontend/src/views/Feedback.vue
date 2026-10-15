<template>
  <div class="page-container feedback-page">
    <div class="panel-title">意见反馈</div>

    <el-card class="feedback-card" shadow="never">
      <el-form @submit.prevent>
        <el-form-item>
          <el-input
            v-model="content"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="欢迎反馈使用问题或改进建议（2000 字以内）"
          />
        </el-form-item>
        <el-button type="primary" :loading="submitting" @click="onSubmit">提交反馈</el-button>
      </el-form>
    </el-card>

    <div class="feedback-list-header">
      <div class="feedback-list-title">
        {{ auth.isAdmin ? '全部用户反馈' : '我的反馈' }}
      </div>
      <el-button
        v-if="auth.isAdmin && items.length"
        type="danger"
        plain
        size="small"
        @click="onClearAll"
      >
        清空全部反馈
      </el-button>
    </div>
    <div v-loading="loading">
      <template v-if="items.length">
        <el-card v-for="item in items" :key="item.id" class="feedback-item" shadow="never">
          <div class="feedback-meta">
            <span v-if="auth.isAdmin" class="feedback-user">{{ item.account }}</span>
            <span class="feedback-time">{{ formatTime(item.created_at) }}</span>
            <el-button
              v-if="auth.isAdmin"
              class="feedback-delete"
              size="small"
              type="danger"
              link
              @click="onDelete(item)"
            >
              删除
            </el-button>
          </div>
          <div class="feedback-content">{{ item.content }}</div>
        </el-card>
      </template>
      <el-empty v-else-if="!loading" description="暂无反馈记录" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import http from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()
const content = ref('')
const items = ref([])
const loading = ref(false)
const submitting = ref(false)

async function loadList() {
  loading.value = true
  try {
    items.value = await http.get('/feedback')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function onSubmit() {
  if (!content.value.trim()) {
    ElMessage.warning('请输入反馈内容')
    return
  }
  submitting.value = true
  try {
    await http.post('/feedback', { content: content.value.trim() })
    ElMessage.success('反馈已提交，感谢您的建议')
    content.value = ''
    await loadList()
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function onDelete(item) {
  try {
    await ElMessageBox.confirm('确定删除该条反馈吗？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await http.delete(`/feedback/${item.id}`)
    ElMessage.success('删除成功')
    await loadList()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

async function onClearAll() {
  try {
    await ElMessageBox.confirm(`确定清空全部 ${items.value.length} 条反馈吗？此操作不可恢复。`, '清空确认', {
      type: 'warning',
      confirmButtonText: '全部清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const data = await http.delete('/feedback')
    ElMessage.success(`已清空 ${data?.deleted ?? 0} 条反馈`)
    await loadList()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

onMounted(loadList)
</script>

<style scoped>
.feedback-page {
  max-width: 860px;
}

.feedback-card {
  border-radius: var(--sl-radius);
}

.feedback-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 24px 0 14px;
}

.feedback-list-title {
  font-size: 16px;
  font-weight: 700;
}

.feedback-delete {
  margin-left: auto;
}

.feedback-item {
  border-radius: var(--sl-radius);
  margin-bottom: 12px;
}

.feedback-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 12px;
  color: var(--sl-text-sub);
  margin-bottom: 6px;
}

.feedback-user {
  color: var(--sl-primary);
  font-weight: 600;
}

.feedback-content {
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
