<template>
  <div class="preview-overlay" @click.self="$emit('close')">
    <div class="preview-panel">
      <div class="preview-header">
        <span class="section-label">{{ action === 'pipeline' ? 'ONE-CLICK DRAFT' : 'AI REWRITE' }}</span>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>
      <div class="preview-body">
        <div class="news-info">
          <div class="news-meta">
            <span class="badge badge-blue">{{ news.source_name }}</span>
            <span class="badge badge-purple">{{ news.category }}</span>
            <span class="heat">🔥 {{ news.heat_score }}</span>
          </div>
          <h2 class="news-title">{{ news.title }}</h2>
          <p class="news-summary">{{ news.summary }}</p>
          <a v-if="news.url" :href="news.url" target="_blank" rel="noopener" class="source-link">查看原文 →</a>
        </div>

        <div v-if="!articleSaved" class="rewrite-form">
          <div class="form-row">
            <label>写作风格
              <select v-model="form.style">
                <option v-for="s in styles" :key="s.name" :value="s.name">{{ s.name }}</option>
                <option v-if="!styles.length" value="专业深度">专业深度</option>
              </select>
            </label>
            <label>AI 模型
              <select v-model="form.model">
                <option v-for="m in models" :key="m.key" :value="m.key">{{ m.name }}</option>
              </select>
            </label>
            <label>发布平台
              <select v-model="form.platform">
                <option value="">不指定</option>
                <option v-for="p in platforms" :key="p.key" :value="p.label">{{ p.label }}</option>
              </select>
            </label>
            <label>目标字数
              <input v-model.number="form.word_count" type="number" min="200" max="5000" step="100" />
            </label>
          </div>
          <p v-if="selectedPlatform?.rules" class="platform-rules">📌 平台规范：{{ selectedPlatform.rules }}</p>
          <label class="full-label">补充提示词
            <textarea v-model="form.extra_prompt" rows="2" placeholder="如：重点分析影响、多用数据..." />
          </label>
          <div class="suggestions-box">
            <button class="btn" @click="loadSuggestions" :disabled="suggestionLoading">
              {{ suggestionLoading ? 'AI 生成建议中...' : '💡 生成 AI 写作建议' }}
            </button>
            <p v-if="suggestionError" class="msg err">{{ suggestionError }}</p>
            <label v-for="s in suggestions" :key="s" class="suggestion-item" :class="{ on: appliedSuggestions.includes(s) }">
              <input type="checkbox" :checked="appliedSuggestions.includes(s)" @change="toggleSuggestion(s)" />
              <span>{{ s }}</span>
            </label>
          </div>
          <button class="btn primary generate-btn" @click="generate" :disabled="generating">
            {{ generating ? 'AI 生成中...' : action === 'pipeline' ? '🚀 创建并后台生成' : '✨ 生成 AI 改写文章' }}
          </button>
          <p v-if="error" class="msg err">{{ error }}</p>
        </div>

        <div v-if="generating" class="generating-box">
          <div class="gen-bar"><div class="gen-fill"></div></div>
          <p class="gen-text">{{ streamText.slice(-60) || 'AI 正在撰写...' }}</p>
        </div>

        <div v-if="articleMd" class="editor-box">
          <div class="editor-head">
            <input v-model="articleTitle" class="title-input" placeholder="文章标题" />
            <div class="editor-actions">
            <button class="btn" @click="copyMd">📋 复制 Markdown</button>
            <button class="btn" @click="exportPdf(articleTitle, articleMd)">📄 导出 PDF</button>
            <button class="btn warn" @click="checkRisk" :disabled="riskChecking || riskRevising || !articleMd.trim() || generating">{{ riskChecking ? '检查中...' : '🛡 风控检查' }}</button>
            <button class="btn primary" @click="save" :disabled="saving">{{ saving ? '保存中...' : '💾 保存文章' }}</button>
              <button class="btn accent" @click="showPublish = true">🚀 发布</button>
            </div>
          </div>
          <RichEditor v-model="articleMd" @html-change="articleHtml = $event" />
          <div v-if="risk" class="risk-panel" :class="risk.level || 'unknown'">
            <p class="risk-title">
              {{ risk.pass ? '✅ 风控检查通过' : '⚠️ 风控检查发现风险' }}
              <span v-if="risk.level" class="risk-badge">{{ risk.level === 'low' ? '低风险' : risk.level === 'medium' ? '中风险' : risk.level === 'high' ? '高风险' : '未知' }}</span>
            </p>
            <ul v-if="risk.issues && risk.issues.length" class="risk-issues">
              <li v-for="(i, idx) in risk.issues" :key="idx">{{ i }}</li>
            </ul>
            <p v-if="risk.suggestions && risk.suggestions.length" class="risk-suggest">💡 建议：{{ risk.suggestions.join('；') }}</p>
            <p v-if="risk.level === 'high'" class="risk-warn">⚠️ 高风险内容不建议发布，请修改后重新检查。</p>
            <div v-if="risk.issues && risk.issues.length || risk.suggestions && risk.suggestions.length" class="risk-actions">
              <button class="btn accent revise-btn" @click="reviseByRisk" :disabled="riskRevising || generating">
                {{ riskRevising ? 'AI 修改中...' : '✨ AI 按建议修改' }}
              </button>
            </div>
            <div v-if="riskRevising" class="revise-box">
              <div class="gen-bar"><div class="gen-fill"></div></div>
              <p class="revise-text">{{ riskReviseText.slice(-80) || 'AI 正在结合风控建议修改正文...' }}</p>
            </div>
          </div>
          <p v-if="riskMsg" class="msg err">{{ riskMsg }}</p>
          <p v-if="savedMsg" class="msg">{{ savedMsg }}</p>
        </div>
      </div>
    </div>

    <div v-if="showPublish" class="publish-modal-overlay" @click.self="showPublish = false">
      <div class="publish-modal card">
        <h3>选择发布平台</h3>
        <div class="platform-grid">
          <label v-for="p in platforms" :key="p.key" class="platform-option" :class="{ on: publishPlatforms.includes(p.label) }">
            <input type="checkbox" :value="p.label" v-model="publishPlatforms" />
            <span>{{ p.label }}（{{ p.min_words }}-{{ p.max_words }}字）</span>
          </label>
        </div>
        <p v-if="publishError" class="msg err">{{ publishError }}</p>
        <div class="modal-actions">
          <button class="btn" @click="showPublish = false">取消</button>
          <button class="btn primary" @click="doPublish" :disabled="!publishPlatforms.length">创建发布任务</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { createPublishTasks, getPlatforms, getPublicConfig, getRewriteSuggestions, getWriteStyles, pipelineAPI, rewriteStream, riskCheck, riskReviseStream, saveArticle } from '../api'
