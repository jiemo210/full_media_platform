import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn, isAdmin } from '../store'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../components/Login.vue'), meta: { guest: true } },
  { path: '/', name: 'Home', component: () => import('../components/Home.vue'), meta: { auth: true } },
  { path: '/create', name: 'Create', component: () => import('../components/Create.vue'), meta: { auth: true } },
  { path: '/search', name: 'MaterialSearch', component: () => import('../components/MaterialSearch.vue'), meta: { auth: true } },
  { path: '/articles', name: 'Articles', component: () => import('../components/Articles.vue'), meta: { auth: true } },
  { path: '/publish', name: 'Publish', component: () => import('../components/Publish.vue'), meta: { auth: true } },
  { path: '/novels', name: 'NovelLibrary', component: () => import('../components/NovelLibrary.vue'), meta: { auth: true } },
  { path: '/novels/create', name: 'NovelCreate', component: () => import('../components/NovelCreate.vue'), meta: { auth: true } },
  { path: '/novels/:id', name: 'NovelEditor', component: () => import('../components/NovelEditor.vue'), meta: { auth: true } },
  {
    path: '/admin', name: 'Admin', component: () => import('../components/AdminLayout.vue'), meta: { auth: true, admin: true },
    children: [
      { path: '', redirect: '/admin/stats' },
      { path: 'stats', name: 'AdminStats', component: () => import('../components/AdminStats.vue') },
      { path: 'users', name: 'AdminUsers', component: () => import('../components/AdminUsers.vue') },
      { path: 'news', name: 'AdminNews', component: () => import('../components/AdminNews.vue') },
      { path: 'articles', name: 'AdminArticles', component: () => import('../components/AdminArticles.vue') },
      { path: 'novels', name: 'AdminNovels', component: () => import('../components/AdminNovels.vue') },
      { path: 'media', name: 'AdminMedia', component: () => import('../components/AdminMedia.vue') },
      { path: 'sources', name: 'AdminSources', component: () => import('../components/AdminSources.vue') },
      { path: 'models', name: 'AdminModels', component: () => import('../components/AdminModels.vue') },
      { path: 'styles', name: 'AdminStyles', component: () => import('../components/AdminStyles.vue') },
      { path: 'platforms', name: 'AdminPlatforms', component: () => import('../components/AdminPlatforms.vue') },
      { path: 'config', name: 'AdminConfig', component: () => import('../components/AdminConfig.vue') },
      { path: 'logs', name: 'AdminLogs', component: () => import('../components/AdminLogs.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() { return { top: 0 } },
})

router.beforeEach((to) => {
  if (to.meta.auth && !isLoggedIn()) return '/login'
  if (to.meta.admin && !isAdmin()) return '/'
  if (to.meta.guest && isLoggedIn()) return '/'
})

export default router
