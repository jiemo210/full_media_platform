<template>
  <div class="articles-page">
    <div class="container">
      <span class="section-label">ARTICLE LIBRARY</span>
      <h1 class="page-title">文章库</h1>
      <p class="page-desc">AI 改写 / 创作生成的文章，可编辑、导出、发布</p>
      <p v-if="listMsg" class="msg" :class="{ err: listMsg.startsWith('❌') }">{{ listMsg }}</p>

      <div class="article-list">
        <div v-for="a in articles" :key="a.id" class="article-item card">
          <div class="article-head">
            <span class="badge" :class="a.source_type === 'rewrite' ? 'badge-blue' : 'badge-purple'">
              {{ a.source_type === 'rewrite' ? 'AI 改写' : 'AI 创作' }}
            </span>
            <span class="article-time">{{ formatTime(a.created_at) }}</span>
          </div>
          <h3 class="article-title" @click="open(a)">{{ a.title }}</h3>
          <p class="article-preview">{{ plainText(a.content_md).slice(0, 120) }}...</p>
          <div class="article-actions">
            <button class="btn" @click="open(a)">📝 编辑</button>
            <button class="btn" @click="copyRich(a)">📋 复制</button>
            <button class="btn" @click="exportPdf(a.title, a.content_md)">📄 导出 PDF</button>
            <button class="btn accent" @click="openPublish(a)">🚀 发布</button>
            <button class="btn del" @click="remove(a)">删除</button>
          </div>
        </div>
        <p v-if="!articles.length && loaded" class="empty-tip">暂无文章，去「热点新闻」AI 改写或「AI 创作」生成</p>
        <Pager :page="page" :total="total" :page-size="pageSize" @change="load" />
      </div>
    </div>

    <Teleport to="body">
      <div v-if="editing" class="editor-overlay" @click.self="editing = null">
        <div class="editor-panel">
          <div class="editor-head">
            <input v-model="editTitle" class="title-input" />
            <div class="actions">
              <button class="btn" @click="editing = null">关闭</button>
              <button class="btn primary" @click="saveEdit">💾 保存</button>
            </div>
          </div>
          <RichEditor v-model="editMd" @html-change="editHtml = $event" />
          <p v-if="editMsg" class="msg">{{ editMsg }}</p>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="publishTarget" class="editor-overlay" @click.self="publishTarget = null">
        <div class="publish-modal card">
          <h3>发布：{{ publishTarget.title }}</h3>
          <div class="platform-grid">
            <label v-for="p in platforms" :key="p.key" class="platform-option" :class="{ on: pubPlatforms.includes(p.label) }">
              <input type="checkbox" :value="p.label" v-model="pubPlatforms" />
              <span>{{ p.label }}</span>
            </label>
          </div>
          <p v-if="pubError" class="msg err">{{ pubError }}</p>
          <div class="modal-actions">
            <button class="btn" @click="publishTarget = null">取消</button>
            <button class="btn primary" @click="doPublish" :disabled="!pubPlatforms.length">创建发布任务</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { createPublishTasks, deleteArticle, getArticles, getPlatforms, updateArticle } from '../api'
import RichEditor from './RichEditor.vue'
import Pager from './Pager.vue'
import { toast } from '../toast'
import { copyRichHtml, exportPdf } from '../utils'

const articles = ref([])
const page = ref(1)
const pageSize = 12
const total = ref(0)
const loaded = ref(false)
const editing = ref(null)
const editTitle = ref('')
const editMd = ref('')
const editHtml = ref('')
const editMsg = ref('')
const listMsg = ref('')
const platforms = ref([])
const publishTarget = ref(null)
const pubPlatforms = ref([])
const pubError = ref('')

const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
const plainText = (md) => (md || '').replace(/[#>*`\-\[\]()]/g, '').replace(/\n+/g, ' ')

async function load(p = 1) {
  page.value = p
  try {
    const res = await getArticles({ page: page.value, page_size: pageSize })
    articles.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) {}
}

function open(a) {
  editing.value = a
  editTitle.value = a.title
  editMd.value = a.content_md
  editHtml.value = a.content_html
  editMsg.value = ''
}

async function saveEdit() {
  try {
    await updateArticle(editing.value.id, { title: editTitle.value, content_md: editMd.value, content_html: editHtml.value })
    editMsg.value = '✅ 已保存'
    load()
  } catch (e) { editMsg.value = `❌ ${e.message}` }
}

async function copyRich(a) {
  const ok = await copyRichHtml(a.title, a.content_md)
  toast(ok ? '📋 已复制带格式正文' : '复制失败，请手动选择正文复制', ok ? 'success' : 'error')
}

function openPublish(a) {
  publishTarget.value = a
  pubPlatforms.value = []
  pubError.value = ''
}

async function doPublish() {
  try {
    await createPublishTasks({ article_id: publishTarget.value.id, title: publishTarget.value.title, content: publishTarget.value.content_md, platforms: pubPlatforms.value })
    publishTarget.value = null
    toast(`🎉 已创建 ${pubPlatforms.value.length} 个发布任务，可前往发布页一键跳转发布`, 'success', { label: '前往发布', to: '/publish' })
  } catch (e) { pubError.value = e.message; toast(`❌ ${e.message || '发布失败'}`, 'error') }
}

async function remove(a) {
  if (!confirm(`确认删除「${a.title.slice(0, 30)}」？`)) return
  listMsg.value = ''
  try {
    await deleteArticle(a.id)
    listMsg.value = '✅ 文章已删除'
    load()
  } catch (e) {
    listMsg.value = `❌ ${e.message || '删除失败'}`
  }
}

onMounted(async () => {
  load()
  try { platforms.value = await getPlatforms() } catch (e) {}
})
</script>

<style scoped>
.articles-page { padding-bottom: 2rem; }
.article-list { display: flex; flex-direction: column; gap: 12px; }
.article-item { padding: 16px 18px; }
.article-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.article-time { font-size: 0.72rem; color: var(--text-muted); font-family: var(--font-mono); }
.article-title { font-size: 1.02rem; cursor: pointer; margin-bottom: 4px; }
.article-title:hover { color: var(--accent-blue); }
.article-preview { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 10px; }
.article-actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; }
.editor-overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.7); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.editor-panel { width: 900px; max-width: 96vw; max-height: 92vh; overflow-y: auto; background: var(--glass-deep); border: 1px solid var(--glass-border); border-radius: 22px; padding: 1.3rem; }
.editor-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.title-input { flex: 1; font-size: 1rem; font-weight: 600; }
.publish-modal { width: 480px; max-width: 92vw; padding: 1.4rem; }
.publish-modal h3 { margin-bottom: 0.8rem; }
.platform-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 0.8rem; }
.platform-option { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.8rem; cursor: pointer; }
.platform-option.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.platform-option input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