import RichEditor from './RichEditor.vue'
import { copyRichHtml, exportPdf, splitTitle } from '../utils'
import { toast } from '../toast'

const props = defineProps({ news: Object, action: { type: String, default: 'rewrite' } })
const emit = defineEmits(['close'])

const styles = ref([])
const models = ref([])
const platforms = ref([])
const form = ref({ style: '专业深度', model: '', platform: '', extra_prompt: '', word_count: 800 })
const suggestions = ref([])
const appliedSuggestions = ref([])
const suggestionLoading = ref(false)
const suggestionError = ref('')
const selectedPlatform = computed(() => platforms.value.find(p => p.label === form.value.platform) || null)
const generating = ref(false)
const streamText = ref('')
const articleMd = ref('')
const articleHtml = ref('')
const articleTitle = ref('')
const articleSaved = ref(false)
const saving = ref(false)
const savedMsg = ref('')
const riskChecking = ref(false)
const risk = ref(null)
const riskMsg = ref('')
const riskRevising = ref(false)
const riskReviseText = ref('')
const error = ref('')
const showPublish = ref(false)
const publishPlatforms = ref([])
const publishError = ref('')

function generate() {
  error.value = ''
  risk.value = null
  riskMsg.value = ''
  if (props.action === 'pipeline') {
    createPipelineTask()
    return
  }
  generating.value = true
  streamText.value = ''
  rewriteStream(
    props.news.id,
    { style: form.value.style, model: form.value.model, platform: form.value.platform, extra_prompt: form.value.extra_prompt, word_count: form.value.word_count },
    (token) => { streamText.value += token },
    (content) => {
      const full = content || streamText.value
      const { title: aiTitle, body } = splitTitle(full)
      articleMd.value = body
      articleTitle.value = aiTitle || props.news.title
      articleHtml.value = ''
      generating.value = false
    },
    (err) => { error.value = err.message; generating.value = false },
  )
}

async function createPipelineTask() {
  generating.value = true
  error.value = ''
  try {
    const run = await pipelineAPI.create({
      source_type: 'rewrite',
      news_id: props.news.id,
      style: form.value.style,
      word_count: form.value.word_count || 800,
      platform: form.value.platform,
      model: form.value.model,
      extra_prompt: form.value.extra_prompt,
      auto_fix: true,
    })
    toast(`⚡ 已后台创建成稿任务 #${run.id}`, 'success', { label: '查看任务', to: '/pipeline' })
    emit('close')
  } catch (e) {
    error.value = e.message || '任务创建失败'
    toast(`❌ ${error.value}`, 'error')
  } finally {
    generating.value = false
  }
}

