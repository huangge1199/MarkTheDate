<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import customParseFormat from 'dayjs/plugin/customParseFormat'
dayjs.extend(customParseFormat)

/** 把后端返回的日期/时间规范化为 el-date-picker 可接受的本地时间字符串。 */
function normalizeDateTime(v?: string | null): string {
  if (!v) return ''
  const d = dayjs(v)
  if (!d.isValid()) return ''
  // 全天（无时分）→ 输出 YYYY-MM-DDTHH:mm:ss 占位 00:00:00，
  // 因为 el-date-picker 的 value-format 锁定了该格式。
  // 配合 form.all_day 来表达"仅日期"的语义。
  return d.format('YYYY-MM-DDTHH:mm:ss')
}
import MarkdownEditor from '@/components/MarkdownEditor.vue'
import {
  createEvent,
  getEvent,
  updateEvent,
  type EventCreate,
  type EventDetail,
  type Reminder,
} from '@/api/events'
import { applyOptimized, fetchUrl, optimizeMarkdown } from '@/api/ai'

const route = useRoute()
const router = useRouter()

const editing = ref<EventDetail | null>(null)
const isNew = computed(() => !route.params.id)

// 表单
const form = ref<EventCreate>({
  title: '',
  start: dayjs().format('YYYY-MM-DDTHH:mm:ss'),
  end: null,
  all_day: false,
  reminders: [],
  tags: [],
  status: 'planned',
  source_url: undefined,
  content: '',
})

const content = ref('')
const tagsInput = ref('')
const loading = ref(false)
const saving = ref(false)

// URL 抓取
const fetchUrlInput = ref('')
const fetching = ref(false)
const fetchSessionId = ref<string | null>(null)

// AI 优化
const optimizing = ref(false)
const aiDialog = ref(false)
const aiInstruction = ref('')
const aiBefore = ref('')
const aiAfter = ref('')
const aiSummary = ref('')
const aiEventId = ref('')

watch(content, (v) => {
  form.value.content = v
})

watch(
  () => route.params.id,
  async (id) => {
    if (id) await loadDetail(String(id))
    else resetForm()
  },
  { immediate: true }
)

async function loadDetail(id: string) {
  loading.value = true
  try {
    const d = await getEvent(id)
    editing.value = d
    form.value = {
      title: d.title,
      start: d.start,
      end: d.end ?? null,
      all_day: d.all_day,
      reminders: d.reminders ?? [],
      tags: d.tags ?? [],
      status: d.status,
      source_url: d.source_url ?? undefined,
      content: d.content,
    }
    content.value = d.content
    tagsInput.value = (d.tags ?? []).join(', ')
  } catch (e: any) {
    ElMessage.error(e.message)
    router.push({ name: 'events' })
  } finally {
    loading.value = false
  }
}

function resetForm() {
  const dateQuery = route.query.date as string | undefined
  const base = dateQuery ? dayjs(dateQuery).hour(9).minute(0) : dayjs()
  form.value = {
    title: '',
    start: base.format('YYYY-MM-DDTHH:mm:ss'),
    end: null,
    all_day: false,
    reminders: [],
    tags: [],
    status: 'planned',
    source_url: undefined,
    content: '',
  }
  content.value = ''
  tagsInput.value = ''
  editing.value = null
}

