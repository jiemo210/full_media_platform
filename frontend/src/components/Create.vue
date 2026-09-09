<template>
  <div class="create-page">
    <div class="container">
      <span class="section-label">AI CONTENT CREATION</span>
      <h1 class="page-title">AI 创作</h1>
      <p class="page-desc">输入主题，AI 生成文章后自动进入富文本编辑器（Markdown 格式自动渲染）</p>

      <div class="create-layout">
        <div class="input-panel card">
          <label class="field">创作主题 *
            <textarea v-model="topic" rows="4" placeholder="如：新能源汽车市场竞争格局分析" />
          </label>
          <div class="form-row">
          <label class="field">写作风格
              <select v-model="style">
                <option v-for="s in styles" :key="s.name" :value="s.name">{{ s.name }}</option>
                <option v-if="!styles.length" value="专业深度">专业深度</option>
              </select>
            </label>
            <label class="field">AI 模型
              <select v-model="modelKey">
                <option v-for="m in models" :key="m.key" :value="m.key">{{ m.name }}</option>
              </select>
            </label>
            <label class="field">目标字数
              <input v-model.number="wordCount" type="number" min="200" max="5000" step="100" />
            </label>
          </div>
          <label class="field">发布平台（可选）
            <select v-model="platform">
              <option value="">不指定</option>
              <option v-for="p in platforms" :key="p.key" :value="p.label">{{ p.label }}</option>
            </select>
          </label>
          <p v-if="selectedPlatform?.rules" class="platform-rules">📌 平台规范：{{ selectedPlatform.rules }}</p>
          <label class="field">补充提示词
            <textarea v-model="extraPrompt" rows="2" placeholder="如：多用数据、突出行业影响..." />
          </label>
          <button class="btn primary generate-btn" @click="generate" :disabled="generating || !topic.trim()">
            {{ generating ? 'AI 创作中...' : '✨ 开始创作' }}
          </button>
          <p v-if="error" class="msg err">{{ error }}</p>
        </div>

        <div class="output-panel">
          <div v-if="generating" class="generating-box card">
            <div class="gen-bar"><div class="gen-fill"></div></div>
            <p class="gen-text">{{ streamText.slice(-60) || 'AI 正在撰写...' }}</p>
          </div>

          <div v-if="md" class="editor-wrap card">
            <div class="editor-head">
              <input v-model="title" class="title-input" placeholder="文章标题" />
              <div class="editor-actions">
                <button class="btn" @click="copyMd">📋 复制</button>
                <button class="btn" @click="exportPdf(title, md)">📄 导出 PDF</button>
                <button class="btn warn" @click="checkRisk" :disabled="riskChecking || riskRevising || !md.trim() || generating">{{ riskChecking ? '检查中...' : '🛡 风控检查' }}</button>
                <button class="btn primary" @click="save" :disabled="saving">{{ saving ? '保存中...' : '💾 保存' }}</button>
                <button class="btn accent" @click="showPublish = true">🚀 发布</button>
              </div>
            </div>
            <RichEditor v-model="md" @html-change="html = $event" />
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

          <div v-if="!md && !generating" class="empty-output card">
            <p>输入主题后点击「开始创作」，AI 生成的文章会自动以 Markdown 渲染到富文本编辑器</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showPublish" class="publish-overlay" @click.self="showPublish = false">
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
import { useRoute } from 'vue-router'
import { createPublishTasks, createStream, getPlatforms, getPublicConfig, riskCheck, riskReviseStream, saveArticle } from '../api'
import RichEditor from './RichEditor.vue'
import { copyRichHtml, exportPdf, splitTitle } from '../utils'
import { toast } from '../toast'

const styles = ref([])
const models = ref([])
const platforms = ref([])
const topic = ref('')
const style = ref('专业深度')
const wordCount = ref(800)
const platform = ref('')
const modelKey = ref('')
const extraPrompt = ref('')
const generating = ref(false)
const streamText = ref('')
const md = ref('')
const html = ref('')
const title = ref('')
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
const selectedPlatform = computed(() => platforms.value.find(p => p.label === platform.value) || null)
const route = useRoute()

function generate() {
  error.value = ''
  risk.value = null
  riskMsg.value = ''
  generating.value = true
  streamText.value = ''
  createStream(
    { topic: topic.value, style: style.value, word_count: wordCount.value, extra_prompt: extraPrompt.value, platform: platform.value, model: modelKey.value },
    (token) => { streamText.value += token },
    (content) => {
      const full = content || streamText.value
      const { title: aiTitle, body } = splitTitle(full)
      md.value = body
      title.value = aiTitle || topic.value
      html.value = ''
      generating.value = false
    },
    (err) => { error.value = err.message; generating.value = false },
  )
}

