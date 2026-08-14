import http from './http'

export interface FetchResponse {
  title: string
  start?: string | null
  end?: string | null
  all_day: boolean
  tags: string[]
  source_url: string
  content: string
  raw_html_excerpt: string
  confidence: 'high' | 'medium' | 'low'
}

export interface AIOptimizeResponse {
  event_id: string
  before: string
  after: string
  diff_summary?: string
}

export interface AISuggestResponse {
  title?: string | null
  start?: string | null
  end?: string | null
  tags: string[]
  summary?: string | null
}

export function fetchUrl(url: string) {
  return http.post<FetchResponse>('/fetch', { url })
}

export function optimizeMarkdown(event_id: string, instruction?: string) {
  return http.post<AIOptimizeResponse>('/ai/optimize', { event_id, instruction })
}

export function applyOptimized(event_id: string, content: string) {
  return http.post<{ ok: boolean; file_path: string }>(`/ai/apply/${event_id}`, { content })
}

export function suggestMetadata(content: string) {
  return http.post<AISuggestResponse>('/ai/suggest', { content })
}