<template>
  <a-modal
    :open="open"
    :footer="null"
    :width="modalWidth"
    :wrap-class-name="isMaximized ? 'preview-maximized' : ''"
    @cancel="$emit('update:open', false)"
  >
    <template #title>
      <div class="preview-title-bar">
        <span class="preview-title-text" :title="title">{{ title }}</span>
        <a-button type="text" size="small" @click="isMaximized = !isMaximized">
          <FullscreenOutlined v-if="!isMaximized" />
          <FullscreenExitOutlined v-else />
          {{ isMaximized ? '还原' : '最大化' }}
        </a-button>
      </div>
    </template>

    <div class="preview-body">
      <!-- 图片 -->
      <img v-if="kind === 'image'" :src="src" :alt="file?.name || '图片预览'" class="preview-image" />

      <!-- PDF -->
      <iframe v-else-if="kind === 'pdf'" :src="src" class="preview-frame" title="PDF 预览" />

      <!-- HTML（沙箱静态展示：允许资源与样式加载，禁止脚本执行） -->
      <iframe v-else-if="kind === 'html'" :src="src" class="preview-frame" sandbox="allow-same-origin" title="HTML 预览" />

      <!-- 视频 -->
      <video v-else-if="kind === 'video'" :src="src" controls class="preview-frame" />

      <!-- 音频 -->
      <audio v-else-if="kind === 'audio'" :src="src" controls class="preview-audio" />

      <!-- Markdown -->
      <div v-else-if="kind === 'markdown'" class="preview-markdown" v-html="renderedHtml" />

      <!-- 文本 / 代码 -->
      <pre v-else-if="kind === 'text'" class="preview-text"><code v-html="highlightedText" /></pre>

      <!-- Office（公网可达走微软在线预览） -->
      <iframe v-else-if="kind === 'office'" :src="officeViewerUrl" class="preview-frame" title="Office 在线预览" />

      <!-- 不支持 -->
      <div v-else class="preview-fallback">
        <FileOutlined class="preview-fallback__icon" />
        <p>该文件类型暂不支持在线预览{{ officeReason }}</p>
        <a-space>
          <a :href="src" target="_blank" rel="noopener">在新窗口打开</a>
          <a-button type="primary" size="small" @click="$emit('download')"><DownloadOutlined /> 下载文件</a-button>
        </a-space>
      </div>
    </div>

    <div v-if="loadingBody" class="preview-loading"><a-spin tip="加载预览内容…" /></div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { DownloadOutlined, FileOutlined, FullscreenExitOutlined, FullscreenOutlined } from '@ant-design/icons-vue'
import type { InfraFileVO } from '@/api/file'
import { infraFileApi } from '@/api/file'

const props = defineProps<{
  open: boolean
  file: InfraFileVO | null
  index?: number
  total?: number
}>()
defineEmits<{ (e: 'update:open', value: boolean): void; (e: 'download'): void }>()

const loadingBody = ref(false)
const markdownHtml = ref('')
const plainText = ref('')

type Kind = 'image' | 'pdf' | 'html' | 'video' | 'audio' | 'markdown' | 'text' | 'office' | 'unknown'
const OFFICE_EXT = /\.(docx?|xlsx?|pptx?)$/i
const MD_EXT = /\.(md|markdown)$/i
const HTML_EXT = /\.(html?|xhtml)$/i
const TEXT_EXT = /\.(txt|json|ya?ml|xml|csv|log|css|js|jsx|ts|tsx|py|java|go|rs|sh|sql|ini|toml)$/i
const VIDEO_EXT = /\.(mp4|webm|ogv|mov|m4v)$/i
const AUDIO_EXT = /\.(mp3|wav|ogg|flac|m4a|aac)$/i
/** 内网/本机地址无法被微软 Office 在线服务访问 */
const PRIVATE_HOST_RE = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[::1\])/

