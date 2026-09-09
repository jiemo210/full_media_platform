<template>
  <div class="novel-library">
    <div class="container">
      <div class="head">
        <div>
          <span class="section-label">NOVEL LIBRARY</span>
          <h1 class="page-title">本地小说库</h1>
          <p class="page-desc">AI 大纲总结（人物介绍 / 情节大纲 / 题材分类），创作时可引入库内总结作为参考</p>
        </div>
        <div class="actions">
          <button class="btn" @click="showImport = true">📥 导入小说</button>
          <router-link to="/novels/create" class="btn primary">✍️ 新建创作</router-link>
        </div>
      </div>

      <div class="filters">
        <input v-model="keyword" placeholder="搜索标题..." @keyup.enter="load(1)" />
        <select v-model="genreFilter" @change="load(1)">
          <option value="">全部题材</option>
          <option v-for="g in genres" :key="g" :value="g">{{ g }}</option>
        </select>
        <button class="btn" @click="load(1)">🔍 搜索</button>
      </div>

      <div class="novel-grid">
        <div v-for="n in novels" :key="n.id" class="novel-card card">
          <div class="card-top">
            <span class="badge badge-blue">{{ n.genre }}</span>
            <span class="badge" :class="n.summary?.genre ? 'badge-green' : ''">{{ n.summary?.genre ? '已总结' : '未总结' }}</span>
            <span class="words">{{ formatWords(n.word_count) }}</span>
          </div>
          <h3 class="novel-title" @click="openDetail(n)">{{ n.title }}</h3>
          <p class="novel-desc">{{ n.synopsis || '暂无梗概' }}</p>
          <div class="card-actions">
            <button class="btn" @click="goEditor(n)">✏️ 编辑</button>
            <button class="btn" @click="openDetail(n)">📖 详情</button>
            <button class="btn accent" @click="referenceCreate(n)">🎯 以此为参考</button>
          </div>
        </div>
        <p v-if="!novels.length && loaded" class="empty-tip">暂无小说，可「新建创作」或「导入小说」</p>
      </div>

      <div class="pager" v-if="total > pageSize">
        <button class="btn" :disabled="page <= 1" @click="load(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button class="btn" :disabled="page >= totalPages" @click="load(page + 1)">下一页</button>
      </div>
      <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
    </div>

    <!-- 导入弹窗 -->
    <div v-if="showImport" class="overlay" @click.self="showImport = false">
      <div class="modal card">
        <h3>导入小说</h3>
        <label class="field">标题<input v-model="importForm.title" placeholder="小说标题" /></label>
        <label class="field">题材
          <select v-model="importForm.genre"><option v-for="g in genres" :key="g" :value="g">{{ g }}</option></select>
        </label>
        <label class="field">正文（按段落自动分章）
          <textarea v-model="importForm.content" rows="10" placeholder="粘贴小说全文..." />
        </label>
        <p v-if="importMsg" class="msg" :class="{ err: importMsg.startsWith('❌') }">{{ importMsg }}</p>
        <div class="modal-actions">
          <button class="btn" @click="showImport = false">取消</button>
          <button class="btn primary" @click="doImport" :disabled="importing">{{ importing ? '导入中...' : '导入' }}</button>
        </div>
      </div>
    </div>

    <!-- 详情弹窗：AI 大纲总结 -->
    <div v-if="detail" class="overlay" @click.self="detail = null">
      <div class="modal detail-modal card">
        <div class="modal-head">
          <h3>{{ detail.title }}</h3>
          <button class="close" @click="detail = null">×</button>
        </div>
        <div class="detail-tags">
          <span class="badge badge-blue">{{ detail.genre }}</span>
          <span v-for="t in (detail.summary?.tags || [])" :key="t" class="badge badge-purple">{{ t }}</span>
          <span class="words">{{ formatWords(detail.word_count) }}</span>
        </div>
        <button class="btn primary" @click="genSummary" :disabled="summarizing">
          {{ summarizing ? 'AI 总结中...' : detail.summary?.genre ? '🔄 重新生成大纲总结' : '✨ 生成 AI 大纲总结' }}
        </button>
        <p v-if="summaryMsg" class="msg">{{ summaryMsg }}</p>
        <div class="summary-sections">
          <div class="summary-section">
            <h4>人物介绍</h4>
            <div v-if="detail.summary?.characters?.length" class="char-list">
              <div v-for="c in detail.summary.characters" :key="c.name" class="char-card">
                <strong>{{ c.name }}</strong>
                <span>{{ c.identity }}</span>
                <p>{{ c.personality }} · {{ c.role }}</p>
              </div>
            </div>
            <p v-else class="muted">未生成</p>
          </div>
          <div class="summary-section">
            <h4>情节大纲</h4>
            <div v-if="detail.summary?.plot" class="plot-line">
              <div v-for="(label, key) in { start: '开端', develop: '发展', climax: '高潮', end: '结局' }" :key="key" class="plot-item">
                <span class="plot-label">{{ label }}</span>
                <span>{{ detail.summary.plot[key] || '—' }}</span>
              </div>
            </div>
            <p v-else class="muted">未生成</p>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="detail = null">关闭</button>
          <button class="btn accent" @click="referenceCreate(detail)">🎯 以此为参考创作</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { novelAPI } from '../api'
