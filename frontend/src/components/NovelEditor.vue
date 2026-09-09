<template>
  <div class="novel-editor" v-if="project">
    <aside class="sidebar">
      <div class="sidebar-head">
        <button class="back" @click="$router.push('/novels')">← 返回</button>
        <h2 class="title">{{ project.title }}</h2>
        <span class="genre badge badge-blue">{{ project.genre }}</span>
      </div>
      <div class="chapter-list">
        <div
          v-for="c in sortedChapters"
          :key="c.id"
          class="chapter-item"
          :class="{ active: current?.id === c.id, done: c.status !== 'draft' }"
          @click="selectChapter(c)"
        >
          <span class="num">{{ String(c.chapter_number).padStart(2, '0') }}</span>
          <span class="c-title">{{ c.title }}</span>
          <span class="wc">{{ formatWords(c.word_count) }}</span>
        </div>
        <p v-if="!sortedChapters.length" class="muted">暂无章节，先生成大纲或新增章节</p>
      </div>
      <div class="sidebar-actions">
        <button class="btn primary" @click="generateAll" :disabled="allGenerating || !sortedChapters.length">
          {{ allGenerating ? `生成中 ${allProgress}/${allTotal}...` : '✨ 一键生成全部章节' }}
        </button>
        <button v-if="allGenerating" class="btn del" @click="stopAll">■ 停止</button>
        <button class="btn" @click="genOutline" :disabled="outlineLoading">{{ outlineLoading ? '生成中...' : '🤖 生成大纲' }}</button>
        <button class="btn" @click="addChapter">+ 新增章节</button>
        <button class="btn" @click="openInfo">⚙️ 项目信息</button>
      </div>
    </aside>

    <main class="main">
      <div v-if="allGenerating" class="all-gen card">
        <div class="gen-bar"><div class="gen-fill"></div></div>
        <p class="gen-text">正在生成 第 {{ allCurrentChapter }} 章《{{ allCurrentTitle }}》（{{ allProgress }}/{{ allTotal }}）</p>
        <p v-if="allText" class="gen-text mono">{{ allText.slice(-80) }}</p>
      </div>
      <div v-if="current" class="editor-wrap">
        <div class="editor-head">
          <input v-model="currentTitle" class="title-input" placeholder="章节标题" />
          <div class="actions">
            <button class="btn" @click="saveChapter" :disabled="saving">{{ saving ? '保存中...' : '💾 保存' }}</button>
            <button class="btn primary" @click="generateContent" :disabled="generating || allGenerating">
              {{ generating ? '生成中...' : current.content ? '🔄 重新生成正文' : '✨ 生成正文' }}
            </button>
          </div>
        </div>
        <div v-if="generating" class="gen-bar"><div class="gen-fill"></div></div>
        <RichEditor v-model="chapterMd" @html-change="chapterHtml = $event" />
        <p v-if="editorMsg" class="msg" :class="{ err: editorMsg.startsWith('❌') }">{{ editorMsg }}</p>
      </div>
      <div v-else class="empty card">
        <h3>选择左侧章节开始编辑</h3>
        <p>点击「生成大纲」或「新增章节」开始创作</p>
      </div>
    </main>

    <!-- 项目信息 -->
    <div v-if="showInfo" class="overlay" @click.self="showInfo = false">
      <div class="modal card info-modal">
        <div class="modal-head"><h3>项目信息</h3><button class="close" @click="showInfo = false">×</button></div>
        <label class="field">标题<input v-model="info.title" /></label>
        <div class="grid2">
          <label class="field">题材
            <select v-model="info.genre"><option v-for="g in genres" :key="g" :value="g">{{ g }}</option></select>
          </label>
          <label class="field">写作风格<input v-model="info.style" /></label>
        </div>
        <label class="field">目标篇幅
          <select v-model="info.length_target">
            <option :value="10000">约 1 万字</option>
            <option :value="30000">约 3 万字</option>
            <option :value="50000">约 5 万字</option>
          </select>
        </label>
        <label class="field">故事梗概<textarea v-model="info.synopsis" rows="3" /></label>
        <label class="check"><input type="checkbox" v-model="info.in_library" /> 加入本地小说库</label>
        <p v-if="infoMsg" class="msg" :class="{ err: infoMsg.startsWith('❌') }">{{ infoMsg }}</p>
        <div class="modal-actions">
          <button class="btn" @click="showInfo = false">关闭</button>
          <button class="btn" @click="genSummary" :disabled="summarizing">{{ summarizing ? '总结中...' : '✨ 生成大纲总结' }}</button>
          <button class="btn primary" @click="saveInfo">💾 保存</button>
          <button class="btn accent" @click="showPublish = true">🚀 发布</button>
        </div>
      </div>
    </div>

    <!-- 发布 -->
    <div v-if="showPublish" class="overlay" @click.self="showPublish = false">
      <div class="modal card">
        <h3>发布小说《{{ project.title }}》</h3>
        <div class="platform-grid">
          <label v-for="p in platforms" :key="p.key" class="platform-option" :class="{ on: pubPlatforms.includes(p.label) }">
            <input type="checkbox" :value="p.label" v-model="pubPlatforms" />
            <span>{{ p.label }}</span>
          </label>
        </div>
        <p v-if="pubMsg" class="msg" :class="{ err: pubMsg.startsWith('❌') }">{{ pubMsg }}</p>
        <div class="modal-actions">
          <button class="btn" @click="showPublish = false">取消</button>
          <button class="btn primary" @click="doPublish" :disabled="!pubPlatforms.length">创建发布任务</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { generateAllStream, generateChapterStream, getPlatforms, novelAPI } from '../api'
