import { reactive, readonly } from 'vue'

const state = reactive({
  token: localStorage.getItem('fmp_token') || '',
  user: JSON.parse(localStorage.getItem('fmp_user') || 'null'),
})

function setAuth(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem('fmp_token', token)
  localStorage.setItem('fmp_user', JSON.stringify(user))
}

function clearAuth() {
  state.token = ''
  state.user = null
  localStorage.removeItem('fmp_token')
  localStorage.removeItem('fmp_user')
}

const isLoggedIn = () => !!state.token
const isAdmin = () => state.user?.role === 'admin'

export function useStore(app) {
  app.provide('store', { state: readonly(state), setAuth, clearAuth, isLoggedIn, isAdmin })
}

export { state, setAuth, clearAuth, isLoggedIn, isAdmin }
