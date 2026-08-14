<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings, type Settings } from '@/api/settings'

const form = ref<Settings>({
  ai_provider: 'openai',
  ai_base_url: '',
  ai_model: '',
  ai_api_key_set: false,
  ollama_base_url: '',
  ollama_model: '',
  smtp_host: '',
  smtp_port: 465,
  smtp_user: '',
  smtp_from: '',
  smtp_configured: false,
  notify_poll_interval_seconds: 60,
})
const apiKey = ref('')
const smtpPass = ref('')
const loading = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    form.value = await getSettings()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload: any = {
      ai_provider: form.value.ai_provider,
      ai_base_url: form.value.ai_base_url,
      ai_model: form.value.ai_model,
      ollama_base_url: form.value.ollama_base_url,
      ollama_model: form.value.ollama_model,
      smtp_host: form.value.smtp_host,
      smtp_port: form.value.smtp_port,
      smtp_user: form.value.smtp_user,
      smtp_from: form.value.smtp_from,
      notify_poll_interval_seconds: form.value.notify_poll_interval_seconds,
    }
    if (apiKey.value) payload.ai_api_key = apiKey.value
    if (smtpPass.value) payload.smtp_pass = smtpPass.value
    form.value = await updateSettings(payload)
    apiKey.value = ''
    smtpPass.value = ''
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="settings-view" v-loading="loading">
    <h2 class="title">设置</h2>

    <el-card class="card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>AI 配置</span>
          <el-tag size="small" type="info">修改后立即生效</el-tag>
        </div>
      </template>
      <el-form label-width="140px">
        <el-form-item label="服务提供方">
          <el-radio-group v-model="form.ai_provider">
            <el-radio value="openai">OpenAI 兼容 API</el-radio>
            <el-radio value="ollama">Ollama（本地）</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.ai_provider === 'openai'">
          <el-form-item label="Base URL">
            <el-input v-model="form.ai_base_url" placeholder="https://api.openai.com/v1" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input
              v-model="apiKey"
              :placeholder="form.ai_api_key_set ? '已设置（输入新值覆盖）' : 'sk-...'"
              show-password
            />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.ai_model" placeholder="gpt-4o-mini" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="Ollama URL">
            <el-input v-model="form.ollama_base_url" placeholder="http://localhost:11434" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.ollama_model" placeholder="llama3.1" />
          </el-form-item>
        </template>
      </el-form>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><span>邮件通知（SMTP）</span></template>
      <el-form label-width="140px">
        <el-form-item label="SMTP 主机">
          <el-input v-model="form.smtp_host" placeholder="smtp.example.com" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.smtp_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.smtp_user" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="smtpPass" type="password" show-password placeholder="留空不修改" />
        </el-form-item>
        <el-form-item label="发件人">
          <el-input v-model="form.smtp_from" placeholder="可选，默认与用户名相同" />
        </el-form-item>
        <el-form-item>
          <el-tag v-if="form.smtp_configured" type="success">已配置</el-tag>
          <el-tag v-else type="info">未配置（不会发送邮件）</el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="card" shadow="never">
      <template #header><span>其他</span></template>
      <el-form label-width="180px">
        <el-form-item label="浏览器通知轮询间隔(秒)">
          <el-input-number v-model="form.notify_poll_interval_seconds" :min="15" :max="3600" />
        </el-form-item>
      </el-form>
    </el-card>

    <div class="actions">
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </div>
  </div>
</template>

<style scoped>
.settings-view { max-width: 800px; margin: 0 auto; }
.title { font-size: 18px; margin: 0 0 16px; }
.card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.actions { display: flex; justify-content: flex-end; margin-top: 12px; }
</style>