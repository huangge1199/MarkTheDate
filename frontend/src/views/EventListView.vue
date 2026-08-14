<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { deleteEvent, listEvents, type EventSummary } from '@/api/events'

const router = useRouter()
const items = ref<EventSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref<string>('')

async function load() {
  loading.value = true
  try {
    const data = await listEvents({
      status: statusFilter.value || undefined,
    })
    items.value = data.filter((e) =>
      !keyword.value || e.title.toLowerCase().includes(keyword.value.toLowerCase())
    )
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function remove(row: EventSummary) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.title}」？此操作会删除对应 Markdown 文件。`, '确认', {
      type: 'warning',
    })
    await deleteEvent(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

function open(id: string) {
  router.push({ name: 'event-edit', params: { id } })
}

function statusType(s: string) {
  return {
    planned: 'primary',
    ongoing: 'warning',
    done: 'success',
    cancelled: 'info',
  }[s] as any
}

function statusLabel(s: string) {
  return {
    planned: '计划',
    ongoing: '进行中',
    done: '已完成',
    cancelled: '已取消',
  }[s] || s
}

onMounted(load)
</script>

<template>
  <div class="event-list">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索标题" clearable style="width: 240px" @change="load" />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 140px" @change="load">
        <el-option label="全部" value="" />
        <el-option label="计划" value="planned" />
        <el-option label="进行中" value="ongoing" />
        <el-option label="已完成" value="done" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button type="primary" @click="router.push({ name: 'event-new' })">
        <el-icon><Plus /></el-icon>新建活动
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" stripe>
      <el-table-column label="标题" min-width="200">
        <template #default="{ row }">
          <a class="link" @click="open(row.id)">
            <span class="dot" :style="{ background: row.color || '#3b82f6' }"></span>
            {{ row.title }}
          </a>
        </template>
      </el-table-column>
      <el-table-column label="开始" width="170">
        <template #default="{ row }">
          {{ dayjs(row.start).format('YYYY-MM-DD HH:mm') }}
        </template>
      </el-table-column>
      <el-table-column label="结束" width="170">
        <template #default="{ row }">
          {{ row.end ? dayjs(row.end).format('YYYY-MM-DD HH:mm') : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="全天" width="70">
        <template #default="{ row }">{{ row.all_day ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标签" min-width="200">
        <template #default="{ row }">
          <span v-for="t in row.tags" :key="t" class="event-tag">{{ t }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link @click="open(row.id)">编辑</el-button>
          <el-button size="small" link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.event-list { max-width: 1200px; margin: 0 auto; }
.link { color: var(--text); cursor: pointer; }
.link:hover { color: var(--accent); }
</style>