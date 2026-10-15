import { createRouter, createWebHashHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('@/views/Register.vue'), meta: { public: true } },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', name: 'market', component: () => import('@/views/Market.vue') },
        { path: 'feedback', name: 'feedback', component: () => import('@/views/Feedback.vue') },
        { path: 'profile', name: 'profile', component: () => import('@/views/Profile.vue') },
        {
          path: 'admin',
          component: AdminLayout,
          meta: { admin: true },
          redirect: '/admin/resources',
          children: [
            { path: 'resources', name: 'admin-resources', component: () => import('@/views/admin/Resources.vue') },
            { path: 'users', name: 'admin-users', component: () => import('@/views/admin/Users.vue') },
            { path: 'settings', name: 'admin-settings', component: () => import('@/views/admin/Settings.vue') },
            { path: 'logs', name: 'admin-logs', component: () => import('@/views/admin/Logs.vue') },
            { path: 'feedback', name: 'admin-feedback', component: () => import('@/views/Feedback.vue') },
          ],
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.isAdmin) {
    return { name: 'market' }
  }
  if (to.meta.public && auth.isLoggedIn && (to.name === 'login' || to.name === 'register')) {
    return { name: 'market' }
  }
  return true
})

export default router
