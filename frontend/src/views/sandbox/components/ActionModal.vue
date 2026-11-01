<template>
  <div class="mask" :class="{ on: show }">
    <div class="modal">
      <div class="mh">⚡ 施加行动到世界状态<div class="spacer"></div><span style="font-size:10.5px;color:var(--fg3)">行动写入沙箱，不影响生产本体</span></div>
      <div class="mb">
        <div class="field"><label>目标实体</label>
          <select :value="target" @change="emit('update:target', ($event.target as HTMLSelectElement).value)">
            <option v-for="e in entities" :key="e.entity_code" :value="e.entity_code">{{ entityDisplayName(entities, e.entity_code) }} · {{ e.object_code }}{{ e.masked ? '（脱敏）' : '' }}</option>
          </select>
          <div class="note" :class="{ lock: noteLock }">{{ note }}</div>
        </div>
        <div class="field"><label>行动类型</label>
          <select :value="template" @change="emit('update:template', ($event.target as HTMLSelectElement).value)">
            <option v-for="tp in templates" :key="tp.code" :value="tp.code">{{ tp.name }}（{{ tp.code }}）</option>
          </select>
        </div>
        <div class="field" v-for="p in paramFields" :key="p.key"><label>{{ p.label }}</label>
          <input :value="params[p.key]" :placeholder="p.hint"
            @input="emit('update:params', { ...params, [p.key]: ($event.target as HTMLInputElement).value })" />
        </div>
      </div>
      <div class="mf"><button class="btn" @click="emit('cancel')">取消</button>
        <button class="btn pri" @click="emit('submit')" :disabled="!target || !template">施加并推进 Tick</button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ActionTemplate, WorldEntity } from '@/api/sandbox'
import { entityDisplayName } from '../sandboxView'

// 施加行动模态：表单态由壳持有（target/template/params），本组件只做双向回传。
defineProps<{
  show: boolean
  entities: WorldEntity[]
  templates: ActionTemplate[]
  target: string
  template: string
  paramFields: { key: string; label: string; hint: string }[]
  params: Record<string, any>
  note: string
  noteLock: boolean
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit'): void
  (e: 'update:target', v: string): void
  (e: 'update:template', v: string): void
  (e: 'update:params', v: Record<string, any>): void
}>()
</script>
