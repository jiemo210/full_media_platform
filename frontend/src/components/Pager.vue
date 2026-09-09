<template>
  <div v-if="total > 0" class="pager">
    <button class="btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
    <span class="pager-info">{{ page }} / {{ totalPages }}</span>
    <button class="btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 10 },
})
const emit = defineEmits(['change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function go(p) {
  if (p < 1 || p > totalPages.value) return
  emit('change', p)
}
</script>

<style scoped>
.pager { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 1.2rem; font-size: 0.82rem; }
.pager-info { color: var(--text-muted); font-size: 0.82rem; }
</style>
