/**
 * 全媒体聚合平台 - 界面主题管理
 * 颜色模式（深色/浅色）+ 背景方案，持久化到 localStorage。
 */
import { reactive } from 'vue'

const THEME_KEY = 'fmp_theme'

export const BACKGROUNDS = [
  { key: 'aurora', label: '极光之夜', emoji: '🌌' },
  { key: 'ocean', label: '深海', emoji: '🌊' },
  { key: 'violet', label: '暮色紫', emoji: '🌆' },
  { key: 'paper', label: '宣纸白', emoji: '📄' },
]

function loadSaved() {
  try {
    const raw = JSON.parse(localStorage.getItem(THEME_KEY) || '{}')
    return {
      mode: raw.mode === 'light' ? 'light' : 'dark',
      background: BACKGROUNDS.some(b => b.key === raw.background) ? raw.background : 'aurora',
    }
  } catch (e) {
    return { mode: 'dark', background: 'aurora' }
  }
}

const saved = loadSaved()
const state = reactive({ mode: saved.mode, background: saved.background })

export function applyTheme() {
  const root = document.documentElement
  root.dataset.theme = state.mode
  root.dataset.bg = state.background
  localStorage.setItem(THEME_KEY, JSON.stringify({ mode: state.mode, background: state.background }))
}

export function setMode(mode) {
  state.mode = mode === 'light' ? 'light' : 'dark'
  applyTheme()
}

export function setBackground(key) {
  if (!BACKGROUNDS.some(b => b.key === key)) return
  state.background = key
  if (key === 'paper') state.mode = 'light'
  else if (state.mode === 'light' && key !== 'paper') state.mode = 'dark'
  applyTheme()
}

export function initTheme() {
  applyTheme()
}

export { state }
