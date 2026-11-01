<template>
  <div class="col">
    <div class="ptabs">
      <button v-for="t in advisorTabs" :key="t.k" class="ptab" :class="{ on: aview === t.k }" @click="emit('set-view', t.k)">{{ t.label }}</button>
    </div>
    <div class="pb" style="display:flex;flex-direction:column">
      <!-- chat -->
      <div v-if="aview === 'chat'" class="chat">
        <div class="msgs" ref="msgBox">
          <div v-for="(b, i) in chat" :key="i" class="bub" :class="b.who">
            <div class="bh"><span class="who">{{ b.who === 'u' ? '用户' : 'Agent' }}</span> {{ b.time }}<span v-if="b.run" class="run">（进行中…）</span></div>
            <div v-html="b.html"></div>
            <div v-if="b.evidence && b.evidence.length" class="tool">🔧 引用证据 {{ b.evidence.join(', ') }}{{ b.degraded ? '（LLM 降级 · 确定性摘要）' : '' }}</div>
          </div>
        </div>
        <div class="cmdchips">
          <span class="cmdchip" @click="emit('ask', '当前最高风险实体是什么？为何风险高？')">查看风险最高实体</span>
          <span class="cmdchip" @click="emit('ask', '解释因果传播路径与关键传导点')">解释传播路径</span>
        </div>
        <div class="chatbox">
          <input class="inp" :value="chatInput" placeholder="输入消息…（Enter 发送）"
            @input="emit('update:chatInput', ($event.target as HTMLInputElement).value)"
            @keydown.enter="emit('send')" />
          <button class="btn pri sm" :disabled="asking || !hasScene" @click="emit('send')">{{ asking ? '思考中…' : '发送' }}</button>
        </div>
      </div>
      <!-- audit -->
      <div v-else-if="aview === 'audit'" style="overflow:auto">
        <div class="sub">行动审计 · 本沙箱内</div>
        <div v-for="a in actionLogs" :key="a.id" class="obs" :class="a.gate_result === 'denied' ? 'err' : a.gate_result === 'pending' ? '' : 'info'">
          <div class="oh">T{{ a.tick }} · {{ a.gate_result }}</div>
          对 <code>{{ a.target_entity_code }}</code> 施加 <code>{{ a.template_code }}</code><span v-if="a.gate_reason"> · 原因 {{ a.gate_reason }}</span>
        </div>
        <div v-if="!actionLogs.length" class="empty"><div class="ic">📋</div>暂无行动记录<div style="margin-top:4px">施加行动后，所有对世界状态的改变都会在此留痕，可回放审计</div></div>
        <div class="obs info" style="margin-top:4px"><div class="oh">隔离声明</div>沙箱世界为生产本体的克隆快照，行动写入沙箱代理键，不回写生产。</div>
      </div>
      <!-- rec -->
      <div v-else style="overflow:auto">
        <div class="sub">推荐问答 · 基于当前场景</div>
        <div v-for="q in recommendations" :key="q" class="scard" style="cursor:pointer" @click="emit('ask', q)">
          <div class="sh"><span class="tag p">Q</span><b style="white-space:normal">{{ q }}</b></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { ActionLog } from '@/api/sandbox'

// AI 顾问台列（col ④）：对话 / 行动审计 / 推荐问答。问答请求上抛由壳调用 advisor API。
type AdvisorView = 'chat' | 'audit' | 'rec'
type ChatBubble = {
  who: 'u' | 'a'; time: string; html: string; run?: boolean; evidence?: number[]; degraded?: boolean
}

const props = defineProps<{
  aview: AdvisorView
  chat: ChatBubble[]
  chatInput: string
  asking: boolean
  actionLogs: ActionLog[]
  recommendations: string[]
  hasScene: boolean
}>()

const emit = defineEmits<{
  (e: 'set-view', v: AdvisorView): void
  (e: 'ask', q: string): void
  (e: 'send'): void
  (e: 'update:chatInput', v: string): void
}>()

const advisorTabs = [
  { k: 'chat', label: '推演对话' }, { k: 'audit', label: '行动审计' }, { k: 'rec', label: '推荐问答' },
] as const

// 对话气泡滚动到底部属本列局部 DOM 行为，随 chat 变化自动执行
const msgBox = ref<HTMLElement | null>(null)
watch(() => props.chat, async () => {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}, { deep: true, flush: 'post' })
</script>
