const BASE_URL = '/api'

async function request(url, options = {}) {
  const token = localStorage.getItem('fmp_token') || ''
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE_URL}${url}`, { headers, ...options })
  // 登录接口的 401 = 用户名或密码错误，交下面的 err.detail 显示真实原因；
  // 其他接口的 401 才视为会话过期。
  if (res.status === 401 && !url.includes('/auth/login')) {
    localStorage.removeItem('fmp_token')
    localStorage.removeItem('fmp_user')
    if (!location.pathname.startsWith('/login')) location.href = '/login'
    throw new Error('未登录或登录已过期')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `API Error: ${res.status}`)
  }
  return res.json()
}

// 认证
export const login = (data) => request('/auth/login', { method: 'POST', body: JSON.stringify(data) })
export const changePassword = (data) => request('/auth/change-password', { method: 'POST', body: JSON.stringify(data) })

// 热点新闻
export const getPublicConfig = () => request('/config')
export const getNews = (params = {}) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return request(`/news?${new URLSearchParams(clean)}`)
}
export const getTopNews = (limit = 10) => request(`/news/top?limit=${limit}`)
export const getNewsDetail = (id) => request(`/news/${id}`)
export const crawlNews = () => request('/news/crawl', { method: 'POST' })
export const getCrawlStatus = () => request('/news/crawl/status')

const STREAM_IDLE_TIMEOUT = 120000 // 120s 无数据视为超时

async function _readStream(res, handler, controller, onError) {
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let finished = false
  let lastData = Date.now()
  const idleTimer = setInterval(() => {
    if (finished) { clearInterval(idleTimer); return }
    if (Date.now() - lastData > STREAM_IDLE_TIMEOUT) {
      clearInterval(idleTimer)
      try { controller?.abort() } catch (e) {}
      onError?.(new Error('生成超时：长时间未收到内容，请重试'))
    }
  }, 5000)
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      lastData = Date.now()
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const parsed = JSON.parse(line.slice(6).trim())
          if (parsed.type === 'done' || parsed.type === 'error') finished = true
          handler?.(parsed)
        } catch (e) {}
      }
    }
    clearInterval(idleTimer)
    // 流正常关闭但没有收到 done 事件 = 服务端中断
    if (!finished) onError?.(new Error('生成中断：连接提前关闭，请重试'))
  } catch (err) {
    clearInterval(idleTimer)
    if (err.name !== 'AbortError') onError?.(err)
  }
}

function _postStream(url, data, handler, onError) {
  const controller = new AbortController()
  const token = localStorage.getItem('fmp_token') || ''
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  fetch(`${BASE_URL}${url}`, {
    method: 'POST', headers, body: JSON.stringify(data), signal: controller.signal,
  }).then(async (res) => {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      onError?.(new Error(err.detail || `API Error: ${res.status}`))
      return
    }
    await _readStream(res, handler, controller, onError)
  }).catch((err) => { if (err.name !== 'AbortError') onError?.(err) })
  return controller
}

// AI 文章流式
export function rewriteStream(newsId, data, onToken, onDone, onError) {
  return _postStream(`/articles/rewrite/stream?news_id=${newsId}`, data, (ev) => {
    if (ev.type === 'token') onToken?.(ev.content)
    else if (ev.type === 'done') onDone?.(ev.content)
    else if (ev.type === 'error') onError?.(new Error(ev.message))
  }, onError)
}

export function createStream(data, onToken, onDone, onError) {
  return _postStream('/articles/create/stream', data, (ev) => {
    if (ev.type === 'token') onToken?.(ev.content)
    else if (ev.type === 'done') onDone?.(ev.content)
    else if (ev.type === 'error') onError?.(new Error(ev.message))
  }, onError)
}

export const rewriteSave = (newsId, data) => request(`/articles/rewrite?news_id=${newsId}`, { method: 'POST', body: JSON.stringify(data) })
export const createSave = (data) => request('/articles/create', { method: 'POST', body: JSON.stringify(data) })
export const saveArticle = (data) => request('/articles/save', { method: 'POST', body: JSON.stringify(data) })
export const getArticles = (params = {}) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return request(`/articles?${new URLSearchParams(clean)}`)
}
export const getArticle = (id) => request(`/articles/${id}`)
export const updateArticle = (id, data) => request(`/articles/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteArticle = (id) => request(`/articles/${id}`, { method: 'DELETE' })
export const getWriteStyles = () => request('/articles/styles')
export const getRewriteSuggestions = (newsId, data = {}) => request(`/articles/suggestions?news_id=${newsId}`, { method: 'POST', body: JSON.stringify(data) })
export const riskCheck = (data) => request('/articles/risk-check', { method: 'POST', body: JSON.stringify(data) })

// 按风控建议修改文章（SSE 流式）
export function riskReviseStream(data, onToken, onDone, onError) {
  return _postStream('/articles/risk-revise', data, (ev) => {
    if (ev.type === 'token') onToken?.(ev.content)
    else if (ev.type === 'done') onDone?.(ev.content)
    else if (ev.type === 'error') onError?.(new Error(ev.message))
  }, onError)
}

// 资料搜索
export const searchMaterials = (query, days = 0) => request('/search/materials', { method: 'POST', body: JSON.stringify({ query, days }) })

