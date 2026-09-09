<template>
  <div class="novel-create">
    <div class="container">
      <span class="section-label">NOVEL CREATION</span>
      <h1 class="page-title">短篇小说创作</h1>
      <p class="page-desc">题材/设定/大纲三步引导，可引入小说库大纲总结作为参考；1-5 万字短篇</p>

      <div class="steps">
        <span v-for="(s, i) in stepNames" :key="i" class="step" :class="{ active: step === i + 1, done: step > i + 1 }">
          {{ i + 1 }}. {{ s }}
        </span>
      </div>

      <!-- 第1步：基本信息 -->
      <div v-if="step === 1" class="panel card">
        <label class="field">作品标题 *<input v-model="form.title" placeholder="如：雾城迷踪" /></label>
        <div class="grid2">
          <label class="field">题材
            <select v-model="form.genre">
              <option v-for="g in genres" :key="g" :value="g">{{ g }}</option>
            </select>
          </label>
          <label class="field">目标篇幅
            <select v-model="form.length_target">
              <option :value="10000">约 1 万字</option>
              <option :value="30000">约 3 万字</option>
              <option :value="50000">约 5 万字</option>
            </select>
          </label>
        </div>
        <label class="field">写作风格<input v-model="form.style" placeholder="如：悬疑紧凑 / 温暖治愈" /></label>
        <label class="field">参考作品（从小说库选择，注入其大纲总结）
          <select v-model="form.reference_ids" multiple>
            <option v-for="n in library" :key="n.id" :value="n.id">{{ n.title }}（{{ n.genre }}）</option>
          </select>
        </label>
        <p v-if="preRefs.length" class="ref-tip">🎯 已从「以此为参考创作」带入：{{ preRefs.map(r => r.title).join('、') }}</p>
        <div class="panel-actions">
          <button class="btn primary" @click="createProject" :disabled="creating || !form.title.trim()">
            {{ creating ? '创建中...' : '下一步：创建并生成设定' }}
          </button>
        </div>
      </div>

      <!-- 第2步：设定 -->
      <div v-if="step === 2 && project" class="panel card">
        <div class="panel-head">
          <h3>设定生成（梗概 / 世界观 / 角色）</h3>
          <button class="btn" @click="genSettings" :disabled="genSettingsLoading">{{ genSettingsLoading ? '生成中...' : '🔄 重新生成' }}</button>
        </div>
        <label class="field">故事梗概
          <textarea v-model="settings.synopsis" rows="3" />
        </label>
        <label class="field">世界观设定
          <textarea v-model="settings.world_setting" rows="3" />
        </label>
        <label class="field">角色卡（JSON 数组）
          <textarea v-model="settings.charactersText" rows="5" />
        </label>
        <p v-if="genMsg" class="msg">{{ genMsg }}</p>
        <div class="panel-actions">
          <button class="btn" @click="step = 1">上一步</button>
          <button class="btn primary" @click="saveSettings">保存设定，下一步：生成大纲</button>
        </div>
      </div>

      <!-- 第3步：大纲 -->
      <div v-if="step === 3 && project" class="panel card">
        <div class="panel-head">
          <h3>分章大纲</h3>
          <button class="btn" @click="genOutline" :disabled="genOutlineLoading">{{ genOutlineLoading ? '生成中...' : '🔄 重新生成' }}</button>
        </div>
        <div v-if="outline.length" class="outline-list">
          <div v-for="o in outline" :key="o.chapter" class="outline-item">
            <strong>第{{ o.chapter }}章 {{ o.title }}</strong>
            <p>{{ (o.points || []).join(' / ') }}</p>
          </div>
        </div>
        <p v-else class="muted">{{ genOutlineLoading ? 'AI 正在生成大纲...' : '点击“生成大纲”开始' }}</p>
        <div class="panel-actions">
          <button class="btn" @click="step = 2">上一步</button>
          <button class="btn primary" @click="goEditor">🚀 进入编辑器开始写作</button>
        </div>
      </div>
      <p v-if="error" class="msg err">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { novelAPI } from '../api'
import { toast } from '../toast'

