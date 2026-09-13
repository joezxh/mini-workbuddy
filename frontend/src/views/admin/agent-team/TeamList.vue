<template>
  <div class="team-list-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">{{ t('teamMgmt.title') }}</h2>
        <p class="page-sub">{{ t('teamMgmt.subtitle') }}</p>
      </div>
      <a-button type="primary" @click="openCreateModal">
        <PlusOutlined /> {{ t('teamMgmt.createTeam') }}
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="team-grid">
        <a-card
          v-for="team in teams"
          :key="team.id"
          class="team-card"
          hoverable
          @click="goEditor(team.id)"
        >
          <template #title>
            <div class="card-title">
              <ApartmentOutlined />
              <span>{{ team.name || team.team_name }}</span>
            </div>
          </template>
          <template #extra>
            <div @click.stop @mousedown.stop @pointerdown.stop>
              <a-switch
                :checked="team.is_active"
                :checked-children="t('skillHub.enabled')"
                :un-checked-children="t('teamMgmt.off')"
                size="small"
                @change="(val: boolean) => toggleActive(team, val)"
              />
            </div>
          </template>
          <div class="card-body">
            <p class="card-code">{{ team.team_code }}</p>
            <p class="card-desc">{{ team.description || t('agentMgmt.noDescription') }}</p>
            <div class="card-meta">
              <a-tag v-if="team.category">{{ team.category }}</a-tag>
              <span class="member-count">
                <TeamOutlined /> {{ t('teamMgmt.memberCount', { count: team.member_count || 0 }) }}
              </span>
            </div>
          </div>
          <template #actions>
            <a-button type="link" size="small" @click.stop="goEditor(team.id)">
              <EditOutlined /> {{ t('teamMgmt.orchestrate') }}
            </a-button>
            <a-button type="link" size="small" danger @click.stop="confirmDelete(team)">
              <DeleteOutlined /> {{ t('common.delete') }}
            </a-button>
          </template>
        </a-card>

        <a-card v-if="!loading && teams.length === 0" class="empty-card">
          <a-empty :description="t('teamMgmt.noTeams')" />
        </a-card>
      </div>
    </a-spin>

    <!-- 新建 / 编辑团队 -->
    <a-modal
      v-model:open="createVisible"
      :title="editingId ? t('teamMgmt.editTeam') : t('teamMgmt.createTeam')"
      @ok="submitCreate"
      @cancel="createVisible = false"
      :confirm-loading="submitting"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item :label="t('teamMgmt.teamCode')">
          <a-input v-model:value="form.team_code" :placeholder="t('teamMgmt.teamCodePlaceholder')" :disabled="!!editingId" />
        </a-form-item>
        <a-form-item :label="t('teamMgmt.teamName')" required>
          <a-input v-model:value="form.team_name" :placeholder="t('teamMgmt.teamNamePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('teamMgmt.category')">
          <a-input v-model:value="form.category" :placeholder="t('teamMgmt.categoryPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('skillHub.description')">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ApartmentOutlined,
  TeamOutlined,
  EditOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import * as api from '@/api/agentTeam'

const { t } = useI18n()
const teams = ref<api.TeamOut[]>([])
const loading = ref(false)
const createVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const form = ref({
  team_code: '',
  team_name: '',
  category: '',
  description: ''
})

const fetchTeams = async () => {
  loading.value = true
  try {
    const res = await api.listTeams({ is_active: undefined })
    teams.value = (res as any) || []
  } catch (e: any) {
    message.error(t('teamMgmt.loadListFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
  } finally {
    loading.value = false
  }
}

const openCreateModal = () => {
  editingId.value = null
  form.value = { team_code: '', team_name: '', category: '', description: '' }
  createVisible.value = true
}

const submitCreate = async () => {
  if (!form.value.team_name) {
    message.warning(t('teamMgmt.nameRequired'))
    return
  }
  submitting.value = true
  try {
    // 后端 TeamCreate 使用 name（团队编码留空由后端自动生成）
    const payload: api.TeamCreate = {
      name: form.value.team_name,
      description: form.value.description || undefined,
      category: form.value.category || undefined
    }
    if (!editingId.value && form.value.team_code) {
      payload.team_code = form.value.team_code
    }
    if (editingId.value) {
      await api.updateTeam(editingId.value, payload as any)
      message.success(t('teamMgmt.updated'))
    } else {
      await api.createTeam(payload)
      message.success(t('teamMgmt.created'))
    }
    createVisible.value = false
    fetchTeams()
  } catch (e: any) {
    message.error(t('teamMgmt.saveFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
  } finally {
    submitting.value = false
  }
}

const goEditor = (id: number) => {
  window.dispatchEvent(new CustomEvent('open-agent-team-editor', {
    detail: { teamId: id },
    bubbles: true
  }))
}

const toggleActive = async (team: api.TeamOut, val: boolean) => {
  try {
    await api.updateTeam(team.id, { is_active: val } as any)
    team.is_active = val
    message.success(val ? t('teamMgmt.enabledMsg') : t('teamMgmt.disabledMsg'))
  } catch (e: any) {
    message.error(t('teamMgmt.toggleFailed', { msg: e?.message || t('agentMgmt.unknownError') }))
    // 回滚 UI 状态
    team.is_active = !val
  }
}

const confirmDelete = (team: api.TeamOut) => {
  if (!window.confirm(t('teamMgmt.deleteConfirm', { name: team.name || team.team_name }))) return
  api.deleteTeam(team.id)
    .then(() => { message.success(t('teamMgmt.deleted')); fetchTeams() })
    .catch((e: any) => message.error(t('teamMgmt.deleteFailed', { msg: e?.message || t('agentMgmt.unknownError') })))
}

onMounted(fetchTeams)
</script>

<style scoped lang="less">
.team-list-page {
  padding: 20px 24px;
  height: 100%;
  overflow: auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.page-sub {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}
.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.team-card {
  border-radius: 10px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-body {
  min-height: 84px;
}
.card-code {
  color: var(--accent-cyan);
  font-family: monospace;
  margin: 0 0 6px;
}
.card-desc {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0 0 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.member-count {
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
