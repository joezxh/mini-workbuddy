<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? t('skillMgmt.editRule') : t('skillMgmt.newRule')"
    :width="800"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :ok-text="t('common.save')"
    :cancel-text="t('common.cancel')"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      :label-col="{ span: 5 }"
      :wrapper-col="{ span: 18 }"
    >
      <a-form-item :label="t('skillHub.ruleName')" name="name">
        <a-input v-model:value="formData.name" :placeholder="t('skillMgmt.ruleNamePlaceholder')" />
      </a-form-item>

      <a-form-item :label="t('skillMgmt.package')" name="package_id">
        <a-select
          v-model:value="formData.package_id"
          :placeholder="t('skillMgmt.selectPackage')"
          :loading="loadingPackages"
          show-search
          :filter-option="filterPackageOption"
          allow-clear
        >
          <a-select-option
            v-for="pkg in skillPackages"
            :key="pkg.package_id"
            :value="pkg.package_id"
          >
            {{ pkg.name }} ({{ pkg.package_id }})
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="t('skillMgmt.agent')" name="agent_name">
        <a-input
          v-model:value="formData.agent_name"
          :placeholder="t('skillMgmt.agentPlaceholder')"
          allow-clear
        />
      </a-form-item>

      <a-form-item :label="t('skillHub.rulePriority')" name="priority">
        <div style="display: flex; align-items: center; gap: 8px;">
          <a-input-number
            v-model:value="formData.priority"
            :min="1"
            :max="9999"
            style="width: 200px"
          />
          <span class="form-hint" style="margin: 0">{{ t('skillMgmt.priorityHint') }}</span>
        </div>
      </a-form-item>

      <a-form-item :label="t('skillHub.ruleConditions')" :wrapper-col="{ span: 18, offset: 0 }">
        <div class="conditions-builder">
          <a-form
            :label-col="{ span: 6 }"
            :wrapper-col="{ span: 17 }"
            style="background: transparent"
          >
            <a-form-item :label="t('skillMgmt.eventType')">
              <a-select
                v-model:value="formData.conditions.event_types"
                mode="tags"
                :placeholder="t('skillMgmt.eventTypePlaceholder')"
                style="width: 100%"
                allow-clear
              />
            </a-form-item>

            <a-form-item :label="t('skillMgmt.keywords')">
              <a-select
                v-model:value="formData.conditions.keywords"
                mode="tags"
                :placeholder="t('skillMgmt.keywordsPlaceholder')"
                style="width: 100%"
                allow-clear
              />
            </a-form-item>

            <a-form-item :label="t('skillMgmt.timeRange')">
              <div style="display: flex; align-items: center; gap: 8px;">
                <a-time-picker
                  v-model:value="formData.conditions.time_start"
                  format="HH:mm"
                  :placeholder="t('skillMgmt.start')"
                  style="width: 120px"
                />
                <span style="color: var(--fg-muted)">~</span>
                <a-time-picker
                  v-model:value="formData.conditions.time_end"
                  format="HH:mm"
                  :placeholder="t('skillMgmt.end')"
                  style="width: 120px"
                />
              </div>
            </a-form-item>

            <a-form-item :label="t('skillMgmt.riskLevelGte')">
              <a-input-number
                v-model:value="formData.conditions.risk_level_gte"
                :min="0"
                :max="5"
                style="width: 200px"
              />
            </a-form-item>

            <a-form-item :label="t('skillMgmt.customConditions')">
              <a-textarea
                v-model:value="customConditionsJson"
                placeholder='{"region": "华东"}'
                :auto-size="{ minRows: 2, maxRows: 4 }"
                @change="handleCustomConditionsChange"
              />
            </a-form-item>
          </a-form>
        </div>
      </a-form-item>

      <a-form-item :label="t('skillMgmt.activeStatus')">
        <a-switch
          v-model:checked="formData.is_active"
          :checked-children="t('skillHub.enabled')"
          :un-checked-children="t('skillHub.disabled')"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import dayjs, { Dayjs } from 'dayjs'
import {
  createSkillRule,
  updateSkillRule,
  type SkillRule,
} from '@/api/skillRule'
import { getSkills, type SkillPackage } from '@/api/skill'

