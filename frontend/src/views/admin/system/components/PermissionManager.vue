<template>
  <div class="menu-manager">
    <!-- 搜索栏 -->
    <div class="search-bar">
      <a-form layout="inline" :model="queryParams">
        <a-form-item :label="t('sys.permission.menuName')">
          <a-input
            v-model:value="queryParams.name"
            :placeholder="t('sys.permission.inputMenuName')"
            allow-clear
            style="width: 200px"
            @press-enter="handleQuery"
          />
        </a-form-item>
        <a-form-item :label="t('sys.permission.status')">
          <a-select
            v-model:value="queryParams.status"
            :placeholder="t('sys.permission.selectStatus')"
            allow-clear
            style="width: 150px"
          >
            <a-select-option :value="0">{{ t('sys.permission.statusOn') }}</a-select-option>
            <a-select-option :value="1">{{ t('sys.permission.statusOff') }}</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" @click="handleQuery">
              <template #icon><SearchOutlined /></template>
              {{ t('sys.permission.search') }}
            </a-button>
            <a-button @click="handleReset">
              <template #icon><ReloadOutlined /></template>
              {{ t('sys.permission.reset') }}
            </a-button>
            <a-button type="primary" @click="openForm('create')">
              <template #icon><PlusOutlined /></template>
              {{ t('sys.permission.add') }}
            </a-button>
            <a-button @click="toggleExpandAll">
              <template #icon><SwapOutlined /></template>
              {{ isExpandAll ? t('sys.permission.collapse') : t('sys.permission.expand') }}
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </div>

    <!-- 树形表格 -->
    <a-table
      :columns="columns"
      :data-source="dataSource"
      :loading="loading"
      :pagination="false"
      :default-expand-all-rows="isExpandAll"
      :indent-size="20"
      row-key="id"
      size="middle"
      children-column-name="children"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <div style="display: flex; align-items: center">
            <img
              v-if="isImageColorIcon(record.colorIcon)"
              :src="record.colorIcon"
              style="margin-right: 6px; width: 16px; height: 16px; object-fit: contain"
            />
            <span
              v-else-if="isEmojiColorIcon(record.colorIcon)"
              class="color-icon-cell"
            >{{ record.colorIcon }}</span>
            <component
              :is="getIconComponent(record.icon)"
              v-else-if="record.icon"
              style="margin-right: 6px; font-size: 14px; color: var(--accent-cyan)"
            />
            <component
              :is="record.type === 1 ? FolderOutlined : FileOutlined"
              v-else
              style="margin-right: 6px; font-size: 14px; color: var(--accent-cyan)"
            />
            <span>{{ record.name }}</span>
            <a-tag :color="typeColor(record.type)" style="margin-left: 8px">{{ typeName(record.type) }}</a-tag>
          </div>
        </template>
        <template v-else-if="column.key === 'i18n'">
          <a-popover v-if="record.i18nKey" trigger="click" placement="bottomLeft">
            <span class="col-i18n-trigger">
              <GlobalOutlined />
              {{ getTranslationForLocale(record.i18nKey, 'zh-CN') || record.i18nKey }}
              <DownOutlined style="font-size: 10px" />
            </span>
            <template #content>
              <div class="col-i18n-popover">
                <div v-for="locale in LOCALE_LABELS" :key="locale.key" class="col-i18n-popover-row">
                  <span class="col-i18n-popover-lang">{{ locale.label }}</span>
                  <span class="col-i18n-popover-text">{{ getTranslationForLocale(record.i18nKey, locale.key) || '-' }}</span>
                </div>
              </div>
            </template>
          </a-popover>
          <span v-else style="color: var(--fg-secondary)">-</span>
        </template>
        <template v-else-if="column.key === 'icon'">
          <span>{{ record.icon || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-switch
            :checked="record.status === 0"
            :loading="statusUpdating[record.id]"
            :checked-children="t('sys.permission.statusOn')"
            :un-checked-children="t('sys.permission.statusOff')"
            @change="(val: any) => handleStatusChange(record, val)"
          />
        </template>
        <template v-else-if="column.key === 'visible'">
          <a-tag :color="record.visible === 1 ? 'blue' : 'default'">
            {{ record.visible === 1 ? t('sys.permission.visibleShow') : t('sys.permission.visibleHide') }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space :size="4">
            <a-button type="link" size="small" @click="openForm('update', record.id)">{{ t('sys.permission.edit') }}</a-button>
            <a-button type="link" size="small" @click="openForm('create', undefined, record.id)">{{ t('sys.permission.addChild') }}</a-button>
            <a-popconfirm :title="t('sys.permission.deleteConfirm')" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>{{ t('sys.permission.delete') }}</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新增/编辑菜单弹窗 -->
    <a-modal
      v-model:open="formVisible"
      :title="formType === 'update' ? t('sys.permission.updateTitle') : t('sys.permission.createTitle')"
      :width="640"
      :confirm-loading="formLoading"
      :mask-closable="false"
      :destroy-on-close="true"
      @ok="submitForm"
      @cancel="formVisible = false"
      :ok-text="t('common.confirm')"
      :cancel-text="t('common.cancel')"
      :body-style="{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto', paddingRight: '8px' }"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        :label-col="{ style: { width: '88px' } }"
        layout="horizontal"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.parentMenu')" name="parentId">
              <a-tree-select
                v-model:value="formData.parentId"
                :tree-data="menuTree"
                :field-names="{ children: 'children', label: 'name', value: 'id' }"
                tree-default-expand-all
                :placeholder="t('sys.permission.selectParent')"
                allow-clear
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.menuType')" name="type">
              <a-radio-group v-model:value="formData.type">
                <a-radio-button :value="1">{{ t('sys.permission.typeDir') }}</a-radio-button>
                <a-radio-button :value="2">{{ t('sys.permission.typeMenu') }}</a-radio-button>
                <a-radio-button :value="3">{{ t('sys.permission.typeBtn') }}</a-radio-button>
              </a-radio-group>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.menuName')" name="name">
              <a-input v-model:value="formData.name" :placeholder="t('sys.permission.inputMenuName')" allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.displaySort')" name="sort">
              <a-input-number v-model:value="formData.sort" :min="0" :max="9999" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row v-show="formData.type !== 3" :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.menuIcon')" name="icon">
              <a-select
                v-model:value="formData.icon"
                :placeholder="t('sys.permission.selectIcon')"
                allow-clear
                show-search
                :filter-option="filterIcon"
                :dropdown-match-select-width="false"
                :dropdown-style="{ width: '420px', padding: '12px' }"
                :trigger-action="['click']"
              >
                <template #dropdownRender="{ menuNode: menu }">
                  <component :is="menu" />
                  <a-divider style="margin: 8px 0" />
                  <div class="icon-grid">
                    <div
                      v-for="icon in availableIcons"
                      :key="icon.name"
                      class="icon-item"
                      :class="{ selected: formData.icon === icon.name }"
                      :title="icon.name"
                      @click="selectIcon(icon.name)"
                    >
                      <component :is="icon.component" />
                    </div>
                  </div>
                </template>
                <a-select-option :value="formData.icon" :disabled="true">
                  <span style="display: flex; align-items: center">
                    <component :is="getIconComponent(formData.icon)" v-if="formData.icon" style="margin-right: 6px" />
                    {{ formData.icon || t('sys.permission.selectIconPlaceholder') }}
                  </span>
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.routePath')" name="path">
              <a-input v-model:value="formData.path" :placeholder="t('sys.permission.routePlaceholder')" allow-clear />
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 彩色图标：支持上传图片，或直接挑选 Emoji 图标（二者均优先于 antd 图标名渲染） -->
        <a-row v-show="formData.type !== 3" :gutter="16">
          <a-col :span="24">
            <a-form-item :label="t('sys.permission.colorIcon')">
              <div class="color-icon-row">
                <a-upload
                  :file-list="[]"
                  :show-upload-list="false"
                  :before-upload="beforeColorIconUpload"
                  accept="image/png,image/jpeg,image/svg+xml"
                >
                  <a-button>
                    <template #icon><UploadOutlined /></template>
                    {{ t('sys.permission.colorIconUpload') }}
                  </a-button>
                </a-upload>
                <a-popover
                  v-model:open="emojiPickerOpen"
                  trigger="click"
                  placement="bottomLeft"
                  :overlay-style="{ width: '340px' }"
                >
                  <template #content>
                    <div class="emoji-picker">
                      <a-input
                        v-model:value="emojiKeyword"
                        :placeholder="t('sys.permission.colorIconEmojiSearch')"
                        allow-clear
                        size="small"
                      />
                      <div class="emoji-picker__body">
                        <div v-for="g in filteredEmojiGroups" :key="g.group" class="emoji-picker__group">
                          <div class="emoji-picker__group-title">{{ g.group }}</div>
                          <div class="emoji-picker__grid">
                            <button
                              v-for="item in g.items"
                              :key="item.char"
                              type="button"
                              class="emoji-picker__item"
                              :class="{ 'emoji-picker__item--active': formData.colorIcon === item.char }"
                              :title="item.name"
                              @click="pickEmoji(item.char)"
                            >{{ item.char }}</button>
                          </div>
                        </div>
                        <div v-if="!filteredEmojiGroups.length" class="emoji-picker__empty">
                          {{ t('sys.permission.colorIconEmojiEmpty') }}
                        </div>
                      </div>
                    </div>
                  </template>
                  <a-button>
                    <template #icon><SmileOutlined /></template>
                    {{ t('sys.permission.colorIconEmoji') }}
                  </a-button>
                </a-popover>
                <div v-if="formData.colorIcon" class="color-icon-preview">
                  <img
                    v-if="isImageColorIcon(formData.colorIcon)"
                    :src="formData.colorIcon"
                    :alt="t('sys.permission.colorIcon')"
                  />
                  <span
                    v-else-if="isEmojiColorIcon(formData.colorIcon)"
                    class="color-icon-preview__emoji"
                  >{{ formData.colorIcon }}</span>
                  <a-button type="text" size="small" danger @click="clearColorIcon">
                    {{ t('sys.permission.colorIconClear') }}
                  </a-button>
                </div>
                <span class="color-icon-hint">{{ t('sys.permission.colorIconHint') }}</span>
              </div>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row v-show="formData.type === 2" :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.componentPath')" name="component">
              <a-input v-model:value="formData.component" :placeholder="t('sys.permission.componentPlaceholder')" allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.componentName')" name="componentName">
              <a-input v-model:value="formData.componentName" :placeholder="t('sys.permission.componentNamePlaceholder')" allow-clear />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item v-show="formData.type === 3" :label="t('sys.permission.permissionFlag')" name="permission">
          <a-input v-model:value="formData.permission" :placeholder="t('sys.permission.permissionPlaceholder')" allow-clear />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="t('sys.permission.menuStatus')" name="status">
              <a-radio-group v-model:value="formData.status">
                <a-radio :value="0">{{ t('sys.permission.statusOn') }}</a-radio>
                <a-radio :value="1">{{ t('sys.permission.statusOff') }}</a-radio>
              </a-radio-group>
            </a-form-item>
          </a-col>
          <a-col v-show="formData.type !== 3" :span="12">
            <a-form-item :label="t('sys.permission.colVisible')" name="visible">
              <a-radio-group v-model:value="formData.visible">
                <a-radio :value="1">{{ t('sys.permission.visibleShow') }}</a-radio>
                <a-radio :value="0">{{ t('sys.permission.visibleHide') }}</a-radio>
              </a-radio-group>
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col v-show="formData.type !== 3" :span="12">
            <a-form-item :label="t('sys.permission.alwaysShowLabel')" name="alwaysShow">
              <a-radio-group v-model:value="formData.alwaysShow">
                <a-radio :value="1">{{ t('sys.permission.alwaysShowOn') }}</a-radio>
                <a-radio :value="0">{{ t('sys.permission.alwaysShowOff') }}</a-radio>
              </a-radio-group>
            </a-form-item>
          </a-col>
          <a-col v-show="formData.type === 2" :span="12">
            <a-form-item :label="t('sys.permission.keepAliveLabel')" name="keepAlive">
              <a-radio-group v-model:value="formData.keepAlive">
                <a-radio :value="1">{{ t('sys.permission.keepAliveOn') }}</a-radio>
                <a-radio :value="0">{{ t('sys.permission.keepAliveOff') }}</a-radio>
              </a-radio-group>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item :label="t('sys.permission.i18nKeyLabel')" name="i18nKey">
          <a-input v-model:value="formData.i18nKey" :placeholder="t('sys.permission.i18nKeyPlaceholder')" allow-clear />
        </a-form-item>

        <!-- 4语言翻译预览（可编辑） -->
        <a-form-item v-if="formData.i18nKey" :label="t('sys.permission.i18nPreview')">
          <div class="i18n-preview">
            <div v-for="locale in LOCALE_LABELS" :key="locale.key" class="i18n-preview-row">
              <span class="i18n-preview-label">{{ locale.label }}</span>
              <a-input
                v-model:value="i18nDraft[locale.key]"
                size="small"
                @change="applyTranslationEdit(locale.key)"
              />
            </div>
            <div class="i18n-preview-hint">{{ t('sys.permission.i18nEditHint') }}</div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed, watch, markRaw, type Component } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  ReloadOutlined,
  PlusOutlined,
  SwapOutlined,
  FolderOutlined,
  FileOutlined,
  SettingOutlined,
  DashboardOutlined,
  UserOutlined,
  DatabaseOutlined,
  RobotOutlined,
  ApiOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  ApartmentOutlined,
  OrderedListOutlined,
  AlertOutlined,
  BankOutlined,
  EnvironmentOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  MessageOutlined,
  BulbOutlined,
  CommentOutlined,
  TagsOutlined,
  SafetyCertificateOutlined,
  MergeCellsOutlined,
  ReadOutlined,
  ToolOutlined,
  LinkOutlined,
  HomeOutlined,
  TeamOutlined,
  KeyOutlined,
  LockOutlined,
  BellOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusSquareOutlined,
  MinusSquareOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  FilterOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
  DownloadOutlined,
  UploadOutlined,
  SaveOutlined,
  SyncOutlined,
  UndoOutlined,
  RedoOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CaretUpOutlined,
  CaretDownOutlined,
  CaretLeftOutlined,
  CaretRightOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  MoreOutlined,
  LeftOutlined,
  RightOutlined,
  UpOutlined,
  DownOutlined,
  StepForwardOutlined,
  StepBackwardOutlined,
  FastForwardOutlined,
  FastBackwardOutlined,
  ShrinkOutlined,
  ArrowsAltOutlined,
  UpCircleOutlined,
  DownCircleOutlined,
  LeftCircleOutlined,
  RightCircleOutlined,
  PlaySquareOutlined,
  PauseCircleOutlined,
  ProfileOutlined,
  AccountBookOutlined,
  ContactsOutlined,
  CarryOutOutlined,
  CalendarOutlined,
  CloudOutlined,
  RocketOutlined,
  ShopOutlined,
  WalletOutlined,
  GiftOutlined,
  TrophyOutlined,
  BuildOutlined,
  ExperimentOutlined,
  BugOutlined,
  CrownOutlined,
  FlagOutlined,
  HeatMapOutlined,
  InteractionOutlined,
  FundOutlined,
  DollarOutlined,
  EuroOutlined,
  PoundOutlined,
  YuqueOutlined,
  CodeOutlined,
  CodepenOutlined,
  RedditOutlined,
  AlipayOutlined,
  DingdingOutlined,
  WeiboOutlined,
  GitlabOutlined,
  GithubOutlined,
  GoogleOutlined,
  FacebookOutlined,
  LinkedinOutlined,
  SkypeOutlined,
  DropboxOutlined,
  DribbbleOutlined,
  BehanceOutlined,
  MediumOutlined,
  AmazonOutlined,
  AntCloudOutlined,
  ZhihuOutlined,
  SmileOutlined,
} from '@ant-design/icons-vue'
import { getMenuList, getMenuSimpleList, getMenuDetail, createMenu, updateMenu, deleteMenu } from '@/api/admin'
import { setTranslationOverride } from '@/i18n'
import { filterEmojiIconGroups, isEmojiColorIcon, isImageColorIcon } from '@/constants/emoji-icons'
import type { MenuItem, MenuForm } from '@/api/admin'

const { t, messages } = useI18n()

// ── 4语言翻译预览 ──────────────────────────────────────────
const LOCALE_LABELS: { key: string; label: string }[] = [
  { key: 'zh-CN', label: '简体中文' },
  { key: 'zh-TW', label: '繁體中文' },
  { key: 'en-US', label: 'English' },
  { key: 'ja-JP', label: '日本語' },
]

/** 从全局 i18n messages 获取指定 locale 下某 key 的翻译 */
function getTranslationForLocale(i18nKey: string, localeKey: string): string {
  const msgs = messages.value as Record<string, any>
  const localeMsgs = msgs[localeKey]
  if (!localeMsgs || !i18nKey) return ''
  const parts = i18nKey.split('.')
  let val: any = localeMsgs
  for (const p of parts) {
    if (val && typeof val === 'object') val = val[p]
    else return ''
  }
  return typeof val === 'string' ? val : ''
}

// ── 图标映射 ──────────────────────────────────────────────
const allIconComponents = [
  SettingOutlined, DashboardOutlined, UserOutlined, DatabaseOutlined,
  RobotOutlined, ApiOutlined, ClockCircleOutlined, GlobalOutlined,
  ThunderboltOutlined, PlayCircleOutlined, BarChartOutlined, CloudUploadOutlined,
  ApartmentOutlined, OrderedListOutlined, AlertOutlined, BankOutlined,
  EnvironmentOutlined, CloudServerOutlined, FileTextOutlined, FolderOpenOutlined,
  MessageOutlined, BulbOutlined, CommentOutlined, TagsOutlined,
  SafetyCertificateOutlined, MergeCellsOutlined, ReadOutlined, ToolOutlined,
  LinkOutlined, HomeOutlined, TeamOutlined, KeyOutlined, LockOutlined,
  BellOutlined, CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined,
  InfoCircleOutlined, QuestionCircleOutlined, StopOutlined, DeleteOutlined,
  EditOutlined, PlusSquareOutlined, MinusSquareOutlined, EyeOutlined, EyeInvisibleOutlined,
  FilterOutlined, SortAscendingOutlined, SortDescendingOutlined, DownloadOutlined,
  UploadOutlined, SaveOutlined, SyncOutlined, UndoOutlined, RedoOutlined,
  ArrowUpOutlined, ArrowDownOutlined, ArrowLeftOutlined, ArrowRightOutlined,
  CaretUpOutlined, CaretDownOutlined, CaretLeftOutlined, CaretRightOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, MenuOutlined, MoreOutlined,
  LeftOutlined, RightOutlined,
  UpOutlined, DownOutlined, StepForwardOutlined, StepBackwardOutlined,
  FastForwardOutlined, FastBackwardOutlined, ShrinkOutlined, ArrowsAltOutlined,
  UpCircleOutlined, DownCircleOutlined, LeftCircleOutlined, RightCircleOutlined,
  PlaySquareOutlined, PauseCircleOutlined, ProfileOutlined,
  AccountBookOutlined, ContactsOutlined, CarryOutOutlined, CalendarOutlined,
  CloudOutlined, RocketOutlined, ShopOutlined, WalletOutlined, GiftOutlined,
  TrophyOutlined, BuildOutlined, ExperimentOutlined, BugOutlined, CrownOutlined,
  FlagOutlined, HeatMapOutlined, InteractionOutlined, FundOutlined,
  DollarOutlined, EuroOutlined, PoundOutlined, YuqueOutlined, CodeOutlined,
  CodepenOutlined, RedditOutlined, WeiboOutlined, GitlabOutlined, GithubOutlined,
  GoogleOutlined, FacebookOutlined, LinkedinOutlined, SkypeOutlined, DropboxOutlined,
  DribbbleOutlined, BehanceOutlined, MediumOutlined, AmazonOutlined,
  AntCloudOutlined, ZhihuOutlined, AlipayOutlined, DingdingOutlined,
]

const iconMap: Record<string, Component> = {}
const availableIcons: { name: string; component: Component }[] = []

allIconComponents.forEach(icon => {
  const name = icon.displayName || icon.name
  iconMap[name] = markRaw(icon)
  availableIcons.push({ name, component: markRaw(icon) })
})

function getIconComponent(iconName?: string): Component {
  if (!iconName) return markRaw(FolderOutlined)
  return iconMap[iconName] || markRaw(FileOutlined)
}

function selectIcon(iconName: string) {
  formData.value.icon = iconName
}

function filterIcon(input: string, option: any) {
  return option.value?.toLowerCase().includes(input.toLowerCase())
}

function typeColor(type: number) {
  return type === 1 ? 'blue' : type === 2 ? 'green' : 'orange'
}
function typeName(type: number) {
  return type === 1 ? t('sys.permission.typeDir') : type === 2 ? t('sys.permission.typeMenu') : t('sys.permission.typeBtn')
}

// ── 查询 ──────────────────────────────────────────────
const loading = ref(false)
const dataSource = ref<MenuItem[]>([])
const isExpandAll = ref(true)
const statusUpdating = reactive<Record<number, boolean>>({})

const queryParams = reactive<{ name?: string; status?: number }>({
  name: undefined,
  status: undefined,
})

const columns = computed(() => [
  { title: t('sys.permission.menuName'), dataIndex: 'name', key: 'name', width: 260, fixed: 'left' as const },
  { title: t('sys.permission.colI18n'), key: 'i18n', width: 200 },
  { title: t('sys.permission.colIcon'), dataIndex: 'icon', key: 'icon', width: 180, ellipsis: true },
  { title: t('sys.permission.colSort'), dataIndex: 'sort', key: 'sort', width: 70 },
  { title: t('sys.permission.colPermission'), dataIndex: 'permission', key: 'permission', width: 200, ellipsis: true },
  { title: t('sys.permission.colVisible'), key: 'visible', width: 80 },
  { title: t('sys.permission.colStatus'), key: 'status', width: 90 },
  { title: t('sys.permission.colAction'), key: 'action', width: 200, fixed: 'right' as const },
])

async function loadData() {
  loading.value = true
  try {
    const res = await getMenuList({
      name: queryParams.name || undefined,
      status: queryParams.status,
    })
    if (res.code === 0) {
      dataSource.value = res.data || []
    }
  } catch (e: any) {
    message.error(`${t('sys.permission.loadError')}：${e?.message || t('sysMgmt.unknownError')}`)
    dataSource.value = []
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  loadData()
}

function handleReset() {
  queryParams.name = undefined
  queryParams.status = undefined
  loadData()
}

function toggleExpandAll() {
  isExpandAll.value = !isExpandAll.value
  // 重新加载数据以触发展开/折叠
  loadData()
}

async function handleStatusChange(record: MenuItem, val: boolean | string | number) {
  const newStatus = val === true || val === 'true' || val === 1 ? 0 : 1
  statusUpdating[record.id] = true
  try {
    const res = await updateMenu(record.id, { status: newStatus })
    if (res.code === 0) {
      record.status = newStatus
      message.success(t('sys.permission.statusUpdated'))
    } else {
      message.error(res.message || t('sys.permission.statusUpdateError'))
    }
  } catch (e: any) {
    message.error(`${t('sys.permission.statusUpdateError')}：${e?.message || t('sysMgmt.unknownError')}`)
  } finally {
    statusUpdating[record.id] = false
  }
}

async function handleDelete(id: number) {
  try {
    const res = await deleteMenu(id)
    if (res.code === 0) {
      message.success(t('sys.permission.deleteSuccess'))
      loadData()
    } else {
      message.error(res.message || t('sys.permission.deleteError'))
    }
  } catch (e: any) {
    message.error(`${t('sys.permission.deleteError')}：${e?.message || t('sysMgmt.unknownError')}`)
  }
}

// ── 表单弹窗 ──────────────────────────────────────────────
const formVisible = ref(false)
const formType = ref<'create' | 'update'>('create')
const formLoading = ref(false)
const formRef = ref()
const menuTree = ref<any[]>([])

const MAX_COLOR_ICON_BYTES = 100 * 1024

/** 彩色图标上传：校验类型与大小后用 FileReader 转 data URL，直接写入表单（不自动上传）。 */
function beforeColorIconUpload(file: File) {
  if (!['image/png', 'image/jpeg', 'image/svg+xml'].includes(file.type)) {
    message.error(t('sys.permission.colorIconInvalidType'))
    return false
  }
  if (file.size > MAX_COLOR_ICON_BYTES) {
    message.error(t('sys.permission.colorIconTooLarge'))
    return false
  }
  const reader = new FileReader()
  reader.onload = () => {
    if (typeof reader.result === 'string') formData.value.colorIcon = reader.result
  }
  reader.onerror = () => message.error(t('sys.permission.colorIconInvalidType'))
  reader.readAsDataURL(file)
  return false
}

function clearColorIcon() {
  formData.value.colorIcon = ''
}

// ── Emoji 彩色图标选择器 ────────────────────────────────────────────────────
const emojiPickerOpen = ref(false)
const emojiKeyword = ref('')
const filteredEmojiGroups = computed(() => filterEmojiIconGroups(emojiKeyword.value))

/** 选中一个 Emoji 图标：直接写入表单（存 emoji 字符，由彩色 emoji 字体渲染）。 */
function pickEmoji(char: string) {
  formData.value.colorIcon = char
  emojiPickerOpen.value = false
  emojiKeyword.value = ''
}

function createDefaultForm(): MenuForm {
  return {
    name: '',
    permission: '',
    path: '',
    type: 2,
    sort: 0,
    parentId: 0,
    icon: '',
    colorIcon: '',
    component: '',
    componentName: '',
    status: 0,
    visible: 1,
    keepAlive: 0,
    alwaysShow: 0,
    i18nKey: '',
  }
}

const formData = ref<MenuForm>(createDefaultForm())

// 可编辑翻译草稿（按 locale 存储输入框当前值）
const i18nDraft = reactive<Record<string, string>>({})

/** 按当前 i18nKey 重新加载 4 语言草稿 */
function refreshI18nDraft() {
  const key = formData.value.i18nKey || ''
  for (const l of LOCALE_LABELS) {
    i18nDraft[l.key] = key ? getTranslationForLocale(key, l.key) : ''
  }
}

watch(() => formData.value.i18nKey, refreshI18nDraft)

/** 写回修改的翻译：运行时立即生效，并持久化到本浏览器（localStorage） */
function applyTranslationEdit(localeKey: string) {
  const key = formData.value.i18nKey
  if (!key) return
  const val = (i18nDraft[localeKey] || '').trim()
  if (!val) {
    // 清空视为放弃修改，回退为当前翻译
    i18nDraft[localeKey] = getTranslationForLocale(key, localeKey)
    return
  }
  if (val === getTranslationForLocale(key, localeKey)) return
  setTranslationOverride(localeKey, key, val)
  message.success(t('sys.permission.i18nUpdated'))
}

const formRules = computed(() => ({
  name: [{ required: true, message: t('sys.permission.nameRequired'), trigger: 'blur' }],
  type: [{ required: true, message: t('sys.permission.typeRequired'), trigger: 'change' }],
  sort: [{ required: true, message: t('sys.permission.sortRequired'), trigger: 'blur' }],
}))

async function loadMenuTree() {
  try {
    const res = await getMenuSimpleList()
    if (res.code === 0) {
      const list = res.data || []
      // 构建树形结构供 TreeSelect 使用
      menuTree.value = buildTreeSelect(list)
    }
  } catch {
    menuTree.value = [{ id: 0, name: t('sys.permission.rootCategory'), children: [] }]
  }
}

function buildTreeSelect(list: { id: number; parentId: number | null; name: string }[]): any[] {
  const map: Record<number, any> = {}
  const roots: any[] = []
  for (const item of list) {
    map[item.id] = { id: item.id, name: item.name, children: [] }
  }
  for (const item of list) {
    const pid = item.parentId || 0
    if (pid === 0 || !map[pid]) {
      roots.push(map[item.id])
    } else {
      map[pid].children.push(map[item.id])
    }
  }
  return [{ id: 0, name: t('sys.permission.rootCategory'), children: roots }]
}

async function openForm(type: 'create' | 'update', id?: number, parentId?: number) {
  formType.value = type
  formData.value = createDefaultForm()

  await loadMenuTree()

  if (parentId !== undefined) {
    formData.value.parentId = parentId
  }

  if (type === 'update' && id !== undefined) {
    formLoading.value = true
    try {
      const res = await getMenuDetail(id)
      if (res.code === 0) {
        const d = res.data
        formData.value = {
          id: d.id,
          name: d.name || '',
          permission: d.permission || '',
          path: d.path || '',
          type: d.type || 2,
          sort: d.sort || 0,
          parentId: d.parentId || 0,
          icon: d.icon || '',
          colorIcon: d.colorIcon || '',
          component: d.component || '',
          componentName: d.componentName || '',
          status: d.status ?? 0,
          visible: d.visible ?? 1,
          keepAlive: d.keepAlive ?? 0,
          alwaysShow: d.alwaysShow ?? 0,
          i18nKey: d.i18nKey || '',
        }
      }
    } catch (e: any) {
      message.error(`${t('sys.permission.loadDetailError')}：${e?.message || t('sysMgmt.unknownError')}`)
    } finally {
      formLoading.value = false
    }
  }

  await nextTick()
  refreshI18nDraft()
  formVisible.value = true
}

// 将前端 camelCase 字段转为后端 snake_case
function toApiData(data: MenuForm): any {
  return {
    name: data.name,
    permission: data.permission,
    path: data.path,
    type: data.type,
    sort: data.sort,
    parent_id: data.parentId,
    icon: data.icon,
    color_icon: data.colorIcon || '',
    component: data.component,
    component_name: data.componentName,
    status: data.status,
    visible: data.visible,
    keep_alive: data.keepAlive,
    always_show: data.alwaysShow,
    i18n_key: data.i18nKey || null,
  }
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch (e: any) {
    const errorFields = e?.errorFields || []
    if (errorFields.length > 0) {
      const firstError = errorFields[0]
      const errorMsg = firstError.errors?.[0] || t('sys.permission.validateError')
      message.error(`${t('sys.permission.validateErrorDetail')}：${errorMsg}`)
    } else {
      message.error(t('sys.permission.validateError'))
    }
    return
  }

  // 路径校验（不再校验 /）
  if (formData.value.type !== 3 && formData.value.path) {
    const isExternal = /^(https?:|mailto:|tel:)/.test(formData.value.path)
    if (!isExternal && formData.value.path.includes(' ')) {
      message.error(t('sys.permission.pathNoSpace'))
      return
    }
  }

  formLoading.value = true
  try {
    if (formType.value === 'create') {
      const res = await createMenu(toApiData(formData.value) as MenuForm)
      if (res.code === 0) {
        message.success(t('sys.permission.createSuccess'))
        formVisible.value = false
        loadData()
      } else {
        message.error(res.message || t('sys.permission.createError'))
      }
    } else {
      const res = await updateMenu(formData.value.id!, toApiData(formData.value))
      if (res.code === 0) {
        message.success(t('sys.permission.updateSuccess'))
        formVisible.value = false
        loadData()
      } else {
        message.error(res.message || t('sys.permission.updateError'))
      }
    }
  } catch (e: any) {
    const respData = e?.response?.data || {}
    const detail = respData.detail || respData.message || respData.msg
    const text = typeof detail === 'string' ? detail : (detail && detail.msg) || e?.message || t('sysMgmt.unknownError')
    message.error(`${formType.value === 'create' ? t('sys.permission.createError') : t('sys.permission.updateError')}：${text}`)
  } finally {
    formLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.menu-manager {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-bar {
  padding: 16px 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-glow);
  border-radius: 4px;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.icon-grid::-webkit-scrollbar {
  width: 6px;
}

.icon-grid::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 3px;
}

.icon-grid::-webkit-scrollbar-track {
  background: var(--bg-page);
}

.icon-item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
  color: var(--fg-secondary);
}

.icon-item:hover {
  background: var(--accent-soft);
  color: var(--accent);
}

.icon-item.selected {
  background: var(--accent);
  color: var(--fg-inverse);
}

.color-icon-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.color-icon-preview {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-subtle);

  img {
    width: 24px;
    height: 24px;
    object-fit: contain;
  }
}

/* Emoji 型彩色图标（菜单里以彩色 emoji 字体渲染） */
.color-icon-preview__emoji {
  font-size: 20px;
  line-height: 1;
  font-family: var(--emoji-font);
}

/* 表格单元格里的 emoji 图标 */
.color-icon-cell {
  margin-right: 6px;
  font-size: 15px;
  line-height: 1;
  font-family: var(--emoji-font);
}

.color-icon-hint {
  font-size: 12px;
  color: var(--fg-muted);
}

/* ── Emoji 选择器 ─────────────────────────────────────────────────────────── */
.emoji-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.emoji-picker__body {
  max-height: 280px;
  overflow-y: auto;
}

.emoji-picker__group + .emoji-picker__group {
  margin-top: 10px;
}

.emoji-picker__group-title {
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 4px;
}

.emoji-picker__grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
}

.emoji-picker__item {
  width: 100%;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  font-size: 18px;
  line-height: 1;
  font-family: var(--emoji-font);
  cursor: pointer;
  transition: background-color var(--transition), border-color var(--transition);

  &:hover {
    background: var(--accent-soft);
  }

  &--active {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
}

.emoji-picker__empty {
  padding: 12px 0;
  text-align: center;
  font-size: 12px;
  color: var(--fg-muted);
}

.i18n-preview {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.i18n-preview-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px;
  background: var(--bg-page, #f5f5f5);
  border-radius: 4px;
  font-size: 13px;
}

.i18n-preview-label {
  flex-shrink: 0;
  width: 70px;
  font-weight: 600;
  color: var(--fg-secondary);
}

.i18n-preview-hint {
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.5;
}

/* ── 表格 i18n 翻译列（Popover 下拉） ── */
.col-i18n-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--accent, #1890ff);
  background: var(--bg-page, #f5f5f5);
  transition: background 0.2s;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-i18n-trigger:hover {
  background: var(--accent-soft, #e6f7ff);
}

.col-i18n-popover {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 200px;
}

.col-i18n-popover-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border, #f0f0f0);
}

.col-i18n-popover-row:last-child {
  border-bottom: none;
}

.col-i18n-popover-lang {
  flex-shrink: 0;
  width: 56px;
  font-weight: 600;
  font-size: 12px;
  color: var(--fg-secondary, #888);
}

.col-i18n-popover-text {
  flex: 1;
  font-size: 13px;
  color: var(--fg, #333);
  word-break: break-all;
}
</style>
