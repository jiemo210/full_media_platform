<template>
  <div class="admin-logs">
    <div class="head">
      <h2 class="page-title">日志查看</h2>
      <button class="btn" @click="load">🔄 刷新</button>
    </div>
    <pre class="log-box card">{{ logs || '暂无日志' }}</pre>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminGetLogs } from '../api'

const logs = ref('')
async function load() {
  try { logs.value = (await adminGetLogs(500)).logs } catch (e) { logs.value = e.message }
}
onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.log-box { padding: 14px; font-family: var(--font-mono); font-size: 0.72rem; line-height: 1.6; max-height: 70vh; overflow-y: auto; white-space: pre-wrap; color: var(--text-secondary); }
</style>
