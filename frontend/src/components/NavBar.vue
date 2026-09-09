<template>
  <nav class="navbar">
    <div class="container navbar-inner">
      <router-link to="/" class="brand">
        <span class="brand-icon">◈</span>
        <span class="brand-text">全媒体聚合平台</span>
      </router-link>
      <div class="nav-links">
        <router-link to="/" class="nav-link" active-class="active">📰 热点新闻</router-link>
        <router-link to="/create" class="nav-link" active-class="active">✍️ AI创作</router-link>
        <router-link to="/search" class="nav-link" active-class="active">🔎 资料搜索</router-link>
        <router-link to="/pipeline" class="nav-link" active-class="active">⚡ 成稿任务</router-link>
        <router-link to="/articles" class="nav-link" active-class="active">📚 文章库</router-link>
        <router-link to="/novels" class="nav-link" active-class="active">📖 小说</router-link>
        <router-link to="/publish" class="nav-link" active-class="active">🚀 发布</router-link>
        <router-link v-if="isAdmin" to="/admin" class="nav-link" active-class="active">⚙️ 后台管理</router-link>
      </div>
      <div class="user-box">
        <div class="theme-box">
          <button class="theme-btn" @click="showTheme = !showTheme" title="界面换肤">🎨</button>
          <div v-if="showTheme" class="theme-panel card">
            <p class="theme-title">颜色模式</p>
            <div class="mode-row">
              <button class="mode-btn" :class="{ active: theme.mode === 'dark' }" @click="setMode('dark')">🌙 深色</button>
              <button class="mode-btn" :class="{ active: theme.mode === 'light' }" @click="setMode('light')">☀️ 浅色</button>
            </div>
            <p class="theme-title">背景方案</p>
            <div class="bg-row">
              <button v-for="b in BACKGROUNDS" :key="b.key" class="bg-btn" :class="{ active: theme.background === b.key }" @click="setBackground(b.key)">
                {{ b.emoji }} {{ b.label }}
              </button>
            </div>
          </div>
        </div>
        <span class="user-name">{{ user?.nickname || user?.username }}</span>
        <button class="logout" @click="logout">退出</button>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { state, clearAuth } from '../store'
import { state as theme, setMode, setBackground, BACKGROUNDS } from '../theme'
import { ref } from 'vue'
import { onMounted, onUnmounted } from 'vue'

const router = useRouter()
const user = computed(() => state.user)
const isAdmin = computed(() => state.user?.role === 'admin')
const showTheme = ref(false)

function onDocClick(e) {
  if (showTheme.value && !e.target.closest('.theme-box')) {
    showTheme.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

function logout() {
  clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.navbar { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; background: rgba(13, 20, 40, 0.8); -webkit-backdrop-filter: blur(22px) saturate(180%); backdrop-filter: blur(22px) saturate(180%); border-bottom: 1px solid var(--glass-border); }
.navbar-inner { display: flex; align-items: center; height: 60px; gap: 18px; }
.brand { display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--text-primary); }
.brand-icon { font-size: 1.4rem; color: var(--accent-red); }
.brand-text { font-family: var(--font-serif); font-weight: 700; font-size: 1.05rem; }
.nav-links { display: flex; gap: 6px; flex: 1; }
.nav-link { padding: 7px 13px; border-radius: 999px; font-size: 0.82rem; color: var(--text-secondary); text-decoration: none; }
.nav-link:hover { background: var(--glass-bg); color: var(--text-primary); }
.nav-link.active { background: rgba(100, 210, 255, 0.16); color: var(--accent-blue); }
.user-box { display: flex; align-items: center; gap: 10px; }
.theme-box { position: relative; }
.theme-btn { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--glass-border); background: var(--glass-bg); cursor: pointer; font-size: 0.9rem; }
.theme-panel { position: absolute; right: 0; top: 42px; width: 240px; padding: 12px; z-index: 3000; background: rgba(13, 20, 40, 0.97); -webkit-backdrop-filter: blur(24px); backdrop-filter: blur(24px); }
[data-theme="light"] .theme-panel { background: rgba(245, 247, 252, 0.98); }
.theme-title { font-size: 0.7rem; color: var(--text-muted); margin: 8px 0 6px; }
.theme-title:first-child { margin-top: 0; }
.mode-row { display: flex; gap: 8px; }
.mode-btn { flex: 1; padding: 7px; border: 1px solid var(--glass-border); border-radius: 999px; background: var(--glass-bg); color: var(--text-secondary); cursor: pointer; font-size: 0.78rem; }
.mode-btn.active { border-color: var(--accent-blue); color: var(--accent-blue); background: rgba(100, 210, 255, 0.14); }
.bg-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.bg-btn { padding: 6px 8px; border: 1px solid var(--glass-border); border-radius: 8px; background: var(--glass-bg-soft); color: var(--text-secondary); cursor: pointer; font-size: 0.72rem; }
.bg-btn.active { border-color: var(--accent-blue); color: var(--accent-blue); }
.user-name { font-size: 0.82rem; color: var(--text-secondary); }
.logout { background: none; border: 1px solid var(--glass-border); color: var(--text-muted); padding: 5px 12px; border-radius: 999px; cursor: pointer; font-size: 0.76rem; }
@media (max-width: 768px) {
  .nav-link { font-size: 0.74rem; padding: 6px 9px; }
  .brand-text { display: none; }
}
</style>