async function checkRisk() {
  riskChecking.value = true
  risk.value = null
  riskMsg.value = ''
  try {
    risk.value = await riskCheck({ title: articleTitle.value, content: articleMd.value, platform: form.value.platform })
    if (risk.value.level === 'high') toast('⚠️ 高风险内容，建议修改后再发布', 'error')
    else if (risk.value.level === 'medium') toast('⚠️ 存在中风险点，建议按提示修改', 'info')
    else toast('✅ 风控检查通过', 'success')
  } catch (e) {
    riskMsg.value = `❌ ${e.message}`
  } finally {
    riskChecking.value = false
  }
}

function reviseByRisk() {
  if (!risk.value || !articleMd.value.trim()) return
  riskRevising.value = true
  riskReviseText.value = ''
  riskMsg.value = ''
  riskReviseStream(
    {
      title: articleTitle.value,
      content: articleMd.value,
      platform: form.value.platform,
      issues: risk.value.issues || [],
      suggestions: risk.value.suggestions || [],
    },
    (token) => { riskReviseText.value += token },
    (content) => {
      const full = content || riskReviseText.value
      const { title: aiTitle, body } = splitTitle(full)
      if (body.trim()) {
        articleMd.value = body
        articleTitle.value = aiTitle || articleTitle.value
        articleHtml.value = ''
      }
      riskRevising.value = false
      risk.value = null
      savedMsg.value = '✅ 已按风控建议修改完成，建议重新执行风控检查'
      toast('✅ 已按风控建议修改，建议重新风控检查', 'success')
    },
    (err) => {
      riskRevising.value = false
      riskMsg.value = `❌ ${err.message}`
      toast(`❌ ${err.message}`, 'error')
    },
  )
}

async function loadSuggestions() {
  suggestionLoading.value = true
  suggestionError.value = ''
  try {
    const res = await getRewriteSuggestions(props.news.id, { model: form.value.model, count: 4 })
    suggestions.value = res.suggestions || []
    appliedSuggestions.value = suggestions.value.filter(s => form.value.extra_prompt.includes(s))
  } catch (e) {
    suggestionError.value = e.message || '建议生成失败'
  } finally {
    suggestionLoading.value = false
  }
}

function toggleSuggestion(s) {
  const idx = appliedSuggestions.value.indexOf(s)
  const marker = `[改写建议] ${s}`
  if (idx >= 0) {
    appliedSuggestions.value.splice(idx, 1)
    form.value.extra_prompt = form.value.extra_prompt.split('\n').filter(l => l.trim() !== marker).join('\n')
  } else {
    appliedSuggestions.value.push(s)
    form.value.extra_prompt = (form.value.extra_prompt + '\n' + marker).trim()
  }
}

async function save() {
  saving.value = true
  savedMsg.value = ''
  try {
    await saveArticle({
      news_id: props.news.id,
      title: articleTitle.value,
      content_md: articleMd.value,
      content_html: articleHtml.value,
      source_type: 'rewrite',
      style: form.value.style,
      platform: form.value.platform,
    })
    articleSaved.value = true
    savedMsg.value = '✅ 文章已保存到文章库'
  } catch (e) {
    savedMsg.value = `❌ ${e.message}`
  } finally {
    saving.value = false
  }
}

async function copyMd() {
  const ok = await copyRichHtml(articleTitle.value, articleMd.value)
  savedMsg.value = ok ? '✅ 已复制带格式正文' : '复制失败，请手动选择正文复制'
  toast(ok ? '📋 已复制带格式正文' : '复制失败', ok ? 'success' : 'error')
}

async function doPublish() {
  publishError.value = ''
  try {
    await createPublishTasks({ title: articleTitle.value, content: articleMd.value, platforms: publishPlatforms.value, news_id: props.news.id })
    showPublish.value = false
    savedMsg.value = '✅ 发布任务已创建，可在「发布」页查看'
    toast(`🎉 已创建 ${publishPlatforms.value.length} 个发布任务，可前往发布页一键跳转发布`, 'success', { label: '前往发布', to: '/publish' })
  } catch (e) {
    publishError.value = e.message
    toast(`❌ ${e.message || '发布失败'}`, 'error')
  }
}

onMounted(async () => {
  try {
    const [tpls, cfg] = await Promise.all([getPlatforms(), getPublicConfig().catch(() => null)])
    platforms.value = tpls
    models.value = cfg?.ai_models || []
    if (cfg?.write_styles?.length) styles.value = cfg.write_styles
    else styles.value = (await getWriteStyles().catch(() => ({ styles: [] }))).styles || []
    if (models.value.length) form.value.model = models.value[0].key
  } catch (e) {}
})
</script>