import { toast } from '../toast'

const router = useRouter()
const genres = ['玄幻', '都市', '悬疑', '言情', '科幻', '历史', '武侠', '奇幻', '现实', '其他']
const novels = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 12
const keyword = ref('')
const genreFilter = ref('')
const loaded = ref(false)
const msg = ref('')
const showImport = ref(false)
const importForm = ref({ title: '', genre: '玄幻', content: '' })
const importing = ref(false)
const importMsg = ref('')
const detail = ref(null)
const summarizing = ref(false)
const summaryMsg = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const formatWords = (w) => w ? `${Math.round(w / 100) / 10}万字` : '0字'

async function load(p = 1) {
  page.value = p
  try {
    const res = await novelAPI.getNovels({ page: page.value, page_size: pageSize, keyword: keyword.value || undefined, genre: genreFilter.value || undefined, library: true })
    novels.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) { msg.value = `❌ ${e.message}` }
}

async function doImport() {
  if (!importForm.value.title.trim() || !importForm.value.content.trim()) { importMsg.value = '标题和正文必填'; return }
  importing.value = true
  importMsg.value = ''
  try {
    await novelAPI.importNovel(importForm.value)
    importMsg.value = '✅ 导入成功'
    showImport.value = false
    toast('📥 小说已导入本地库', 'success')
    load(1)
  } catch (e) { importMsg.value = `❌ ${e.message}` } finally { importing.value = false }
}

function openDetail(n) { detail.value = { ...n } }
function goEditor(n) { router.push(`/novels/${n.id}`) }
function referenceCreate(n) { router.push(`/novels/create?refs=${n.id}`) }

async function genSummary() {
  summarizing.value = true
  summaryMsg.value = ''
  try {
    const res = await novelAPI.generateSummary(detail.value.id)
    detail.value.summary = res.summary
    summaryMsg.value = '✅ 大纲总结已生成'
    load(page.value)
  } catch (e) { summaryMsg.value = `❌ ${e.message}` } finally { summarizing.value = false }
}

onMounted(() => load(1))
</script>

<style scoped>
.novel-library { padding-bottom: 2rem; }
.head { display: flex; justify-content: space-between; align-items: flex-end; margin: 1.5rem 0 1rem; flex-wrap: wrap; gap: 12px; }
.actions { display: flex; gap: 10px; }
.filters { display: flex; gap: 10px; margin-bottom: 1.2rem; }
.novel-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.novel-card { padding: 16px; display: flex; flex-direction: column; gap: 8px; }
.card-top { display: flex; gap: 8px; align-items: center; }
.words { margin-left: auto; font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono); }
.novel-title { font-size: 1.05rem; cursor: pointer; }
.novel-title:hover { color: var(--accent-blue); }
.novel-desc { font-size: 0.8rem; color: var(--text-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em; }
.card-actions { display: flex; gap: 8px; margin-top: auto; }
.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 1.2rem; }
.overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.68); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { width: 560px; max-width: 94vw; max-height: 90vh; overflow-y: auto; padding: 1.3rem; }
.detail-modal { width: 760px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
.close { background: none; border: none; color: var(--text-muted); font-size: 1.4rem; cursor: pointer; }
.detail-tags { display: flex; gap: 8px; align-items: center; margin-bottom: 0.8rem; }
.summary-sections { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 1rem; }
.summary-section { background: var(--glass-bg-soft); border: 1px solid var(--glass-border); border-radius: 12px; padding: 12px; }
.summary-section h4 { margin-bottom: 10px; font-size: 0.9rem; }
.char-list { display: flex; flex-direction: column; gap: 8px; }
.char-card { background: var(--glass-bg); border-radius: 10px; padding: 8px 10px; }
.char-card strong { margin-right: 6px; }
.char-card span { font-size: 0.78rem; color: var(--text-muted); }
.char-card p { font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px; }
.plot-line { display: flex; flex-direction: column; gap: 8px; }
.plot-item { display: flex; gap: 10px; font-size: 0.82rem; }
.plot-label { flex-shrink: 0; color: var(--accent-blue); font-weight: 600; }
.muted { color: var(--text-muted); font-size: 0.8rem; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.field textarea { resize: vertical; font-family: var(--font-mono); font-size: 0.8rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 1rem; }
@media (max-width: 760px) { .summary-sections { grid-template-columns: 1fr; } }
</style>