const props = defineProps<{
  ruleId?: number
  ruleData?: SkillRule | null
  defaultAgentName?: string
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const { t } = useI18n()
const submitting = ref(false)
const loadingPackages = ref(false)
const formRef = ref<any>(null)
const customConditionsJson = ref<string>('')

// 动态加载的数据
const skillPackages = ref<SkillPackage[]>([])

const isEdit = computed(() => !!props.ruleId)

const formData = reactive({
  name: '',
  package_id: '',
  agent_name: '',
  priority: 100,
  is_active: true,
  conditions: {
    event_types: [] as string[],
    keywords: [] as string[],
    time_start: undefined as Dayjs | undefined,
    time_end: undefined as Dayjs | undefined,
    risk_level_gte: undefined as number | undefined,
    context_match: {} as Record<string, any>,
  },
})

const rules = computed(() => ({
  name: [{ required: true, message: t('skillMgmt.ruleNameRequired') }],
  package_id: [{ required: true, message: t('skillMgmt.packageRequired') }],
  priority: [{ required: true, message: t('skillMgmt.priorityRequired') }],
}))

watch(() => visible.value, (val) => {
  if (val) {
    initForm()
    loadSkillPackages()
  }
})

watch(() => props.ruleData, (val) => {
  if (val) initForm()
})

// ── 动态加载技能包列表 ─────────────────────────────────────────────────────────
async function loadSkillPackages() {
  loadingPackages.value = true
  try {
    const res = await getSkills() as any
    skillPackages.value = res.packages || res.items || []
  } catch (e: any) {
    message.error(t('skillMgmt.loadPackagesFailed') + (e.message || ''))
    skillPackages.value = []
  } finally {
    loadingPackages.value = false
  }
}

// ── 搜索过滤 ───────────────────────────────────────────────────────────────────
function filterPackageOption(input: string, option: any) {
  const label = option.children?.[0]?.children || ''
  return String(label).toLowerCase().includes(input.toLowerCase())
}

function initForm() {
  if (props.ruleData) {
    Object.assign(formData, {
      name: props.ruleData.name,
      package_id: props.ruleData.package_id,
      agent_name: props.ruleData.agent_name || '',
      priority: props.ruleData.priority,
      is_active: props.ruleData.is_active,
    })
    const cond = props.ruleData.conditions || {}
    formData.conditions = {
      event_types: cond.event_types || [],
      keywords: cond.keywords || [],
      time_start: cond.time_range?.start ? dayjs(cond.time_range.start, 'HH:mm') : undefined,
      time_end: cond.time_range?.end ? dayjs(cond.time_range.end, 'HH:mm') : undefined,
      risk_level_gte: cond.context_match?.risk_level?.['$gte'],
      context_match: cond.context_match || {},
    }
    customConditionsJson.value = JSON.stringify(formData.conditions.context_match, null, 2)
  } else {
    Object.assign(formData, {
      name: '',
      package_id: '',
      agent_name: props.defaultAgentName || '',
      priority: 100,
      is_active: true,
    })
    formData.conditions = {
      event_types: [],
      keywords: [],
      time_start: undefined,
      time_end: undefined,
      risk_level_gte: undefined,
      context_match: {},
    }
    customConditionsJson.value = '{}'
  }
}

function handleCustomConditionsChange() {
  try {
    const parsed = JSON.parse(customConditionsJson.value || '{}')
    formData.conditions.context_match = parsed
  } catch {
    message.warning(t('skillMgmt.customJsonError'))
  }
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    // 构造后端需要的 conditions 结构
    const conditions: Record<string, any> = {}
    if (formData.conditions.event_types?.length) {
      conditions.event_types = formData.conditions.event_types
    }
    if (formData.conditions.keywords?.length) {
      conditions.keywords = formData.conditions.keywords
    }
    if (formData.conditions.time_start || formData.conditions.time_end) {
      conditions.time_range = {
        start: formData.conditions.time_start?.format('HH:mm') || '',
        end: formData.conditions.time_end?.format('HH:mm') || '',
      }
    }
    if (formData.conditions.risk_level_gte !== undefined && formData.conditions.risk_level_gte !== null) {
      conditions.context_match = {
        ...formData.conditions.context_match,
        risk_level: { $gte: formData.conditions.risk_level_gte },
      }
    } else if (Object.keys(formData.conditions.context_match || {}).length > 0) {
      conditions.context_match = formData.conditions.context_match
    }

    const payload = {
      name: formData.name,
      package_id: formData.package_id,
      agent_name: formData.agent_name || undefined,
      priority: formData.priority,
      is_active: formData.is_active,
      conditions,
    }

    if (isEdit.value && props.ruleId) {
      await updateSkillRule(props.ruleId, payload)
      message.success(t('skillMgmt.updateSuccess'))
    } else {
      await createSkillRule(payload)
      message.success(t('skillMgmt.createSuccess'))
    }

    emit('success')
  } catch (e: any) {
    message.error((isEdit.value ? t('skillMgmt.updateFailed') : t('skillMgmt.createFailed')) + (e.message || t('skillHub.unknownError')))
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  formRef.value?.resetFields()
}
</script>

<style scoped lang="less">
.conditions-builder {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 12px;
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--fg-muted);
  margin-top: 4px;
}
</style>