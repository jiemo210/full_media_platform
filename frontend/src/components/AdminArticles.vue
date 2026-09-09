<template>
  <div class="admin-articles">
    <h2 class="page-title">文章管理</h2>
    <table class="tbl card">
      <thead><tr><th>ID</th><th>标题</th><th>类型</th><th>风格</th><th>平台</th><th>时间</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="a in articles" :key="a.id">
          <td>{{ a.id }}</td>
          <td class="title-cell">{{ a.title }}</td>
          <td><span class="badge" :class="a.source_type === 'rewrite' ? 'badge-blue' : 'badge-purple'">{{ a.source_type === 'rewrite' ? '改写' : '创作' }}</span></td>
          <td>{{ a.style }}</td>
          <td>{{ a.platform || '-' }}</td>
          <td class="muted">{{ formatTime(a.created_at) }}</td>
          <td><button class="btn del" @click="remove(a)">删除</button></td>
        </tr>
        <tr v-if="!articles.length"><td colspan="7" class="empty-cell">暂无文章</td></tr>
      </tbody>
    </table>
    <Pager :page="page" :total="total" :page-size="pageSize" @change="load" />
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { deleteArticle, getArticles } from '../api'
import Pager from './Pager.vue'

const articles = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const msg = ref('')
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

async function load(p = 1) {
  page.value = p
  try {
    const res = await getArticles({ page: page.value, page_size: pageSize })
    articles.value = res.items
    total.value = res.total
  } catch (e) { msg.value = `❌ ${e.message}` }
}
async function remove(a) {
  if (!confirm(`确认删除「${a.title.slice(0, 30)}」？`)) return
  try { await deleteArticle(a.id); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}
onMounted(load)
</script>

<style scoped>
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.title-cell { max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
</style>
