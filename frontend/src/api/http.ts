import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

http.interceptors.response.use(
  (r) => r.data,
  (err) => {
    const msg = err?.response?.data?.detail || err.message
    return Promise.reject(new Error(msg))
  }
)

export default http