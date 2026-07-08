// BiasGuard — API client
// Thin wrapper around fetch() for talking to the FastAPI backend.

const BASE = 'http://localhost:8000'

// --- token storage (in-memory + localStorage mirror) -------------
function getToken() {
  return sessionStorage.getItem('biasguard_token')
}
function setToken(t) {
  if (t) sessionStorage.setItem('biasguard_token', t)
  else sessionStorage.removeItem('biasguard_token')
}

// --- core request helper -----------------------------------------
async function request(path, { method = 'GET', body, form, auth = true } = {}) {
  const headers = {}
  let payload

  if (form) {
    // OAuth2 login expects form-encoded data
    payload = new URLSearchParams(form).toString()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (body) {
    payload = JSON.stringify(body)
    headers['Content-Type'] = 'application/json'
  }

  if (auth) {
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  let res
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload })
  } catch {
    throw new Error(
      'Cannot reach the BiasGuard server. Is the backend running on port 8000?'
    )
  }

  if (!res.ok) {
    if (res.status === 401 && auth) {
      // session expired or token invalid - clear it and bounce to login
      setToken(null)
      if (window.location.pathname !== '/') window.location.assign('/')
    }
    let detail = `Request failed (${res.status})`
    try {
      const data = await res.json()
      if (data.detail) detail = typeof data.detail === 'string'
        ? data.detail
        : JSON.stringify(data.detail)
    } catch { /* keep default */ }
    throw new Error(detail)
  }

  if (res.status === 204) return null
  return res.json()
}

// --- public API ---------------------------------------------------
export const api = {
  getToken,
  setToken,
  isLoggedIn: () => !!getToken(),

  async signup(email, password) {
    const data = await request('/signup', {
      method: 'POST', auth: false, body: { email, password },
    })
    setToken(data.access_token)
    return data
  },

  async login(email, password) {
    const data = await request('/login', {
      method: 'POST', auth: false,
      form: { username: email, password },
    })
    setToken(data.access_token)
    return data
  },

  logout() {
    setToken(null)
  },

  me() {
    return request('/me')
  },

  listTrades() {
    return request('/trades')
  },

  addTrade(trade) {
    return request('/trades', { method: 'POST', body: trade })
  },

  deleteTrade(id) {
    return request(`/trades/${id}`, { method: 'DELETE' })
  },

  analyze() {
    return request('/analyze', { method: 'POST' })
  },

  report() {
    return request('/report')
  },
}
