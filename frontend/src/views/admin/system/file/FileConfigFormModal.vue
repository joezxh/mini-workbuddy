<template>
  <a-modal
    :open="open"
    :title="isEdit ? '编辑存储配置' : '新增存储配置'"
    :confirm-loading="submitting"
    ok-text="保存"
    cancel-text="取消"
    :width="620"
    @ok="onSubmit"
    @cancel="$emit('update:open', false)"
  >
    <a-form :model="form" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="config-form">
      <a-form-item label="配置名称" required>
        <input v-model="form.name" class="cfg-input" placeholder="例如：生产环境对象存储" />
      </a-form-item>
      <a-form-item label="配置编码" required extra="业务按此 code 选择存储；master 为默认主存储">
        <input v-model="form.code" class="cfg-input" :disabled="isEdit && form.master" placeholder="例如：kms / ai-image / master" />
      </a-form-item>
      <a-form-item label="存储器" required>
        <a-select v-model:value="form.storage" :options="storageOptions" />
      </a-form-item>

      <a-divider orientation="left" plain>存储参数</a-divider>

      <template v-if="form.storage === Storage.LOCAL">
        <a-form-item label="存储根目录">
          <input v-model="form.basePath" class="cfg-input" placeholder="留空使用系统默认 backend/uploads/infra_files" />
        </a-form-item>
      </template>

      <template v-if="form.storage === Storage.S3">
        <a-form-item label="Endpoint">
          <input v-model="form.endpoint" class="cfg-input" placeholder="https://s3.example.com（MinIO/OSS/七牛等）" />
        </a-form-item>
        <a-form-item label="Bucket">
          <input v-model="form.bucket" class="cfg-input" placeholder="存储桶名称" />
        </a-form-item>
        <a-form-item label="Access Key">
          <input v-model="form.accessKey" class="cfg-input" placeholder="访问密钥 AK" />
        </a-form-item>
        <a-form-item label="Access Secret">
          <input v-model="form.accessSecret" type="password" class="cfg-input" placeholder="访问密钥 SK" />
        </a-form-item>
        <a-form-item label="Region">
          <input v-model="form.region" class="cfg-input" placeholder="留空自动从 endpoint 推断" />
        </a-form-item>
        <a-form-item label="Path Style">
          <a-switch v-model:checked="form.enablePathStyleAccess" />
          <span class="cfg-hint">MinIO 开启；腾讯云 COS 等云厂商请关闭（虚拟主机式）</span>
        </a-form-item>
        <a-form-item label="公开读">
          <a-switch v-model:checked="form.enablePublicAccess" />
          <span class="cfg-hint">关闭则下载走预签名 URL</span>
        </a-form-item>
      </template>

      <a-form-item label="访问域名" :extra="form.storage === Storage.DB ? '下载 URL 使用的对外域名，留空则相对路径' : '可选，自定义下载域名'">
        <input v-model="form.domain" class="cfg-input" placeholder="https://file.example.com" />
      </a-form-item>
      <a-form-item label="备注">
        <input v-model="form.remark" class="cfg-input" placeholder="可选说明" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { FileConfigVO, FileConfigSaveVO, FileClientConfig } from '@/api/file'
import { FileStorageEnum, IMPLEMENTED_STORAGES, FileStorageLabels, fileConfigApi } from '@/api/file'

const Storage = FileStorageEnum
/** 编辑（id 必有）或复制新建（id 缺省）共用 */
type EditingConfig = Omit<FileConfigVO, 'id'> & { id?: number }
const props = defineProps<{ open: boolean; config: EditingConfig | null; defaultCode?: string }>()
const emit = defineEmits<{ (e: 'update:open', value: boolean): void; (e: 'saved'): void }>()

const submitting = ref(false)
const storageOptions = IMPLEMENTED_STORAGES.map(v => ({ value: v, label: FileStorageLabels[v] }))

interface FlatForm {
  id?: number
  name: string
  code: string
  storage: number
  master: boolean
  domain: string
  basePath: string
  endpoint: string
  bucket: string
  accessKey: string
  accessSecret: string
  region: string
  enablePathStyleAccess: boolean
  enablePublicAccess: boolean
  remark: string
}
const blank = (): FlatForm => ({
  name: '', code: props.defaultCode || '', storage: Storage.S3, master: false,
  domain: '', basePath: '', endpoint: '', bucket: '', accessKey: '', accessSecret: '',
  region: '', enablePathStyleAccess: false, enablePublicAccess: false, remark: '',
})
const form = reactive<FlatForm>(blank())
const isEdit = computed(() => !!form.id)

watch(() => props.open, (open) => {
  if (!open) return
  Object.assign(form, blank())
  if (props.config) {
    const c = props.config
    Object.assign(form, {
      id: c.id, name: c.name, code: c.code, storage: c.storage, master: c.master,
      domain: c.config.domain || '', basePath: c.config.basePath || '',
      endpoint: c.config.endpoint || '', bucket: c.config.bucket || '',
      accessKey: c.config.accessKey || '', accessSecret: c.config.accessSecret || '',
      region: c.config.region || '',
      enablePathStyleAccess: c.config.enablePathStyleAccess ?? true,
      enablePublicAccess: c.config.enablePublicAccess ?? false,
      remark: c.remark || '',
    })
  }
})

function buildConfig(): FileClientConfig {
  const cfg: FileClientConfig = {}
  if (form.domain) cfg.domain = form.domain
  if (form.storage === Storage.LOCAL && form.basePath) cfg.basePath = form.basePath
  if (form.storage === Storage.S3) {
    cfg.endpoint = form.endpoint
    cfg.bucket = form.bucket
    cfg.accessKey = form.accessKey
    cfg.accessSecret = form.accessSecret
    if (form.region) cfg.region = form.region
    cfg.enablePathStyleAccess = form.enablePathStyleAccess
    cfg.enablePublicAccess = form.enablePublicAccess
  }
  return cfg
}

async function onSubmit() {
  if (!form.name.trim() || !form.code.trim()) {
    message.warning('请填写配置名称与编码')
    return
  }
  const payload: FileConfigSaveVO = {
    id: form.id, name: form.name.trim(), code: form.code.trim(), storage: form.storage,
    config: buildConfig(), remark: form.remark || undefined,
  }
  submitting.value = true
  try {
    if (isEdit.value) await fileConfigApi.update(payload)
    else await fileConfigApi.create(payload)
    message.success(isEdit.value ? '配置已更新' : '配置已创建')
    emit('saved')
    emit('update:open', false)
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="less">
.config-form { padding-right: 8px; }
.cfg-input {
  width: 100%; height: 32px; padding: 4px 11px;
  border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-surface); color: var(--fg); font-size: 14px;
  outline: none; transition: border-color 160ms ease, box-shadow 160ms ease;
  &:focus { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 16%, transparent); }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}
.cfg-hint { margin-left: 10px; font-size: 12px; color: var(--fg-secondary); }
</style>
