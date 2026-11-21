<template>
  <div class="mgr">
    <div class="mgr-bar">
      <a-button type="primary" size="small" @click="addChannel">＋ 新增渠道</a-button>
      <span class="hint">点击渠道行展开配置 · 开关控制启用 · 变更实时同步至语音会话</span>
      <span class="spacer"></span>
      <span class="sync">同步状态：<b :class="syncClass">{{ syncLabel }}</b></span>
    </div>

    <div class="mgr-body">
      <template v-for="(group, gname) in groupedChannels" :key="gname">
        <div class="section-label">{{ gname }}</div>
        <div
          v-for="ch in group"
          :key="ch.key"
          class="ch-card"
          :class="{ on: ch.active, open: expanded.has(ch.key) }"
        >
          <div class="ch-main">
            <div class="ch-ic">{{ ch.icon }}</div>
            <div class="ch-info">
              <div class="ch-nm">
                {{ ch.name }}
                <span :class="['st', stateClass(ch)]">{{ stateLabel(ch) }}</span>
                <span v-if="ch.capability === 'pending_backend'" class="st warn">模拟分发</span>
              </div>
              <div class="ch-desc">{{ ch.desc }}</div>
            </div>
            <a-select
              :value="ch.output"
              size="small"
              class="ch-output"
              :options="outputModeOptions"
              @click.stop
              @change="(v: OutputMode) => emit('changeOutput', { key: ch.key, output: v })"
            />
            <div class="switch" :class="{ on: ch.active }" @click.stop="emit('toggle', ch.key)"></div>
            <span class="icon-btn" @click.stop="toggleExpand(ch.key)">{{ expanded.has(ch.key) ? '▴' : '▾' }}</span>
          </div>

          <div class="ch-detail">
            <div class="stat-row" v-if="ch.stats">
              <div class="stat"><div class="k">今日分发</div><div class="v">{{ ch.stats.dispatched }}</div></div>
              <div class="stat"><div class="k">成功数</div><div class="v ok">{{ ch.stats.succeeded }}</div></div>
              <div class="stat"><div class="k">成功率</div><div class="v ok">{{ ch.stats.successRate }}</div></div>
              <div class="stat"><div class="k">输出模式</div><div class="v small">{{ outputLabel(ch.output) }}</div></div>
            </div>
            <div v-if="ch.capability === 'pending_backend'" class="cap-tip">⚠ 真实外发待后端启用（当前为模拟分发，不会实际发送消息）</div>
            <div v-if="ch.capability === 'unsupported'" class="cap-tip err">✖ 暂不支持真实发送：后端未接入该渠道能力，启用后仅记录日志</div>
            <div class="detail-actions">
              <a-button size="small" @click="emit('test', ch.key)">▶ 测试发送</a-button>
              <a-button size="small" @click="editChannel(ch)">编辑配置</a-button>
              <a-button size="small" danger @click="emit('remove', ch.key)">删除</a-button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ChannelItem, OutputMode } from '../types'
import { OUTPUT_MODE_LABEL } from '../types'

const props = defineProps<{
  channels: ChannelItem[]
  syncState: 'idle' | 'pending' | 'acked'
}>()

const emit = defineEmits<{
  toggle: [key: string]
  changeOutput: [payload: { key: string; output: OutputMode }]
  add: [channel: ChannelItem]
  remove: [key: string]
  update: [channel: ChannelItem]
  test: [key: string]
}>()

const expanded = ref<Set<string>>(new Set())
const outputModeOptions: Array<{ value: OutputMode; label: string }> = [
  { value: 'text', label: OUTPUT_MODE_LABEL.text },
  { value: 'voice', label: OUTPUT_MODE_LABEL.voice },
  { value: 'both', label: OUTPUT_MODE_LABEL.both },
  { value: 'off', label: OUTPUT_MODE_LABEL.off },
]

const groupedChannels = computed(() => {
  const im = ['wechat', 'whatsapp', 'telegram']
  return {
    '即时通信渠道': props.channels.filter((c) => im.includes(c.key)),
    '其他渠道': props.channels.filter((c) => !im.includes(c.key)),
  }
})

const syncLabel = computed(() => {
  if (props.syncState === 'pending') return '已下发（本地）· 等待 ACK'
  if (props.syncState === 'acked') return '后端已确认'
  return '已下发（本地）'
})
const syncClass = computed(() => (props.syncState === 'acked' ? 'ok' : props.syncState === 'pending' ? 'warn' : ''))