/** 预览一律走同源代理（inline + 正确 Content-Type）：iframe/img/video/fetch 通用，无 CORS 问题 */
const src = computed(() => props.file ? infraFileApi.previewUrl(props.file) : '')
const fileName = computed(() => props.file ? (props.file.name || props.file.path.split('/').pop() || '') : '')
const mime = computed(() => props.file?.type || '')
const publicAbsoluteUrl = computed(() => {
  if (!props.file) return ''
  const raw = props.file.url || ''
  if (/^https?:\/\//i.test(raw) && !raw.includes('/api/v1/')) return raw
  try {
    const abs = new URL(src.value, window.location.origin).href
    return abs
  } catch { return '' }
})
const isPubliclyReachable = computed(() => {
  const u = publicAbsoluteUrl.value
  if (!u) return false
  try {
    return !PRIVATE_HOST_RE.test(new URL(u).hostname)
  } catch { return false }
})

const kind = computed<Kind>(() => {
  const f = props.file
  if (!f) return 'unknown'
  const name = fileName.value.toLowerCase()
  if (mime.value.startsWith('image/')) return 'image'
  if (mime.value === 'application/pdf' || name.endsWith('.pdf')) return 'pdf'
  if (mime.value === 'text/html' || HTML_EXT.test(name)) return 'html'
  if (mime.value.startsWith('video/') || VIDEO_EXT.test(name)) return 'video'
  if (mime.value.startsWith('audio/') || AUDIO_EXT.test(name)) return 'audio'
  if (mime.value === 'text/markdown' || MD_EXT.test(name)) return 'markdown'
  if (mime.value.startsWith('text/') || TEXT_EXT.test(name)) return 'text'
  if (mime.value.includes('officedocument') || mime.value.includes('msword')
    || mime.value.includes('ms-powerpoint') || OFFICE_EXT.test(name)) return 'office'
  return 'unknown'
})
/** Office 走在线预览的条件：文件链接公网可达（私有桶预签名 URL 即满足） */
const officePreviewable = computed(() => kind.value === 'office' && isPubliclyReachable.value)
const officeReason = computed(() => kind.value === 'office'
  ? '（Office 在线预览需文件链接公网可访问；当前为内网/本地链接）' : '')
const officeViewerUrl = computed(() => officePreviewable.value
  ? `https://view.officeapps.live.com/op/view.aspx?src=${encodeURIComponent(publicAbsoluteUrl.value)}` : '')

const renderedHtml = computed(() => markdownHtml.value)
const highlightedText = computed(() => plainText.value)

// ── 窗口尺寸：默认加大，可一键最大化 ────────────────────────────────────────
const isMaximized = ref(false)
const modalWidth = computed(() => (kind.value === 'office' || kind.value === 'pdf' || kind.value === 'html' ? 1200 : 1080))
const title = computed(() => {
  if (!props.file) return '文件预览'
  const pos = props.total ? `${(props.index ?? 0) + 1} / ${props.total} — ` : ''
  return pos + fileName.value
})

// ── Markdown / 文本内容加载 ────────────────────────────────────────────────
const MAX_INLINE_BYTES = 2 * 1024 * 1024

async function loadBody() {
  markdownHtml.value = ''
  plainText.value = ''
  const f = props.file
  if (!f || !['markdown', 'text'].includes(kind.value)) return
  loadingBody.value = true
  try {
    const resp = await fetch(src.value)
    const buf = await resp.arrayBuffer()
    if (buf.byteLength > MAX_INLINE_BYTES) {
      plainText.value = '// 文件超过 2MB，请下载后查看'
      return
    }
    const text = new TextDecoder('utf-8').decode(buf)
    if (kind.value === 'markdown') {
      const { default: MarkdownIt } = await import('markdown-it')
      const { default: DOMPurify } = await import('dompurify')
      const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
      markdownHtml.value = DOMPurify.sanitize(md.render(text))
    } else {
      try {
        const hljs = (await import('highlight.js')).default
        await import('highlight.js/styles/github.css')
        const lang = fileName.value.split('.').pop()?.toLowerCase() || ''
        if (lang && hljs.getLanguage(lang)) {
          plainText.value = hljs.highlight(text, { language: lang }).value
          return
        }
      } catch { /* 降级为纯文本 */ }
      plainText.value = escapeHtml(text)
    }
  } catch (e) {
    plainText.value = `// 预览内容加载失败：${e instanceof Error ? e.message : String(e)}`
  } finally {
    loadingBody.value = false
  }
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

watch(() => [props.open, props.file?.id], ([open]) => {
  if (open) loadBody()
})
</script>

<style scoped lang="less">
.preview-title-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-right: 28px; }
.preview-title-text { font-size: 15px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-body { min-height: 420px; display: grid; place-items: center; }
.preview-image { max-width: 100%; max-height: 76vh; object-fit: contain; }
.preview-frame { width: 100%; height: 76vh; border: 0; }
.preview-audio { width: 100%; }
.preview-markdown {
  width: 100%; max-height: 76vh; overflow: auto; padding: 4px 8px;
  font-size: 14px; line-height: 1.7; color: var(--fg);
  :deep(h1, h2, h3) { margin: 14px 0 8px; font-weight: 600; }
  :deep(p) { margin: 8px 0; }
  :deep(pre) { background: var(--bg); padding: 10px; border-radius: 6px; overflow: auto; }
  :deep(code) { font-family: Consolas, Monaco, monospace; font-size: 13px; }
  :deep(table) { border-collapse: collapse; margin: 10px 0; :deep(td), :deep(th) { border: 1px solid var(--border); padding: 4px 10px; } }
  :deep(img) { max-width: 100%; }
  :deep(blockquote) { border-left: 3px solid var(--accent); margin: 8px 0; padding: 2px 12px; color: var(--fg-secondary); }
}
.preview-text {
  width: 100%; max-height: 76vh; overflow: auto; margin: 0;
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  padding: 12px 14px; font-size: 13px; line-height: 1.6;
  code { font-family: Consolas, Monaco, monospace; white-space: pre; }
}
.preview-fallback { display: flex; flex-direction: column; align-items: center; gap: 12px; color: var(--fg-secondary); }
.preview-fallback__icon { font-size: 48px; color: var(--fg-muted, var(--fg-secondary)); }
.preview-loading { display: grid; place-items: center; padding: 12px; }
</style>

<!-- 最大化态作用于 Modal teleport 到 body 的 wrap，需全局样式 -->
<style lang="less">
.preview-maximized {
  .ant-modal {
    max-width: 100vw;
    width: 100vw !important;
    top: 0;
    padding-bottom: 0;
    margin: 0 auto;
  }
  .ant-modal-content { display: flex; flex-direction: column; min-height: 100vh; border-radius: 0; }
  .ant-modal-body { flex: 1; overflow: auto; }
  .preview-body { min-height: calc(100vh - 100px); }
  .preview-frame, .preview-markdown, .preview-text { max-height: calc(100vh - 130px); height: calc(100vh - 130px); }
  .preview-image { max-height: calc(100vh - 130px); }
}
</style>