async function save() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  form.value.tags = tagsInput.value
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean)
  saving.value = true
  // 抓取会话 id：保存时让后端把临时图片搬到 events 目录
  const sid = fetchSessionId.value
  try {
    if (editing.value) {
      await updateEvent(editing.value.id, form.value, { fetch_session_id: sid })
      ElMessage.success('已保存')
      router.push({ name: 'events' })
    } else {
      await createEvent(form.value, { fetch_session_id: sid })
      ElMessage.success('已创建')
      router.push({ name: 'events' })
    }
    fetchSessionId.value = null
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!editing.value) return
  try {
    await ElMessageBox.confirm(`确定删除「${editing.value.title}」？`, '确认', { type: 'warning' })
    await (await import('@/api/events')).deleteEvent(editing.value.id)
    ElMessage.success('已删除')
    router.push({ name: 'events' })
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

function addReminder() {
  form.value.reminders = [
    ...(form.value.reminders ?? []),
    { type: 'browser', offset_minutes: 60 } as Reminder,
  ]
}
function removeReminder(idx: number) {
  form.value.reminders = form.value.reminders?.filter((_, i) => i !== idx) ?? []
}

async function doFetch() {
  if (!fetchUrlInput.value.trim()) {
    ElMessage.warning('请输入 URL')
    return
  }
  fetching.value = true
  try {
    const r = await fetchUrl(fetchUrlInput.value)
    fetchSessionId.value = r.session_id || null
    applyFetch(r)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    fetching.value = false
  }
}

function applyFetch(r: any) {
  if (!r) return
  form.value.title = r.title || form.value.title
  if (r.start) form.value.start = normalizeDateTime(r.start)
  if (r.end) form.value.end = normalizeDateTime(r.end)
  form.value.all_day = !!r.all_day
  form.value.tags = r.tags || form.value.tags || []
  tagsInput.value = (r.tags || []).join(', ')
  form.value.source_url = r.source_url ?? form.value.source_url
  content.value = r.content ?? content.value
  ElMessage.success('已填入表单，请确认后保存')
}

async function doOptimize() {
  if (!editing.value) {
    ElMessage.warning('请先保存活动后再使用 AI 优化')
    return
  }
  optimizing.value = true
  try {
    const r = await optimizeMarkdown(editing.value.id, aiInstruction.value || undefined)
    aiBefore.value = r.before
    aiAfter.value = r.after
    aiSummary.value = r.diff_summary || ''
    aiEventId.value = r.event_id
    aiDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    optimizing.value = false
  }
}

async function applyAi() {
  try {
    await applyOptimized(aiEventId.value, aiAfter.value)
    content.value = aiAfter.value
    aiDialog.value = false
    ElMessage.success('已应用 AI 优化')
    await loadDetail(aiEventId.value)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function colorChoices() {
  return ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']
}

onMounted(() => {
  if (!isNew.value && route.params.id) loadDetail(String(route.params.id))
})
</script>

<template>
  <div class="editor-view" v-loading="loading">
    <div class="toolbar">
      <h2 class="title">{{ isNew ? '新建活动' : '编辑活动' }}</h2>
      <div class="grow"></div>
      <el-button @click="router.back()">返回</el-button>
      <el-button v-if="!isNew" type="danger" plain @click="remove">删除</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>

    <div class="layout">
      <!-- 左：元数据 -->
      <div class="card meta">
        <el-form label-position="top">
          <el-form-item label="标题">
            <el-input v-model="form.title" placeholder="活动标题" />
          </el-form-item>
          <el-form-item label="URL 抓取">
            <div class="url-row">
              <el-input v-model="fetchUrlInput" placeholder="https://..." clearable />
              <el-button :loading="fetching" @click="doFetch">抓取</el-button>
            </div>
          </el-form-item>
          <el-form-item label="起始时间">
            <el-date-picker
              v-model="form.start"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              format="YYYY-MM-DD HH:mm"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="结束时间">
            <el-date-picker
              v-model="form.end"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              format="YYYY-MM-DD HH:mm"
              style="width: 100%"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.all_day">全天事件</el-checkbox>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status" style="width: 100%">
              <el-option label="计划" value="planned" />
              <el-option label="进行中" value="ongoing" />
              <el-option label="已完成" value="done" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="tagsInput" placeholder="逗号分隔" />
          </el-form-item>
          <el-form-item label="颜色">
            <div class="color-row">
              <span
                v-for="c in colorChoices()"
                :key="c"
                class="color-dot"
                :class="{ active: form.color === c }"
                :style="{ background: c }"
                @click="form.color = c"
              ></span>
              <el-button size="small" link @click="form.color = undefined">清除</el-button>
            </div>
          </el-form-item>
          <el-form-item label="来源 URL">
            <el-input v-model="form.source_url" placeholder="可选" />
          </el-form-item>

          <el-divider content-position="left">提醒规则</el-divider>
          <div v-for="(r, idx) in form.reminders" :key="idx" class="reminder-row">
            <el-select v-model="r.type" style="width: 100px">
              <el-option label="浏览器" value="browser" />
              <el-option label="邮件" value="email" />
            </el-select>
            <el-input-number v-model="r.offset_minutes" :min="0" :max="10080" />
            <span class="muted">分钟前</span>
            <el-input
              v-if="r.type === 'email'"
              v-model="r.email"
              placeholder="收件人"
              style="width: 160px"
            />
            <el-button link type="danger" @click="removeReminder(idx)">删除</el-button>
          </div>
          <el-button size="small" @click="addReminder">+ 添加提醒</el-button>
        </el-form>
      </div>

      <!-- 右：Markdown 编辑器 -->
      <div class="card content-card">
        <div class="content-toolbar">
          <span class="muted">Markdown 内容</span>
          <div class="grow"></div>
          <el-button :loading="optimizing" :disabled="isNew" @click="doOptimize">
            <el-icon><MagicStick /></el-icon> AI 优化
          </el-button>
        </div>
        <MarkdownEditor v-model="content" :height="560" />
      </div>
    </div>

    <!-- AI 优化结果 -->
    <el-dialog v-model="aiDialog" title="AI 优化结果" width="900">
      <div v-if="aiSummary">
        <el-alert :title="aiSummary" type="info" :closable="false" />
      </div>
      <div class="diff-grid">
        <div>
          <h4>原内容</h4>
          <pre class="preview">{{ aiBefore }}</pre>
        </div>
        <div>
          <h4>优化后</h4>
          <pre class="preview">{{ aiAfter }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="aiDialog = false">取消</el-button>
        <el-button type="primary" @click="applyAi">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.editor-view { max-width: 1400px; margin: 0 auto; }
.title { margin: 0; font-size: 18px; }
.grow { flex: 1; }
.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  margin-top: 16px;
}
.card { background: white; padding: 16px; border-radius: 8px; border: 1px solid var(--border); }
.url-row { display: flex; gap: 8px; }
.url-row > .el-input { flex: 1; }
.color-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.color-dot {
  display: inline-block;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
}
.color-dot.active { border-color: #111; }
.reminder-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.content-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.content-card { padding: 12px; }
.preview {
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12px;
}
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .diff-grid { grid-template-columns: 1fr; }
}
</style>