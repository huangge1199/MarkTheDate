<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const links = [
  { name: 'calendar', label: '日历', icon: 'Calendar' },
  { name: 'events', label: '活动', icon: 'List' },
  { name: 'settings', label: '设置', icon: 'Setting' },
]

const active = computed(() => router.currentRoute.value.name)
function go(name: string) {
  router.push({ name })
}
</script>

<template>
  <header class="app-header">
    <div class="brand" @click="go('calendar')">
      <img src="/favicon.svg" alt="logo" width="28" height="28" />
      <span class="brand-name">MarkTheDate</span>
      <span class="brand-sub">活动日期管理</span>
    </div>
    <nav class="nav">
      <el-button
        v-for="l in links"
        :key="l.name"
        :type="active === l.name ? 'primary' : 'default'"
        text
        @click="go(l.name)"
      >
        <el-icon><component :is="l.icon" /></el-icon>
        <span>{{ l.label }}</span>
      </el-button>
    </nav>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: white;
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.brand-name {
  font-weight: 700;
  font-size: 18px;
  color: var(--text);
}
.brand-sub {
  color: var(--text-muted);
  font-size: 13px;
  margin-left: 6px;
}
.nav {
  display: flex;
  gap: 4px;
}
</style>