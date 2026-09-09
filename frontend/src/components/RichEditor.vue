<template>
  <div class="rich-editor">
    <div class="editor-toolbar">
      <button class="tb-btn" title="标题2" @click="format('h2')">H2</button>
      <button class="tb-btn" title="标题3" @click="format('h3')">H3</button>
      <span class="tb-sep"></span>
      <button class="tb-btn" title="加粗" @click="format('bold')"><b>B</b></button>
      <button class="tb-btn" title="斜体" @click="format('italic')"><i>I</i></button>
      <span class="tb-sep"></span>
      <button class="tb-btn" title="无序列表" @click="format('ul')">• 列表</button>
      <button class="tb-btn" title="引用" @click="format('blockquote')">❝ 引用</button>
      <button class="tb-btn" title="代码块" @click="format('code')">&lt;/&gt;</button>
      <button class="tb-btn" title="链接" @click="format('link')">🔗</button>
      <button class="tb-btn" title="插入图片" @click="format('image')">🖼</button>
      <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onImageFile" />
      <span class="tb-sep"></span>
      <button class="tb-btn mode" :class="{ active: viewMode === 'edit' }" @click="viewMode = 'edit'">编辑</button>
      <button class="tb-btn mode" :class="{ active: viewMode === 'preview' }" @click="viewMode = 'preview'">预览</button>
      <span class="tb-hint">Markdown 自动渲染</span>
    </div>

    <div v-show="viewMode === 'edit'" class="editor-area">
      <div ref="editable" class="editable" contenteditable="true" @input="onInput" @blur="onInput" @paste="onPaste"></div>
    </div>
    <div v-show="viewMode === 'preview'" class="preview-area" v-html="previewHtml"></div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { uploadImage } from '../api'
import { safeUrl } from '../utils'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'html-change'])

const editable = ref(null)
const fileInput = ref(null)
const viewMode = ref('edit')
const previewHtml = ref('')
let lastHtml = ''

function mdToHtml(md) {
  if (!md) return ''
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const attr = (s) => esc(s).replace(/"/g, '&quot;')
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/!\[([^\]]*)\]\(([^)]*)\)/g, (m, alt, src) => {
      const s = safeUrl(src, 'image')
      return s
        ? `<img src="${attr(s)}" alt="${attr(alt)}" style="max-width:100%;border-radius:8px;margin:8px 0;" />`
        : m
    })
    .replace(/\[([^\]]*)\]\(([^)]*)\)/g, (m, label, href) => {
      const h = safeUrl(href)
      return h
        ? `<a href="${attr(h)}" target="_blank" rel="noopener">${label}</a>`
        : m
    })
  const lines = md.split(/\r?\n/)
  let html = ''
  let inList = false
  let inCode = false
  let codeBuf = []
  const closeList = () => { if (inList) { html += '</ul>'; inList = false } }
  for (const raw of lines) {
    const line = raw
    if (line.trim().startsWith('```')) {
      if (inCode) { html += '<pre><code>' + codeBuf.join('\n') + '</code></pre>'; codeBuf = []; inCode = false }
      else { closeList(); inCode = true }
      continue
    }
    if (inCode) { codeBuf.push(esc(line)); continue }
    if (!line.trim()) { closeList(); continue }
    const h = line.match(/^(#{1,6})\s+(.+)$/)
    if (h) { closeList(); html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue }
    if (/^>\s?/.test(line)) { closeList(); html += `<blockquote>${inline(line.replace(/^>\s?/, ''))}</blockquote>`; continue }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) { html += '<ul>'; inList = true }
      html += `<li>${inline(line.replace(/^[-*]\s+/, ''))}</li>`
      continue
    }
    closeList()
    html += `<p>${inline(line)}</p>`
  }
  closeList()
  if (inCode) html += '<pre><code>' + codeBuf.join('\n') + '</code></pre>'
  return html
}

function sanitizeHtml(html) {
  const div = document.createElement('div')
  div.innerHTML = html || ''
  div.querySelectorAll('script, style, iframe, object, embed, link, meta, form, video, audio, source').forEach((el) => el.remove())
  div.querySelectorAll('*').forEach((el) => {
    ;[...el.attributes].forEach((attrItem) => {
      const n = attrItem.name.toLowerCase()
      if (n.startsWith('on')) {
        el.removeAttribute(attrItem.name)
      } else if (n === 'href' || n === 'src' || n === 'xlink:href') {
        const v = attrItem.value.trim().toLowerCase()
        const ok = n === 'src'
          ? v.startsWith('http://') || v.startsWith('https://') || v.startsWith('/media/') || v.startsWith('data:image/') || v.startsWith('//')
          : v.startsWith('http://') || v.startsWith('https://') || v.startsWith('mailto:') || v.startsWith('//')
        if (!ok) el.removeAttribute(attrItem.name)
      }
    })
  })
  return div
}

