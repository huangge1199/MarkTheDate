<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import NotificationCenter from './components/NotificationCenter.vue'
import { useNotificationPolling } from './composables/useBrowserNotify'

const route = useRoute()

onMounted(() => {
  // 启动浏览器通知轮询
  useNotificationPolling()
})
</script>

<template>
  <AppHeader />
  <main class="page">
    <router-view v-slot="{ Component }">
      <transition name="fade">
        <component :is="Component" :key="route.fullPath" />
      </transition>
    </router-view>
  </main>
  <NotificationCenter />
</template>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>