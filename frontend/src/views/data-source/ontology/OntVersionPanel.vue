<template>
  <div class="ont-version">
    <!-- 发布动作 -->
    <a-card size="small" :title="t2('发布新版本')" class="ont-version__publish">
      <a-space direction="vertical" style="width: 100%">
        <a-textarea v-model:value="changeNote" :rows="2" :placeholder="t2('变更说明（可选）')" />
        <a-checkbox v-model:checked="overridePending">
          {{ t2('忽略待审项，仅发布已采纳（门禁 1）') }}
        </a-checkbox>
        <a-alert v-if="gateError" type="error" show-icon :message="t2('发布被门禁阻断')" :description="gateError" />
        <a-button type="primary" :loading="publishing" @click="doPublish">{{ t2('发布') }}</a-button>
      </a-space>
    </a-card>

    <a-row :gutter="12">
      <a-col :span="9">
        <a-card size="small" :title="t2('版本时间线')">
          <a-spin :spinning="loadingList">
            <a-empty v-if="!versions.length" :description="t2('尚无发布版本')" />
            <a-timeline v-else>
              <a-timeline-item
                v-for="v in versions"
                :key="v.version"
                :color="v.gate_passed === false ? 'red' : 'green'"
              >
                <a @click="selectVersion(v.version)">
                  <b>v{{ v.version }}</b>
                  <span class="ont-version__meta">{{ v.created_at ? v.created_at.slice(0, 10) : '' }}</span>
                </a>
                <div class="ont-version__counts">
                  {{ t2('对象') }} {{ v.counts?.objects }} · {{ t2('关系') }} {{ v.counts?.relations }} · {{ t2('属性') }} {{ v.counts?.properties }}
                </div>
                <div v-if="v.change_note" class="ont-version__note">{{ v.change_note }}</div>
              </a-timeline-item>
            </a-timeline>
          </a-spin>
        </a-card>
      </a-col>
      <a-col :span="15">
        <a-card size="small" :title="selected ? `v${selected} ${t2('详情')}` : t2('选择版本查看详情')">
          <a-spin :spinning="loadingDetail">
            <template v-if="detail">
              <h4>{{ t2('门禁结论（5 项）') }}</h4>
              <a-table row-key="name" size="small" :pagination="false" :columns="gateCols" :data-source="gateRows" />
              <h4 style="margin-top: 16px">{{ t2('与上一版差异') }}</h4>
              <pre class="ont-version__diff">{{ pretty(detail.diff_json) }}</pre>
            </template>
            <a-empty v-else :description="t2('未选择版本')" />
          </a-spin>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 版本面板（E11 发布 + E12 列表 + E13 快照）：门禁 5 项结论 + diff + 发布触发。
 * 回滚为 P1（§6.1 E14 未列 P0），此处不提供。
 */
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { publishOntology, listOntologyVersions, getOntologyVersion } from '@/api/dataops'
import { t2 } from './ontologyText'

const props = defineProps<{ ontologyId: number | null }>()
const emit = defineEmits<{ (e: 'published'): void }>()

const versions = ref<any[]>([])
const detail = ref<any>(null)
const selected = ref<number | null>(null)
const loadingList = ref(false)
const loadingDetail = ref(false)
const publishing = ref(false)
const changeNote = ref('')
const overridePending = ref(false)
const gateError = ref('')

const gateCols = [
  { title: t2('检查项'), dataIndex: 'name', key: 'name' },
  { title: t2('结果'), key: 'result', width: 90 },
  { title: t2('原因'), dataIndex: 'reason', key: 'reason' },
]

const gateRows = computed(() => {
  const checks = detail.value?.gate_json?.checks || []
  return checks.map((c: any) => ({ ...c, key: c.name }))
})

function pretty(v: any) {
  return v ? JSON.stringify(v, null, 2) : t2('（首个版本，无差异基线）')
}

async function reload() {
  if (!props.ontologyId) return
  loadingList.value = true
  try {
    versions.value = (await listOntologyVersions(props.ontologyId)) as any[]
  } finally {
    loadingList.value = false
  }
}

async function selectVersion(v: number) {
  selected.value = v
  loadingDetail.value = true
  try {
    detail.value = await getOntologyVersion(props.ontologyId!, v)
  } finally {
    loadingDetail.value = false
  }
}

async function doPublish() {
  if (!props.ontologyId) return
  publishing.value = true
  gateError.value = ''
  try {
    const resp: any = await publishOntology(props.ontologyId, {
      change_note: changeNote.value || undefined,
      override_pending: overridePending.value,
    })
    message.success(t2('发布成功'))
    changeNote.value = ''
    overridePending.value = false
    emit('published')
    await reload()
    if (resp?.version) selectVersion(resp.version)
  } catch (e: any) {
    // ApiError → {code,message,detail}；拦截器已弹 message，这里补门禁明细
    const data = e?.response?.data
    if (data?.detail?.blocked_reasons) gateError.value = JSON.stringify(data.detail.blocked_reasons)
  } finally {
    publishing.value = false
  }
}

watch(() => props.ontologyId, () => { selected.value = null; detail.value = null; reload() }, { immediate: true })
</script>

<style lang="less" scoped>
.ont-version {
  &__publish {
    margin-bottom: 12px;
  }
  &__meta {
    margin-left: 8px;
    color: var(--fg-mute, #999);
    font-size: 12px;
  }
  &__counts,
  &__note {
    font-size: 12px;
    color: var(--fg-mute, #999);
  }
  &__diff {
    background: var(--bg-subtle, #fafafa);
    padding: 8px;
    border-radius: 6px;
    font-size: 12px;
    max-height: 360px;
    overflow: auto;
  }
}
</style>