function htmlToMd(html) {
  const div = sanitizeHtml(html)
  const walk = (node, out) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        out.push(child.textContent)
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        const tag = child.tagName.toLowerCase()
        if (tag === 'h1') { out.push('#'); walk(child, out); out.push('', '') }
        else if (tag === 'h2') { out.push('##'); walk(child, out); out.push('', '') }
        else if (tag === 'h3') { out.push('###'); walk(child, out); out.push('', '') }
        else if (tag === 'h4') { out.push('####'); walk(child, out); out.push('', '') }
        else if (tag === 'p') { walk(child, out); out.push('') }
        else if (tag === 'strong' || tag === 'b') { out.push('**'); walk(child, out); out.push('**') }
        else if (tag === 'em' || tag === 'i') { out.push('*'); walk(child, out); out.push('*') }
        else if (tag === 'code') { out.push('`'); walk(child, out); out.push('`') }
        else if (tag === 'a') { out.push('['); walk(child, out); out.push(`](${child.getAttribute('href') || ''})`) }
        else if (tag === 'img') out.push(`![${child.getAttribute('alt') || ''}](${child.getAttribute('src') || ''})`)
        else if (tag === 'ul') { out.push(''); child.querySelectorAll(':scope > li').forEach((li) => out.push(`- ${li.textContent}`)); out.push('') }
        else if (tag === 'ol') { let i = 1; child.querySelectorAll(':scope > li').forEach((li) => out.push(`${i++}. ${li.textContent}`)); out.push('') }
        else if (tag === 'blockquote') { const t = []; walk(child, t); out.push(`> ${t.join('').trim()}`, '') }
        else if (tag === 'pre') { out.push('```', child.textContent.trim(), '```', '') }
        else if (tag === 'br') out.push('')
        else walk(child, out)
      }
    })
  }
  const out = []
  walk(div, out)
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

function onInput() {
  const html = editable.value.innerHTML
  if (html === lastHtml) return
  lastHtml = html
  const md = htmlToMd(html)
  emit('update:modelValue', md)
  emit('html-change', html)
}

function format(cmd) {
  editable.value?.focus()
  if (cmd === 'h2' || cmd === 'h3' || cmd === 'blockquote') {
    document.execCommand('formatBlock', false, cmd === 'blockquote' ? 'blockquote' : cmd)
  } else if (cmd === 'code') {
    document.execCommand('formatBlock', false, 'pre')
  } else if (cmd === 'link') {
    const url = prompt('输入链接地址：', 'https://')
    if (url) document.execCommand('createLink', false, url)
  } else if (cmd === 'image') {
    fileInput.value?.click()
  } else {
    document.execCommand(cmd)
  }
  onInput()
}

function onImageFile(e) {
  const file = e.target.files[0]
  if (!file) return
  insertImageFile(file)
  e.target.value = ''
}

async function insertImageFile(file) {
  try {
    // 优先上传到素材库，引用 URL（避免 base64 膨胀数据库）
    const asset = await uploadImage(file)
    editable.value?.focus()
    document.execCommand('insertImage', false, asset.url)
    onInput()
    return
  } catch (e) {
    // 上传失败降级：base64 内嵌（保留可用性）
  }
  const reader = new FileReader()
  reader.onload = () => {
    editable.value?.focus()
    document.execCommand('insertImage', false, reader.result)
    onInput()
  }
  reader.readAsDataURL(file)
}

function onPaste(e) {
  const files = e.clipboardData?.files
  if (!files || !files.length) return
  const file = files[0]
  if (!file.type.startsWith('image/')) return
  e.preventDefault()
  insertImageFile(file)
}

function render() {
  if (!editable.value) return
  const md = props.modelValue || ''
  const html = mdToHtml(md)
  if (editable.value.innerHTML !== html) {
    editable.value.innerHTML = html
    lastHtml = html
  }
  previewHtml.value = html
}

watch(() => props.modelValue, render)
onMounted(render)
</script>

<style scoped>
.rich-editor { border: 1px solid var(--glass-border); border-radius: var(--radius-md); overflow: hidden; background: var(--glass-bg-soft); }
.editor-toolbar { display: flex; align-items: center; gap: 4px; padding: 8px 10px; border-bottom: 1px solid var(--glass-border); background: var(--glass-bg); flex-wrap: wrap; }
.tb-btn { padding: 5px 10px; border: 1px solid transparent; border-radius: 8px; background: none; color: var(--text-secondary); cursor: pointer; font-size: 0.8rem; }
.tb-btn:hover { background: var(--glass-bg-strong); color: var(--text-primary); }
.tb-btn.mode.active { background: rgba(100, 210, 255, 0.16); color: var(--accent-blue); }
.tb-sep { width: 1px; height: 18px; background: var(--glass-border); margin: 0 4px; }
.tb-hint { margin-left: auto; font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono); }
.editor-area { min-height: 320px; max-height: 520px; overflow-y: auto; padding: 14px 16px; }
.editable { outline: none; min-height: 300px; font-size: 0.92rem; line-height: 1.85; }
.editable :deep(h2), .editable :deep(h3) { margin: 0.8em 0 0.4em; font-family: var(--font-serif); }
.editable :deep(blockquote) { border-left: 3px solid var(--accent-blue); padding-left: 12px; color: var(--text-muted); margin: 8px 0; }
.editable :deep(pre) { background: rgba(5, 8, 18, 0.6); border-radius: 8px; padding: 10px; font-family: var(--font-mono); font-size: 0.78rem; overflow-x: auto; margin: 8px 0; }
.editable :deep(code) { background: rgba(5, 8, 18, 0.5); padding: 1px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.82em; }
.preview-area { min-height: 320px; max-height: 520px; overflow-y: auto; padding: 14px 16px; font-size: 0.92rem; line-height: 1.85; }
.preview-area :deep(h2), .preview-area :deep(h3) { margin: 0.8em 0 0.4em; font-family: var(--font-serif); }
.preview-area :deep(blockquote) { border-left: 3px solid var(--accent-blue); padding-left: 12px; color: var(--text-muted); margin: 8px 0; }
.preview-area :deep(pre) { background: rgba(5, 8, 18, 0.6); border-radius: 8px; padding: 10px; font-family: var(--font-mono); font-size: 0.78rem; overflow-x: auto; margin: 8px 0; }
.preview-area :deep(code) { background: rgba(5, 8, 18, 0.5); padding: 1px 6px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.82em; }
</style>
