<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import Vditor from 'vditor'
import 'vditor/dist/index.css'

const props = defineProps<{
  modelValue: string
  height?: number
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
}>()

const editorRef = ref<HTMLDivElement | null>(null)
let vditor: Vditor | null = null

function init() {
  if (!editorRef.value) return
  vditor = new Vditor(editorRef.value, {
    height: props.height ?? 480,
    mode: 'wysiwyg',
    placeholder: props.placeholder ?? '在这里写 Markdown...',
    value: props.modelValue ?? '',
    theme: 'classic',
    toolbar: [
      'headings',
      'bold',
      'italic',
      'strike',
      '|',
      'list',
      'ordered-list',
      'check',
      '|',
      'quote',
      'code',
      'inline-code',
      '|',
      'link',
      'table',
      '|',
      'preview',
      'fullscreen',
      'help',
    ],
    cache: { enable: false },
    input(value: string) {
      emit('update:modelValue', value)
    },
    after() {
      // 同步一次初始值
    },
  })
}

onMounted(init)
onBeforeUnmount(() => vditor?.destroy())

watch(
  () => props.modelValue,
  (v) => {
    if (vditor && v !== vditor.getValue()) {
      vditor.setValue(v ?? '')
    }
  }
)
</script>

<template>
  <div ref="editorRef" class="markdown-editor"></div>
</template>

<style scoped>
.markdown-editor {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
</style>