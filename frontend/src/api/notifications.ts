import http from './http'

export interface PendingNotification {
  event_id: string
  event_title: string
  event_start: string
  reminder_type: 'browser' | 'email'
  reminder_key: string
  trigger_at: string
  offset_minutes: number
}

export function pendingNotifications() {
  return http.get<PendingNotification[]>('/notifications/pending')
}

export function ackNotification(reminder_key: string) {
  return http.post<void>('/notifications/ack', { reminder_key })
}