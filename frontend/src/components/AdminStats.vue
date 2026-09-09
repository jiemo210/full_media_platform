<template>
  <div class="admin-stats">
    <h2 class="page-title">数据统计</h2>
    <div class="stat-grid" v-if="stats">
      <div class="stat-card card"><span class="stat-num">{{ stats.total_news }}</span><span class="stat-label">热点新闻</span></div>
      <div class="stat-card card"><span class="stat-num">{{ stats.total_articles }}</span><span class="stat-label">AI 文章</span></div>
      <div class="stat-card card"><span class="stat-num">{{ stats.total_publish_tasks }}</span><span class="stat-label">发布任务</span></div>
      <div class="stat-card card"><span class="stat-num">{{ sourceCount }}</span><span class="stat-label">新闻源</span></div>
    </div>
    <div class="card sources-card">
      <h3>新闻源状态</h3>
      <table class="tbl">
        <thead><tr><th>来源</th><th>名称</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="(cfg, key) in (stats?.sources || {})" :key="key">
            <td class="mono">{{ key }}</td>
            <td>{{ cfg.name }}</td>
            <td><span class="badge" :class="cfg.enabled ? 'badge-green' : ''">{{ cfg.enabled ? '启用' : '停用' }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="stats?.last_crawl_time" class="msg">最近抓取：{{ formatTime(stats.last_crawl_time) }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getStats } from '../api'

const stats = ref(null)
const sourceCount = computed(() => Object.keys(stats.value?.sources || {}).length)
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN') : ''

onMounted(async () => {
  try { stats.value = await getStats() } catch (e) {}
})
</script>

<style scoped>
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 1.2rem; }
.stat-card { padding: 1.2rem; display: flex; flex-direction: column; gap: 4px; }
.stat-num { font-size: 2rem; font-weight: 700; font-family: var(--font-mono); }
.stat-label { font-size: 0.78rem; color: var(--text-muted); }
.sources-card { padding: 1.2rem; }
.sources-card h3 { margin-bottom: 0.8rem; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th, .tbl td { padding: 9px 12px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.mono { font-family: var(--font-mono); }
</style>
