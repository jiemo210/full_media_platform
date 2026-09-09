<template>
  <div class="admin-platforms">
    <div class="head">
      <h2 class="page-title">发布平台管理</h2>
      <button class="btn primary" @click="openCreate">+ 新增平台</button>
    </div>
    <p class="desc">配置平台规范性要求与发布跳转链接，AI 创作 / AI 改写的发布平台下拉取自这里</p>
    <table class="tbl card">
      <thead><tr><th>排序</th><th>Key</th><th>名称</th><th>字数范围</th><th>规范性要求</th><th>风控要求</th><th>跳转链接</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="p in platforms" :key="p.key">
          <td>{{ p.sort }}</td>
          <td class="mono">{{ p.key }}</td>
          <td>{{ p.label }}</td>
          <td>{{ p.min_words }}-{{ p.max_words }}</td>
          <td class="rules-cell">{{ p.rules }}</td>
          <td class="rules-cell">{{ p.risk_rules || '-' }}</td>
          <td class="mono muted">{{ p.jump_url || '-' }}</td>
          <td><span class="badge" :class="p.enabled ? 'badge-green' : ''">{{ p.enabled ? '启用' : '停用' }}</span></td>
          <td class="actions">
            <button class="btn" @click="openEdit(p)">编辑</button>
            <button class="btn del" @click="remove(p)">删除</button>
          </td>
        </tr>
        <tr v-if="!platforms.length"><td colspan="9" class="empty-cell">暂无平台</td></tr>
      </tbody>
    </table>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>

    <div v-if="form.show" class="overlay" @click.self="form.show = false">
      <div class="modal card">
        <h3>{{ form.originalKey ? '编辑平台' : '新增平台' }}</h3>
        <div class="grid2">
          <label class="field">Key<input v-model="form.key" placeholder="如 toutiao" /></label>
          <label class="field">名称<input v-model="form.label" placeholder="如 今日头条" /></label>
          <label class="field">最小字数<input v-model.number="form.min_words" type="number" /></label>
          <label class="field">最大字数<input v-model.number="form.max_words" type="number" /></label>
        </div>
        <label class="field">规范性要求 / 约束
          <textarea v-model="form.rules" rows="2" placeholder="如：标题吸引、段落短、避免营销词汇" />
        </label>
        <label class="field">平台风控要求（AI 风控检查时重点核查，如“需 AI 内容标识”“禁医疗/金融违规宣传”）
          <textarea v-model="form.risk_rules" rows="2" placeholder="留空则复用规范性要求" />
        </label>
        <label class="field">发布跳转链接
          <input v-model="form.jump_url" placeholder="https://..." />
        </label>
        <label class="field">排序（数字越小越靠前）<input v-model.number="form.sort" type="number" /></label>
        <div class="check-row">
          <label><input type="checkbox" v-model="form.enabled" /> 启用</label>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="form.show = false">取消</button>
          <button class="btn primary" @click="save" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminCreatePlatform, adminDeletePlatform, adminGetPlatforms, adminUpdatePlatform } from '../api'

const platforms = ref([])
const msg = ref('')
const saving = ref(false)
const form = ref({ show: false, originalKey: '', key: '', label: '', min_words: 0, max_words: 0, rules: '', risk_rules: '', jump_url: '', sort: 1, enabled: true })

async function load() {
  try {
    platforms.value = (await adminGetPlatforms()).platforms.sort((a, b) => (a.sort || 0) - (b.sort || 0))
  } catch (e) { msg.value = `❌ ${e.message}` }
}
function openCreate() {
  form.value = { show: true, originalKey: '', key: '', label: '', min_words: 100, max_words: 500, rules: '', risk_rules: '', jump_url: '', sort: platforms.value.length + 1, enabled: true }
}
function openEdit(p) {
  form.value = { show: true, originalKey: p.key, key: p.key, label: p.label, min_words: p.min_words, max_words: p.max_words, rules: p.rules || '', risk_rules: p.risk_rules || '', jump_url: p.jump_url || '', sort: p.sort || 1, enabled: p.enabled }
}
async function save() {
  saving.value = true
  msg.value = ''
  const payload = { key: form.value.key, label: form.value.label, min_words: form.value.min_words, max_words: form.value.max_words, rules: form.value.rules, risk_rules: form.value.risk_rules, jump_url: form.value.jump_url, sort: form.value.sort, enabled: form.value.enabled }
  try {
    if (form.value.originalKey) await adminUpdatePlatform(form.value.originalKey, payload)
    else await adminCreatePlatform(payload)
    form.value.show = false
    msg.value = '✅ 已保存'
    load()
  } catch (e) { msg.value = `❌ ${e.message}` } finally { saving.value = false }
}
async function remove(p) {
  if (!confirm(`确认删除平台「${p.label}」？`)) return
  try { await adminDeletePlatform(p.key); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}
onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; }
.desc { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 12px; text-align: left; font-size: 0.8rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.7rem; color: var(--text-muted); }
.mono { font-family: var(--font-mono); font-size: 0.76rem; }
.muted { color: var(--text-muted); }
.rules-cell { max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
.overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.65); display: flex; align-items: center; justify-content: center; }
.modal { width: 520px; max-width: 94vw; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.field textarea { resize: vertical; }
.check-row { font-size: 0.82rem; margin-bottom: 8px; }
.check-row label { display: flex; align-items: center; gap: 6px; }
.check-row input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