// 发布
export const getPlatforms = () => request('/publish/platforms')
export const createPublishTasks = (data) => request('/publish/tasks', { method: 'POST', body: JSON.stringify(data) })
export const getPublishTasks = (params = {}) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return request(`/publish/tasks?${new URLSearchParams(clean)}`)
}
export const publishTask = (id) => request(`/publish/tasks/${id}/publish`, { method: 'POST' })
export const confirmPublishTask = (id) => request(`/publish/tasks/${id}/confirm`, { method: 'POST' })
export const updatePublishTask = (id, data) => request(`/publish/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deletePublishTask = (id) => request(`/publish/tasks/${id}`, { method: 'DELETE' })

// 后台
export const getStats = () => request('/admin/stats')
export const getSources = () => request('/admin/sources')
export const saveSources = (sources) => request('/admin/sources', { method: 'PUT', body: JSON.stringify({ sources }) })
export const checkSourcesHealth = () => request('/admin/sources/health', { method: 'POST' })

// 后台管理
export const adminGetUsers = () => request('/admin/users')
export const adminCreateUser = (data) => request('/admin/users', { method: 'POST', body: JSON.stringify(data) })
export const adminUpdateUser = (id, data) => request(`/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const adminDeleteUser = (id) => request(`/admin/users/${id}`, { method: 'DELETE' })
export const adminGetNews = (params = {}) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return request(`/admin/news?${new URLSearchParams(clean)}`)
}
export const adminDeleteNews = (id) => request(`/admin/news/${id}`, { method: 'DELETE' })
export const adminGetLogs = (lines = 200) => request(`/admin/logs?lines=${lines}`)
export const adminGetModels = () => request('/admin/models')
export const adminCreateModel = (data) => request('/admin/models', { method: 'POST', body: JSON.stringify(data) })
export const adminUpdateModel = (key, data) => request(`/admin/models/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify(data) })
export const adminDeleteModel = (key) => request(`/admin/models/${encodeURIComponent(key)}`, { method: 'DELETE' })
export const adminGetStyles = () => request('/admin/styles')
export const adminCreateStyle = (data) => request('/admin/styles', { method: 'POST', body: JSON.stringify(data) })
export const adminUpdateStyles = (styles) => request('/admin/styles', { method: 'PUT', body: JSON.stringify({ styles }) })
export const adminDeleteStyle = (name) => request(`/admin/styles/${encodeURIComponent(name)}`, { method: 'DELETE' })
export const adminGetConfig = () => request('/admin/config')
export const adminUpdateConfig = (updates) => request('/admin/config', { method: 'PUT', body: JSON.stringify({ updates }) })

// 素材库
export const uploadImage = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('type', 'image')
  const token = localStorage.getItem('fmp_token') || ''
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch('/api/media/upload', { method: 'POST', headers, body: fd }).then(async (res) => {
    if (res.status === 401) {
      localStorage.removeItem('fmp_token')
      localStorage.removeItem('fmp_user')
      window.location.href = '/login'
      throw new Error('未登录或登录已过期')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `上传失败: ${res.status}`)
    }
    return res.json()
  })
}
export const getMediaAssets = (params = {}) => {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
  return request(`/media?${new URLSearchParams(clean)}`)
}
export const deleteMediaAsset = (id) => request(`/media/${id}`, { method: 'DELETE' })

// 短篇小说
export const novelAPI = {
  getNovels: (params = {}) => {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
    return request(`/novels?${new URLSearchParams(clean)}`)
  },
  getNovel: (id) => request(`/novels/${id}`),
  createNovel: (data) => request('/novels', { method: 'POST', body: JSON.stringify(data) }),
  importNovel: (data) => request('/novels/import', { method: 'POST', body: JSON.stringify(data) }),
  updateNovel: (id, data) => request(`/novels/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteNovel: (id) => request(`/novels/${id}`, { method: 'DELETE' }),
  generateSettings: (id) => request(`/novels/${id}/settings/generate`, { method: 'POST' }),
  generateOutline: (id, chapterCount) => request(`/novels/${id}/outline/generate`, { method: 'POST', body: JSON.stringify({ chapter_count: chapterCount }) }),
  generateSummary: (id) => request(`/novels/${id}/summary`, { method: 'POST' }),
  getChapters: (id) => request(`/novels/${id}/chapters`),
  addChapter: (id) => request(`/novels/${id}/chapters`, { method: 'POST' }),
  getChapter: (pid, cid) => request(`/novels/${pid}/chapters/${cid}`),
  updateChapter: (pid, cid, data) => request(`/novels/${pid}/chapters/${cid}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteChapter: (pid, cid) => request(`/novels/${pid}/chapters/${cid}`, { method: 'DELETE' }),
  publishNovel: (id, platforms) => request(`/novels/${id}/publish`, { method: 'POST', body: JSON.stringify({ platforms }) }),
}

export function generateChapterStream(pid, cid, data, onToken, onDone, onError) {
  return _postStream(`/novels/${pid}/chapters/${cid}/generate`, data, (ev) => {
    if (ev.type === 'token') onToken?.(ev.content)
    else if (ev.type === 'done') onDone?.(ev)
    else if (ev.type === 'error') onError?.(new Error(ev.message))
  }, onError)
}

// 一键生成全部章节（逐章流式事件）
export function generateAllStream(pid, data, onEvent, onError) {
  return _postStream(`/novels/${pid}/generate-all`, data, (ev) => {
    if (ev.type === 'error') onError?.(new Error(ev.message))
    else onEvent?.(ev)
  }, onError)
}
export const adminGetPlatforms = () => request('/admin/platforms')
export const adminCreatePlatform = (data) => request('/admin/platforms', { method: 'POST', body: JSON.stringify(data) })
export const adminUpdatePlatform = (key, data) => request(`/admin/platforms/${encodeURIComponent(key)}`, { method: 'PUT', body: JSON.stringify(data) })
export const adminUpdatePlatforms = (platforms) => request('/admin/platforms', { method: 'PUT', body: JSON.stringify({ platforms }) })
export const adminDeletePlatform = (key) => request(`/admin/platforms/${encodeURIComponent(key)}`, { method: 'DELETE' })
