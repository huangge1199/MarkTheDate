<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { getCalendar, type CalendarDay } from '@/api/events'

const router = useRouter()
const cursor = ref(dayjs())
const days = ref<CalendarDay[]>([])
const loading = ref(false)

const year = computed(() => cursor.value.year())
const month = computed(() => cursor.value.month() + 1)

const grid = computed(() => {
  // 计算月历网格（首列为周一）
  const first = cursor.value.startOf('month')
  const offset = (first.day() + 6) % 7 // 周一为 0
  const total = cursor.value.daysInMonth()
  const cells: Array<{ date: dayjs.Dayjs; events: any[]; inMonth: boolean }> = []

  // 前置空白
  for (let i = 0; i < offset; i++) {
    cells.push({ date: first.subtract(offset - i, 'day'), events: [], inMonth: false })
  }
  const byDate: Record<string, any[]> = {}
  for (const d of days.value) byDate[d.date] = d.events
  for (let i = 1; i <= total; i++) {
    const date = cursor.value.date(i)
    const key = date.format('YYYY-MM-DD')
    cells.push({ date, events: byDate[key] ?? [], inMonth: true })
  }
  // 补齐到 6 行 = 42 格
  while (cells.length < 42) {
    cells.push({ date: cells[cells.length - 1].date.add(1, 'day'), events: [], inMonth: false })
  }
  return cells
})

const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日']

async function refresh() {
  loading.value = true
  try {
    const data = await getCalendar(year.value, month.value)
    days.value = data.days
  } catch (e: any) {
    ElMessage.error(e.message || '加载日历失败')
  } finally {
    loading.value = false
  }
}

function prev() {
  cursor.value = cursor.value.subtract(1, 'month')
}
function next() {
  cursor.value = cursor.value.add(1, 'month')
}
function today() {
  cursor.value = dayjs()
}
function openEvent(id: string) {
  router.push({ name: 'event-edit', params: { id } })
}
function newOn(date: dayjs.Dayjs) {
  router.push({ name: 'event-new', query: { date: date.format('YYYY-MM-DD') } })
}

watch([year, month], refresh)
onMounted(refresh)
</script>

<template>
  <div class="calendar-view">
    <div class="toolbar">
      <el-button-group>
        <el-button @click="prev"><el-icon><ArrowLeft /></el-icon></el-button>
        <el-button @click="today">今天</el-button>
        <el-button @click="next"><el-icon><ArrowRight /></el-icon></el-button>
      </el-button-group>
      <h2 class="title">{{ year }} 年 {{ month }} 月</h2>
      <el-button type="primary" @click="router.push({ name: 'event-new' })">
        <el-icon><Plus /></el-icon>新建活动
      </el-button>
    </div>

    <div class="grid">
      <div class="cell weekday" v-for="w in weekdayLabels" :key="w">{{ w }}</div>
      <div
        v-for="(c, i) in grid"
        :key="i"
        class="cell day"
        :class="{ 'is-other': !c.inMonth, 'is-today': c.inMonth && c.date.isSame(dayjs(), 'day') }"
        @click="c.inMonth && newOn(c.date)"
      >
        <div class="day-head">
          <span class="date-num">{{ c.date.date() }}</span>
        </div>
        <div class="day-events" @click.stop>
          <div
            v-for="ev in c.events.slice(0, 3)"
            :key="ev.id"
            class="ev"
            :style="{ borderLeftColor: ev.color || '#3b82f6' }"
            @click="openEvent(ev.id)"
            :title="ev.title"
          >
            <span class="dot" :style="{ background: ev.color || '#3b82f6' }"></span>
            <span class="ev-title">{{ ev.title }}</span>
          </div>
          <div v-if="c.events.length > 3" class="muted">+{{ c.events.length - 3 }} 更多</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.calendar-view { max-width: 1200px; margin: 0 auto; }
.title { margin: 0 12px; font-size: 18px; }
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: white;
}
.cell {
  min-height: 110px;
  padding: 6px;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.cell.weekday {
  min-height: auto;
  padding: 8px;
  font-weight: 600;
  background: #f9fafb;
  color: var(--text-muted);
  text-align: center;
}
.cell.day {
  cursor: pointer;
  background: white;
  display: flex;
  flex-direction: column;
}
.cell.is-other { background: #fafafa; color: #cbd5e1; }
.cell.is-today { background: #eff6ff; }
.day-head { display: flex; justify-content: flex-end; }
.date-num { font-size: 13px; }
.day-events { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; }
.ev {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #eff6ff;
  font-size: 12px;
  cursor: pointer;
  border-left: 3px solid #3b82f6;
}
.ev:hover { background: #dbeafe; }
.ev-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 110px;
}
</style>