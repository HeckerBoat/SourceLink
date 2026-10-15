<template>
  <div>
    <header class="sl-header">
      <div class="brand" @click="$router.push('/')">
        <span class="logo"><el-icon><Link /></el-icon></span>
        <span>{{ site.siteName }}</span>
      </div>
      <div class="actions">
        <el-button v-if="auth.isAdmin" text class="desktop-only" @click="$router.push('/admin/resources')">
          <el-icon style="margin-right: 4px"><Setting /></el-icon>管理后台
        </el-button>
        <el-dropdown @command="onCommand">
          <span style="display: flex; align-items: center; gap: 6px; cursor: pointer; outline: none">
            <el-avatar :size="30" style="background: var(--sl-primary)">
              {{ auth.displayName.charAt(0).toUpperCase() }}
            </el-avatar>
            <span class="username">{{ auth.displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="home"><el-icon><Goods /></el-icon>资源市场</el-dropdown-item>
              <el-dropdown-item command="profile"><el-icon><User /></el-icon>我的</el-dropdown-item>
              <el-dropdown-item command="feedback"><el-icon><ChatDotRound /></el-icon>意见反馈</el-dropdown-item>
              <el-dropdown-item v-if="auth.isAdmin" command="admin">
                <el-icon><Setting /></el-icon>管理后台
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <router-view />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import { useSiteStore } from '@/stores/site'

const router = useRouter()
const auth = useAuthStore()
const site = useSiteStore()

site.loadPublicConfig()

function onCommand(command) {
  if (command === 'home') router.push('/')
  else if (command === 'profile') router.push('/profile')
  else if (command === 'feedback') router.push('/feedback')
  else if (command === 'admin') router.push('/admin/resources')
  else if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning', confirmButtonText: '退出', cancelButtonText: '取消' })
      .then(() => {
        auth.logout()
        router.push('/login')
      })
      .catch(() => {})
  }
}
</script>