const route = useRoute()
const router = useRouter()
const genres = ['玄幻', '都市', '悬疑', '言情', '科幻', '历史', '武侠', '奇幻', '现实', '其他']
const stepNames = ['基本信息', '设定生成', '分章大纲']
const step = ref(1)
const form = ref({ title: '', genre: '悬疑', length_target: 30000, style: '悬疑紧凑', reference_ids: [] })
const project = ref(null)
const settings = ref({ synopsis: '', world_setting: '', charactersText: '[]' })
const outline = ref([])
const library = ref([])
const preRefs = ref([])
const creating = ref(false)
const genSettingsLoading = ref(false)
const genOutlineLoading = ref(false)
const genMsg = ref('')
const error = ref('')

async function loadLibrary() {
  try {
    const res = await novelAPI.getNovels({ page_size: 100, library: true })
    library.value = res.items
    const refs = (route.query.refs || '').toString().split(',').map(Number).filter(Boolean)
    if (refs.length) {
      form.value.reference_ids = refs
      preRefs.value = library.value.filter(n => refs.includes(n.id))
    }
  } catch (e) {}
}

async function createProject() {
  creating.value = true
  error.value = ''
  try {
    project.value = await novelAPI.createNovel({
      title: form.value.title.trim(),
      genre: form.value.genre,
      length_target: form.value.length_target,
      style: form.value.style,
      reference_ids: form.value.reference_ids,
    })
    step.value = 2
    await genSettings()
  } catch (e) { error.value = e.message } finally { creating.value = false }
}

async function genSettings() {
  if (!project.value) return
  genSettingsLoading.value = true
  genMsg.value = ''
  error.value = ''
  try {
    const res = await novelAPI.generateSettings(project.value.id)
    settings.value = {
      synopsis: res.settings.synopsis || '',
      world_setting: res.settings.world_setting || '',
      charactersText: JSON.stringify(res.settings.characters || [], null, 2),
    }
  } catch (e) { error.value = e.message } finally { genSettingsLoading.value = false }
}

async function saveSettings() {
  error.value = ''
  let characters = []
  try { characters = JSON.parse(settings.value.charactersText || '[]') } catch (e) { error.value = '角色卡 JSON 格式错误'; return }
  try {
    await novelAPI.updateNovel(project.value.id, {
      synopsis: settings.value.synopsis,
      world_setting: settings.value.world_setting,
      characters,
    })
    step.value = 3
    await genOutline()
  } catch (e) { error.value = e.message }
}

async function genOutline() {
  if (!project.value) return
  genOutlineLoading.value = true
  error.value = ''
  try {
    const count = form.value.length_target <= 10000 ? 12 : form.value.length_target <= 20000 ? 20 : form.value.length_target <= 35000 ? 30 : 45
    const res = await novelAPI.generateOutline(project.value.id, count)
    outline.value = res.outline || []
    toast(`✅ 大纲已生成（${outline.value.length} 章）`, 'success')
  } catch (e) { error.value = e.message } finally { genOutlineLoading.value = false }
}

function goEditor() {
  router.push(`/novels/${project.value.id}`)
}

onMounted(loadLibrary)
</script>

<style scoped>
.novel-create { padding-bottom: 2rem; }
.steps { display: flex; gap: 10px; margin: 1rem 0; flex-wrap: wrap; }
.step { padding: 6px 14px; border-radius: 999px; border: 1px solid var(--glass-border); font-size: 0.8rem; color: var(--text-muted); }
.step.active { border-color: var(--accent-blue); color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.step.done { border-color: var(--accent-green); color: var(--accent-green); }
.panel { padding: 1.3rem; max-width: 760px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 12px; }
.field textarea { resize: vertical; font-family: var(--font-mono); font-size: 0.8rem; }
.field select[multiple] { min-height: 90px; }
.ref-tip { font-size: 0.8rem; color: var(--accent-blue); margin-bottom: 12px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.panel-head h3 { font-family: var(--font-serif); }
.panel-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 1rem; }
.outline-list { display: flex; flex-direction: column; gap: 10px; max-height: 420px; overflow-y: auto; }
.outline-item { background: var(--glass-bg-soft); border: 1px solid var(--glass-border); border-radius: 10px; padding: 10px 12px; }
.outline-item p { font-size: 0.78rem; color: var(--text-secondary); margin-top: 4px; }
.muted { color: var(--text-muted); }
</style>