<style scoped>
.preview-overlay { position: fixed; inset: 0; z-index: 1100; background: rgba(5, 8, 18, 0.68); -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.preview-panel { width: 860px; max-width: 96vw; max-height: 92vh; overflow-y: auto; background: var(--glass-deep); border: 1px solid var(--glass-border); border-radius: 24px; box-shadow: var(--shadow-lg); padding: 1.3rem 1.5rem; }
.preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
.close-btn { background: none; border: none; color: var(--text-muted); font-size: 1.5rem; cursor: pointer; line-height: 1; }
.news-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.heat { margin-left: auto; color: var(--accent-red); font-family: var(--font-mono); font-size: 0.82rem; }
.news-title { font-family: var(--font-serif); font-size: 1.3rem; margin-bottom: 8px; }
.news-summary { color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 8px; }
.source-link { font-size: 0.78rem; }
.rewrite-form { margin-top: 1rem; display: flex; flex-direction: column; gap: 10px; }
.form-row { display: flex; gap: 14px; }
.form-row label { display: flex; flex-direction: column; gap: 5px; font-size: 0.76rem; color: var(--text-muted); flex: 1; }
.full-label { display: flex; flex-direction: column; gap: 5px; font-size: 0.76rem; color: var(--text-muted); }
.generate-btn { align-self: flex-start; margin-top: 4px; }
.suggestions-box { display: flex; flex-direction: column; gap: 6px; }
.platform-rules { font-size: 0.76rem; color: var(--accent-blue); background: rgba(100, 210, 255, 0.1); border: 1px solid rgba(100, 210, 255, 0.25); border-radius: 8px; padding: 7px 10px; }
.suggestions-box .btn { align-self: flex-start; }
.suggestion-item { display: flex; align-items: flex-start; gap: 8px; padding: 7px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.78rem; color: var(--text-secondary); cursor: pointer; }
.suggestion-item.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.suggestion-item input { accent-color: var(--accent-blue); margin-top: 2px; }
.generating-box { margin-top: 1rem; }
.gen-bar { height: 4px; background: var(--glass-bg); border-radius: 2px; overflow: hidden; }
.gen-fill { height: 100%; width: 60%; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); animation: slide 1.2s infinite ease-in-out; }
@keyframes slide { 0% { margin-left: -60%; } 100% { margin-left: 100%; } }
.gen-text { margin-top: 8px; font-size: 0.76rem; color: var(--text-muted); font-family: var(--font-mono); }
.editor-box { margin-top: 1.1rem; display: flex; flex-direction: column; gap: 10px; }
.editor-head { display: flex; gap: 10px; align-items: center; }
.title-input { flex: 1; font-size: 1rem; font-weight: 600; }
.editor-actions { display: flex; gap: 8px; }
.btn.warn { border-color: rgba(255, 159, 10, 0.45); color: #FFD60A; }
.risk-panel { margin-top: 10px; padding: 10px 12px; border-radius: 10px; font-size: 0.8rem; border: 1px solid var(--glass-border); background: var(--glass-bg-soft); }
.risk-panel.high { border-color: rgba(255, 69, 58, 0.5); background: rgba(255, 69, 58, 0.08); }
.risk-panel.medium { border-color: rgba(255, 159, 10, 0.5); background: rgba(255, 159, 10, 0.07); }
.risk-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.risk-badge { font-size: 0.7rem; padding: 1px 8px; border-radius: 999px; background: rgba(255, 159, 10, 0.2); color: #FFD60A; }
.risk-panel.high .risk-badge { background: rgba(255, 69, 58, 0.2); color: #FF9B94; }
.risk-issues { margin: 6px 0 0 0; padding-left: 18px; color: var(--text-secondary); }
.risk-issues li { margin: 2px 0; }
.risk-suggest { margin: 6px 0 0; color: var(--accent-green); }
.risk-warn { margin: 6px 0 0; color: #FF9B94; }
.risk-actions { margin-top: 10px; display: flex; gap: 8px; }
.revise-btn { font-size: 0.8rem; }
.revise-box { margin-top: 10px; padding: 8px 10px; border: 1px dashed var(--glass-border); border-radius: 10px; }
.revise-text { margin-top: 6px; font-size: 0.76rem; color: var(--text-muted); font-family: var(--font-mono); }
.publish-modal-overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.6); display: flex; align-items: center; justify-content: center; }
.publish-modal { width: 480px; max-width: 92vw; padding: 1.4rem; }
.publish-modal h3 { margin-bottom: 0.8rem; font-family: var(--font-serif); }
.platform-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 0.8rem; }
.platform-option { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.8rem; cursor: pointer; }
.platform-option.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.platform-option input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
