<template>
  <div class="admin-novels">
    <div class="head">
      <h2 class="page-title">小说管理</h2>
      <input v-model="keyword" placeholder="搜索标题..." @keyup.enter="load(1)" />
    </div>
    <table class="tbl card">
      <thead><tr><th>ID</th><th>标题</th><th>题材</th><th>字数</th><th>状态</th><th>总结</th><th>时间</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="n in novels" :key="n.id">
          <td>{{ n.id }}</td>
          <td class="title-cell">{{ n.title }}</td>
          <td>{{ n.genre }}</td>
          <td class="mono">{{ n.word_count }}</td>
          <td>{{ statusLabel(n.status) }}</td>
          <td><span class="badge" :class="n.summary?.genre ? 'badge-green' : ''">{{ n.summary?.genre ? '已总结' : '未总结' }}</span></td>
          <td class="muted">{{ formatTime(n.updated_at) }}</td>
          <td class="actions">
            <button class="btn" @click="genSummary(n)" :disabled="summarizingId === n.id">{{ summarizingId === n.id ? '总结中...' : '✨ 大纲总结' }}</button>
            <button class="btn del" @click="remove(n)">删除</button>
          </td>
        </tr>
        <tr v-if="!novels.length"><td colspan="8" class="empty-cell">暂无小说</td></tr>
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
import { novelAPI } from '../api'

const novels = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const msg = ref('')
const summarizingId = ref(null)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
const statusLabel = (s) => ({ draft: '草稿', setting: '设定中', outline: '大纲', writing: '写作中', completed: '已完成', imported: '已导入' }[s] || s)

async function load(p = 1) {
  page.value = p
  try {
    const res = await novelAPI.getNovels({ page: page.value, page_size: pageSize, keyword: keyword.value || undefined })
    novels.value = res.items
    total.value = res.total
  } catch (e) { msg.value = `❌ ${e.message}` }
}

async function genSummary(n) {
  summarizingId.value = n.id
  msg.value = ''
  try {
    const res = await novelAPI.generateSummary(n.id)
    n.summary = res.summary
    msg.value = `✅ 已生成总结（题材：${res.summary.genre}）`
  } catch (e) { msg.value = `❌ ${e.message}` } finally { summarizingId.value = null }
}

async function remove(n) {
  if (!confirm(`确认删除《${n.title}》？`)) return
  try { await novelAPI.deleteNovel(n.id); msg.value = '✅ 已删除'; load(page.value) } catch (e) { msg.value = `❌ ${e.message}` }
}

onMounted(() => load(1))
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.title-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mono { font-family: var(--font-mono); }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 1rem; }
</style>
