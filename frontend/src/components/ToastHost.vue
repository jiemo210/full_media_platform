<template>
  <div class="toast-host">
    <transition-group name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast-item" :class="t.type" @click="go(t)">
        <span class="toast-icon">{{ t.type === 'error' ? '❌' : t.type === 'info' ? 'ℹ️' : '✅' }}</span>
        <span class="toast-msg">{{ t.message }}</span>
        <button v-if="t.action" class="toast-action" @click.stop="go(t)">{{ t.action.label }}</button>
        <button class="toast-close" @click.stop="dismiss(t.id)">×</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { toasts, dismiss } from '../toast'

const router = useRouter()

function go(t) {
  if (!t.action) return
  if (/^https?:/.test(t.action.to)) window.open(t.action.to, '_blank')
  else router.push(t.action.to)
}
</script>

<style scoped>
.toast-host { position: fixed; top: 74px; left: 50%; transform: translateX(-50%); z-index: 5000; display: flex; flex-direction: column; gap: 10px; width: min(520px, 92vw); }
.toast-item { display: flex; align-items: center; gap: 10px; padding: 13px 16px; border-radius: 14px; background: rgba(13, 20, 40, 0.97); border: 1px solid var(--glass-border); box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45); cursor: pointer; -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px); }
.toast-item.success { border-left: 4px solid var(--accent-green); }
.toast-item.error { border-left: 4px solid #FF453A; }
.toast-item.info { border-left: 4px solid var(--accent-blue); }
.toast-icon { font-size: 1.1rem; flex-shrink: 0; }
.toast-msg { flex: 1; font-size: 0.9rem; color: var(--text-primary); line-height: 1.45; }
.toast-action { padding: 6px 14px; border: none; border-radius: 999px; background: var(--accent-blue); color: #0b1020; font-weight: 600; font-size: 0.8rem; cursor: pointer; flex-shrink: 0; }
.toast-close { background: none; border: none; color: var(--text-muted); font-size: 1.1rem; cursor: pointer; flex-shrink: 0; line-height: 1; }
.toast-enter-active, .toast-leave-active { transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-16px) scale(0.96); }
</style>
