<template>
  <div class="admin-layout">
    <aside class="admin-sidebar">
      <div class="sidebar-head">
        <span class="sidebar-icon">◈</span>
        <span class="sidebar-title">全媒体聚合平台</span>
        <span class="sidebar-ver">管理</span>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/admin/stats" class="nav-item" active-class="active">📊 数据统计</router-link>
        <router-link to="/admin/users" class="nav-item" active-class="active">👥 用户管理</router-link>
        <router-link to="/admin/news" class="nav-item" active-class="active">📰 新闻管理</router-link>
        <router-link to="/admin/articles" class="nav-item" active-class="active">📝 文章管理</router-link>
        <router-link to="/admin/novels" class="nav-item" active-class="active">📖 小说管理</router-link>
        <router-link to="/admin/media" class="nav-item" active-class="active">🖼️ 素材库</router-link>
        <router-link to="/admin/sources" class="nav-item" active-class="active">🔗 新闻源管理</router-link>
        <router-link to="/admin/models" class="nav-item" active-class="active">🤖 AI 模型</router-link>
        <router-link to="/admin/styles" class="nav-item" active-class="active">🎨 写作风格</router-link>
        <router-link to="/admin/platforms" class="nav-item" active-class="active">📤 发布平台</router-link>
        <router-link to="/admin/config" class="nav-item" active-class="active">⚙️ 页面配置</router-link>
        <router-link to="/admin/logs" class="nav-item" active-class="active">📋 日志查看</router-link>
        <hr class="divider" />
        <router-link to="/" class="nav-item">🏠 返回前台</router-link>
      </nav>
    </aside>
    <main class="admin-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.admin-layout { display: flex; min-height: 100vh; }
.admin-sidebar { width: 210px; position: fixed; top: 0; bottom: 0; left: 0; z-index: 900; background: var(--glass-deep); -webkit-backdrop-filter: blur(24px); backdrop-filter: blur(24px); border-right: 1px solid var(--glass-border); display: flex; flex-direction: column; }
.sidebar-head { padding: 1.1rem 1rem; border-bottom: 1px solid var(--glass-bg); display: flex; align-items: center; gap: 8px; }
.sidebar-icon { color: var(--accent-red); font-size: 1.3rem; }
.sidebar-title { font-family: var(--font-serif); font-size: 0.98rem; font-weight: 700; }
.sidebar-ver { margin-left: auto; font-size: 0.6rem; color: var(--text-muted); font-family: var(--font-mono); }
.sidebar-nav { flex: 1; padding: 0.5rem 0; overflow-y: auto; display: flex; flex-direction: column; }
.nav-item { padding: 10px 1.2rem; font-size: 0.84rem; color: var(--text-muted); text-decoration: none; border-left: 3px solid transparent; }
.nav-item:hover { background: var(--glass-bg-soft); color: var(--text-primary); }
.nav-item.active { background: rgba(100, 210, 255, 0.14); color: var(--text-primary); border-left-color: var(--accent-blue); }
.divider { border: none; border-top: 1px solid var(--glass-bg); margin: 0.4rem 0; }
.admin-main { margin-left: 210px; flex: 1; padding: 1.5rem; min-height: 100vh; }
@media (max-width: 768px) {
  .admin-sidebar { display: none; }
  .admin-main { margin-left: 0; }
}
</style>
