<template>
  <div class="admin-styles">
    <div class="head">
      <h2 class="page-title">写作风格管理</h2>
      <button class="btn primary" @click="openCreate">+ 新增风格</button>
    </div>
    <p class="desc">写作风格 / 改写风格统一以此处维护数据为准（AI 创作与 AI 改写均读取）</p>
    <table class="tbl card">
      <thead><tr><th>#</th><th>风格名称</th><th>风格说明</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="(s, i) in styles" :key="s.name">
          <td>{{ i + 1 }}</td>
          <td class="name">{{ s.name }}</td>
          <td class="desc-cell">{{ s.description }}</td>
          <td class="actions">
            <button class="btn" @click="openEdit(s)">编辑</button>
            <button class="btn del" @click="remove(s)">删除</button>
          </td>
        </tr>
        <tr v-if="!styles.length"><td colspan="4" class="empty-cell">暂无风格</td></tr>
      </tbody>
    </table>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>

    <div v-if="form.show" class="overlay" @click.self="form.show = false">
      <div class="modal card">
        <h3>{{ form.originalName ? '编辑风格' : '新增风格' }}</h3>
        <label class="field">风格名称<input v-model="form.name" placeholder="如 深度解读" /></label>
        <label class="field">风格说明
          <textarea v-model="form.description" rows="3" placeholder="描述该风格的写作特点" />
        </label>
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
import { adminCreateStyle, adminDeleteStyle, adminGetStyles, adminUpdateStyles } from '../api'

const styles = ref([])
const msg = ref('')
const saving = ref(false)
const form = ref({ show: false, originalName: '', name: '', description: '' })

async function load() {
  try { styles.value = (await adminGetStyles()).styles } catch (e) { msg.value = `❌ ${e.message}` }
}
function openCreate() {
  form.value = { show: true, originalName: '', name: '', description: '' }
}
function openEdit(s) {
  form.value = { show: true, originalName: s.name, name: s.name, description: s.description || '' }
}
async function save() {
  saving.value = true
  msg.value = ''
  try {
    if (form.value.originalName) {
      const list = styles.value.map(s => s.name === form.value.originalName ? { name: form.value.name, description: form.value.description } : s)
      await adminUpdateStyles(list)
    } else {
      await adminCreateStyle({ name: form.value.name, description: form.value.description })
    }
    form.value.show = false
    msg.value = '✅ 已保存'
    load()
  } catch (e) { msg.value = `❌ ${e.message}` } finally { saving.value = false }
}
async function remove(s) {
  if (!confirm(`确认删除风格「${s.name}」？`)) return
  try { await adminDeleteStyle(s.name); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}
onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; }
.desc { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.name { font-weight: 600; }
.desc-cell { color: var(--text-muted); font-size: 0.78rem; }
.actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-cell { text-align: center; color: var(--text-muted); padding: 2rem; }
.overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.65); display: flex; align-items: center; justify-content: center; }
.modal { width: 440px; max-width: 92vw; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.field textarea { resize: vertical; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
