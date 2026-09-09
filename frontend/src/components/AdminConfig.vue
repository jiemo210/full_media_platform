<template>
  <div class="admin-config">
    <h2 class="page-title">页面与系统配置</h2>
    <p class="desc">修改后点击保存立即生效</p>
    <div class="config-card card" v-if="config">
      <label class="field">新闻列表每页数量
        <input v-model.number="config.NEWS_PAGE_SIZE" type="number" min="5" max="100" />
      </label>
      <label class="field">自动抓取间隔（秒）
        <input v-model.number="config.CRAWL_INTERVAL" type="number" min="60" />
      </label>
      <label class="field">启动自动抓取
        <input type="checkbox" v-model="config.AUTO_CRAWL" class="check" />
      </label>
      <label class="field">默认 AI 模型
        <select v-model="config.AI_MODEL">
          <option v-for="m in models" :key="m.key" :value="m.key">{{ m.name }}</option>
        </select>
      </label>
      <label class="field">素材存储目录（MEDIA_DIR，修改后需重启后端）
        <input v-model="config.MEDIA_DIR" placeholder="./media" />
      </label>
      <label class="field">AI 限流（每用户每小时调用次数）
        <input v-model.number="config.AI_RATE_LIMIT" type="number" min="1" />
      </label>
      <label class="field">AI 限流窗口（小时）
        <input v-model.number="config.AI_RATE_WINDOW" type="number" min="1" />
      </label>
      <label class="field">发布频率限制（每用户每小时任务数）
        <input v-model.number="config.PUBLISH_RATE_LIMIT" type="number" min="1" />
      </label>
      <label class="field">发布任务总数上限
        <input v-model.number="config.PUBLISH_TASK_LIMIT" type="number" min="1" />
      </label>
      <label class="field">AI 风控检查开关
        <input type="checkbox" v-model="config.RISK_CHECK_ENABLED" class="check" />
      </label>
      <label class="field">风控检查补充要求（会追加到风控提示词，如“需标注 AI 生成内容”）
        <textarea v-model="config.RISK_CHECK_EXTRA" rows="2" placeholder="如：需标注 AI 生成内容；涉未成年人内容需谨慎" />
      </label>
      <button class="btn primary" @click="save" :disabled="saving">{{ saving ? '保存中...' : '💾 保存配置' }}</button>
    </div>
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminGetConfig, adminGetModels, adminUpdateConfig } from '../api'

const config = ref(null)
const models = ref([])
const saving = ref(false)
const msg = ref('')

async function load() {
  try {
    config.value = (await adminGetConfig()).config
    models.value = (await adminGetModels()).models
  } catch (e) { msg.value = `❌ ${e.message}` }
}
async function save() {
  saving.value = true
  msg.value = ''
  try {
    await adminUpdateConfig({ ...config.value })
    msg.value = '✅ 配置已保存并生效'
  } catch (e) { msg.value = `❌ ${e.message}` } finally { saving.value = false }
}
onMounted(load)
</script>

<style scoped>
.desc { font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1rem; }
.config-card { padding: 1.3rem; max-width: 520px; display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 0.8rem; color: var(--text-secondary); }
.check { width: 20px; height: 20px; accent-color: var(--accent-blue); }
</style>
