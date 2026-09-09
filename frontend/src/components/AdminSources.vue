<template>
  <div class="sources-page">
    <div class="container">
      <span class="section-label">SOURCE MANAGEMENT</span>
      <h1 class="page-title">新闻源管理</h1>
      <p class="page-desc">启用/停用新闻源，一键探测可用性，移除失效源（已剔除微博/知乎/36氪/澎湃/抖音/浙江等失效源）</p>

      <div class="source-actions">
        <button class="btn accent" @click="checkHealth" :disabled="checking">{{ checking ? '探测中...' : '🔍 健康探测' }}</button>
        <button class="btn primary" @click="save" :disabled="saving">💾 保存配置</button>
        <span v-if="msg" class="msg">{{ msg }}</span>
      </div>

      <table class="source-table card">
        <thead>
          <tr><th>来源</th><th>名称</th><th>状态</th><th>健康</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="(cfg, key) in sources" :key="key">
            <td class="mono">{{ key }}</td>
            <td><input v-model="cfg.name" class="name-input" /></td>
            <td>
              <label class="switch">
                <input type="checkbox" v-model="cfg.enabled" />
                <span>{{ cfg.enabled ? '启用' : '停用' }}</span>
              </label>
            </td>
            <td>
              <span v-if="health[key]" class="health" :class="{ ok: health[key].ok, fail: !health[key].ok }">
                {{ health[key].ok ? `可用（${health[key].count} 条）` : '不可用' }}
              </span>
              <span v-else class="muted">未探测</span>
            </td>
            <td><button class="btn del" @click="remove(key)">移除</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { checkSourcesHealth, getSources, saveSources } from '../api'

const sources = ref({})
const health = ref({})
const checking = ref(false)
const saving = ref(false)
const msg = ref('')

async function load() {
  try { sources.value = (await getSources()).sources } catch (e) { msg.value = e.message }
}

async function checkHealth() {
  checking.value = true
  msg.value = ''
  try { health.value = (await checkSourcesHealth()).health } catch (e) { msg.value = e.message } finally { checking.value = false }
}

async function save() {
  saving.value = true
  try { await saveSources(sources.value); msg.value = '✅ 源配置已保存' } catch (e) { msg.value = e.message } finally { saving.value = false }
}

function remove(key) {
  if (!confirm(`确认移除新闻源「${sources.value[key].name}」（${key}）？`)) return
  delete sources.value[key]
  delete health.value[key]
}

onMounted(load)
</script>

<style scoped>
.sources-page { padding-bottom: 2rem; }
.source-actions { display: flex; align-items: center; gap: 12px; margin-bottom: 1rem; }
.source-table { width: 100%; border-collapse: collapse; overflow: hidden; }
.source-table th, .source-table td { padding: 12px 16px; text-align: left; font-size: 0.84rem; border-bottom: 1px solid var(--glass-bg); }
.source-table th { background: var(--glass-bg); font-size: 0.72rem; color: var(--text-muted); }
.mono { font-family: var(--font-mono); font-size: 0.8rem; }
.name-input { padding: 5px 10px; font-size: 0.82rem; width: 160px; }
.switch { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.8rem; }
.switch input { accent-color: var(--accent-blue); }
.health { font-size: 0.74rem; padding: 2px 10px; border-radius: 999px; }
.health.ok { background: rgba(48, 209, 88, 0.16); color: var(--accent-green); }
.health.fail { background: rgba(255, 69, 58, 0.16); color: #FF9B94; }
.muted { color: var(--text-muted); font-size: 0.76rem; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
</style>
