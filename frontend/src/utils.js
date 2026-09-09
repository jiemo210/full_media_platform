/**
 * 全媒体聚合平台 - 通用工具
 */

/**
 * URL 协议白名单：链接仅允许 http/https/mailto；图片允许 http/https、本地 /media/ 与 base64。
 * 用于阻止 javascript: 等伪协议注入。
 */
export function safeUrl(url, kind = 'link') {
  const u = (url || '').trim()
  const low = u.toLowerCase()
  if (kind === 'image') {
    if (low.startsWith('http://') || low.startsWith('https://') || low.startsWith('/media/') || low.startsWith('data:image/')) {
      return u
    }
    return ''
  }
  if (low.startsWith('http://') || low.startsWith('https://') || low.startsWith('mailto:')) {
    return u
  }
  return ''
}

/**
 * 从 AI 生成的 Markdown 中拆分标题与正文。
 * 首个一级标题（# ）作为标题，正文不再重复包含标题。
 */
export function splitTitle(md) {
  const text = (md || '').replace(/^\uFEFF/, '')
  const lines = text.split('\n')
  if (lines.length && /^#\s+/.test(lines[0])) {
    return { title: lines[0].replace(/^#\s+/, '').trim(), body: lines.slice(1).join('\n').trim() }
  }
  return { title: '', body: text.trim() }
}

/** Markdown → 纯文本（富文本预览内容的可粘贴版本） */
export function mdToPlainText(md) {
  if (!md) return ''
  return md
    .replace(/```[\s\S]*?```/g, (m) => m.replace(/```/g, '').trim())
    .split(/\r?\n/)
    .map((line) => line
      .replace(/^#{1,6}\s+/, '')
      .replace(/^>\s?/, '')
      .replace(/^[-*]\s+/, '• ')
      .replace(/^\d+[.、)]\s+/, '')
      .replace(/!\[(.*?)\]\(.*?\)/g, '$1')
      .replace(/\[(.*?)\]\(.*?\)/g, '$1')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/`([^`]+)`/g, '$1'))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function mdToHtml(md) {
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
  let html = ''
  let inList = false
  const closeList = () => { if (inList) { html += '</ul>'; inList = false } }
  for (const raw of (md || '').split(/\r?\n/)) {
    if (!raw.trim()) { closeList(); continue }
    const h = raw.match(/^(#{1,6})\s+(.+)$/)
    if (h) { closeList(); html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue }
    if (/^>\s?/.test(raw)) { closeList(); html += `<blockquote>${inline(raw.replace(/^>\s?/, ''))}</blockquote>`; continue }
    if (/^[-*]\s+/.test(raw)) { if (!inList) { html += '<ul>'; inList = true } html += `<li>${inline(raw.replace(/^[-*]\s+/, ''))}</li>`; continue }
    closeList()
    html += `<p>${inline(raw)}</p>`
  }
  closeList()
  return html
}

/** 导出 PDF：打开打印窗口，用户选择“另存为 PDF” */
export function exportPdf(title, md) {
  const body = mdToHtml(md)
  const w = window.open('', '_blank', 'width=860,height=1100')
  if (!w) return
  w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title || '文章'}</title>
    <style>
      body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; max-width: 760px; margin: 32px auto; padding: 0 24px; color: #222; line-height: 1.8; }
      h1 { font-size: 26px; border-bottom: 2px solid #333; padding-bottom: 10px; }
      h2 { font-size: 20px; margin-top: 28px; } h3 { font-size: 17px; }
      blockquote { border-left: 3px solid #999; padding-left: 12px; color: #555; margin: 12px 0; }
      pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }
      code { background: #f5f5f5; padding: 1px 5px; border-radius: 4px; }
      p { margin: 10px 0; } ul { padding-left: 24px; }
      @media print { body { margin: 0; } }
    </style></head><body><h1>${title || ''}</h1>${body}</body></html>`)
  w.document.close()
  w.focus()
  setTimeout(() => { w.print(); }, 300)
}

/** 富文本复制：复制带格式的 HTML（含纯文本降级），优先 ClipboardItem */
export async function copyRichHtml(title, md) {
  const html = `<h1 style="font-size:1.6em;margin:0 0 0.5em;">${(title || '').replace(/</g, '&lt;')}</h1>` + mdToHtml(md)
  const plain = `${title || ''}\n\n${mdToPlainText(md)}`.trim()
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([plain], { type: 'text/plain' }),
        }),
      ])
      return true
    }
  } catch (e) {}
  try {
    const div = document.createElement('div')
    div.contentEditable = 'true'
    div.innerHTML = html
    div.style.position = 'fixed'
    div.style.left = '-9999px'
    document.body.appendChild(div)
    const range = document.createRange()
    range.selectNodeContents(div)
    const sel = window.getSelection()
    sel.removeAllRanges()
    sel.addRange(range)
    const ok = document.execCommand('copy')
    sel.removeAllRanges()
    div.remove()
    return ok
  } catch (e) {
    return false
  }
}
