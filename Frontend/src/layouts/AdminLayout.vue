<template>
  <div class="admin-body">
    <aside class="admin-side">
      <el-menu :default-active="activePath" router class="admin-menu">
        <el-menu-item index="/admin/resources">
          <el-icon><Files /></el-icon><span>资源块管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon><span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/settings">
          <el-icon><Tools /></el-icon><span>站点配置</span>
        </el-menu-item>
        <el-menu-item index="/admin/logs">
          <el-icon><Document /></el-icon><span>访问记录</span>
        </el-menu-item>
        <el-menu-item index="/admin/feedback">
          <el-icon><ChatDotRound /></el-icon><span>用户反馈</span>
        </el-menu-item>
      </el-menu>
    </aside>
    <main class="admin-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// /feedback 与 /admin/feedback 复用同一反馈组件，菜单高亮保持一致
const activePath = computed(() => (route.path === '/feedback' ? '/admin/feedback' : route.path))
</script>

<style scoped>
.admin-menu {
  border-right: none;
}
.admin-menu :deep(.el-menu-item.is-active) {
  border-radius: 8px;
}
</style>
