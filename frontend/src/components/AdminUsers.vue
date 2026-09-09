<template>
  <div class="admin-users">
    <div class="head">
      <h2 class="page-title">用户管理</h2>
      <button class="btn primary" @click="openCreate">+ 新增用户</button>
    </div>
    <table class="tbl card">
      <thead><tr><th>ID</th><th>用户名</th><th>昵称</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>{{ u.id }}</td>
          <td>{{ u.username }}</td>
          <td>{{ u.nickname || '-' }}</td>
          <td><span class="badge" :class="roleClass(u.role)">{{ u.role }}</span></td>
          <td>{{ u.is_active ? '启用' : '禁用' }}</td>
          <td class="actions">
            <button class="btn" @click="openEdit(u)">编辑</button>
            <button class="btn" @click="resetPw(u)">重置密码</button>
            <button class="btn del" v-if="u.username !== 'admin'" @click="remove(u)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>

    <div v-if="form.show" class="overlay" @click.self="form.show = false">
      <div class="modal card">
        <h3>{{ form.id ? '编辑用户' : '新增用户' }}</h3>
        <label class="field">用户名<input v-model="form.username" :disabled="!!form.id" /></label>
        <label class="field">昵称<input v-model="form.nickname" /></label>
        <label class="field">角色
          <select v-model="form.role"><option value="admin">admin</option><option value="editor">editor</option><option value="viewer">viewer</option></select>
        </label>
        <label class="field">密码<input v-model="form.password" type="password" :placeholder="form.id ? '留空则不修改' : '设置密码'" /></label>
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
import { adminCreateUser, adminDeleteUser, adminGetUsers, adminUpdateUser } from '../api'

const users = ref([])
const msg = ref('')
const saving = ref(false)
const form = ref({ show: false, id: null, username: '', nickname: '', role: 'viewer', password: '' })

const roleClass = (r) => ({ admin: 'badge-blue', editor: 'badge-purple', viewer: 'badge-green' }[r] || '')

async function load() {
  try { users.value = (await adminGetUsers()).users } catch (e) { msg.value = `❌ ${e.message}` }
}

function openCreate() {
  form.value = { show: true, id: null, username: '', nickname: '', role: 'viewer', password: '' }
}
function openEdit(u) {
  form.value = { show: true, id: u.id, username: u.username, nickname: u.nickname || '', role: u.role, password: '' }
}
async function save() {
  saving.value = true
  msg.value = ''
  try {
    if (form.value.id) {
      await adminUpdateUser(form.value.id, { nickname: form.value.nickname, role: form.value.role, password: form.value.password || undefined })
    } else {
      if (!form.value.username || !form.value.password) { msg.value = '❌ 用户名和密码必填'; return }
      await adminCreateUser({ username: form.value.username, nickname: form.value.nickname, role: form.value.role, password: form.value.password })
    }
    form.value.show = false
    msg.value = '✅ 已保存'
    load()
  } catch (e) { msg.value = `❌ ${e.message}` } finally { saving.value = false }
}
async function resetPw(u) {
  const pw = prompt(`为 ${u.username} 设置新密码：`)
  if (!pw) return
  try { await adminUpdateUser(u.id, { password: pw }); msg.value = '✅ 密码已重置' } catch (e) { msg.value = `❌ ${e.message}` }
}
async function remove(u) {
  if (!confirm(`确认删除用户 ${u.username}？`)) return
  try { await adminDeleteUser(u.id); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.tbl { width: 100%; border-collapse: collapse; overflow: hidden; }
.tbl th, .tbl td { padding: 10px 14px; text-align: left; font-size: 0.82rem; border-bottom: 1px solid var(--glass-bg); }
.tbl th { font-size: 0.72rem; color: var(--text-muted); }
.actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.overlay { position: fixed; inset: 0; z-index: 1200; background: rgba(5, 8, 18, 0.65); display: flex; align-items: center; justify-content: center; }
.modal { width: 420px; max-width: 92vw; padding: 1.3rem; }
.modal h3 { margin-bottom: 0.8rem; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.78rem; color: var(--text-muted); margin-bottom: 10px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
