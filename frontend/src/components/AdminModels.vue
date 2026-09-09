<template>
  <div class="admin-models">
    <div class="head">
      <h2 class="page-title">AI 模型配置</h2>
      <button class="btn primary" @click="openCreate">+ 新增模型</button>
    </div>
    <table class="tbl card">
      <thead><tr><th>Key</th><th>名称</th><th>模型 ID</th><th>接口地址</th><th>API Key</th><th>状态</th><th>默认</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="m in models" :key="m.key">
          <td class="mono">{{ m.key }}</td>
          <td>{{ m.name }}</td>
          <td class="mono">{{ m.model }}</td>
          <td class="mono muted">{{ m.base_url || '(默认)' }}</td>
          <td class="mono muted">{{ m.api_key || '—' }}</td>
          <td><span class="badge" :class="m.enabled ? 'badge-green' : ''">{{ m.enabled ? '启用' : '停用' }}</span></td>
          <td>{{ m.is_default ? '★' : '' }}</td>
          <td class="actions">
            <button class="btn" @click="openEdit(m)">编辑</button>
            <button class="btn del" @click="remove(m)">删除</button>
          </td>
        </tr>
        <tr v-if="!models.length"><td colspan="8" class="empty-cell">暂无模型</td></tr>
      </tbody>
    </table>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>

    <div v-if="form.show" class="overlay" @click.self="form.show = false">
      <div class="modal card">
        <h3>{{ form.originalKey ? '编辑模型' : '新增模型' }}</h3>
        <label class="field">Key<input v-model="form.key" placeholder="如 deepseek-chat" /></label>
        <label class="field">名称<input v-model="form.name" placeholder="如 DeepSeek Chat" /></label>
        <label class="field">模型 ID<input v-model="form.model" placeholder="如 deepseek-chat" /></label>
        <label class="field">接口地址（留空用默认）
          <input v-model="form.base_url" placeholder="https://api.deepseek.com" />
        </label>
        <label class="field">API Key（留空用全局 FMP_AI_API_KEY）
          <input v-model="form.api_key" type="password" :placeholder="form.keyConfigured ? '已配置（留空保持不变）' : '留空用全局 FMP_AI_API_KEY'" />
        </label>
        <div class="check-row">
          <label><input type="checkbox" v-model="form.enabled" /> 启用</label>
          <label><input type="checkbox" v-model="form.is_default" /> 设为默认</label>
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
import { adminCreateModel, adminDeleteModel, adminGetModels, adminUpdateModel } from '../api'

const models = ref([])
const msg = ref('')
const saving = ref(false)
const form = ref({ show: false, originalKey: '', keyConfigured: false, key: '', name: '', model: '', base_url: '', api_key: '', enabled: true, is_default: false })

async function load() {
  try { models.value = (await adminGetModels()).models } catch (e) { msg.value = `❌ ${e.message}` }
}
function openCreate() {
  form.value = { show: true, originalKey: '', keyConfigured: false, key: '', name: '', model: '', base_url: '', api_key: '', enabled: true, is_default: false }
}
function openEdit(m) {
  form.value = { show: true, originalKey: m.key, keyConfigured: !!m.api_key, key: m.key, name: m.name, model: m.model, base_url: m.base_url || '', api_key: '', enabled: m.enabled, is_default: m.is_default }
}
async function save() {
  saving.value = true
  msg.value = ''
  const payload = { key: form.value.key, name: form.value.name, model: form.value.model, base_url: form.value.base_url, api_key: form.value.api_key, enabled: form.value.enabled, is_default: form.value.is_default }
  try {
    if (form.value.originalKey) await adminUpdateModel(form.value.originalKey, payload)
    else await adminCreateModel(payload)
    form.value.show = false
    msg.value = '✅ 已保存'
    load()
  } catch (e) { msg.value = `❌ ${e.message}` } finally { saving.value = false }
}
async function remove(m) {
  if (!confirm(`确认删除模型 ${m.key}？`)) return
  try { await adminDeleteModel(m.key); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}
onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.mono { font-family: var(--font-mono); font-size: 0.78rem; }
.muted { color: var(--text-muted); }
.actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
.overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.65); display: flex; align-items: center; justify-content: center; }
.modal { width: 460px; max-width: 92vw; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.check-row { display: flex; gap: 20px; font-size: 0.82rem; margin-bottom: 8px; }
.check-row label { display: flex; align-items: center; gap: 6px; }
.check-row input { accent-color: var(--accent-blue); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