function toggleExpand(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

function stateClass(ch: ChannelItem): string {
  const map: Record<string, string> = {
    enabled: 'ok', configured: 'cfg', pending_backend: 'warn', unsupported: 'err',
  }
  return ch.active ? 'ok' : map[ch.capability] || 'off'
}

function stateLabel(ch: ChannelItem): string {
  if (!ch.active) return ch.capability === 'unsupported' ? '暂不支持' : '未启用'
  return ch.capability === 'pending_backend' ? '已启用 · 模拟' : '已启用'
}

function outputLabel(o: OutputMode): string {
  return OUTPUT_MODE_LABEL[o] || o
}

function addChannel() {
  const key = `custom_${Date.now()}`
  const ch: ChannelItem = {
    key,
    name: '新渠道',
    icon: '🔗',
    desc: '自定义输出渠道',
    active: false,
    output: 'text',
    capability: 'pending_backend',
    lastValidOutput: 'text',
    stats: { dispatched: 0, succeeded: 0, successRate: '—' },
  }
  emit('add', ch)
  expanded.value = new Set([...expanded.value, key])
}

function editChannel(ch: ChannelItem) {
  const name = window.prompt('渠道名称', ch.name)
  if (name && name.trim()) emit('update', { ...ch, name: name.trim() })
}
</script>

<style scoped>
.mgr { display: flex; flex-direction: column; }
.mgr-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; border-bottom: 1px solid #374151; flex-wrap: wrap;
}
.mgr-bar .hint { font-size: 11px; color: #6b7280; }
.mgr-bar .spacer { flex: 1; }
.sync { font-size: 11px; color: #9ca3af; }
.sync b { color: #9ca3af; font-weight: 400; }
.sync b.ok { color: #6ee7b7; }
.sync b.warn { color: #fcd34d; }
.mgr-body { padding: 12px; max-height: 520px; overflow-y: auto; }
.section-label { font-size: 10px; color: #6b7280; letter-spacing: 1px; margin: 2px 2px 7px; text-transform: uppercase; }
.ch-card { background: #1f2937; border: 1px solid #374151; border-radius: 10px; margin-bottom: 9px; overflow: hidden; transition: 0.2s; }
.ch-card.on { border-color: rgba(16, 185, 129, 0.5); }
.ch-main { display: flex; align-items: center; gap: 9px; padding: 10px 12px; }
.ch-ic { font-size: 18px; width: 24px; text-align: center; }
.ch-info { flex: 1; min-width: 0; }
.ch-nm { font-weight: 600; font-size: 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ch-desc { font-size: 10px; color: #9ca3af; margin-top: 1px; }
.st { font-size: 9px; padding: 1px 6px; border-radius: 6px; white-space: nowrap; }
.st.ok { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; }
.st.cfg { background: rgba(59, 130, 246, 0.16); color: #93c5fd; }
.st.off { background: rgba(148, 163, 184, 0.14); color: #9ca3af; }
.st.warn { background: rgba(245, 158, 11, 0.16); color: #fcd34d; }
.st.err { background: rgba(239, 68, 68, 0.16); color: #fca5a5; }
.ch-output { width: 110px; }
.switch { width: 30px; height: 16px; border-radius: 10px; background: #374151; position: relative; cursor: pointer; flex-shrink: 0; transition: 0.2s; }
.switch::after { content: ''; position: absolute; width: 12px; height: 12px; border-radius: 50%; background: #9ca3af; top: 2px; left: 2px; transition: 0.2s; }
.switch.on { background: #10b981; }
.switch.on::after { left: 16px; background: #fff; }
.icon-btn { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 2px 5px; font-size: 13px; }
.icon-btn:hover { color: #e5e7eb; }
.ch-detail { display: none; border-top: 1px solid #374151; padding: 10px 12px; background: rgba(0, 0, 0, 0.15); }
.ch-card.open .ch-detail { display: block; }
.stat-row { display: flex; gap: 16px; flex-wrap: wrap; }
.stat { flex: 1; min-width: 90px; background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 7px 10px; }
.stat .k { font-size: 10px; color: #6b7280; }
.stat .v { font-size: 16px; font-weight: 600; color: #818cf8; margin-top: 2px; }
.stat .v.ok { color: #6ee7b7; }
.stat .v.small { font-size: 12px; }
.cap-tip { font-size: 10px; color: #fcd34d; margin-top: 6px; }
.cap-tip.err { color: #fca5a5; }
.detail-actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
</style>
