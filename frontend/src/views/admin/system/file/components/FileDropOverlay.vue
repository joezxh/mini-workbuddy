<template>
  <Teleport to="body">
    <Transition name="drop-fade">
      <div v-if="active" class="drop-overlay" @dragenter.prevent @dragover.prevent @drop.prevent="onDrop">
        <div class="drop-overlay__inner">
          <UploadOutlined class="drop-overlay__icon" />
          <div class="drop-overlay__title">释放以上传文件</div>
          <div class="drop-overlay__hint">支持任意文件，单个文件最大 50 MB</div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { UploadOutlined } from '@ant-design/icons-vue'

const emit = defineEmits<{ (e: 'drop', files: FileList): void }>()
const active = ref(false)
let depth = 0

function onDragEnter(e: DragEvent) {
  if (!e.dataTransfer?.types.includes('Files')) return
  depth++
  active.value = true
}
function onDragLeave() {
  depth = Math.max(0, depth - 1)
  if (depth === 0) active.value = false
}
function onDrop(e: DragEvent) {
  depth = 0
  active.value = false
  if (e.dataTransfer?.files?.length) emit('drop', e.dataTransfer.files)
}
function onWindowLeave() {
  depth = 0
  active.value = false
}

onMounted(() => {
  document.addEventListener('dragenter', onDragEnter)
  document.addEventListener('dragleave', onDragLeave)
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('drop', onDrop)
  window.addEventListener('blur', onWindowLeave)
})
onBeforeUnmount(() => {
  document.removeEventListener('dragenter', onDragEnter)
  document.removeEventListener('dragleave', onDragLeave)
  document.removeEventListener('dragover', onDragOver)
  document.removeEventListener('drop', onDrop)
  window.removeEventListener('blur', onWindowLeave)
})
function onDragOver(e: DragEvent) { e.preventDefault() }
</script>

<style scoped lang="less">
.drop-overlay {
  position: fixed; inset: 0; z-index: 3000;
  display: grid; place-items: center;
  background: color-mix(in srgb, var(--bg) 82%, transparent);
  backdrop-filter: blur(6px);
}
.drop-overlay__inner {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 48px 72px; border: 2px dashed var(--accent); border-radius: 16px;
  background: var(--bg-surface);
}
.drop-overlay__icon { font-size: 48px; color: var(--accent); }
.drop-overlay__title { font-size: 20px; font-weight: 600; color: var(--fg); }
.drop-overlay__hint { font-size: 13px; color: var(--fg-secondary); }
.drop-fade-enter-active, .drop-fade-leave-active { transition: opacity 180ms ease; }
.drop-fade-enter-from, .drop-fade-leave-to { opacity: 0; }
</style>
