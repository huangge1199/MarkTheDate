import http from './http'

export interface Settings {
  ai_provider: string
  ai_base_url: string
  ai_model: string
  ai_api_key_set: boolean
  ollama_base_url: string
  ollama_model: string
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_from: string
  smtp_configured: boolean
  notify_poll_interval_seconds: number
}

export function getSettings() {
  return http.get<Settings>('/settings')
}

export function updateSettings(payload: Partial<Settings> & { ai_api_key?: string; smtp_pass?: string }) {
  return http.put<Settings>('/settings', payload)
}