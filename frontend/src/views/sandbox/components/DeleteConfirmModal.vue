<template>
  <div class="mask" v-if="show">
    <div class="modal" style="width:380px">
      <div class="mh" style="color:var(--err)">🗑 删除推演沙盘</div>
      <div class="mb" style="font-size:12px;color:var(--fg2);line-height:1.7">
        将永久删除场景「{{ sceneName }}」及其 <b style="color:var(--fg)">{{ checkpointCount }} 个检查点 / {{ branchCount }} 个分支</b>，克隆的沙箱世界状态会一并回收。此操作不可撤销。
      </div>
      <div class="mf"><button class="btn" @click="emit('cancel')">取消</button><button class="btn danger" @click="emit('confirm')">确认删除</button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 删除沙盘确认模态：仅回传 cancel / confirm，删除调用由壳执行。
defineProps<{
  show: boolean
  sceneName: string
  checkpointCount: number
  branchCount: number
}>()

const emit = defineEmits<{ (e: 'cancel'): void; (e: 'confirm'): void }>()
</script>
