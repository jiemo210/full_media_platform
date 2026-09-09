<template>
  <div class="login-page">
    <div class="login-card">
      <span class="section-label">FULL MEDIA PLATFORM</span>
      <h1 class="login-title">全媒体聚合平台</h1>
      <p class="login-desc">热点挖掘 · AI 改写 · 一键发布</p>
      <form v-if="mode === 'login'" @submit.prevent="handleLogin">
        <input v-model="username" type="text" placeholder="用户名" class="login-input" autocomplete="username" />
        <input v-model="password" type="password" placeholder="密码" class="login-input" autocomplete="current-password" />
        <p v-if="error" class="login-error">{{ error }}</p>
        <button class="btn primary login-btn" :disabled="loading">{{ loading ? '登录中...' : '登 录' }}</button>
      </form>
      <form v-else @submit.prevent="handleChangePassword">
        <p class="change-tip">检测到您仍在使用初始密码，请先设置新密码（至少 8 位）：</p>
        <input v-model="newPassword" type="password" placeholder="新密码" class="login-input" autocomplete="new-password" />
        <input v-model="confirmPassword" type="password" placeholder="确认新密码" class="login-input" autocomplete="new-password" />
        <p v-if="error" class="login-error">{{ error }}</p>
        <button class="btn primary login-btn" :disabled="loading">{{ loading ? '提交中...' : '设置新密码' }}</button>
      </form>
      <p v-if="mode === 'login'" class="login-hint">初始管理员账号请及时修改默认密码</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { changePassword, login } from '../api'
import { setAuth } from '../store'
import { toast } from '../toast'

const router = useRouter()
const username = ref('')
const password = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)
const mode = ref('login')

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const res = await login({ username: username.value, password: password.value })
    setAuth(res.token, res.user)
    if (res.must_change_password) {
      mode.value = 'change'
      toast('请先修改初始密码', 'info')
    } else {
      router.push('/')
    }
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

async function handleChangePassword() {
  error.value = ''
  if (newPassword.value.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await changePassword({ old_password: password.value, new_password: newPassword.value })
    toast('✅ 密码已修改，请牢记新密码', 'success')
    router.push('/')
  } catch (e) {
    error.value = e.message || '修改失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.login-card { width: 380px; max-width: 90vw; background: var(--glass-deep); -webkit-backdrop-filter: blur(28px); backdrop-filter: blur(28px); border: 1px solid var(--glass-border); border-radius: 28px; box-shadow: var(--shadow-lg); padding: 2rem; }
.login-title { font-family: var(--font-serif); font-size: 1.5rem; margin: 0.5rem 0 0.2rem; }
.login-desc { color: var(--text-muted); font-size: 0.82rem; margin-bottom: 1.4rem; }
.login-input { width: 100%; margin-bottom: 0.8rem; }
.login-btn { width: 100%; margin-top: 0.4rem; }
.login-error { color: #FF9B94; font-size: 0.8rem; margin-bottom: 0.6rem; }
.change-tip { font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.8rem; line-height: 1.5; }
.login-hint { margin-top: 1.2rem; text-align: center; font-size: 0.74rem; color: var(--text-muted); }
</style>
