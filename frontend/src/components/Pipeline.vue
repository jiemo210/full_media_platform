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
        <div class="timeline">
          <div v-for="a in selected.artifacts" :key="a.id" class="tl-item" :class="a.status">
            <span class="tl-icon">{{ a.status === 'done' ? '✅' : a.status === 'running' ? '⏳' : a.status === 'failed' ? '❌' : '⏭' }}</span>
            <div class="tl-body">
              <div class="tl-line">
                <strong>{{ a.stage_label }}</strong>
                <span v-if="a.status === 'done'" class="muted">（{{ a.word_count }} 字）</span>
              </div>
              <div v-if="a.title" class="tl-title">{{ a.title }}</div>
              <div v-if="a.meta?.level && a.stage === 'risk'" class="risk-tag" :class="a.meta.level">
                风控：{{ a.meta.level === 'low' ? '低风险' : a.meta.level === 'medium' ? '中风险' : a.meta.level === 'high' ? '高风险' : '—' }}
                <span v-if="a.meta.issues?.length" class="muted">（{{ a.meta.issues.length }} 个风险点）</span>
              </div>
              <div v-if="a.meta?.fixed" class="fixed-tag">✏️ 已按风控建议自动修订</div>
            </div>
          </div>
        </div>
        <div v-if="selected.status === 'completed'" class="done-actions">
          <span class="done-tip">✅ 已入库<template v-if="selected.article_id">（文章 ID {{ selected.article_id }}）</template></span>
          <button class="btn primary small" @click="$router.push('/articles')">📚 前往文章库</button>
          <button class="btn accent small" @click="$router.push({ path: '/publish' })">🚀 前往发布</button>
        </div>
        <div v-if="liveLog.length" class="live-log">
          <div v-for="(l, i) in liveLog" :key="i" class="log-line" :class="l.cls">{{ l.text }}</div>
        </div>
      </div>
    </div>

    <!-- 新建任务 -->
    <div v-if="showCreate" class="overlay" @click.self="showCreate = false">
      <div class="modal card">
        <h3>⚡ 新建成稿任务</h3>
        <div class="seg">
          <button :class="{ on: form.source_type === 'rewrite' }" @click="form.source_type = 'rewrite'">📰 热点改写</button>
          <button :class="{ on: form.source_type === 'create' }" @click="form.source_type = 'create'">✍️ 自由创作</button>
        </div>
        <label v-if="form.source_type === 'create'" class="field">创作主题 *
          <input v-model="form.topic" placeholder="如：新能源汽车出口最新动态分析" />
        </label>
        <p v-else class="news-tip">📰 将改写新闻：{{ preselectTitle || '（将自动抓取热点原文）' }}</p>
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
import { useRoute, useRouter } from 'vue-router'
import { getPlatforms, getPublicConfig, pipelineAPI, pipelineEvents } from '../api'
import { toast } from '../toast'

const route = useRoute()
const router = useRouter()
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
const preselectNewsId = ref(null)
const preselectTitle = ref('')
const form = ref({ source_type: 'create', topic: '', style: '专业深度', word_count: 800, platform: '', model: '', auto_fix: true })
const liveLog = ref([])
const eventController = ref(null)

const STATUS_TEXT = { queued: '排队中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
const statusText = (s) => STATUS_TEXT[s] || s
const formatTime = (v) => v ? new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
const canCreate = computed(() => form.value.source_type === 'rewrite' ? !!preselectNewsId.value : !!form.value.topic.trim())

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
  liveLog.value = []
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
      if (ev.type === 'stage_start') pushLog(`开始：${ev.payload?.label || ev.payload?.stage}`, '')
      else if (ev.type === 'stage_done') pushLog(`完成：${ev.payload?.label || ev.payload?.stage}`, 'ok')
      else if (ev.type === 'stage_skip') pushLog(`跳过：${ev.payload?.label || ev.payload?.stage}`, '')
      else if (ev.type === 'run_status' && ev.payload?.status) {
        pushLog(`状态：${statusText(ev.payload.status)}${ev.payload.error ? ' · ' + ev.payload.error : ''}`, ev.payload.status === 'failed' ? 'err' : ev.payload.status === 'completed' ? 'ok' : '')
        if (['completed', 'failed', 'cancelled'].includes(ev.payload.status)) {
          loadDetail(false)
          load()
        }
      }
    },
    (err) => { msg.value = `❌ ${err.message}` },
  )
}

function pushLog(text, cls) {
  liveLog.value.push({ text, cls })
  if (liveLog.value.length > 50) liveLog.value.shift()
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
      source_type: form.value.source_type,
      news_id: form.value.source_type === 'rewrite' ? preselectNewsId.value : undefined,
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
  const qNewsId = Number(route.query.news_id)
  if (qNewsId) {
    preselectNewsId.value = qNewsId
    preselectTitle.value = String(route.query.title || '')
    form.value.source_type = 'rewrite'
  }
  try {
    const [tpls, cfg] = await Promise.all([getPlatforms(), getPublicConfig().catch(() => null)])
    platforms.value = tpls
    models.value = cfg?.ai_models || []
    if (cfg?.write_styles?.length) styles.value = cfg.write_styles
    if (models.value.length) form.value.model = models.value[0].key
  } catch (e) {}
  await load()
  if (qNewsId) {
    showCreate.value = true
  }
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
.timeline { display: flex; flex-direction: column; gap: 6px; }
.tl-item { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; }
.tl-icon { width: 22px; text-align: center; }
.tl-body { flex: 1; }
.tl-title { font-size: 0.84rem; color: var(--text-secondary); }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.risk-tag { font-size: 0.76rem; margin-top: 2px; }
.risk-tag.high { color: #FF9B94; }
.risk-tag.medium { color: #FFD60A; }
.risk-tag.low { color: var(--accent-green); }
.fixed-tag { font-size: 0.76rem; color: var(--accent-green); margin-top: 2px; }
.done-actions { margin-top: 1rem; display: flex; gap: 10px; align-items: center; }
.done-tip { color: var(--accent-green); font-size: 0.84rem; }
.live-log { margin-top: 1rem; border-top: 1px solid var(--glass-border); padding-top: 8px; font-family: var(--font-mono); font-size: 0.74rem; }
.log-line.ok { color: var(--accent-green); }
.log-line.err { color: #FF9B94; }
.overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.68); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { width: 560px; max-width: 94vw; max-height: 90vh; overflow-y: auto; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; font-family: var(--font-serif); }
.seg { display: flex; gap: 8px; margin-bottom: 12px; }
.seg button { flex: 1; padding: 8px; border: 1px solid var(--glass-border); border-radius: 10px; background: var(--glass-bg-soft); color: var(--text-secondary); cursor: pointer; font-size: 0.84rem; }
.seg button.on { border-color: var(--accent-blue); color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.news-tip { font-size: 0.82rem; color: var(--accent-blue); background: rgba(100, 210, 255, 0.08); border-radius: 8px; padding: 8px 10px; margin-bottom: 10px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.check-row { display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; margin: 6px 0 8px; }
.check-row input { accent-color: var(--accent-blue); }
.mode-tip { font-size: 0.74rem; color: var(--text-muted); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.empty-tip { text-align: center; color: var(--text-muted); padding: 2rem; }
</style>