async function checkRisk() {
  riskChecking.value = true
  risk.value = null
  riskMsg.value = ''
  try {
    risk.value = await riskCheck({ title: title.value, content: md.value, platform: platform.value })
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
  if (!risk.value || !md.value.trim()) return
  riskRevising.value = true
  riskReviseText.value = ''
  riskMsg.value = ''
  riskReviseStream(
    {
      title: title.value,
      content: md.value,
      platform: platform.value,
      issues: risk.value.issues || [],
      suggestions: risk.value.suggestions || [],
    },
    (token) => { riskReviseText.value += token },
    (content) => {
      const full = content || riskReviseText.value
      const { title: aiTitle, body } = splitTitle(full)
      if (body.trim()) {
        md.value = body
        title.value = aiTitle || title.value
        html.value = ''
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

async function save() {
  saving.value = true
  savedMsg.value = ''
  try {
    await saveArticle({
      title: title.value,
      content_md: md.value,
      content_html: html.value,
      source_type: 'create',
      style: style.value,
      platform: platform.value,
    })
    savedMsg.value = '✅ 已保存到文章库'
  } catch (e) {
    savedMsg.value = `❌ ${e.message}`
  } finally {
    saving.value = false
  }
}

async function copyMd() {
  const ok = await copyRichHtml(title.value, md.value)
  savedMsg.value = ok ? '✅ 已复制带格式正文' : '复制失败，请手动选择正文复制'
  toast(ok ? '📋 已复制带格式正文' : '复制失败', ok ? 'success' : 'error')
}

async function doPublish() {
  publishError.value = ''
  try {
    await createPublishTasks({ title: title.value, content: md.value, platforms: publishPlatforms.value })
    showPublish.value = false
    savedMsg.value = '✅ 发布任务已创建'
    toast(`🎉 已创建 ${publishPlatforms.value.length} 个发布任务，可前往发布页一键跳转发布`, 'success', { label: '前往发布', to: '/publish' })
  } catch (e) {
    publishError.value = e.message
    toast(`❌ ${e.message || '发布失败'}`, 'error')
  }
}

onMounted(async () => {
  if (route.query.topic) topic.value = String(route.query.topic).slice(0, 200)
  try {
    const [tpls, cfg] = await Promise.all([getPlatforms(), getPublicConfig().catch(() => null)])
    platforms.value = tpls
    models.value = cfg?.ai_models || []
    if (cfg?.write_styles?.length) styles.value = cfg.write_styles
    if (models.value.length) modelKey.value = models.value[0].key
  } catch (e) {}
})
</script>

<style scoped>
.create-page { padding-bottom: 2rem; }
.create-layout { display: grid; grid-template-columns: 360px 1fr; gap: 20px; }
.input-panel { padding: 1.3rem; display: flex; flex-direction: column; gap: 12px; align-self: start; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); }
.form-row { display: flex; gap: 12px; flex-wrap: wrap; }
.form-row .field { flex: 1; min-width: 130px; }
.field input, .field select, .field textarea { width: 100%; min-width: 0; }
.platform-rules { font-size: 0.76rem; color: var(--accent-blue); background: rgba(100, 210, 255, 0.1); border: 1px solid rgba(100, 210, 255, 0.25); border-radius: 8px; padding: 7px 10px; }
.generate-btn { margin-top: 4px; }
.output-panel { display: flex; flex-direction: column; gap: 14px; }
.generating-box { padding: 1.2rem; }
.gen-bar { height: 4px; background: var(--glass-bg); border-radius: 2px; overflow: hidden; }
.gen-fill { height: 100%; width: 60%; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); animation: slide 1.2s infinite ease-in-out; }
@keyframes slide { 0% { margin-left: -60%; } 100% { margin-left: 100%; } }
.gen-text { margin-top: 8px; font-size: 0.76rem; color: var(--text-muted); font-family: var(--font-mono); }
.editor-wrap { padding: 1.2rem; }
.editor-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
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
.empty-output { padding: 3rem; text-align: center; color: var(--text-muted); font-size: 0.88rem; }
.publish-overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.6); display: flex; align-items: center; justify-content: center; }
.publish-modal { width: 480px; max-width: 92vw; padding: 1.4rem; }
.publish-modal h3 { margin-bottom: 0.8rem; font-family: var(--font-serif); }
.platform-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 0.8rem; }
.platform-option { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.8rem; cursor: pointer; }
.platform-option.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.platform-option input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 900px) {
  .create-layout { grid-template-columns: 1fr; }
}
</style>
