<template>
  <div class="mask" v-if="show">
    <div class="modal">
      <div class="mh">＋ 新建推演场景<div class="spacer"></div><span style="font-size:10.5px;color:var(--fg3)">从已发布本体应用克隆世界状态</span></div>
      <div class="mb">
        <div class="field"><label>世界来源本体（已发布）</label>
          <select v-model="form.ontology_id">
            <option :value="undefined" disabled>请选择已发布本体</option>
            <option v-for="o in ontologies" :key="o.id" :value="o.id">{{ o.name }}（{{ o.code }} · v{{ o.current_version }}）</option>
          </select>
          <div class="note" v-if="!ontologies.length">暂无已发布本体，请先在本体建模工作台发布</div>
        </div>
        <div class="field"><label>场景名称</label><input v-model="form.name" placeholder="如：SUP006 断供风险传导" /></div>
        <div class="field"><label>Tick 上限</label><input type="number" v-model.number="form.tick_max" min="1" max="1000" /></div>
      </div>
      <div class="mf"><button class="btn" @click="emit('cancel')">取消</button>
        <button class="btn pri" @click="submit" :disabled="busy || !form.ontology_id || !form.name.trim()">创建并克隆</button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'

// 新建场景模态：表单态在本组件内，克隆调用由壳发起。
interface OntologyOption { id: number; code: string; name: string; current_version: number }

const props = defineProps<{
  show: boolean
  ontologies: OntologyOption[]
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'create', payload: { ontology_id: number; name: string; tick_max: number }): void
}>()

const form = reactive<{ ontology_id?: number; name: string; tick_max: number }>({
  ontology_id: undefined, name: '', tick_max: 12,
})

// 每次关闭后重置名称，保持与原 monolith 一致的「创建后清空名称」行为
watch(() => props.show, (open) => { if (!open) form.name = '' })

function submit() {
  if (!form.ontology_id || !form.name.trim()) return
  emit('create', { ontology_id: form.ontology_id, name: form.name.trim(), tick_max: form.tick_max })
  form.name = ''
}
</script>
