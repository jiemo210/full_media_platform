<template>
  <div id="app-root">
    <NavBar v-if="!isLoginPage" />
    <main class="main-content" :class="{ 'no-nav': isLoginPage }">
      <router-view />
    </main>
    <ToastHost />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'
import ToastHost from './components/ToastHost.vue'

const route = useRoute()
const isLoginPage = computed(() => route.path === '/login')
</script>

<style>
.main-content { min-height: 100vh; padding-top: 66px; }
.main-content.no-nav { padding-top: 0; }
</style>
