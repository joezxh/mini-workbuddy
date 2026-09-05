<template>
  <div class="team-list-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">智能体团队</h2>
        <p class="page-sub">管理多智能体团队拓扑，支持模板实例化、成员编排与运行回放</p>
      </div>
      <a-button type="primary" @click="openCreateModal">
        <PlusOutlined /> 新建团队
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="team-grid">
        <a-card
          v-for="t in teams"
          :key="t.id"
          class="team-card"
          hoverable
          @click="goEditor(t.id)"
        >
          <template #title>
            <div class="card-title">
              <ApartmentOutlined />
              <span>{{ t.name || t.team_name }}</span>
            </div>
          </template>
          <template #extra>
            <div @click.stop @mousedown.stop @pointerdown.stop>
              <a-switch
                :checked="t.is_active"
                checked-children="启用"
                un-checked-children="停用"
                size="small"
                @change="(val: boolean) => toggleActive(t, val)"
              />
            </div>
          </template>
          <div class="card-body">
            <p class="card-code">{{ t.team_code }}</p>
            <p class="card-desc">{{ t.description || '暂无描述' }}</p>
            <div class="card-meta">
              <a-tag v-if="t.category">{{ t.category }}</a-tag>
              <span class="member-count">
                <TeamOutlined /> {{ t.member_count || 0 }} 名成员
              </span>
            </div>
          </div>
          <template #actions>
            <a-button type="link" size="small" @click.stop="goEditor(t.id)">
              <EditOutlined /> 编排
            </a-button>
            <a-button type="link" size="small" danger @click.stop="confirmDelete(t)">
              <DeleteOutlined /> 删除
            </a-button>
          </template>
        </a-card>

        <a-card v-if="!loading && teams.length === 0" class="empty-card">
          <a-empty description="暂无团队，点击「新建团队」开始" />
        </a-card>
      </div>
    </a-spin>

    <!-- 新建 / 编辑团队 -->
    <a-modal
      v-model:open="createVisible"
      :title="editingId ? '编辑团队' : '新建团队'"
      @ok="submitCreate"
      @cancel="createVisible = false"
      :confirm-loading="submitting"
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="团队编码">
          <a-input v-model:value="form.team_code" placeholder="留空自动生成，如 risk_triage_team" :disabled="!!editingId" />
        </a-form-item>
        <a-form-item label="团队名称" required>
          <a-input v-model:value="form.team_name" placeholder="如 风险研判团队" />
        </a-form-item>
        <a-form-item label="分类">
          <a-input v-model:value="form.category" placeholder="如 风险处置" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ApartmentOutlined,
  TeamOutlined,
  EditOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import * as api from '@/api/agentTeam'

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
    message.error('加载团队列表失败：' + (e?.message || e))
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
    message.warning('请填写团队名称')
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
      message.success('更新成功')
    } else {
      await api.createTeam(payload)
      message.success('创建成功')
    }
    createVisible.value = false
    fetchTeams()
  } catch (e: any) {
    message.error('保存失败：' + (e?.message || e))
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

const toggleActive = async (t: api.TeamOut, val: boolean) => {
  try {
    await api.updateTeam(t.id, { is_active: val } as any)
    t.is_active = val
    message.success(val ? '已启用' : '已停用')
  } catch (e: any) {
    message.error('状态切换失败：' + (e?.message || e))
    // 回滚 UI 状态
    t.is_active = !val
  }
}

const confirmDelete = (t: api.TeamOut) => {
  if (!window.confirm(`确认删除团队「${t.name || t.team_name}」？此操作不可恢复。`)) return
  api.deleteTeam(t.id)
    .then(() => { message.success('已删除'); fetchTeams() })
    .catch((e: any) => message.error('删除失败：' + (e?.message || e)))
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
