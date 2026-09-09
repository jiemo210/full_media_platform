/** 全局提示（显著位置 + 可交互操作） */
import { reactive } from 'vue'

export const toasts = reactive([])
let seq = 0

export function toast(message, type = 'success', action = null, duration = 4500) {
  const id = ++seq
  toasts.push({ id, message, type, action })
  setTimeout(() => dismiss(id), duration)
  return id
}

export function dismiss(id) {
  const idx = toasts.findIndex(t => t.id === id)
  if (idx >= 0) toasts.splice(idx, 1)
}
