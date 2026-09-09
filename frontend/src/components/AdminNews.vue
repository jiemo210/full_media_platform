<template>
  <div class="admin-news">
    <div class="head">
      <h2 class="page-title">新闻管理</h2>
      <div class="actions">
        <input v-model="keyword" placeholder="搜索标题..." @keyup.enter="load(1)" />
        <button class="btn accent" @click="doCrawl" :disabled="crawling">{{ crawling ? '抓取中...' : '🕷 一键抓取' }}</button>
      </div>
    </div>
    <table class="tbl card">
      <thead><tr><th>ID</th><th>标题</th><th>来源</th><th>分类</th><th>热度</th><th>时间</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="n in news" :key="n.id">
          <td>{{ n.id }}</td>
          <td class="title-cell">{{ n.title }}</td>
          <td>{{ n.source_name }}</td>
          <td>{{ n.category }}</td>
          <td class="heat">{{ n.heat_score }}</td>
          <td class="muted">{{ formatTime(n.created_at) }}</td>
          <td><button class="btn del" @click="remove(n)">删除</button></td>
        </tr>
        <tr v-if="!news.length"><td colspan="7" class="empty-cell">暂无数据</td></tr>
      </tbody>
    </table>
    <div class="pager" v-if="total > pageSize">
      <button class="btn" :disabled="page <= 1" @click="load(page - 1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button class="btn" :disabled="page >= totalPages" @click="load(page + 1)">下一页</button>
    </div>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminDeleteNews, adminGetNews, crawlNews, getCrawlStatus } from '../api'

const news = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const crawling = ref(false)
const msg = ref('')
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

async function load(p = 1) {
  page.value = p
  try {
    const res = await adminGetNews({ page: page.value, page_size: pageSize, keyword: keyword.value || undefined })
    news.value = res.items
    total.value = res.total
  } catch (e) { msg.value = `❌ ${e.message}` }
}
async function remove(n) {
  if (!confirm(`确认删除「${n.title.slice(0, 30)}」？`)) return
  try { await adminDeleteNews(n.id); msg.value = '✅ 已删除'; load(page.value) } catch (e) { msg.value = `❌ ${e.message}` }
}
async function doCrawl() {
  crawling.value = true
  msg.value = ''
  try {
    await crawlNews()
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const st = await getCrawlStatus()
      if (st.running) {
        const done = Object.values(st.progress || {}).reduce((a, b) => a + b, 0)
        msg.value = `🕷 抓取中... 已处理 ${done} 条`
        continue
      }
      msg.value = st.error ? `❌ 抓取失败：${st.error}` : `✅ 抓取完成：${st.total} 条，新增 ${st.new_count} 条`
      break
    }
    load(1)
  } catch (e) { msg.value = `❌ ${e.message}` } finally { crawling.value = false }
}
onMounted(() => load(1))
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 10px; }
.actions { display: flex; gap: 10px; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.title-cell { max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.heat { color: var(--accent-red); font-family: var(--font-mono); }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 1rem; }
</style>
