<template>
  <div class="pipeline-page">
    <div class="container">
      <div class="head">
        <div>
          <span class="section-label">ONE-CLICK PIPELINE</span>
          <h1 class="page-title">成稿任务</h1>
          <p class="page-desc">选题 → 素材 → AI 成文 → 风控 → 修订 → 入库，一键自动完成</p>
        </div>
        <div class="head-actions">
          <select v-model="statusFilter" @change="load()">
            <option value="">全部状态</option>
            <option value="queued">排队中</option>
            <option value="running">执行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
          <button class="btn" @click="load">🔄 刷新</button>
          <button class="btn primary" @click="openCreate">⚡ 新建成稿任务</button>
        </div>
      </div>
      <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>

      <div class="run-list">
        <div v-for="r in runs" :key="r.id" class="run-card card" @click="selectRun(r)" :class="{ active: selected?.id === r.id }">
          <div class="run-head">
            <span class="badge" :class="r.source_type === 'rewrite' ? 'badge-blue' : 'badge-purple'">
              {{ r.source_type === 'rewrite' ? '热点改写' : '自由创作' }}
            </span>
            <span class="run-title">{{ r.display_title || r.topic || `任务 #${r.id}` }}</span>
            <span class="status" :class="r.status">{{ statusText(r.status) }}</span>
          </div>
          <div class="run-meta">
            <span v-if="r.current_stage_label && r.status === 'running'">⏳ {{ r.current_stage_label }}</span>
            <span>AI 调用 {{ r.ai_calls }} 次</span>
            <span>{{ formatTime(r.created_at) }}</span>
          </div>
          <p v-if="r.error" class="err-text">❌ {{ r.error }}</p>
          <div class="run-actions">
            <button class="btn small" @click.stop="selectRun(r)">👁 详情</button>
            <button v-if="r.status === 'failed' || r.status === 'cancelled'" class="btn small accent" @click.stop="retry(r)">🔁 重试</button>
            <button v-if="r.status === 'queued' || r.status === 'running'" class="btn small del" @click.stop="cancel(r)">✖ 取消</button>
          </div>
        </div>
        <p v-if="!runs.length && loaded" class="empty-tip">暂无任务，点击右上角「⚡ 新建成稿任务」</p>
      </div>

      <div class="pager" v-if="total > pageSize">
        <button class="btn" :disabled="page <= 1" @click="page--; load()">上一页</button>
        <span>{{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }}</span>
        <button class="btn" :disabled="page * pageSize >= total" @click="page++; load()">下一页</button>
      </div>

      <!-- 详情 -->
      <div v-if="selected" class="detail card">
        <div class="detail-head">
          <h3>任务 #{{ selected.id }} · {{ selected.display_title || selected.topic }}</h3>
          <div>
            <button class="btn small" @click="loadDetail(true)">🔄 刷新</button>
            <button class="btn small" @click="selected = null">✕ 关闭</button>
          </div>
        </div>
        <div v-if="selected.error" class="err-text">❌ {{ selected.error }}</div>
        <div class="stage-list">
          <div v-for="a in selected.artifacts" :key="a.id" class="stage-card" :class="a.status" @click="toggleStage(a.id)">
            <div class="stage-head">
              <span class="st-icon">{{ a.status === 'done' ? '✅' : a.status === 'running' ? '⏳' : a.status === 'failed' ? '❌' : '⏭' }}</span>
              <strong class="st-label">{{ a.stage_label }}</strong>
              <span class="st-status" :class="a.status">{{ stageStatusText(a.status) }}</span>
              <span class="st-meta">
                <template v-if="a.status === 'done'">
                  {{ a.word_count }} 字 · 完成于 {{ formatTime(a.updated_at) }}
                </template>
                <template v-else-if="a.status === 'running'">执行中…</template>
              </span>
              <span class="st-chev">{{ expandedIds.has(a.id) ? '▴' : '▾' }}</span>
            </div>
            <div v-if="expandedIds.has(a.id)" class="stage-body">
              <div v-if="a.title" class="st-title">{{ a.title }}</div>
              <div v-if="a.stage === 'risk' && a.meta?.level" class="risk-block" :class="a.meta.level">
                <p class="risk-line">
                  风控：{{ riskLevelText(a.meta.level) }}
                  <span v-if="a.meta.pass !== undefined" class="muted">（{{ a.meta.pass ? '通过' : '未通过' }}）</span>
                </p>
                <ul v-if="a.meta.issues?.length" class="risk-ul">
                  <li v-for="(i, idx) in a.meta.issues" :key="idx">⚠️ {{ i }}</li>
                </ul>
                <p v-if="a.meta.suggestions?.length" class="sugg-line">💡 建议：{{ a.meta.suggestions.join('；') }}</p>
              </div>
              <div v-if="a.meta?.fixed" class="fixed-tag">✏️ 已按风控建议自动修订</div>
              <div v-if="a.meta?.article_id" class="meta-line">📄 已入库文章 ID：{{ a.meta.article_id }}</div>
              <div v-if="a.meta?.url" class="meta-line">
                来源：<a :href="a.meta.url" target="_blank" rel="noopener">{{ a.meta.source_name || a.meta.url }}</a>
              </div>
              <pre v-if="a.content_md" class="st-content">{{ a.content_md }}</pre>
              <p v-else-if="a.status === 'done'" class="muted">（本阶段无正文内容）</p>
            </div>
          </div>
          <p v-if="!selected.artifacts?.length" class="muted">任务尚未产生阶段产物，等待 Worker 执行…</p>
        </div>
        <div v-if="selected.status === 'completed'" class="done-actions">
          <span class="done-tip">✅ 已入库<template v-if="selected.article_id">（文章 ID {{ selected.article_id }}）</template></span>
          <button class="btn primary small" @click="$router.push('/articles')">📚 前往文章库</button>
          <button class="btn accent small" @click="$router.push({ path: '/publish' })">🚀 前往发布</button>
        </div>
      </div>
    </div>

    <!-- 新建任务 -->
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="modal card">
        <h3>⚡ 新建成稿任务（自由创作）</h3>
        <label class="field">创作主题 *
          <input v-model="form.topic" placeholder="如：新能源汽车出口最新动态分析" />
        </label>
        <div class="grid2">
          <label class="field">写作风格
            <select v-model="form.style">
              <option v-for="s in styles" :key="s.name" :value="s.name">{{ s.name }}</option>
            </select>
          </label>
          <label class="field">目标字数
            <input v-model.number="form.word_count" type="number" min="200" max="5000" step="100" />
          </label>
        </div>
        <div class="grid2">
          <label class="field">AI 模型
            <select v-model="form.model">
              <option v-for="m in models" :key="m.key" :value="m.key">{{ m.name }}</option>
            </select>
          </label>
          <label class="field">目标平台（可选）
            <select v-model="form.platform">
              <option value="">不指定</option>
              <option v-for="p in platforms" :key="p.key" :value="p.label">{{ p.label }}</option>
            </select>
          </label>
        </div>
        <div class="check-row">
          <label><input type="checkbox" v-model="form.auto_fix" /> 风控高风险时自动按建议修订</label>
          <span class="mode-tip">模式：自动（后台顺序执行）</span>
        </div>
        <p v-if="createError" class="msg err">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn" @click="showCreate = false">取消</button>
          <button class="btn primary" @click="create" :disabled="creating || !canCreate">
            {{ creating ? '创建中...' : '🚀 开始一键成稿' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getPlatforms, getPublicConfig, pipelineAPI, pipelineEvents } from '../api'
import { toast } from '../toast'

const runs = ref([])
const selected = ref(null)
const statusFilter = ref('')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const loaded = ref(false)
const msg = ref('')
const styles = ref([])
const models = ref([])
const platforms = ref([])
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const form = ref({ topic: '', style: '专业深度', word_count: 800, platform: '', model: '', auto_fix: true })
const eventController = ref(null)
const expandedIds = ref(new Set())
let terminalHandled = false

const STATUS_TEXT = { queued: '排队中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
const STAGE_STATUS_TEXT = { running: '执行中', done: '已完成', failed: '失败', skipped: '已跳过' }
const statusText = (s) => STATUS_TEXT[s] || s
const stageStatusText = (s) => STAGE_STATUS_TEXT[s] || s
const riskLevelText = (l) => l === 'low' ? '低风险' : l === 'medium' ? '中风险' : l === 'high' ? '高风险' : (l === 'skipped' ? '未执行' : l || '—')
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
const canCreate = computed(() => !!form.value.topic.trim())

async function load() {
  try {
    const res = await pipelineAPI.list({ status: statusFilter.value || undefined, page: page.value, page_size: pageSize })
    runs.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) { msg.value = `❌ ${e.message}` }
}

function selectRun(r) {
  selected.value = { ...r }
  terminalHandled = false
  loadDetail(true)
}

async function loadDetail(withContent = false) {
  if (!selected.value) return
  try {
    selected.value = await pipelineAPI.get(selected.value.id, withContent ? 1 : 0)
    subscribe(selected.value.id)
  } catch (e) { msg.value = `❌ ${e.message}` }
}

function subscribe(id) {
  try { eventController.value?.abort() } catch (e) {}
  eventController.value = pipelineEvents(
    id,
    (ev) => {
      if (ev.type === 'run_status' && ev.payload?.status && ['completed', 'failed', 'cancelled'].includes(ev.payload.status)) {
        if (!terminalHandled) {
          terminalHandled = true
          loadDetail(false)
          load()
        }
      }
    },
    (err) => { msg.value = `❌ ${err.message}` },
  )
}

function toggleStage(id) {
  const set = new Set(expandedIds.value)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  expandedIds.value = set
}

function openCreate() {
  createError.value = ''
  form.value = { ...form.value, topic: '', style: styles.value[0]?.name || '专业深度', platform: '', model: models.value[0]?.key || '' }
  showCreate.value = true
}

async function create() {
  creating.value = true
  createError.value = ''
  try {
    const payload = {
      source_type: 'create',
      topic: form.value.topic.trim(),
      style: form.value.style,
      word_count: form.value.word_count,
      platform: form.value.platform,
      model: form.value.model,
      auto_fix: form.value.auto_fix,
    }
    const run = await pipelineAPI.create(payload)
    showCreate.value = false
    toast(`⚡ 成稿任务 #${run.id} 已启动`, 'success')
    await load()
    selectRun(run)
  } catch (e) { createError.value = e.message || '创建失败' } finally { creating.value = false }
}

async function retry(r) {
  try { await pipelineAPI.retry(r.id); toast(`🔁 任务 #${r.id} 已重新排队`, 'success'); load() } catch (e) { msg.value = `❌ ${e.message}` }
}

async function cancel(r) {
  if (!confirm(`确认取消任务 #${r.id}？`)) return
  try { await pipelineAPI.cancel(r.id); toast('已取消', 'info'); load() } catch (e) { msg.value = `❌ ${e.message}` }
}

onMounted(async () => {
  try {
    const [tpls, cfg] = await Promise.all([getPlatforms(), getPublicConfig().catch(() => null)])
    platforms.value = tpls
    models.value = cfg?.ai_models || []
    if (cfg?.write_styles?.length) styles.value = cfg.write_styles
    if (models.value.length) form.value.model = models.value[0].key
  } catch (e) {}
  await load()
})

onUnmounted(() => { try { eventController.value?.abort() } catch (e) {} })
</script>

<style scoped>
.pipeline-page { padding-bottom: 2rem; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 10px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.run-list { display: flex; flex-direction: column; gap: 10px; }
.run-card { padding: 12px 16px; cursor: pointer; }
.run-card.active { border-color: var(--accent-blue); }
.run-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.run-title { font-weight: 600; font-size: 0.92rem; flex: 1; }
.status { font-size: 0.72rem; padding: 2px 10px; border-radius: 999px; }
.status.queued { background: rgba(255, 159, 10, 0.15); color: #FFD60A; }
.status.running { background: rgba(100, 210, 255, 0.15); color: var(--accent-blue); }
.status.completed { background: rgba(48, 209, 88, 0.15); color: var(--accent-green); }
.status.failed { background: rgba(255, 69, 58, 0.15); color: #FF9B94; }
.status.cancelled { background: rgba(255, 159, 10, 0.12); color: var(--text-muted); }
.run-meta { display: flex; gap: 14px; font-size: 0.74rem; color: var(--text-muted); margin-top: 4px; }
.err-text { color: #FF9B94; font-size: 0.78rem; margin-top: 4px; }
.run-actions { display: flex; gap: 8px; margin-top: 8px; }
.btn.small { padding: 4px 10px; font-size: 0.76rem; }
.detail { margin-top: 1rem; padding: 1.1rem 1.2rem; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; flex-wrap: wrap; gap: 8px; }
.detail-head h3 { font-family: var(--font-serif); }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.stage-list { display: flex; flex-direction: column; gap: 8px; margin-top: 0.4rem; }
.stage-card { border: 1px solid var(--glass-border); border-radius: 10px; overflow: hidden; background: var(--glass-bg-soft); }
.stage-card.running { border-color: rgba(100, 210, 255, 0.5); }
.stage-card.failed { border-color: rgba(255, 69, 58, 0.55); }
.stage-head { display: flex; align-items: center; gap: 10px; padding: 9px 12px; cursor: pointer; }
.st-icon { width: 20px; text-align: center; }
.st-label { font-size: 0.86rem; }
.st-status { font-size: 0.7rem; padding: 1px 9px; border-radius: 999px; background: var(--glass-bg); }
.st-status.done { color: var(--accent-green); }
.st-status.running { color: var(--accent-blue); }
.st-status.failed { color: #FF9B94; }
.st-status.skipped { color: var(--text-muted); }
.st-meta { margin-left: auto; font-size: 0.72rem; color: var(--text-muted); }
.st-chev { color: var(--text-muted); font-size: 0.72rem; }
.stage-body { padding: 4px 12px 12px 42px; border-top: 1px dashed var(--glass-border); }
.st-title { font-size: 0.9rem; font-weight: 600; margin: 8px 0 4px; }
.risk-block { margin-top: 6px; padding: 8px 10px; border-radius: 8px; background: rgba(255, 159, 10, 0.08); }
.risk-block.high { background: rgba(255, 69, 58, 0.1); }
.risk-block.low { background: rgba(48, 209, 88, 0.08); }
.risk-line { font-size: 0.78rem; color: #FFD60A; }
.risk-block.high .risk-line { color: #FF9B94; }
.risk-block.low .risk-line { color: var(--accent-green); }
.risk-ul { margin: 4px 0 0; padding-left: 16px; font-size: 0.76rem; color: var(--text-secondary); }
.risk-ul li { margin: 2px 0; }
.sugg-line { margin: 4px 0 0; font-size: 0.76rem; color: var(--accent-green); }
.fixed-tag { font-size: 0.76rem; color: var(--accent-green); margin-top: 2px; }
.meta-line { margin-top: 4px; font-size: 0.76rem; color: var(--text-secondary); }
.meta-line a { color: var(--accent-blue); }
.st-content { margin-top: 8px; padding: 10px; background: rgba(5, 8, 18, 0.45); border-radius: 8px; font-size: 0.78rem; line-height: 1.7; white-space: pre-wrap; word-break: break-word; max-height: 360px; overflow-y: auto; }
.done-actions { margin-top: 1rem; display: flex; gap: 10px; align-items: center; }
.done-tip { color: var(--accent-green); font-size: 0.84rem; }
.overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.68); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { width: 560px; max-width: 94vw; max-height: 90vh; overflow-y: auto; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; font-family: var(--font-serif); }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.check-row { display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; margin: 6px 0 8px; }
.check-row input { accent-color: var(--accent-blue); }
.mode-tip { font-size: 0.74rem; color: var(--text-muted); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.empty-tip { text-align: center; color: var(--text-muted); padding: 2rem; }
</style>
