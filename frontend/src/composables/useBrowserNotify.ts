/** 浏览器通知 composable：轮询 + Notification API。*/
import { onMounted, onUnmounted, ref } from 'vue'
import { ElNotification } from 'element-plus'
import {
  ackNotification,
  pendingNotifications,
  type PendingNotification,
} from '@/api/notifications'

const seen = new Set<string>()

async function showNotification(n: PendingNotification) {
  if (seen.has(n.reminder_key)) return
  seen.add(n.reminder_key)

  const body = `将于 ${new Date(n.event_start).toLocaleString()} 开始（提前 ${n.offset_minutes} 分钟）`
  // 系统通知（需用户授权）
  if ('Notification' in window && Notification.permission === 'granted') {
    try {
      new Notification(n.event_title, { body, icon: '/favicon.svg' })
    } catch (e) {
      // 某些浏览器仍需要页面交互，降级到 Element Plus
    }
  }
  ElNotification({
    title: n.event_title,
    message: body,
    type: 'warning',
    duration: 0,
    position: 'top-right',
  })

  try {
    await ackNotification(n.reminder_key)
  } catch (e) {
    console.warn('ack failed', e)
  }
}

let timer: number | null = null

async function tick() {
  try {
    const items = await pendingNotifications()
    for (const it of items) await showNotification(it)
  } catch (e) {
    console.warn('pending notifications failed', e)
  }
}

export function useNotificationPolling() {
  const permission = ref<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  )

  async function requestPermission() {
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'default') {
      permission.value = await Notification.requestPermission()
    } else {
      permission.value = Notification.permission
    }
  }

  onMounted(() => {
    requestPermission()
    tick()
    timer = window.setInterval(tick, 60_000)
  })

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })

  return { permission, requestPermission }
}