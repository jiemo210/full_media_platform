<template>
  <div class="search-page">
    <div class="container">
      <span class="section-label">MATERIAL SEARCH</span>
      <h1 class="page-title">资料搜索</h1>
      <p class="page-desc">输入主题，AI 检索相关新闻与热点资料并精选，辅助创作选题与素材收集</p>

      <div class="search-bar card">
        <input
          v-model="query"
          class="search-input"
          placeholder="如：新能源汽车出口最新动态 / 郑州暴雨灾后恢复"
          @keyup.enter="search"
        />
        <select v-model="days" class="days-select" title="时间范围">
          <option :value="0">不限时间</option>
          <option :value="1">近 24 小时</option>
          <option :value="3">近 3 天</option>
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
        </select>
        <button class="btn primary" @click="search" :disabled="searching || !query.trim()">
          {{ searching ? 'AI 搜索中...' : '🔎 AI 搜索资料' }}
        </button>
      </div>
      <p v-if="error" class="msg err">{{ error }}</p>

      <div v-if="result" class="result-wrap">
        <div class="summary card">
          <h3 class="summary-title">📋 AI 综合摘要</h3>
          <p class="summary-text">{{ result.summary }}</p>
          <p class="meta">
            检索词：{{ (result.queries || []).join(' / ') || result.query }}
            · 网页资料 {{ result.web_count || 0 }} 条 / 本地热点 {{ result.local_count || 0 }} 条
            · 时间范围：{{ result.days ? '近 ' + result.days + ' 天' : '不限' }}
          </p>
          <div v-if="result.related_queries && result.related_queries.length" class="chips">
            <span class="chips-label">延伸搜索：</span>
            <button v-for="q in result.related_queries" :key="q" class="chip" @click="useQuery(q)">{{ q }}</button>
          </div>
        </div>

        <div class="item-list">
          <div v-for="(it, idx) in result.items" :key="idx" class="item card" :class="{ matched: it.matched, hot: it.is_hot }">
            <div class="item-head">
              <a :href="it.url" target="_blank" rel="noopener" class="item-title">{{ it.title }}</a>
              <span class="badge" :class="it.kind === 'local' ? 'badge-blue' : 'badge-purple'">
                {{ it.kind === 'local' ? '本地热点' : '网页资料' }}
              </span>
              <span v-if="it.is_hot" class="hot-tag">🔥 热点</span>
            </div>
            <p class="item-snippet">{{ it.snippet || it.reason || '（无摘要）' }}</p>
            <div class="item-foot">
              <span class="src">来源：{{ it.source }}</span>
              <span v-if="it.reason" class="reason">💡 {{ it.reason }}</span>
              <button class="btn small create-btn" @click="createFrom(it)">✍️ 以此主题创作</button>
            </div>
          </div>
          <p v-if="!result.items.length" class="empty-tip">未检索到资料，试试更换关键词</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { searchMaterials } from '../api'
import { toast } from '../toast'

const router = useRouter()
const query = ref('')
const days = ref(0)
const searching = ref(false)
const error = ref('')
const result = ref(null)

async function search() {
  const q = query.value.trim()
  if (!q) return
  searching.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await searchMaterials(q, days.value)
    toast(`🔎 检索完成：${result.value.items.length} 条`, 'success')
  } catch (e) {
    error.value = e.message || '搜索失败'
    toast(`❌ ${error.value}`, 'error')
  } finally {
    searching.value = false
  }
}

function useQuery(q) {
  query.value = q
  search()
}

function createFrom(it) {
  router.push({ path: '/create', query: { topic: it.title } })
}
</script>

<style scoped>
.search-page { padding-bottom: 2rem; }
.search-bar { display: flex; gap: 10px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.search-input { flex: 1; font-size: 0.95rem; }
.days-select { padding: 8px 10px; border-radius: 10px; border: 1px solid var(--glass-border); background: var(--glass-bg); color: var(--text-primary); font-size: 0.82rem; }
.summary { padding: 1.1rem 1.2rem; margin-bottom: 1rem; }
.summary-title { font-family: var(--font-serif); margin-bottom: 8px; }
.summary-text { color: var(--text-primary); font-size: 0.9rem; line-height: 1.7; }
.meta { margin-top: 8px; font-size: 0.76rem; color: var(--text-muted); }
.chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.chips-label { font-size: 0.76rem; color: var(--text-muted); }
.chip { padding: 4px 12px; border: 1px solid var(--glass-border); border-radius: 999px; background: var(--glass-bg-soft); color: var(--text-secondary); cursor: pointer; font-size: 0.76rem; }
.chip:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.item-list { display: flex; flex-direction: column; gap: 12px; }
.item { padding: 1rem 1.2rem; }
.item.matched { border-color: rgba(100, 210, 255, 0.35); }
.item.hot { border-color: rgba(255, 69, 58, 0.35); }
.item-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.item-title { font-size: 0.95rem; font-weight: 600; color: var(--text-primary); text-decoration: none; }
.item-title:hover { color: var(--accent-blue); }
.hot-tag { color: #FF9B94; font-size: 0.76rem; }
.item-snippet { margin-top: 6px; font-size: 0.82rem; color: var(--text-secondary); line-height: 1.6; }
.item-foot { display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.src { font-size: 0.74rem; color: var(--text-muted); }
.reason { font-size: 0.76rem; color: var(--accent-green); flex: 1; }
.btn.small { padding: 4px 10px; font-size: 0.76rem; }
.create-btn { border-color: rgba(100, 210, 255, 0.35); color: var(--accent-blue); }
.empty-tip { text-align: center; color: var(--text-muted); padding: 2rem; }
</style>
