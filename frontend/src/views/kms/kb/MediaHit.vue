<template>
  <div v-if="media" class="media-hit">
    <template v-if="media.kind === 'audio' && fileUrl">
      <audio controls preload="none" :src="fileUrl" class="media-hit__player"
             @loadedmetadata="seekTo" />
    </template>
    <template v-else-if="media.kind === 'video' && fileUrl">
      <video controls preload="none" :src="fileUrl" class="media-hit__player"
             @loadedmetadata="seekTo" />
    </template>
    <a-tag v-if="media.kind === 'drawing' && locator?.layer" color="purple">
      {{ t('kbMgmt.mediaLayer') }} {{ locator.layer }}
    </a-tag>
    <a-tag v-if="locatorText" color="cyan">{{ locatorText }}</a-tag>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  media: { kind: string; locator: Record<string, number | string> | null } | null | undefined
  documentId: string
  knowledgeId: number
}>()

const { t } = useI18n()

const locator = computed(() => props.media?.locator || null)

/** 音视频原文件走后端下载端点（dev 经 Vite proxy） */
const fileUrl = computed(() =>
  props.media && ['audio', 'video'].includes(props.media.kind)
    ? `/api/v1/kb/knowledges/${props.knowledgeId}/documents/${props.documentId}/file`
    : '')

function seekTo(e: Event) {
  const start = Number(locator.value?.start_ms ?? 0)
  if (start > 0) (e.target as HTMLMediaElement).currentTime = start / 1000
}

const locatorText = computed(() => {
  const loc = locator.value || {}
  if (loc.start_ms != null && loc.start_ms !== '') {
    const s = Math.floor(Number(loc.start_ms) / 1000)
    const mm = String(Math.floor(s / 60)).padStart(2, '0')
    const ss = String(s % 60).padStart(2, '0')
    return `${mm}:${ss}`
  }
  if (loc.frame_index != null && loc.frame_index !== '') return `${t('kbMgmt.mediaFrame')} ${loc.frame_index}`
  return ''
})
</script>

<style scoped>
.media-hit {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.media-hit__player {
  max-width: 320px;
  height: 32px;
}
video.media-hit__player {
  height: auto;
  max-height: 180px;
}
</style>
