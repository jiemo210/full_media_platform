<template>
  <div class="home-page">
    <div class="container">
      <div class="page-header">
        <div>
          <span class="section-label">HOT NEWS MINING</span>
          <h1 class="page-title">热点新闻</h1>
          <p class="page-desc">8 大来源实时聚合，AI 一键改写发布到全媒体平台</p>
        </div>
        <div class="header-actions">
          <span v-if="crawlMsg" class="crawl-msg" :class="{ err: crawlErr }">{{ crawlMsg }}</span>
          <button class="btn accent" @click="doCrawl" :disabled="crawling">{{ crawling ? '抓取中...' : '🕷 一键抓取' }}</button>
        </div>
      </div>

      <div class="filters">
        <div class="search-box">
          <input v-model="keyword" placeholder="搜索新闻标题/摘要..." @keyup.enter="load(1)" />
          <button class="btn" @click="load(1)">🔍 搜索</button>
        </div>
        <select v-model="sourceFilter" @change="load(1)">
          <option value="">全部来源</option>
          <option v-for="(cfg, key) in sources" :key="key" :value="key">{{ cfg.name }}</option>
        </select>
        <select v-model="categoryFilter" @change="load(1)">
          <option value="">全部分类</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="sortBy" @change="load(1)">
          <option value="heat">按热度</option>
          <option value="time">按时间</option>
        </select>
      </div>

      <div class="home-layout">
        <div class="news-list">
          <div v-for="n in newsList" :key="n.id" class="news-card card" @click="selectedNews = n">
            <div class="news-main">
              <div class="news-top">
                <span class="badge badge-blue">{{ n.source_name }}</span>
                <span class="badge badge-purple">{{ n.category }}</span>
                <span class="news-heat">🔥 {{ n.heat_score }}</span>
              </div>
              <h3 class="news-title">{{ n.title }}</h3>
              <p class="news-summary">{{ n.summary }}</p>
              <div class="news-footer">
                <span class="news-time">🕐 首次抓取 {{ formatTime(n.created_at) }}</span>
                <div class="news-actions">
                  <button class="mini-btn" @click.stop="openRewrite(n)">✍️ AI 改写</button>
                  <button class="mini-btn mini-primary" @click.stop="openPipelineModal(n)">⚡ 一键成稿</button>
                </div>
              </div>
            </div>
          </div>
          <p v-if="!newsList.length && loaded" class="empty-tip">暂无新闻，点击右上角「一键抓取」</p>
        </div>

        <aside class="top-panel card">
          <h3 class="top-title">热门排行 TOP10</h3>
          <div v-for="(n, i) in topNews" :key="n.id" class="top-item" @click="selectedNews = n">
            <span class="top-rank" :class="{ top3: i < 3 }">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="top-text">{{ n.title }}</span>
          </div>
        </aside>
      </div>

      <div class="pager" v-if="total > pageSize">
        <button class="btn" :disabled="page <= 1" @click="load(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button class="btn" :disabled="page >= totalPages" @click="load(page + 1)">下一页</button>
      </div>
    </div>

    <Teleport to="body">
      <NewsPreview v-if="selectedNews" :news="selectedNews" :action="selectedAction" @close="selectedNews = null" />
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { crawlNews, getCrawlStatus, getNews, getPublicConfig, getSources, getTopNews } from '../api'
import NewsPreview from './NewsPreview.vue'


const newsList = ref([])
const topNews = ref([])
const sources = ref({})
const categories = ['综合', '时政', '财经', '科技', '社会', '国际', '文体']
const sourceFilter = ref('')
const categoryFilter = ref('')
const sortBy = ref('time')
const keyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const loaded = ref(false)
const crawling = ref(false)
const crawlMsg = ref('')
const crawlErr = ref(false)
const selectedNews = ref(null)
const selectedAction = ref('rewrite')

function openRewrite(n) {
  selectedAction.value = 'rewrite'
  selectedNews.value = n
}

function openPipelineModal(n) {
  selectedAction.value = 'pipeline'
  selectedNews.value = n
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''

async function load(p = 1) {
  page.value = p
  try {
    const res = await getNews({
      page: page.value, page_size: pageSize.value,
      source: sourceFilter.value || undefined,
      category: categoryFilter.value || undefined,
      sort: sortBy.value,
      keyword: keyword.value || undefined,
    })
    newsList.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) { crawlMsg.value = e.message; crawlErr.value = true }
}

async function loadTop() {
  try { topNews.value = await getTopNews(10) } catch (e) {}
}

async function doCrawl() {
  crawling.value = true
  crawlMsg.value = ''
  try {
    await crawlNews()
    // 轮询后台抓取状态
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const st = await getCrawlStatus()
      if (st.running) {
        const done = Object.values(st.progress || {}).reduce((a, b) => a + b, 0)
        crawlMsg.value = `抓取中... 已处理 ${done} 条`
        continue
      }
      crawlMsg.value = st.error ? `抓取失败：${st.error}` : `抓取完成：共 ${st.total} 条，新增 ${st.new_count} 条`
      crawlErr.value = !!st.error
      break
    }
    crawlErr.value = false
    load(1)
    loadTop()
  } catch (e) {
    crawlMsg.value = e.message || '抓取失败'
    crawlErr.value = true
  } finally {
    crawling.value = false
  }
}

