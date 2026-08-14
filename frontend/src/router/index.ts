import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'calendar',
    component: () => import('@/views/CalendarView.vue'),
    meta: { title: '日历' },
  },
  {
    path: '/events',
    name: 'events',
    component: () => import('@/views/EventListView.vue'),
    meta: { title: '活动列表' },
  },
  {
    path: '/events/new',
    name: 'event-new',
    component: () => import('@/views/EventEditorView.vue'),
    meta: { title: '新建活动' },
  },
  {
    path: '/events/:id',
    name: 'event-edit',
    component: () => import('@/views/EventEditorView.vue'),
    meta: { title: '编辑活动' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '设置' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? 'MarkTheDate'} · MarkTheDate`
})

export default router