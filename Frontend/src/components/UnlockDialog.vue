<template>
  <el-dialog
    :model-value="modelValue"
    :title="stage === 'input' ? '解锁资源' : '资源网盘链接'"
    width="440px"
    :close-on-click-modal="false"
    @update:model-value="(v) => $emit('update:modelValue', v)"
    @closed="reset"
  >
    <template v-if="resource">
      <!-- 阶段一：输入资源块密码 -->
      <div v-if="stage === 'input'">
        <p style="color: var(--sl-text-sub); font-size: 13px; margin-top: 0">
          资源：<strong style="color: var(--sl-text)">{{ resource.name }}</strong>
        </p>
        <el-input
          v-model="password"
          type="password"
          placeholder="请输入资源块密码"
          :prefix-icon="Lock"
          show-password
          @keyup.enter="onUnlock"
        />
      </div>

      <!-- 阶段二：展示网盘链接 -->
      <div v-else class="unlock-result">
        <el-result icon="success" title="解锁成功" sub-title="请妥善保存您的资源链接">
          <template #extra>
            <div class="url-box">
              <el-input :model-value="panUrl" readonly>
                <template #prepend><el-icon><Link /></el-icon></template>
              </el-input>
              <el-button type="primary" @click="copyLink">复制</el-button>
            </div>
            <el-button tag="a" :href="panUrl" target="_blank" rel="noopener" style="margin-top: 12px">
              直接打开链接
            </el-button>
          </template>
        </el-result>
      </div>
    </template>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ stage === 'input' ? '取消' : '关闭' }}</el-button>
      <el-button v-if="stage === 'input'" type="primary" :loading="loading" @click="onUnlock">确认解锁</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  resource: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const stage = ref('input')
const password = ref('')
const panUrl = ref('')
const loading = ref(false)

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    reset()
    // 曾经成功解锁过：无需再输密码，直接拉取网盘链接
    if (props.resource?.unlocked) {
      revealAgain()
    }
  },
)

function reset() {
  stage.value = 'input'
  password.value = ''
  panUrl.value = ''
}

async function revealAgain() {
  loading.value = true
  try {
    const data = await http.post(`/resources/${props.resource.id}/unlock`, {
      block_password: '',
    })
    panUrl.value = data.pan_url
    stage.value = 'revealed'
  } catch {
    // 拉取失败则回退到密码输入阶段，由用户手动解锁
    stage.value = 'input'
  } finally {
    loading.value = false
  }
}

async function onUnlock() {
  if (!password.value) {
    ElMessage.warning('请输入资源块密码')
    return
  }
  loading.value = true
  try {
    const data = await http.post(`/resources/${props.resource.id}/unlock`, {
      block_password: password.value,
    })
    panUrl.value = data.pan_url
    stage.value = 'revealed'
    // 标记为已解锁，下次打开直接展示
    if (props.resource) props.resource.unlocked = true
  } catch {
    // 错误提示已由 axios 拦截器统一弹出，保持输入状态
  } finally {
    loading.value = false
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(panUrl.value)
    ElMessage.success('链接已复制到剪贴板')
  } catch {
    // 非安全上下文（如 http 站点）降级方案
    const input = document.createElement('textarea')
    input.value = panUrl.value
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success('链接已复制到剪贴板')
  }
}
</script>
