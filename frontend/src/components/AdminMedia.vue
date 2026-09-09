<template>
  <div class="admin-media">
    <div class="head">
      <h2 class="page-title">素材库</h2>
      <div class="actions">
        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="upload" />
        <button class="btn primary" @click="$refs.fileInput.click()" :disabled="uploading">{{ uploading ? '上传中...' : '⬆ 上传图片' }}</button>
      </div>
    </div>
    <p class="desc">图片上传后存入本地素材目录（MEDIA_DIR），富文本编辑器插图自动走此通道；共 {{ total }} 个素材</p>
    <div class="asset-grid">
      <div v-for="a in assets" :key="a.id" class="asset-card card">
        <img :src="a.url" class="asset-img" loading="lazy" @error="$event.target.style.display='none'" />
        <div class="asset-info">
          <p class="asset-name">{{ a.original_name || a.url.split('/').pop() }}</p>
          <p class="asset-meta">{{ (a.size / 1024).toFixed(1) }} KB · {{ a.created_at ? formatTime(a.created_at) : '' }}</p>
          <div class="asset-actions">
            <button class="btn" @click="copyUrl(a)">复制链接</button>
            <button class="btn del" @click="remove(a)">删除</button>
          </div>
        </div>
      </div>
    </div>
    <p v-if="!assets.length && loaded" class="empty-tip">素材库为空，点击右上角上传图片</p>
    <Pager :page="page" :total="total" :page-size="pageSize" @change="load" />
    <p v-if="msg" class="msg" :class="{ err: msg.startsWith('❌') }">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { deleteMediaAsset, getMediaAssets, uploadImage } from '../api'
import Pager from './Pager.vue'

const assets = ref([])
const page = ref(1)
const pageSize = 30
const total = ref(0)
const loaded = ref(false)
const uploading = ref(false)
const msg = ref('')
const formatTime = (v) => new Date(v).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

async function load(p = 1) {
  page.value = p
  try {
    const res = await getMediaAssets({ page: page.value, page_size: pageSize })
    assets.value = res.items
    total.value = res.total
    loaded.value = true
  } catch (e) { msg.value = `❌ ${e.message}` }
}

async function upload(e) {
  const file = e.target.files[0]
  if (!file) return
  uploading.value = true
  msg.value = ''
  try {
    const a = await uploadImage(file)
    msg.value = `✅ 已上传：${a.url}`
    load()
  } catch (err) { msg.value = `❌ ${err.message}` } finally { uploading.value = false; e.target.value = '' }
}

async function copyUrl(a) {
  try {
    await navigator.clipboard.writeText(location.origin + a.url)
    msg.value = '✅ 已复制链接'
  } catch (err) {
    const ta = document.createElement('textarea')
    ta.value = location.origin + a.url
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
    msg.value = '✅ 已复制链接'
  }
}

async function remove(a) {
  if (!confirm(`确认删除素材「${a.original_name || a.id}」？`)) return
  try { await deleteMediaAsset(a.id); msg.value = '✅ 已删除'; load() } catch (e) { msg.value = `❌ ${e.message}` }
}

onMounted(load)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; }
.desc { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem; }
.asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.asset-card { overflow: hidden; }
.asset-img { width: 100%; height: 130px; object-fit: cover; display: block; background: var(--glass-bg); }
.asset-info { padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.asset-name { font-size: 0.78rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-meta { font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.asset-actions { display: flex; gap: 8px; }
.btn.del { border-color: rgba(255, 69, 58, 0.4); color: #FF9B94; padding: 5px 12px; }
.empty-tip { text-align: center; color: var(--text-muted); padding: 3rem 0; }
</style>
