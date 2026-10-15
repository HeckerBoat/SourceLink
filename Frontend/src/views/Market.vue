<template>
  <div class="page-container">
    <section class="hero">
      <h1>{{ site.siteName }}</h1>
      <p>精选优质虚拟资源，购买后输入资源块密码即可获取网盘链接。</p>
    </section>

    <div v-loading="loading">
      <div v-if="resources.length" class="resource-grid">
        <ResourceCard v-for="item in resources" :key="item.id" :resource="item" @unlock="openUnlock" />
      </div>
      <el-empty v-else-if="!loading" class="empty-wrap" description="暂无可浏览的资源，敬请期待" />
    </div>

    <UnlockDialog v-model="dialogVisible" :resource="current" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

import http from '@/api/http'
import { useSiteStore } from '@/stores/site'
import ResourceCard from '@/components/ResourceCard.vue'
import UnlockDialog from '@/components/UnlockDialog.vue'

const site = useSiteStore()

const loading = ref(false)
const resources = ref([])
const dialogVisible = ref(false)
const current = ref(null)

async function loadResources() {
  loading.value = true
  try {
    resources.value = await http.get('/resources')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    loading.value = false
  }
}

function openUnlock(resource) {
  current.value = resource
  dialogVisible.value = true
}

onMounted(loadResources)
</script>
