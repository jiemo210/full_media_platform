import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useStore } from './store'
import './assets/style.css'
import { initTheme } from './theme'

initTheme()
createApp(App).use(router).use(useStore).mount('#app')