onMounted(async () => {
  load(1)
  loadTop()
  try {
    const cfg = await getPublicConfig()
    if (cfg?.news_page_size) pageSize.value = cfg.news_page_size
    sources.value = (await getSources().catch(() => ({ sources: {} }))).sources
  } catch (e) {}
})
</script>

<style scoped>
.home-page { padding-bottom: 2rem; }
.page-header { display: flex; justify-content: space-between; align-items: flex-end; margin: 1.5rem 0 1rem; flex-wrap: wrap; gap: 12px; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.crawl-msg { font-size: 0.8rem; color: var(--accent-green); }
.crawl-msg.err { color: #FF9B94; }
.filters { display: flex; gap: 10px; margin-bottom: 1.2rem; }
.search-box { display: flex; gap: 6px; }
.search-box input { width: 220px; }
.home-layout { display: grid; grid-template-columns: 1fr 320px; gap: 20px; }
.news-list { display: flex; flex-direction: column; gap: 12px; }
.news-card { padding: 16px 18px; cursor: pointer; transition: var(--transition); }
.news-card:hover { background: var(--glass-bg-strong); transform: translateY(-2px); }
.news-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.news-heat { margin-left: auto; font-size: 0.78rem; color: var(--accent-red); font-family: var(--font-mono); }
.news-title { font-size: 1.05rem; line-height: 1.5; margin-bottom: 6px; }
.news-summary { font-size: 0.82rem; color: var(--text-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.news-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.news-time { font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono); }
.news-actions { display: flex; gap: 8px; }
.mini-btn { padding: 4px 12px; border: 1px solid var(--glass-border); border-radius: 999px; background: var(--glass-bg); color: var(--text-secondary); font-size: 0.74rem; cursor: pointer; white-space: nowrap; }
.mini-btn:hover { color: var(--text-primary); border-color: var(--text-muted); }
.mini-btn.mini-primary { border-color: rgba(100, 210, 255, 0.45); color: var(--accent-blue); background: rgba(100, 210, 255, 0.1); }
.mini-btn.mini-primary:hover { background: rgba(100, 210, 255, 0.2); }
.mini-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.top-panel { padding: 16px; align-self: start; position: sticky; top: 76px; }
.top-title { font-size: 1rem; margin-bottom: 10px; font-family: var(--font-serif); }
.top-item { display: flex; align-items: center; gap: 10px; padding: 8px 6px; border-radius: 8px; cursor: pointer; font-size: 0.8rem; }
.top-item:hover { background: var(--glass-bg); }
.top-rank { font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); width: 22px; }
.top-rank.top3 { color: var(--accent-red); font-weight: 700; }
.top-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 1.4rem; font-size: 0.82rem; }
.preview-overlay { position: fixed; inset: 0; z-index: 1100; background: rgba(5, 8, 18, 0.68); -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.preview-panel { width: 860px; max-width: 96vw; max-height: 92vh; overflow-y: auto; background: var(--glass-deep); border: 1px solid var(--glass-border); border-radius: 24px; box-shadow: var(--shadow-lg); padding: 1.3rem 1.5rem; }
.preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
.preview-title { font-family: var(--font-serif); font-size: 1.15rem; }
.close-btn { background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; line-height: 1; }
.rewrite-form { display: flex; flex-direction: column; gap: 10px; }
.form-row { display: flex; gap: 14px; }
.form-row label { display: flex; flex-direction: column; gap: 5px; font-size: 0.76rem; color: var(--text-muted); flex: 1; min-width: 0; }
.full-label { display: flex; flex-direction: column; gap: 5px; font-size: 0.76rem; color: var(--text-muted); }
.full-label textarea { width: 100%; resize: vertical; }
.check-row { display: flex; align-items: center; font-size: 0.82rem; }
.check-row label { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); }
.check-row input { accent-color: var(--accent-blue); }
.suggestions-box { display: flex; flex-direction: column; gap: 6px; }
.suggestions-box .btn { align-self: flex-start; }
.suggestion-item { display: flex; align-items: flex-start; gap: 8px; padding: 7px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.78rem; color: var(--text-secondary); cursor: pointer; }
.suggestion-item.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.suggestion-item input { accent-color: var(--accent-blue); margin-top: 2px; }
.preview-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }
@media (max-width: 900px) {
  .home-layout { grid-template-columns: 1fr; }
  .top-panel { position: static; }
  .form-row { flex-direction: column; }
}
</style>
