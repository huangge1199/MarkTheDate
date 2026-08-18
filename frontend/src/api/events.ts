import http from './http'

export interface Reminder {
  type: 'browser' | 'email'
  offset_minutes: number
  email?: string
}

export interface EventSummary {
  id: string
  title: string
  start: string
  end?: string | null
  all_day: boolean
  status: 'planned' | 'ongoing' | 'done' | 'cancelled'
  tags: string[]
  color?: string | null
}

export interface EventDetail extends EventSummary {
  reminders: Reminder[]
  source_url?: string | null
  content: string
  file_path: string
  created_at?: string | null
  updated_at: string
}

export interface EventCreate {
  title: string
  start: string
  end?: string | null
  all_day?: boolean
  reminders?: Reminder[]
  tags?: string[]
  color?: string
  status?: EventSummary['status']
  source_url?: string
  content?: string
  slug?: string
}

export interface EventUpdate {
  title?: string
  start?: string
  end?: string | null
  all_day?: boolean
  reminders?: Reminder[]
  tags?: string[]
  color?: string
  status?: EventSummary['status']
  source_url?: string | null
  content?: string
}

export function listEvents(params?: {
  status?: string
  tag?: string
  date_from?: string
  date_to?: string
}) {
  return http.get<EventSummary[]>('/events', { params })
}

export function getEvent(id: string) {
  return http.get<EventDetail>(`/events/${id}`)
}

export function createEvent(
  payload: EventCreate,
  options?: { fetch_session_id?: string | null },
) {
  return http.post<EventDetail>('/events', payload, {
    params: options?.fetch_session_id ? { fetch_session_id: options.fetch_session_id } : undefined,
  })
}

export function updateEvent(
  id: string,
  payload: EventUpdate,
  options?: { fetch_session_id?: string | null },
) {
  return http.put<EventDetail>(`/events/${id}`, payload, {
    params: options?.fetch_session_id ? { fetch_session_id: options.fetch_session_id } : undefined,
  })
}

export function deleteEvent(id: string) {
  return http.delete<void>(`/events/${id}`)
}

export interface CalendarDay {
  date: string
  events: EventSummary[]
}
export interface CalendarMonth {
  year: number
  month: number
  days: CalendarDay[]
}

export function getCalendar(year: number, month: number) {
  return http.get<CalendarMonth>('/calendar', { params: { year, month } })
}