import { toast } from '../toast'
import RichEditor from './RichEditor.vue'

const route = useRoute()
const genres = ['玄幻', '都市', '悬疑', '言情', '科幻', '历史', '武侠', '奇幻', '现实', '其他']
const project = ref(null)
const current = ref(null)
const currentTitle = ref('')
const chapterMd = ref('')
const chapterHtml = ref('')
const saving = ref(false)
const generating = ref(false)
const allGenerating = ref(false)
const allProgress = ref(0)
const allTotal = ref(0)
const allCurrentChapter = ref(0)
const allCurrentTitle = ref('')
const allText = ref('')
const allController = ref(null)
const outlineLoading = ref(false)
const editorMsg = ref('')
const showInfo = ref(false)
const info = ref({ title: '', genre: '', style: '', length_target: 30000, synopsis: '', in_library: false })
const infoMsg = ref('')
const summarizing = ref(false)
const platforms = ref([])
const showPublish = ref(false)
const pubPlatforms = ref([])
const pubMsg = ref('')

const sortedChapters = computed(() => [...(project.value?.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number))
const formatWords = (w) => w ? `${Math.round(w / 100) / 10}万` : ''

async function load() {
  try {
    project.value = await novelAPI.getNovel(route.params.id)
    const chs = sortedChapters.value
    if (chs.length && !current.value) selectChapter(chs[0])
  } catch (e) { toast(`❌ ${e.message}`, 'error') }
}

function selectChapter(c) {
  current.value = c
  currentTitle.value = c.title
  chapterMd.value = c.content
  chapterHtml.value = ''
  editorMsg.value = ''
}

async function saveChapter() {
  if (!current.value) return
  saving.value = true
  editorMsg.value = ''
  try {
    await novelAPI.updateChapter(route.params.id, current.value.id, {
      title: currentTitle.value,
      content: chapterMd.value,
      status: 'edited',
    })
    editorMsg.value = '✅ 已保存'
    toast('💾 章节已保存', 'success')
    load()
  } catch (e) { editorMsg.value = `❌ ${e.message}` } finally { saving.value = false }
}

async function generateContent() {
  if (!current.value) return
  generating.value = true
  editorMsg.value = ''
  chapterMd.value = ''
  generateChapterStream(
    route.params.id, current.value.id, { model: '', regenerate: !!current.value.content },
    (token) => { chapterMd.value += token },
    (data) => {
      editorMsg.value = `✅ 生成完成（${data.word_count} 字）`
      toast(`✅ 第${current.value.chapter_number}章生成完成`, 'success')
      generating.value = false
      load()
    },
    (err) => {
      editorMsg.value = `❌ ${err.message}`
      toast(`❌ ${err.message}`, 'error')
      generating.value = false
    },
  )
}

function generateAll() {
  if (!sortedChapters.value.length || allGenerating.value) return
  allGenerating.value = true
  allProgress.value = 0
  allTotal.value = sortedChapters.value.length
  allCurrentChapter.value = 0
  allCurrentTitle.value = ''
  allText.value = ''
  editorMsg.value = ''
  allController.value = generateAllStream(
    route.params.id,
    { model: '' },
    (ev) => {
      if (ev.type === 'chapter_start') {
        allProgress.value = ev.index
        allCurrentChapter.value = ev.chapter
        allCurrentTitle.value = ev.title
        allText.value = ''
        const target = sortedChapters.value.find(c => c.chapter_number === ev.chapter)
        if (target) selectChapter(target)
      } else if (ev.type === 'token') {
        allText.value += ev.content
        chapterMd.value += ev.content
      } else if (ev.type === 'chapter_done') {
        editorMsg.value = `✅ 第${ev.chapter}章生成完成（${ev.word_count} 字）`
      } else if (ev.type === 'chapter_skip') {
        editorMsg.value = `⏭ 第${ev.chapter}章已有正文，跳过`
      } else if (ev.type === 'done') {
        allGenerating.value = false
        allController.value = null
        editorMsg.value = `✅ 全部生成完成（本次生成 ${ev.generated} 章，共 ${ev.total_word_count} 字）`
        toast('🎉 全部章节生成完成', 'success')
        load()
      }
    },
    (err) => {
      allGenerating.value = false
      allController.value = null
      editorMsg.value = `❌ ${err.message}`
      toast(`❌ ${err.message}`, 'error')
      load()
    },
  )
}

function stopAll() {
  try { allController.value?.abort() } catch (e) {}
  allGenerating.value = false
  allController.value = null
  editorMsg.value = '已停止生成（已完成章节已保存）'
}

async function addChapter() {
  try {
    await novelAPI.addChapter(route.params.id)
    toast('📄 已新增章节', 'success')
    load()
  } catch (e) { toast(`❌ ${e.message}`, 'error') }
}

async function genOutline() {
  outlineLoading.value = true
  try {
    await novelAPI.generateOutline(route.params.id)
    toast('✅ 大纲已生成', 'success')
    load()
  } catch (e) { toast(`❌ ${e.message}`, 'error') } finally { outlineLoading.value = false }
}

function openInfo() {
  info.value = {
    title: project.value.title, genre: project.value.genre, style: project.value.style,
    length_target: project.value.length_target, synopsis: project.value.synopsis || '',
    in_library: project.value.in_library,
  }
  infoMsg.value = ''
  showInfo.value = true
}

async function saveInfo() {
  try {
    await novelAPI.updateNovel(route.params.id, info.value)
    infoMsg.value = '✅ 已保存'
    toast('💾 项目信息已保存', 'success')
    load()
  } catch (e) { infoMsg.value = `❌ ${e.message}` }
}

async function genSummary() {
  summarizing.value = true
  infoMsg.value = ''
  try {
    const res = await novelAPI.generateSummary(route.params.id)
    infoMsg.value = `✅ 大纲总结已生成（题材：${res.summary.genre}，人物 ${res.summary.characters?.length || 0} 位）`
    toast('✨ AI 大纲总结已生成', 'success')
  } catch (e) { infoMsg.value = `❌ ${e.message}` } finally { summarizing.value = false }
}

async function doPublish() {
  pubMsg.value = ''
  try {
    const res = await novelAPI.publishNovel(route.params.id, pubPlatforms.value)
    pubMsg.value = res.message
    toast(`🎉 ${res.message}`, 'success', { label: '前往发布', to: '/publish' })
    showPublish.value = false
  } catch (e) { pubMsg.value = `❌ ${e.message}` }
}

onMounted(async () => {
  load()
  try { platforms.value = await getPlatforms() } catch (e) {}
})
</script>

<style scoped>
.novel-editor { display: flex; min-height: calc(100vh - 66px); }
.sidebar { width: 250px; border-right: 1px solid var(--glass-border); background: var(--glass-deep); display: flex; flex-direction: column; position: sticky; top: 66px; height: calc(100vh - 66px); }
.sidebar-head { padding: 12px; border-bottom: 1px solid var(--glass-bg); display: flex; align-items: center; gap: 8px; }
.back { background: none; border: 1px solid var(--glass-border); color: var(--text-secondary); border-radius: 8px; padding: 4px 8px; cursor: pointer; font-size: 0.76rem; }
.title { flex: 1; font-size: 0.95rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chapter-list { flex: 1; overflow-y: auto; padding: 6px; }
.chapter-item { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border-radius: 10px; cursor: pointer; font-size: 0.82rem; }
.chapter-item:hover { background: var(--glass-bg); }
.chapter-item.active { background: rgba(100, 210, 255, 0.14); }
.chapter-item.done .c-title { color: var(--accent-green); }
.num { font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted); }
.c-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wc { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.sidebar-actions { padding: 10px; display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--glass-bg); }
.main { flex: 1; padding: 1.2rem; }
.editor-wrap { max-width: 900px; }
.all-gen { padding: 1rem; margin-bottom: 14px; }
.all-gen .gen-text { margin-top: 6px; font-size: 0.76rem; color: var(--text-muted); font-family: var(--font-mono); }
.all-gen .mono { font-family: var(--font-mono); font-size: 0.72rem; }
.editor-head { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.title-input { flex: 1; font-size: 1rem; font-weight: 600; }
.gen-bar { height: 4px; background: var(--glass-bg); border-radius: 2px; overflow: hidden; margin-bottom: 10px; }
.gen-fill { height: 100%; width: 60%; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); animation: slide 1.2s infinite ease-in-out; }
@keyframes slide { 0% { margin-left: -60%; } 100% { margin-left: 100%; } }
.empty { padding: 3rem; text-align: center; color: var(--text-muted); }
.overlay { position: fixed; inset: 0; z-index: 1300; background: rgba(5, 8, 18, 0.68); display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal { width: 520px; max-width: 94vw; max-height: 90vh; overflow-y: auto; padding: 1.3rem; }
.info-modal { width: 620px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; }
.close { background: none; border: none; color: var(--text-muted); font-size: 1.4rem; cursor: pointer; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.field textarea { resize: vertical; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 0.82rem; margin-bottom: 10px; }
.check input { accent-color: var(--accent-blue); }
.platform-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }
.platform-option { display: flex; align-items: center; gap: 8px; padding: 9px 10px; border: 1px solid var(--glass-border); border-radius: 10px; font-size: 0.8rem; cursor: pointer; }
.platform-option.on { border-color: var(--accent-blue); background: rgba(100, 210, 255, 0.12); }
.platform-option input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 0.8rem; flex-wrap: wrap; }
.msg { margin-top: 0.6rem; }
</style>
