import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('veritai_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('veritai_token')
      localStorage.removeItem('veritai_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

export const verifyAPI = {
  verify: (data) => api.post('/verify/', data),
  getReport: (id) => api.get(`/verify/${id}`),
}

export const historyAPI = {
  getHistory: (params) => api.get('/history/', { params }),
  deleteReport: (id) => api.delete(`/history/${id}`),
  getStats: () => api.get('/history/stats/summary'),
}

export default api
