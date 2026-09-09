<template>
  <div class="publish-page">
    <div class="container">
      <span class="section-label">PUBLISH CENTER</span>
      <h1 class="page-title">发布管理</h1>
      <p class="page-desc">发布任务：预览、富文本编辑、一键跳转平台发布、复制带格式正文、导出 PDF</p>

      <div class="filters">
        <select v-model="statusFilter" @change="load(1)">
          <option value="">全部状态</option>
          <option value="pending">待发布</option>
          <option value="jumped">已跳转</option>
          <option value="published">已发布</option>
        </select>
      </div>

      <div class="task-list">
        <div v-for="t in tasks" :key="t.id" class="task-item card">
          <div class="task-head">
            <span class="badge badge-blue">{{ t.platform }}</span>
            <span class="status" :class="t.status">{{ t.status === 'published' ? '已发布' : t.status === 'jumped' ? '已跳转' : '待发布' }}</span>
          </div>
          <h3 class="task-title">{{ t.title }}</h3>
          <p class="task-preview">{{ plainText(t.content).slice(0, 100) }}</p>
          <div class="task-actions">
            <button class="btn" @click="openPreview(t)">👁 预览</button>
            <button class="btn" @click="openEdit(t)">✏️ 编辑</button>
            <button class="btn" @click="copyPackage(t)">📋 复制</button>
            <button class="btn" @click="exportPdf(t.title, t.content)">📄 导出 PDF</button>
            <button class="btn primary" v-if="t.status === 'pending'" @click="publish(t)">🚀 发布跳转</button>
            <button class="btn accent" v-if="t.status === 'jumped'" @click="askConfirm('publish', t)">✅ 确认已发布</button>
            <button class="btn del" @click="askConfirm('delete', t)">🗑 删除</button>
          </div>
        </div>
        <p v-if="!tasks.length && loaded" class="empty-tip">暂无发布任务</p>
        <Pager :page="page" :total="total" :page-size="pageSize" @change="load" />
      </div>
      <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
    </div>

    <!-- 预览弹窗 -->
    <div v-if="previewTask" class="overlay" @click.self="previewTask = null">
      <div class="modal preview-modal card">
        <div class="modal-head">
          <h3>{{ previewTask.title }}</h3>
          <button class="close" @click="previewTask = null">×</button>
        </div>
        <div class="preview-body" v-html="mdToHtml(previewTask.content)"></div>
        <div class="modal-actions">
          <button class="btn" @click="copyPackage(previewTask)">📋 复制</button>
          <button class="btn primary" @click="previewTask = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- 发布跳转被拦截时的回退 -->
    <div v-if="publishFallback" class="overlay" @click.self="publishFallback = null">
      <div class="modal card fallback-modal">
        <h3>发布跳转</h3>
        <p class="fallback-tip">浏览器拦截了新窗口打开，请点击下方按钮手动打开「{{ publishFallback.platform }}」发布页：</p>
        <a :href="publishFallback.url" target="_blank" rel="noopener noreferrer" class="btn primary fallback-link">🚀 打开平台发布页</a>
        <div class="modal-actions">
          <button class="btn" @click="publishFallback = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="editTask" class="overlay" @click.self="editTask = null">
      <div class="modal edit-modal card">
        <div class="modal-head">
          <h3>编辑发布任务</h3>
          <button class="close" @click="editTask = null">×</button>
        </div>
        <label class="field">平台
          <select v-model="editForm.platform">
            <option v-for="p in platforms" :key="p.key" :value="p.label">{{ p.label }}</option>
          </select>
        </label>
        <label class="field">标题
          <input v-model="editForm.title" />
        </label>
        <div class="field">
          <span class="field-label">正文（富文本）</span>
          <RichEditor v-model="editForm.content" />
        </div>
        <p v-if="editMsg" class="msg" :class="{ err: editMsg.startsWith('❌') }">{{ editMsg }}</p>
        <div class="modal-actions">
          <button class="btn" @click="editTask = null">取消</button>
          <button class="btn primary" @click="saveEdit" :disabled="savingEdit">{{ savingEdit ? '保存中...' : '💾 保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 统一风格确认弹窗 -->
    <div v-if="pendingConfirm" class="overlay" @click.self="pendingConfirm = null">
      <div class="modal confirm-modal card">
        <h3>{{ pendingConfirm.kind === 'publish' ? '确认发布' : '删除确认' }}</h3>
        <p class="confirm-text">
          {{ pendingConfirm.kind === 'publish'
            ? '确认已在「' + pendingConfirm.task.platform + '」完成发布？'
            : '确认删除该发布任务？' }}
        </p>
        <div class="modal-actions">
          <button class="btn" @click="pendingConfirm = null">取消</button>
          <button
            class="btn"
            :class="pendingConfirm.kind === 'delete' ? 'del' : 'primary'"
            @click="runConfirm"
            :disabled="confirming"
          >{{ confirming ? '处理中...' : (pendingConfirm.kind === 'delete' ? '删除' : '确认发布') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { confirmPublishTask, deletePublishTask, getPlatforms, getPublishTasks, publishTask, updatePublishTask } from '../api'
import { toast } from '../toast'
import { copyRichHtml, exportPdf, mdToHtml } from '../utils'
import RichEditor from './RichEditor.vue'
import Pager from './Pager.vue'

const tasks = ref([])
const page = ref(1)
const pageSize = 10
const total = ref(0)
const statusFilter = ref('')
const loaded = ref(false)
const msg = ref('')
const platforms = ref([])
const previewTask = ref(null)
const editTask = ref(null)
const editForm = ref({ platform: '', title: '', content: '' })
const editMsg = ref('')
const savingEdit = ref(false)
const publishFallback = ref(null)
const pendingConfirm = ref(null)
const confirming = ref(false)

const plainText = (md) => (md || '').replace(/[#>*`\-\[\]()]/g, '').replace(/\n+/g, ' ').trim()

async function load(p = 1) {
  page.value = p
  try {
    const res = await getPublishTasks({ page: page.value, page_size: pageSize, status: statusFilter.value || undefined })
    tasks.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) { msg.value = `❌ ${e.message}` }
}

function openPreview(t) { previewTask.value = t }
function openEdit(t) {
  editTask.value = t
  editForm.value = { platform: t.platform, title: t.title, content: t.content }
  editMsg.value = ''
}

async function saveEdit() {
  savingEdit.value = true
  editMsg.value = ''
  try {
    await updatePublishTask(editTask.value.id, editForm.value)
    editMsg.value = '✅ 已保存'
    editTask.value = null
    msg.value = '✅ 发布任务已更新'
    load()
  } catch (e) { editMsg.value = `❌ ${e.message}` } finally { savingEdit.value = false }
}

async function copyPackage(t) {
  const ok = await copyRichHtml(t.title, t.content)
  if (ok) {
    toast('📋 已复制带格式正文', 'success')
    msg.value = `已复制 ${t.platform} 正文`
  } else {
    toast('复制失败，请手动选择正文复制', 'error')
  }
}

async function publish(t) {
  // 优先 window.open 自动打开；被拦截则展示可点击回退
  const jumpUrl = t.jump_url
  let opened = false
  if (jumpUrl) opened = openInNewTab(jumpUrl)
  try {
    const res = await publishTask(t.id)
    const target = res?.jump_url || jumpUrl
    if (target && !jumpUrl) opened = openInNewTab(target) || opened
    if (target && !opened) {
      publishFallback.value = { platform: t.platform, url: target }
      toast('浏览器拦截了新窗口，请点击「打开平台」手动跳转', 'info', { label: '打开平台', to: target }, 8000)
    } else if (target) {
      toast(`🚀 已跳转 ${t.platform} 发布页`, 'success', { label: '打开平台', to: target })
    } else {
      toast('✅ 发布完成', 'success')
    }
    msg.value = jumpUrl ? '✅ 已标记发布，并在新窗口打开平台发布页' : '✅ 发布完成'
    load()
  } catch (e) {
    msg.value = `❌ ${e.message}`
    toast(`❌ ${e.message || '发布失败'}`, 'error')
  }
}

function openInNewTab(url) {
  try {
    const win = window.open(url, '_blank', 'noopener')
    if (win) return true
    const a = document.createElement('a')
    a.href = url
    a.target = '_blank'
    a.rel = 'noopener noreferrer'
    document.body.appendChild(a)
    a.click()
    a.remove()
    return true
  } catch (e) {
    return false
  }
}

function askConfirm(kind, t) {
  pendingConfirm.value = { kind, task: t }
}

async function runConfirm() {
  const c = pendingConfirm.value
  if (!c || confirming.value) return
  confirming.value = true
  try {
    if (c.kind === 'delete') {
      await deletePublishTask(c.task.id)
      msg.value = '✅ 发布任务已删除'
      toast('🗑 发布任务已删除', 'success')
    } else {
      await confirmPublishTask(c.task.id)
      msg.value = `✅ 「${c.task.platform}」已标记为已发布`
      toast('✅ 已确认发布', 'success')
    }
    pendingConfirm.value = null
    load()
  } catch (e) {
    msg.value = `❌ ${e.message}`
    toast(`❌ ${e.message || '操作失败'}`, 'error')
  } finally {
    confirming.value = false
  }
}

onMounted(async () => {
  load()
  try { platforms.value = await getPlatforms() } catch (e) {}
})
</script>

<style scoped>
.publish-page { padding-bottom: 2rem; }
.filters { margin-bottom: 1rem; }
.task-list { display: flex; flex-direction: column; gap: 12px; }
.task-item { padding: 16px 18px; }
.task-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.status { font-size: 0.72rem; padding: 2px 10px; border-radius: 999px; }
.status.pending { background: rgba(255, 159, 10, 0.16); color: #FFD60A; }
.status.jumped { background: rgba(100, 210, 255, 0.16); color: var(--accent-blue); }
.status.published { background: rgba(48, 209, 88, 0.16); color: var(--accent-green); }
.task-title { font-size: 1rem; margin-bottom: 4px; }
.task-preview { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.task-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; }
.ext-link { font-size: 0.78rem; }
.overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.68); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { width: 560px; max-width: 94vw; max-height: 88vh; overflow-y: auto; padding: 1.3rem; }
.confirm-modal { width: 380px; }
.edit-modal { width: 880px; max-width: 96vw; }
.preview-modal { width: 680px; }
.confirm-text { margin: 0.5rem 0 0.2rem; color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
.modal-head h3 { font-family: var(--font-serif); }
.close { background: none; border: none; color: var(--text-muted); font-size: 1.4rem; cursor: pointer; line-height: 1; }
.preview-body { font-size: 0.88rem; line-height: 1.8; max-height: 55vh; overflow-y: auto; padding: 12px; background: var(--glass-bg-soft); border: 1px solid var(--glass-border); border-radius: 12px; }
.preview-body :deep(h2), .preview-body :deep(h3) { margin: 0.6em 0 0.3em; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.field-label { font-size: 0.78rem; color: var(--text-muted); }
.field textarea { resize: vertical; font-family: var(--font-mono); font-size: 0.8rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 0.8rem; }
.fallback-modal { text-align: center; }
.fallback-tip { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem; }
.fallback-link { display: inline-block; font-size: 0.95rem; padding: 12px 26px; text-decoration: none; }
</style>
