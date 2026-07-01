import axios from 'axios'

// API base:
//  - local dev: VITE_API_URL = http://localhost:8000  ->  http://localhost:8000/api
//  - production: VITE_API_URL unset  ->  /api  (same origin, served by the backend)
const base = (import.meta.env.VITE_API_URL || '') + '/api'

const api = axios.create({ baseURL: base })

// Attach the JWT to every request if we have one.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
