<template>
  <div class="skill-management">
    <!-- 顶部工具栏：标题 + 主 Tab 切换 + 操作按钮（单行，不增加高度） -->
    <div class="page-header">
      <div class="header-main">
        <h2 class="page-title">{{ t('skillHub.pageTitle') }}</h2>
        <div class="top-tab-bar">
          <div class="top-tab" :class="{ active: activeMainTab === 'packages' }" @click="activeMainTab = 'packages'">{{ t('skillHub.tabPackages') }}</div>
          <div class="top-tab" :class="{ active: activeMainTab === 'hub' }" @click="activeMainTab = 'hub'">{{ t('skillHub.tabHub') }}</div>
        </div>
      </div>
      <div class="header-actions">
        <template v-if="activeMainTab === 'packages'">
          <a-button @click="handleImport">
            <UploadOutlined /> {{ t('skillHub.importZip') }}
          </a-button>
          <a-button type="primary" @click="openPackageForm()">
            <PlusOutlined /> {{ t('skillHub.newPackage') }}
          </a-button>
        </template>
        <a-button v-else type="primary" @click="openRepoModal">
          <PlusOutlined /> {{ t('skillHub.addRepo') }}
        </a-button>
      </div>
    </div>

    <!-- 主内容区：占用剩余高度，内部滚动 -->
    <div class="skill-main">
      <!-- 主 Tab 1: 技能包管理 -->
      <div v-show="activeMainTab === 'packages'" class="management-body">
      <!-- 左侧:包列表 -->
      <div class="left-panel">
        <div class="search-box">
          <a-input-search
            v-model:value="keyword"
            :placeholder="t('skillHub.searchPackage')"
            allow-clear
            @search="loadPackages"
          />
        </div>

        <a-spin v-if="loading" class="loading-wrap" />
        <div v-else-if="!groupedPackages.size" class="empty-hint">
          {{ t('skillHub.noPackages') }}
        </div>
        <div v-else class="package-list">
          <div
            v-for="[cat, pkgs] in groupedPackages"
            :key="cat"
            class="category-group"
          >
            <div class="cat-header" @click="toggleCat(cat)">
              <span>{{ t('skillHub.groupCount', { name: categoryLabel(cat), count: pkgs.length }) }}</span>
              <DownOutlined v-if="collapsedCats.has(cat)" />
              <UpOutlined v-else />
            </div>
            <div v-show="!collapsedCats.has(cat)" class="cat-packages">
              <div
                v-for="pkg in pkgs"
                :key="pkg.package_id"
                class="package-item"
                :class="{ active: selected?.package_id === pkg.package_id }"
                @click="selectPackage(pkg)"
              >
                <span class="pkg-icon">{{ iconLabel(pkg.icon) }}</span>
                <span class="pkg-name">{{ pkg.name }}</span>
                <a-tag v-if="!pkg.enabled" color="default" size="small">{{ t('skillHub.disabled') }}</a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧:包详情 + 触发规则 Tabs -->
      <div class="right-panel">
        <div v-if="!selected" class="detail-placeholder">
          <span>{{ t('skillHub.selectPackageHint') }}</span>
        </div>
        <div v-else class="detail-content">
          <!-- 包头部信息 -->
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon">{{ iconLabel(selected.icon) }}</span>
              <span>{{ selected.name }}</span>
            </div>
            <div class="detail-actions">
              <a-button size="small" @click="openPackageForm(selected)">{{ t('common.edit') }}</a-button>
              <a-button size="small" @click="toggleEnabled(selected)">
                {{ selected.enabled ? t('skillHub.disabled') : t('skillHub.enabled') }}
              </a-button>
              <a-button size="small" @click="handleExport(selected)">{{ t('skillHub.export') }}</a-button>
              <a-popconfirm :title="t('skillHub.deletePackageConfirm')" @confirm="handleDelete(selected)">
                <a-button size="small" danger>{{ t('common.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </div>

          <!-- Tabs: 包详情 / 触发规则 -->
          <a-tabs v-model:activeKey="activeTab" class="detail-tabs">
            <!-- Tab 1: 包详情 -->
            <a-tab-pane key="detail" :tab="t('skillHub.tabDetail')">
              <a-descriptions :column="2" size="small" class="detail-meta">
                <a-descriptions-item :label="t('skillHub.pkgId')">{{ selected.package_id }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.category')">{{ categoryLabel(selected.category) }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.version')">{{ selected.version }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.status')">
                  <a-tag :color="selected.enabled ? 'green' : 'default'">
                    {{ selected.enabled ? t('skillHub.enabled') : t('skillHub.disabled') }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.path')">{{ selected.file_path }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.createdAt')">{{ selected.created_at }}</a-descriptions-item>
                <a-descriptions-item :label="t('skillHub.description')" :span="2">{{ selected.description || '—' }}</a-descriptions-item>
              </a-descriptions>

              <a-divider>{{ t('skillHub.scriptList') }}</a-divider>

              <div class="script-list">
                <div v-if="!selected.scripts?.length" class="script-empty">
                  {{ t('skillHub.noScripts') }}
                </div>
                <div
                  v-for="s in selected.scripts"
                  :key="s.script_id"
                  class="script-item"
                >
                  <div class="script-info">
                    <div class="script-name">
                      <span :class="{ 'text-disabled': !s.enabled }">{{ s.name }}</span>
                      <a-tag v-if="!s.enabled" color="default" size="small">{{ t('skillHub.disabled') }}</a-tag>
                    </div>
                    <div class="script-cmd">{{ s.command }}</div>
                    <div v-if="s.description" class="script-desc">{{ s.description }}</div>
                    </div>
                    <div class="script-actions">
                    <a-switch
                      :checked="s.enabled"
                      size="small"
                      @change="(v: boolean) => toggleScriptEnabled(s, v)"
                    />
                    <a-button size="small" type="text" @click="openScriptForm(s)">{{ t('common.edit') }}</a-button>
                    <a-popconfirm :title="t('skillHub.deleteScriptConfirm')" @confirm="handleDeleteScript(s)">
                      <a-button size="small" type="text" danger>{{ t('common.delete') }}</a-button>
                    </a-popconfirm>
                    </div>
                </div>
              </div>

              <div class="script-footer">
                <a-button type="dashed" @click="openScriptForm()">
                  <PlusOutlined /> {{ t('skillHub.newScript') }}
                </a-button>
              </div>
            </a-tab-pane>

            <!-- Tab 2: 触发规则 -->
            <a-tab-pane key="rules" :tab="t('skillHub.tabRules')">
              <div class="rules-toolbar">
                <a-button type="primary" size="small" @click="openCreateRule">
                  <PlusOutlined /> {{ t('skillHub.newRule') }}
                </a-button>
                <a-button size="small" @click="loadRules">
                  <ReloadOutlined :spin="rulesLoading" /> {{ t('skillHub.refresh') }}
                </a-button>
              </div>

              <a-spin :spinning="rulesLoading">
                <a-table
                  :columns="ruleColumns"
                  :data-source="rules"
                  :pagination="false"
                  row-key="id"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'is_active'">
                      <a-switch
                        :checked="record.is_active"
                        @change="(val: boolean) => toggleRuleActive(record, val)"
                        size="small"
                      />
                    </template>
                    <template v-else-if="column.key === 'priority'">
                      <a-tag :color="priorityColor(record.priority)">{{ record.priority }}</a-tag>
                    </template>
                    <template v-else-if="column.key === 'conditions'">
                      <a-tooltip :title="formatConditions(record.conditions)">
                        <code class="conditions-preview">{{ truncate(formatConditions(record.conditions), 60) }}</code>
                      </a-tooltip>
                    </template>
                    <template v-else-if="column.key === 'action'">
                      <a-space>
                        <a-button type="link" size="small" @click="openEditRule(record)">
                          <EditOutlined /> {{ t('common.edit') }}
                        </a-button>
                        <a-popconfirm
                          :title="t('skillHub.deleteRuleConfirm')"
                          :ok-text="t('common.confirm')"
                          :cancel-text="t('common.cancel')"
                          @confirm="handleDeleteRule(record)"
                        >
                          <a-button type="link" size="small" danger>
                            <DeleteOutlined /> {{ t('common.delete') }}
                          </a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="!rulesLoading && rules.length === 0" :description="t('skillHub.noRules')" />
              </a-spin>
            </a-tab-pane>

            <!-- Tab 3: SKILL.md 文档 -->
            <a-tab-pane key="markdown" tab="SKILL.md">
              <div class="markdown-toolbar">
                <a-space v-if="!markdownEditing">
                  <a-button size="small" type="primary" @click="startEditMarkdown">
                    <EditOutlined /> {{ t('common.edit') }}
                  </a-button>
                  <a-button size="small" @click="loadMarkdown">
                    <ReloadOutlined :spin="markdownLoading" /> {{ t('skillHub.refresh') }}
                  </a-button>
                </a-space>
                <a-space v-else>
                  <a-button size="small" type="primary" :loading="markdownSaving" @click="saveMarkdown">
                    {{ t('common.save') }}
                  </a-button>
                  <a-button size="small" :disabled="markdownSaving" @click="cancelEditMarkdown">
                    {{ t('common.cancel') }}
                  </a-button>
                </a-space>
                <span v-if="markdownSource" class="markdown-source-tag">
                  {{ t('skillHub.source') }}：{{ markdownSourceLabel }}
                </span>
              </div>
              <div class="markdown-container">
                <a-spin :spinning="markdownLoading">
                  <div v-if="markdownError" class="markdown-error">
                    <a-empty :description="markdownError" />
                  </div>
                  <a-textarea
                    v-else-if="markdownEditing"
                    v-model:value="markdownDraft"
                    class="markdown-editor"
                    :placeholder="t('skillHub.markdownPlaceholder')"
                    :auto-size="{ minRows: 18, maxRows: 36 }"
                  />
                  <pre v-else-if="markdownContent" class="markdown-pre">{{ markdownContent }}</pre>
                  <a-empty v-else-if="!markdownLoading" :description="t('skillHub.markdownEmpty')" />
                </a-spin>
              </div>
            </a-tab-pane>

            <!-- Tab 4: 进化配置 -->
            <a-tab-pane key="evolution" :tab="t('skillHub.tabEvolution')">
              <a-spin :spinning="evoLoading">
                <!-- 指标概览 -->
                <div class="evo-metrics">
                  <a-row :gutter="12">
                    <a-col :span="6">
                      <a-statistic :title="t('skillHub.metricSuccess')" :value="(evoMetrics.success_rate * 100).toFixed(1)" suffix="%" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic :title="t('skillHub.metricLatency')" :value="evoMetrics.avg_latency.toFixed(2)" suffix="s" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic :title="t('skillHub.metricExec')" :value="evoMetrics.execution_count" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic :title="t('skillHub.metricRating')" :value="evoMetrics.user_rating.toFixed(2)" />
                    </a-col>
                  </a-row>
                </div>

                <!-- 进化状态 -->
                <a-alert
                  v-if="evoScore < evoConfig.threshold"
                  type="warning"
                  show-icon
                  :message="t('skillHub.evoLow', { score: evoScore.toFixed(3), threshold: evoConfig.threshold })"
                  class="evo-alert"
                />
                <a-alert
                  v-else
                  type="success"
                  show-icon
                  :message="t('skillHub.evoGood', { score: evoScore.toFixed(3), threshold: evoConfig.threshold })"
                  class="evo-alert"
                />

                <!-- 操作按钮 -->
                <div class="evo-actions">
                  <a-button type="primary" :loading="evoTriggering" @click="handleTriggerEvolution">
                    <ThunderboltOutlined /> {{ t('skillHub.trainEvo') }}
                  </a-button>
                  <a-button @click="loadEvolutionData">
                    <ReloadOutlined /> {{ t('skillHub.evoRefresh') }}
                  </a-button>
                </div>

                <!-- 配置表单 -->
                <a-divider>{{ t('skillHub.evoParams') }}</a-divider>
                <a-form layout="inline" class="evo-config-form">
                  <a-form-item :label="t('skillHub.evoThreshold')">
                    <a-input-number
                      v-model:value="evoConfig.threshold"
                      :min="0.1" :max="1.0" :step="0.05"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item :label="t('skillHub.evoWeightSuccess')">
                    <a-input-number
                      v-model:value="evoConfig.weight_success"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item :label="t('skillHub.evoWeightLatency')">
                    <a-input-number
                      v-model:value="evoConfig.weight_latency"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item :label="t('skillHub.evoWeightRating')">
                    <a-input-number
                      v-model:value="evoConfig.weight_user_rating"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item :label="t('skillHub.evoAuto')">
                    <a-switch v-model:checked="evoConfig.is_auto_enabled" @change="saveEvoConfig" />
                  </a-form-item>
                  <a-form-item :label="t('skillHub.evoModel')">
                    <a-select
                      v-model:value="evoConfig.model_code"
                      :placeholder="t('skillHub.evoModelDefault')"
                      style="width: 220px"
                      :loading="chatModelsLoading"
                      allow-clear
                      @change="saveEvoConfig"
                    >
                      <a-select-option v-for="m in chatModels" :key="m.code" :value="m.code">
                        {{ m.name || m.model || m.code }}
                        <span v-if="m.platform" class="model-platform">（{{ m.platform }}）</span>
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-form>

                <!-- 版本历史 -->
                <a-divider>{{ t('skillHub.evoVersionHistory') }}</a-divider>
                <a-table
                  :columns="versionColumns"
                  :data-source="evoVersions"
                  :pagination="false"
                  row-key="version_number"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'is_stable'">
                      <a-tag :color="record.is_stable ? 'green' : 'default'">
                        {{ record.is_stable ? t('skillHub.stable') : t('skillHub.history') }}
                      </a-tag>
                    </template>
                    <template v-else-if="column.key === 'action'">
                      <a-popconfirm
                        v-if="!record.is_stable"
                        :title="t('skillHub.rollbackConfirm', { version: record.version_number })"
                        @confirm="handleRollback(record.version_number)"
                      >
                        <a-button type="link" size="small">{{ t('skillHub.rollback') }}</a-button>
                      </a-popconfirm>
                      <span v-else class="text-disabled">{{ t('skillHub.current') }}</span>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="evoVersions.length === 0" :description="t('skillHub.noVersions')" />

                <!-- 进化日志 -->
                <a-divider>{{ t('skillHub.evoLogs') }}</a-divider>
                <a-table
                  :columns="logColumns"
                  :data-source="evoLogs"
                  :pagination="false"
                  row-key="id"
                  size="small"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.key === 'result'">
                      <a-tag :color="record.result === 'success' ? 'green' : record.result === 'failed' ? 'red' : 'orange'">
                        {{ record.result }}
                      </a-tag>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="evoLogs.length === 0" :description="t('skillHub.noEvoLogs')" />
              </a-spin>
            </a-tab-pane>

            <!-- Tab 5: 对话记录 -->
            <a-tab-pane key="conversations" :tab="t('skillHub.tabConversations')">
              <div class="conversations-container">
                <a-row :gutter="[16, 0]">
                  <!-- 左侧：会话列表 -->
                  <a-col :span="8">
                    <div class="session-list-panel">
                      <div class="panel-header">
                        <span>{{ t('skillHub.execHistory', { total: sessionPagination.total }) }}</span>
                      </div>
                      
                      <a-spin :spinning="sessionsLoading" style="width: 100%">
                        <div class="session-list" ref="sessionListRef">
                          <div
                            v-for="session in sessions"
                            :key="session.session_id"
                            class="session-item"
                            :class="{ active: currentSessionId === session.session_id }"
                            @click="loadSessionMessages(session)"
                          >
                            <div class="session-header">
                              <span class="session-title">{{ session.session_title || t('skillHub.noTitle') }}</span>
                              <span class="session-time">{{ formatTime(session.updated_at) }}</span>
                            </div>
                            <div class="session-info">
                              <span class="session-user">{{ t('skillHub.userId') }}: {{ session.user_id }}</span>
                              <span class="session-msg-count">{{ t('skillHub.msgCount') }}：{{ session.message_count }}</span>
                            </div>
                          </div>
                          
                          <a-empty v-if="!sessions.length && !sessionsLoading" :description="t('skillHub.noSessions')" />
                          
                          <!-- 分页 -->
                          <div class="pagination-wrapper" v-if="sessionPagination.total > (sessionPagination.pageSize || 20)">
                            <a-pagination
                              v-model:current="sessionPage"
                              v-model:page-size="sessionPageSize"
                              :total="sessionPagination.total"
                              show-size-changer
                              show-quick-jumper
                              :show-total="(total: number) => `共 ${total} 条`"
                              @change="onSessionPageChange"
                            />
                          </div>
                        </div>
                      </a-spin>
                    </div>
                  </a-col>

                  <!-- 右侧：消息详情 -->
                  <a-col :span="16">
                    <div class="messages-panel" v-if="currentSessionId">
                      <div class="panel-header">
                        <span>{{ t('skillHub.sessionMessages') }}</span>
                        <a-button size="small" @click="clearCurrentSession">{{ t('skillHub.clear') }}</a-button>
                      </div>
                      
                      <div class="messages-content">
                        <div
                          v-for="msg in messages"
                          :key="msg.message_id"
                          class="message-item"
                          :class="msg.role"
                        >
                          <div class="message-header">
                            <a-tag :color="msg.role === 'user' ? 'blue' : 'green'">
                              {{ msg.role === 'user' ? t('skillHub.roleUser') : t('skillHub.roleAi') }}
                            </a-tag>
                            <span class="message-time">{{ formatTime(msg.created_at) }}</span>
                          </div>
                          <div class="message-content">
                            {{ msg.content }}
                          </div>
                          
                          <!-- 工具调用信息 -->
                          <div v-if="msg.tool_calls" class="tool-calls">
                            <a-divider plain>{{ t('skillHub.toolCalls') }}</a-divider>
                            <pre class="json-preview">{{ JSON.stringify(msg.tool_calls, null, 2) }}</pre>
                          </div>
                          
                          <!-- 工具结果信息 -->
                          <div v-if="msg.tool_results" class="tool-results">
                            <a-divider plain>{{ t('skillHub.toolResults') }}</a-divider>
                            <pre class="json-preview">{{ JSON.stringify(msg.tool_results, null, 2) }}</pre>
                          </div>
                        </div>
                        
                        <a-spin v-if="messagesLoading" :style="{ textAlign: 'center', padding: '20px' }" />
                        <a-empty v-if="!messages.length && !messagesLoading && currentSessionId" :description="t('skillHub.noMessages')" />
                      </div>
                      
                      <!-- 加载更多 -->
                      <div v-if="messages.length > 0" class="load-more-wrapper">
                        <a-button 
                          block 
                          @click="loadMoreMessages" 
                          :loading="messagesLoading"
                          v-if="messages.length >= 50"
                        >
                          {{ t('skillHub.loadMore') }}
                        </a-button>
                      </div>
                    </div>
                    
                    <div v-else class="messages-placeholder">
                      <span>{{ t('skillHub.selectSessionHint') }}</span>
                    </div>
                  </a-col>
                </a-row>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>
      </div>

      <!-- 主 Tab 2: 技能仓库 -->
      <div v-show="activeMainTab === 'hub'" class="hub-body">
          <!-- 仓库选择栏：仓库列表横向一行 -->
          <div class="hub-toolbar">
            <div class="hub-repo-tabs">
              <div
                v-for="r in hubRepos"
                :key="r.id"
                class="hub-repo-tab"
                :class="{ active: hubActiveRepoId === r.id }"
                @click="selectHubRepo(r.id)"
              >
                <span class="hub-repo-name">{{ r.name }}</span>
                <a-tag v-if="r.source_type === 'skillhub'" color="purple" size="small">{{ t('skillHub.cloudMarket') }}</a-tag>
                <a-tag v-else-if="r.is_official" color="blue" size="small">{{ t('skillHub.official') }}</a-tag>
              </div>
              <a-button type="dashed" size="small" class="hub-repo-add" @click="openRepoModal()">
                <PlusOutlined /> {{ t('skillHub.manageRepo') }}
              </a-button>
            </div>
            <div class="hub-toolbar-right">
              <a-input-search
                v-model:value="hubKeyword"
                :placeholder="t('skillHub.searchSkill')"
                allow-clear
                style="width: 280px"
                @search="loadHubSkills(true)"
              />
              <a-button @click="handleRefreshHubRepo" :loading="hubRefreshing">
                <ReloadOutlined /> {{ t('skillHub.refreshRepo') }}
              </a-button>
            </div>
          </div>

          <div class="hub-content" v-if="hubActiveRepoId">
            <!-- 左侧分类 -->
            <div class="hub-cats">
              <div
                class="hub-cat-item"
                :class="{ active: hubActiveCat === '' }"
                @click="selectHubCat('')"
              >
                {{ t('skillHub.all') }} ({{ hubSkillTotal }})
              </div>
              <div
                v-for="c in hubCategories"
                :key="c.key"
                class="hub-cat-item"
                :class="{ active: hubActiveCat === c.key }"
                @click="selectHubCat(c.key)"
              >
                {{ (isCloudMarket ? cloudCategoryLabel(c) : c.name) }} ({{ c.count }})
              </div>
            </div>

            <!-- 右侧列表 -->
            <div class="hub-list">
              <a-spin :spinning="hubLoading">
                <div class="hub-cards">
                  <a-card
                    v-for="item in hubSkills"
                    :key="item.id"
                    size="small"
                    class="hub-card"
                    :title="item.name"
                  >
                    <template #extra>
                      <a-button
                        type="link"
                        size="small"
                        :loading="item._installing"
                        @click="handleInstallHubSkill(item)"
                      >
                        {{ t('skillHub.install') }}
                      </a-button>
                    </template>
                    <div class="hub-card-desc">{{ item.description || '—' }}</div>
                    <div class="hub-card-meta">
                      <a-tag v-if="item.category_name" color="green" size="small">
                        {{ item.category_name }}
                      </a-tag>
                      <a-tag v-if="item.version" size="small">v{{ item.version }}</a-tag>
                      <a-tag v-for="t in (item.tags || [])" :key="t" size="small">{{ t }}</a-tag>
                    </div>
                  </a-card>
                </div>
                <a-empty v-if="!hubLoading && !hubSkills.length" :description="t('skillHub.noSkillsInCat')" />
                <div class="hub-pagination" v-if="hubSkillTotal > hubPageSize">
                  <a-pagination
                    v-model:current="hubPage"
                    v-model:page-size="hubPageSize"
                    :total="hubSkillTotal"
                    show-size-changer
                    :show-total="(tt: number) => t('skillHub.totalCount', { total: tt })"
                    @change="loadHubSkills(false)"
                  />
                </div>
              </a-spin>
            </div>
          </div>
          <a-empty v-else :description="t('skillHub.selectOrAddRepo')" />
        </div>
    </div>
  </div>

    <!-- 弹窗 -->
    <SkillPackageForm ref="pkgFormRef" @success="loadPackages" />
    <SkillScriptForm
      ref="scrFormRef"
      :package-id="selected?.package_id || ''"
      @success="reloadSelected"
    />
    <SkillRuleFormModal
      v-model:visible="ruleFormVisible"
      :rule-id="editingRule?.id"
      :rule-data="editingRule"
      @success="handleRuleFormSuccess"
    />

    <!-- 隐藏的上传 input -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".zip"
      style="display:none"
      @change="onFileSelected"
    />

    <!-- 技能仓库管理弹窗 -->
    <a-modal
      v-model:visible="repoModalVisible"
      :title="t('skillHub.repoModalTitle')"
      @ok="saveRepo"
      :confirm-loading="repoSaving"
      :ok-text="repoEditingId ? t('common.save') : t('skillHub.addRepo')"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('skillHub.repoName')">
          <a-input v-model:value="repoForm.name" :placeholder="t('skillHub.repoNamePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('skillHub.gitUrl')">
          <a-input
            v-model:value="repoForm.url"
            :placeholder="t('skillHub.gitUrlPlaceholder')"
            :disabled="repoForm.is_official"
          />
        </a-form-item>
        <a-form-item :label="t('skillHub.branch')">
          <a-input v-model:value="repoForm.branch" :disabled="repoForm.is_official" />
        </a-form-item>
      </a-form>
      <a-divider>{{ t('skillHub.configuredRepos') }}</a-divider>
      <a-list size="small" :data-source="hubRepos">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta :description="item.url">
              <template #title>
                {{ item.name }}
                <a-tag v-if="item.source_type === 'skillhub'" color="purple" size="small">{{ t('skillHub.cloudMarket') }}</a-tag>
                <a-tag v-else-if="item.is_official" color="blue" size="small">{{ t('skillHub.official') }}</a-tag>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a v-if="!item.is_official" @click="editRepo(item)">{{ t('common.edit') }}</a>
              <a-popconfirm
                v-if="!item.is_official"
                :title="t('skillHub.deleteRepoConfirm')"
                @confirm="deleteRepo(item)"
              >
                <a style="color:var(--err)">{{ t('common.delete') }}</a>
              </a-popconfirm>
              <span v-if="item.is_official" class="text-disabled">{{ t('skillHub.notDeletable') }}</span>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getLocale, type LocaleKey } from '@/i18n'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined, UploadOutlined, DownOutlined, UpOutlined,
  ReloadOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined,
} from '@ant-design/icons-vue'
import {
  listHubRepos, createHubRepo, updateHubRepo, deleteHubRepo, refreshHubRepo,
  listHubCategories, listHubSkills, installHubSkill,
  type HubRepo, type HubCategory, type HubSkillItem,
} from '@/api/skillHub'
import {
  getSkills, deleteSkillPackage, updateSkillPackage,
  deleteScript as apiDeleteScript, updateScript, importSkillPackage, exportSkillPackage,
  getSkillMarkdown, saveSkillMarkdown, ICON_OPTIONS,
} from '@/api/skill'
import { getDictionaryItems } from '@/api/dictionary'
import type { DictionaryItem } from '@/api/dictionary'
import type { SkillPackage, SkillScript } from '@/api/skill'
import {
  getSkillRules, updateSkillRule, deleteSkillRule,
  type SkillRule,
} from '@/api/skillRule'
import { postSessions, getMessages } from '@/api/chatHistory'
import SkillPackageForm from './components/SkillPackageForm.vue'
import SkillScriptForm from './components/SkillScriptForm.vue'
import SkillRuleFormModal from './components/SkillRuleFormModal.vue'
import {
  getSkillMetrics, getEvolutionConfig, updateEvolutionConfig,
  triggerEvolution, getSkillVersions, rollbackVersion, getEvolutionLogs,
  getChatModels,
  type SkillMetrics, type EvolutionConfig, type SkillVersion, type EvolutionLog,
  type ChatModelOption,
} from '@/api/skillEvolution'

const route = useRoute()
const { t } = useI18n()
const loading = ref(false)
const packages = ref<SkillPackage[]>([])
const selected = ref<SkillPackage | null>(null)
const keyword = ref('')
const collapsedCats = ref<Set<string>>(new Set())
const pkgFormRef = ref()
const scrFormRef = ref()
const fileInputRef = ref<HTMLInputElement>()
const categoryOptions = ref<DictionaryItem[]>([])
const activeTab = ref('detail')
const activeMainTab = ref('hub')

// ── 技能仓库（Skill Hub）相关 ─────────────────────────────────────────────────
const hubRepos = ref<HubRepo[]>([])
const hubReposLoading = ref(false)
const hubActiveRepoId = ref<number | null>(null)
const hubRefreshing = ref(false)
const hubCategories = ref<HubCategory[]>([])
const hubActiveCat = ref('')
const hubKeyword = ref('')
const hubSkills = ref<HubSkillItem[]>([])
const hubLoading = ref(false)
const hubPage = ref(1)
const hubPageSize = ref(20)
const hubSkillTotal = ref(0)
// 仓库管理弹窗
const repoModalVisible = ref(false)
const repoSaving = ref(false)
const repoEditingId = ref<number | null>(null)
const repoForm = ref<{ name: string; url: string; branch: string; is_official: boolean }>({
  name: '', url: '', branch: 'main', is_official: false,
})

// ── 触发规则相关 ──────────────────────────────────────────────────────────────
const rules = ref<SkillRule[]>([])
const rulesLoading = ref(false)
const ruleFormVisible = ref(false)
const editingRule = ref<SkillRule | null>(null)

// ── SKILL.md 相关 ─────────────────────────────────────────────────────────────
const markdownContent = ref('')
const markdownLoading = ref(false)
const markdownError = ref('')
const markdownEditing = ref(false)
const markdownSaving = ref(false)
const markdownDraft = ref('')
// 来源标记：db=数据库优先 / workspace=工作区 / file=文件系统
const markdownSource = ref('')
const markdownSourceLabel = computed(() => {
  switch (markdownSource.value) {
    case 'db': return t('skillHub.srcDb')
    case 'workspace': return t('skillHub.srcWorkspace')
    case 'file': return t('skillHub.srcFile')
    default: return ''
  }
})

function startEditMarkdown() {
  markdownDraft.value = markdownContent.value || ''
  markdownEditing.value = true
}

function cancelEditMarkdown() {
  markdownEditing.value = false
  markdownDraft.value = ''
}

async function saveMarkdown() {
  if (!selected.value) return
  markdownSaving.value = true
  try {
    await saveSkillMarkdown(selected.value.package_id, markdownDraft.value)
    markdownContent.value = markdownDraft.value
    if (selected.value) {
      selected.value.skill_markdown = markdownDraft.value
    }
    markdownEditing.value = false
    markdownDraft.value = ''
    message.success(t('skillHub.savedMarkdown'))
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    markdownSaving.value = false
  }
}

// ── 进化配置相关 ─────────────────────────────────────────────────────────────
const evoLoading = ref(false)
const evoTriggering = ref(false)
const evoMetrics = ref<SkillMetrics>({ skill_id: '', execution_count: 0, success_rate: 0, avg_latency: 0, user_rating: 0 })
const evoConfig = ref<EvolutionConfig>({
  skill_id: '', threshold: 0.7, weight_success: 0.4,
  weight_latency: 0.2, weight_user_rating: 0.3, resource_score: 0.8, is_auto_enabled: false,
  model_code: null,
})
const chatModels = ref<ChatModelOption[]>([])
const chatModelsLoading = ref(false)
const evoVersions = ref<SkillVersion[]>([])
const evoLogs = ref<EvolutionLog[]>([])
const evoScore = computed(() => {
  const m = evoMetrics.value
  const c = evoConfig.value
  const latencyScore = Math.max(0, 1 - (m.avg_latency || 0) / 60)
  return (
    c.weight_success * (m.success_rate || 0) +
    c.weight_user_rating * (m.user_rating || 0) +
    c.weight_latency * latencyScore +
    (c.resource_score || 0.8) * 0.1
  )
})

// ── 对话记录相关 ────────────────────────────────────────────────────────────────
const sessionsLoading = ref(false)
const messagesLoading = ref(false)
const sessions = ref<any[]>([])
const messages = ref<any[]>([])
const currentSessionId = ref<number | null>(null)
const sessionPage = ref(1)
const sessionPageSize = ref(20)
const sessionPagination = ref<{ total: number; pageSize?: number }>({ total: 0 })
const sessionListRef = ref<HTMLDivElement>()

interface GetSessionsRequest {
  skill_id: string
  page: number
  page_size: number
}

interface GetMessagesRequest {
  session_id: number
  limit: number
  before_message_id?: number
}

const versionColumns = [
  { title: t('skillHub.verNum'), dataIndex: 'version_number', key: 'version_number', width: 80 },
  { title: t('skillHub.status'), key: 'is_stable', width: 80 },
  { title: t('skillHub.createdAt'), dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: t('skillHub.verAction'), key: 'action', width: 80 },
]

const logColumns = [
  { title: t('skillHub.logTriggerType'), dataIndex: 'trigger_type', key: 'trigger_type', width: 100 },
  { title: t('skillHub.logVerChange'), key: 'version_change', width: 120,
    customRender: ({ record }: any) => `${record.from_version ?? '-'} → ${record.to_version ?? '-'}` },
  { title: t('skillHub.logResult'), key: 'result', width: 100 },
  { title: t('skillHub.logTime'), dataIndex: 'created_at', key: 'created_at', width: 180 },
]

const ruleColumns = [
  { title: t('skillHub.ruleName'), dataIndex: 'name', key: 'name', width: 180 },
  { title: t('skillHub.ruleAgent'), dataIndex: 'agent_name', key: 'agent_name', width: 150 },
  { title: t('skillHub.rulePriority'), dataIndex: 'priority', key: 'priority', width: 80 },
  { title: t('skillHub.ruleConditions'), key: 'conditions', width: 240 },
  { title: t('skillHub.ruleStatus'), key: 'is_active', width: 80 },
  { title: t('skillHub.ruleAction'), key: 'action', width: 150, fixed: 'right' as const },
]

// ── 数据加载 ─────────────────────────────────────────────────────────────────

async function loadCategoryOptions() {
  try {
    const res = await getDictionaryItems('skill_category')
    categoryOptions.value = res || []
  } catch (e) {
    console.error('加载类目字典失败:', e)
    categoryOptions.value = []
  }
}

async function loadPackages() {
  loading.value = true
  try {
    const res = await getSkills()
    packages.value = res?.packages || []
    if (selected.value) {
      const updated = packages.value.find(p => p.package_id === selected.value!.package_id)
      selected.value = updated || null
    }
  } catch (e: any) {
    message.error(t('skillHub.loadFailed') + (e?.data?.detail || e?.message || String(e)))
  } finally {
    loading.value = false
  }
}

// ── 监听 Tab 切换 ───────────────────────────────────────────────────────────────
watch(
  () => activeTab.value,
  (newTab) => {
    if (newTab === 'conversations' && selected.value?.package_id) {
      loadSessions()
    } else {
      messages.value = []
      currentSessionId.value = null
    }
  },
)

onMounted(() => {
  loadCategoryOptions()
  loadPackages()
  loadHubRepos()
})

// ── 技能仓库（Skill Hub）逻辑 ─────────────────────────────────────────────────
async function loadHubRepos() {
  hubReposLoading.value = true
  try {
    const repos = await listHubRepos()
    hubRepos.value = repos || []
    if (!hubActiveRepoId.value && hubRepos.value.length) {
      hubActiveRepoId.value = hubRepos.value[0].id
      await loadHubCategoriesAndSkills()
    }
  } catch (e: any) {
    message.error(t('skillHub.loadRepoFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubReposLoading.value = false
  }
}

async function loadHubCategoriesAndSkills() {
  if (!hubActiveRepoId.value) return
  hubLoading.value = true
  try {
    const [cats, list] = await Promise.all([
      listHubCategories(hubActiveRepoId.value),
      listHubSkills(hubActiveRepoId.value, {
        category: hubActiveCat.value || undefined,
        q: hubKeyword.value || undefined,
        page: hubPage.value,
        page_size: hubPageSize.value,
      }),
    ])
    hubCategories.value = cats || []
    hubSkills.value = list.items || []
    hubSkillTotal.value = list.total || 0
  } catch (e: any) {
    message.error(t('skillHub.loadSkillsFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubLoading.value = false
  }
}

function onHubRepoChange() {
  hubActiveCat.value = ''
  hubPage.value = 1
  loadHubCategoriesAndSkills()
}

function selectHubRepo(id: number) {
  if (hubActiveRepoId.value === id) return
  hubActiveRepoId.value = id
  onHubRepoChange()
}

function selectHubCat(key: string) {
  hubActiveCat.value = key
  hubPage.value = 1
  loadHubCategoriesAndSkills()
}

function loadHubSkills(resetPage: boolean) {
  if (resetPage) hubPage.value = 1
  loadHubCategoriesAndSkills()
}

async function handleRefreshHubRepo() {
  if (!hubActiveRepoId.value) return
  hubRefreshing.value = true
  try {
    await refreshHubRepo(hubActiveRepoId.value)
    message.success(t('skillHub.repoRefreshed'))
    await loadHubCategoriesAndSkills()
  } catch (e: any) {
    message.error(t('skillHub.refreshFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    hubRefreshing.value = false
  }
}

async function handleInstallHubSkill(item: HubSkillItem) {
  if (!hubActiveRepoId.value) return
  item._installing = true
  try {
    const res = await installHubSkill(hubActiveRepoId.value, item.id)
    message.success(t('skillHub.installed', { name: res.name || item.name }))
    loadPackages()
  } catch (e: any) {
    message.error(t('skillHub.installFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    item._installing = false
  }
}

// ── 仓库管理弹窗 ─────────────────────────────────────────────────────────────
function openRepoModal() {
  repoEditingId.value = null
  repoForm.value = { name: '', url: '', branch: 'main', is_official: false }
  repoModalVisible.value = true
}

function editRepo(r: HubRepo) {
  repoEditingId.value = r.id
  repoForm.value = { name: r.name, url: r.url, branch: r.branch, is_official: r.is_official }
  repoModalVisible.value = true
}

async function saveRepo() {
  if (!repoForm.value.name.trim() || !repoForm.value.url.trim()) {
    message.warning(t('skillHub.repoFormRequired'))
    return
  }
  repoSaving.value = true
  try {
    if (repoEditingId.value) {
      await updateHubRepo(repoEditingId.value, {
        name: repoForm.value.name,
        url: repoForm.value.url,
        branch: repoForm.value.branch,
      })
    } else {
      await createHubRepo({
        name: repoForm.value.name,
        url: repoForm.value.url,
        branch: repoForm.value.branch,
      })
    }
    message.success(t('skillHub.repoSaved'))
    repoModalVisible.value = false
    await loadHubRepos()
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  } finally {
    repoSaving.value = false
  }
}

async function deleteRepo(r: HubRepo) {
  try {
    await deleteHubRepo(r.id)
    message.success(t('skillHub.repoDeleted'))
    if (hubActiveRepoId.value === r.id) {
      hubActiveRepoId.value = null
      hubSkills.value = []
    }
    await loadHubRepos()
  } catch (e: any) {
    message.error(t('skillHub.deleteFailed') + (e?.response?.data?.detail || e?.message || t('skillHub.unknownError')))
  }
}

// 根据 package_id 自动选中技能包（从外部跳转过来时）
function selectPackageById(packageId: string) {
  const pkg = packages.value.find(p => p.package_id === packageId)
  if (pkg) {
    selectPackage(pkg)
  }
}

// 监听路由 query 参数变化，自动定位到对应技能包
watch(
  () => route.query.package_id,
  (packageId) => {
    if (packageId && typeof packageId === 'string') {
      // 如果包列表已加载，直接选中；否则等加载完成后选中
      if (packages.value.length > 0) {
        selectPackageById(packageId)
      }
    }
  },
)

// 包列表加载完成后，检查路由中是否有 package_id 参数
watch(
  () => packages.value,
  (pkgs) => {
    if (pkgs.length > 0) {
      const packageId = route.query.package_id
      if (packageId && typeof packageId === 'string') {
        selectPackageById(packageId)
      }
    }
  },
)

async function loadRules() {
  if (!selected.value) return
  rulesLoading.value = true
  try {
    const res = await getSkillRules({
      page: 1,
      page_size: 100,
      package_id: selected.value.package_id,
    }) as any
    rules.value = res.items || []
  } catch (e: any) {
    message.error(t('skillHub.loadRulesFailed') + (e.message || t('skillHub.unknownError')))
  } finally {
    rulesLoading.value = false
  }
}

async function loadMarkdown() {
  if (!selected.value) return
  markdownLoading.value = true
  markdownError.value = ''
  markdownContent.value = ''
  try {
    const res = await getSkillMarkdown(selected.value.package_id)
    markdownContent.value = res.content || ''
    // 来源标记：若数据库已保存 skill_markdown 则优先标记为数据库
    markdownSource.value = selected.value?.skill_markdown ? 'db' : 'file'
  } catch (e: any) {
    if (e?.data?.detail?.includes('不存在')) {
      markdownError.value = t('skillHub.markdownMissing')
    } else {
      markdownError.value = t('skillHub.readFailed') + (e?.data?.detail || e?.message || t('skillHub.unknownError'))
    }
  } finally {
    markdownLoading.value = false
  }
}

// ── 进化配置操作 ─────────────────────────────────────────────────────────────

async function loadEvolutionData() {
  if (!selected.value) return
  evoLoading.value = true
  try {
    const skillId = selected.value.package_id
    const [metrics, config, versions, logs] = await Promise.all([
      getSkillMetrics(skillId),
      getEvolutionConfig(skillId),
      getSkillVersions(skillId),
      getEvolutionLogs(skillId),
    ])
    evoMetrics.value = metrics
    evoConfig.value = config
    evoVersions.value = versions
    evoLogs.value = logs
    await loadChatModels()
  } catch (e: any) {
    message.error(t('skillHub.loadEvoFailed') + (e.message || t('skillHub.unknownError')))
  } finally {
    evoLoading.value = false
  }
}

/** 加载系统已配置的可用 LLM 文本模型（供进化模型选择） */
async function loadChatModels() {
  chatModelsLoading.value = true
  try {
    chatModels.value = await getChatModels()
  } catch (e: any) {
    chatModels.value = []
    // 非阻断：仅影响模型下拉，不影响其余进化数据展示
  } finally {
    chatModelsLoading.value = false
  }
}

async function saveEvoConfig() {
  if (!selected.value) return
  try {
    const { skill_id, ...data } = evoConfig.value
    await updateEvolutionConfig(selected.value.package_id, data)
    message.success(t('skillHub.evoSaved'))
  } catch (e: any) {
    message.error(t('skillHub.saveFailed') + (e.message || t('skillHub.unknownError')))
  }
}

async function handleTriggerEvolution() {
  if (!selected.value) return
  evoTriggering.value = true
  try {
    const res = await triggerEvolution(
      selected.value.package_id,
      evoConfig.value.model_code || null,
    )
    if (res.evolved) {
      message.success(res.message)
    } else {
      message.info(res.message)
    }
    await loadEvolutionData()
  } catch (e: any) {
    message.error(t('skillHub.evoFailed') + (e?.data?.detail || e.message || t('skillHub.unknownError')))
  } finally {
    evoTriggering.value = false
  }
}

async function handleRollback(version: number) {
  if (!selected.value) return
  try {
    await rollbackVersion(selected.value.package_id, version)
    message.success(t('skillHub.rolledBack', { version }))
    await loadEvolutionData()
  } catch (e: any) {
    message.error('回滚失败：' + (e?.data?.detail || e.message || '未知错误'))
  }
}

// ── 过滤与分组 ──────────────────────────────────────────────────────────────

const filteredPackages = computed(() => {
  if (!keyword.value) return packages.value
  const k = keyword.value.toLowerCase()
  return packages.value.filter(p =>
    p.name.toLowerCase().includes(k) || p.package_id.includes(k)
  )
})

const groupedPackages = computed(() => {
  const map = new Map<string, SkillPackage[]>()
  for (const pkg of filteredPackages.value) {
    const cat = pkg.category || 'other'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(pkg)
  }
  return map
})

// ── 交互 ─────────────────────────────────────────────────────────────────────

function toggleCat(cat: string) {
  if (collapsedCats.value.has(cat)) collapsedCats.value.delete(cat)
  else collapsedCats.value.add(cat)
}

function selectPackage(pkg: SkillPackage) {
  selected.value = pkg
  activeTab.value = 'detail'
}

// 切换包时自动加载规则
watch(() => selected.value?.package_id, () => {
  if (selected.value) {
    loadRules()
    loadMarkdown()
    loadEvolutionData()
  } else {
    rules.value = []
    markdownContent.value = ''
    markdownError.value = ''
  }
})

async function reloadSelected() {
  if (!selected.value) return
  try {
    const res = await getSkills()
    const updated = (res?.packages || []).find((p: SkillPackage) => p.package_id === selected.value!.package_id)
    selected.value = updated || null
  } catch { /* ignore */ }
}

async function toggleEnabled(pkg: SkillPackage) {
  try {
    await updateSkillPackage(pkg.package_id, { enabled: !pkg.enabled })
    pkg.enabled = !pkg.enabled
    if (selected.value?.package_id === pkg.package_id) {
      selected.value = { ...selected.value }
    }
    message.success(pkg.enabled ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.opFailed'))
  }
}

async function toggleScriptEnabled(s: SkillScript, enabled: boolean) {
  if (!selected.value) return
  try {
    await updateScript(selected.value.package_id, s.script_id, { enabled })
    s.enabled = enabled
    selected.value = { ...selected.value }
    message.success(enabled ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.opFailed'))
  }
}

async function handleDelete(pkg: SkillPackage) {
  try {
    await deleteSkillPackage(pkg.package_id)
    if (selected.value?.package_id === pkg.package_id) selected.value = null
    await loadPackages()
    message.success(t('skillHub.deleted'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.deleteFailed'))
  }
}

async function handleDeleteScript(s: SkillScript) {
  if (!selected.value) return
  try {
    await apiDeleteScript(selected.value.package_id, s.script_id)
    selected.value.scripts = (selected.value.scripts || []).filter(
      x => x.script_id !== s.script_id
    )
    message.success(t('skillHub.deleted'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.deleteFailed'))
  }
}

// ── 对话记录操作 ────────────────────────────────────────────────────────────────

async function loadSessions() {
  if (!selected.value?.package_id) return
  
  sessionsLoading.value = true
  messages.value = []
  currentSessionId.value = null
  
  try {
    const req: GetSessionsRequest = {
      skill_id: selected.value.package_id,
      page: sessionPage.value,
      page_size: sessionPageSize.value,
    }
    const res = await postSessions(req)
    sessions.value = res.sessions || []
    sessionPagination.value.total = res.total || 0
  } catch (e: any) {
    console.error('加载会话列表失败:', e)
    message.error(e?.data?.detail || e?.message || t('skillHub.loadSessionsFailed'))
  } finally {
    sessionsLoading.value = false
  }
}

function onSessionPageChange(page: number, pageSize?: number) {
  sessionPage.value = page
  sessionPageSize.value = pageSize || sessionPageSize.value
  loadSessions()
}

async function loadSessionMessages(session: any) {
  if (!session.session_id || !selected.value?.package_id) return
  
  currentSessionId.value = session.session_id
  messagesLoading.value = true
  messages.value = []
  
  try {
    const req: GetMessagesRequest = {
      session_id: session.session_id,
      limit: 50,
    }
    const res = await getMessages(selected.value.package_id, req)
    messages.value = res.messages || []
  } catch (e: any) {
    console.error('加载消息失败:', e)
    message.error(e?.data?.detail || t('skillHub.loadMessagesFailed'))
  } finally {
    messagesLoading.value = false
  }
}

function clearCurrentSession() {
  currentSessionId.value = null
  messages.value = []
}

async function loadMoreMessages() {
  if (!currentSessionId.value || !selected.value?.package_id) return
  
  try {
    const lastMsg = messages.value[messages.value.length - 1]
    const req: GetMessagesRequest = {
      session_id: currentSessionId.value,
      limit: 50,
      before_message_id: lastMsg.message_id,
    }
    const res = await getMessages(selected.value.package_id, req)
    const moreMessages = res.messages || []
    
    // 避免重复加载
    if (moreMessages.length > 0 && moreMessages[moreMessages.length - 1].message_id !== lastMsg.message_id) {
      messages.value = [...moreMessages, ...messages.value]
    }
  } catch (e: any) {
    console.error('加载更多消息失败:', e)
    message.error(e?.data?.detail || t('skillHub.loadMoreFailed'))
  }
}

function formatTime(timeStr: string): string {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function openPackageForm(pkg?: SkillPackage) {
  pkgFormRef.value?.open(pkg)
}

function openScriptForm(s?: SkillScript) {
  scrFormRef.value?.open(s)
}

// ── 触发规则操作 ──────────────────────────────────────────────────────────────

function openCreateRule() {
  editingRule.value = null
  ruleFormVisible.value = true
}

function openEditRule(record: SkillRule) {
  editingRule.value = record
  ruleFormVisible.value = true
}

async function toggleRuleActive(record: SkillRule, val: boolean) {
  try {
    await updateSkillRule(record.id, { is_active: val })
    record.is_active = val
    message.success(val ? t('skillHub.enabled') : t('skillHub.disabled'))
  } catch (e: any) {
    message.error(t('skillHub.updateFailed') + (e.message || t('skillHub.unknownError')))
  }
}

async function handleDeleteRule(record: SkillRule) {
  try {
    await deleteSkillRule(record.id)
    message.success(t('skillHub.deleted'))
    loadRules()
  } catch (e: any) {
    message.error(t('skillHub.deleteFailed') + (e.message || t('skillHub.unknownError')))
  }
}

function handleRuleFormSuccess() {
  ruleFormVisible.value = false
  loadRules()
}

function priorityColor(p: number): string {
  if (p <= 10) return 'red'
  if (p <= 50) return 'orange'
  if (p <= 100) return 'blue'
  return 'default'
}

function formatConditions(c: any): string {
  if (!c) return '无条件'
  return JSON.stringify(c, null, 2)
}

function truncate(s: string, n: number): string {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '...' : s
}

// ── 导入/导出 ────────────────────────────────────────────────────────────────

function handleImport() {
  fileInputRef.value?.click()
}

function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)

  Modal.confirm({
    title: t('skillHub.importConfirmTitle'),
    content: t('skillHub.importConfirm', { name: file.name }),
    okText: t('skillHub.import'),
    onOk: async () => {
      try {
        const res = await importSkillPackage(file)
        const d = res.data
        message.success(t('skillHub.importSuccess', { name: d.name, count: d.scripts_count }))
        await loadPackages()
        const newly = packages.value.find(p => p.package_id === d.package_id)
        if (newly) selectPackage(newly)
      } catch (e: any) {
        message.error(e?.data?.detail || t('skillHub.importFailed'))
      }
    },
  })

  ;(e.target as HTMLInputElement).value = ''
}

async function handleExport(pkg: SkillPackage) {
  try {
    const blob = await exportSkillPackage(pkg.package_id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pkg.package_id}.zip`
    a.click()
    URL.revokeObjectURL(url)
    message.success(t('skillHub.exportSuccess'))
  } catch (e: any) {
    message.error(e?.data?.detail || t('skillHub.exportFailed'))
  }
}

// ── 工具 ─────────────────────────────────────────────────────────────────────

// SkillHub 云市场分类多语言映射（参考 https://skillhub.cloud.tencent.com 场景分类）
const CLOUD_CATEGORY_I18N: Record<string, Partial<Record<LocaleKey, string>>> = {
  'office-efficiency': { 'zh-CN': '办公提效', 'zh-TW': '辦公提效', 'en-US': 'Office Efficiency', 'ja-JP': 'オフィス効率化' },
  'writing': { 'zh-CN': '写作辅助', 'zh-TW': '寫作輔助', 'en-US': 'Writing', 'ja-JP': 'ライティング' },
  'programming': { 'zh-CN': '编程开发', 'zh-TW': '程式開發', 'en-US': 'Programming', 'ja-JP': 'プログラミング' },
  'design': { 'zh-CN': '设计创意', 'zh-TW': '設計創意', 'en-US': 'Design', 'ja-JP': 'デザイン' },
  'research': { 'zh-CN': '科研学术', 'zh-TW': '科研學術', 'en-US': 'Research', 'ja-JP': '研究' },
  'marketing': { 'zh-CN': '营销增长', 'zh-TW': '營銷增長', 'en-US': 'Marketing', 'ja-JP': 'マーケティング' },
  'data-analysis': { 'zh-CN': '数据分析', 'zh-TW': '資料分析', 'en-US': 'Data Analysis', 'ja-JP': 'データ分析' },
  'education': { 'zh-CN': '教育培训', 'zh-TW': '教育培訓', 'en-US': 'Education', 'ja-JP': '教育' },
  'life': { 'zh-CN': '生活助手', 'zh-TW': '生活助手', 'en-US': 'Life Assistant', 'ja-JP': '生活支援' },
  'business': { 'zh-CN': '商业办公', 'zh-TW': '商業辦公', 'en-US': 'Business', 'ja-JP': 'ビジネス' },
  'image': { 'zh-CN': '图像生成', 'zh-TW': '圖像生成', 'en-US': 'Image', 'ja-JP': '画像生成' },
  'video': { 'zh-CN': '视频处理', 'zh-TW': '視頻處理', 'en-US': 'Video', 'ja-JP': '動画' },
  'audio': { 'zh-CN': '音频处理', 'zh-TW': '音頻處理', 'en-US': 'Audio', 'ja-JP': '音声' },
  'translation': { 'zh-CN': '翻译', 'zh-TW': '翻譯', 'en-US': 'Translation', 'ja-JP': '翻訳' },
  'finance': { 'zh-CN': '金融财经', 'zh-TW': '金融財經', 'en-US': 'Finance', 'ja-JP': '金融' },
  'law': { 'zh-CN': '法律', 'zh-TW': '法律', 'en-US': 'Law', 'ja-JP': '法律' },
  'health': { 'zh-CN': '医疗健康', 'zh-TW': '醫療健康', 'en-US': 'Health', 'ja-JP': 'ヘルスケア' },
  'game': { 'zh-CN': '游戏', 'zh-TW': '遊戲', 'en-US': 'Game', 'ja-JP': 'ゲーム' },
  'other': { 'zh-CN': '其他', 'zh-TW': '其他', 'en-US': 'Other', 'ja-JP': 'その他' },
}

function cloudCategoryLabel(c: HubCategory): string {
  const loc = getLocale()
  return CLOUD_CATEGORY_I18N[c.key]?.[loc] || c.name || c.key
}

const activeRepo = computed(() => hubRepos.value.find(r => r.id === hubActiveRepoId.value) || null)
const isCloudMarket = computed(() => activeRepo.value?.source_type === 'skillhub')

function categoryLabel(cat?: string) {
  return categoryOptions.value.find(o => o.item_code === cat)?.item_name || cat || '其他'
}

function iconLabel(icon?: string) {
  return ICON_OPTIONS.find(o => o.value === icon)?.label || '📦'
}
</script>

<style scoped>
.skill-management {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  height: 100vh;
  background: var(--bg-input);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.header-main {
  display: flex;
  align-items: center;
  gap: 24px;
  height: 100%;
}

.page-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

/* 顶部主 Tab 切换（位于标题栏，单行） */
.top-tab-bar {
  display: flex;
  align-items: stretch;
  height: 100%;
}

.top-tab {
  display: flex;
  align-items: center;
  padding: 0 4px;
  margin-right: 20px;
  font-size: 14px;
  color: var(--fg-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.top-tab:hover {
  color: var(--accent);
}

.top-tab.active {
  color: var(--accent);
  font-weight: 600;
  border-bottom-color: var(--accent);
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* 主内容区：占用标题栏以下全部高度，内部各自滚动 */
.skill-main {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.management-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  overflow: visible;
}

/* 左侧 */
.left-panel {
  width: 280px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-box {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.loading-wrap {
  margin: 24px auto;
  display: block;
}

.empty-hint {
  padding: 24px;
  text-align: center;
  color: var(--fg-muted);
  font-size: 13px;
}

.package-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.category-group {
  margin-bottom: 4px;
}

.cat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fg-secondary);
  cursor: pointer;
  user-select: none;
}

.cat-header:hover {
  background: var(--bg-input);
}

.cat-packages {
  padding: 0;
}

.package-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px 7px 20px;
  cursor: pointer;
  font-size: 13px;
  color: var(--fg);
  border-radius: 0;
}

.package-item:hover {
  background: var(--accent-soft);
}

.package-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  border-right: 2px solid var(--accent);
}

.pkg-icon {
  font-size: 14px;
}

.pkg-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 右侧 */
.right-panel {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-input);
}

.detail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-muted);
  font-size: 14px;
}

.detail-content {
  padding: 20px 24px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.detail-icon {
  font-size: 20px;
}

.detail-actions {
  display: flex;
  gap: 6px;
}

.detail-meta {
  background: var(--bg-surface);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 16px;
}

.detail-tabs {
  margin-top: 8px;
}

/* 触发规则 Tab */
.rules-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.conditions-preview {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-input);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--fg);
}

.script-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.script-empty {
  text-align: center;
  color: var(--fg-muted);
  padding: 16px;
  background: var(--bg-surface);
  border-radius: 6px;
}

.script-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-surface);
  border-radius: 6px;
  border: 1px solid var(--border);
  gap: 12px;
}

.script-info {
  flex: 1;
  min-width: 0;
}

.script-name {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.script-name .text-disabled {
  color: var(--fg-muted);
  text-decoration: line-through;
}

.script-cmd {
  font-size: 12px;
  color: var(--fg-secondary);
  font-family: monospace;
  margin-top: 2px;
}

.script-desc {
  font-size: 12px;
  color: var(--fg-secondary);
  margin-top: 2px;
}

.script-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.script-footer {
  margin-top: 12px;
}

/* SKILL.md Tab */
.markdown-container {
  background: var(--bg-surface);
  border-radius: 6px;
  border: 1px solid var(--border);
  min-height: 300px;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.markdown-pre {
  margin: 0;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg);
}

.markdown-error {
  padding: 24px;
}

.markdown-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-input);
  border-radius: 6px;
  border: 1px solid var(--border);
}

.markdown-source-tag {
  font-size: 12px;
  color: var(--fg-secondary);
}

.markdown-editor {
  margin: 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.evo-metrics {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg-input);
  border-radius: 6px;
}

.evo-alert {
  margin-bottom: 16px;
}

.evo-actions {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
}

.evo-config-form {
  margin-bottom: 16px;
}

.text-disabled {
  color: var(--fg-muted);
  font-size: 12px;
}

/* ── 对话记录 Tab 样式 ────────────────────────────────────────────────────────── */
.conversations-container {
  min-height: 500px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--bg-input);
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
  border-radius: 4px 4px 0 0;
}

.panel-header span {
  font-weight: 600;
  font-size: 13px;
}

.session-list-panel {
  background: var(--bg-surface);
  border-radius: 4px;
  border: 1px solid var(--border);
  height: calc(100vh - 380px);
  overflow-y: auto;
}

.session-list {
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  margin-bottom: 6px;
  background: var(--bg-input);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.session-item:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
}

.session-item.active {
  background: var(--accent-soft);
  border-color: var(--accent);
  box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.session-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: calc(100% - 60px);
}

.session-time {
  font-size: 12px;
  color: var(--fg-muted);
}

.session-info {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--fg-secondary);
}

.session-user, .session-msg-count {
  flex-shrink: 0;
}

.pagination-wrapper {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.messages-panel {
  background: var(--bg-surface);
  border-radius: 4px;
  border: 1px solid var(--border);
  height: calc(100vh - 380px);
  display: flex;
  flex-direction: column;
}

.messages-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  margin-bottom: 16px;
  padding: 12px;
  background: var(--bg-input);
  border-radius: 4px;
  border-left: 3px solid var(--border);
}

.message-item.user {
  border-left-color: var(--accent);
}

.message-item.assistant {
  border-left-color: var(--ok);
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.message-time {
  font-size: 12px;
  color: var(--fg-muted);
}

.message-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--fg);
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-calls, .tool-results {
  margin-top: 8px;
}

.json-preview {
  background: var(--bg-input);
  padding: 8px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
  margin: 0;
}

.load-more-wrapper {
  padding: 16px;
  border-top: 1px solid var(--border);
}

.messages-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--fg-muted);
  font-size: 13px;
}

/* ── 技能仓库 Tab 样式 ───────────────────────────────────────────────────────── */
.hub-body {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  min-height: 0;
  padding: 16px;
  overflow: visible;
}

/* 未选择仓库时的空状态居中可见 */
.hub-body > .ant-empty {
  margin: auto;
}

.hub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

/* 仓库列表：横向一行 Tab */
.hub-repo-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hub-repo-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--fg-secondary);
  cursor: pointer;
  background: var(--bg-input);
  transition: all 0.2s;
  white-space: nowrap;
}

.hub-repo-tab:hover {
  color: var(--accent);
  border-color: var(--accent);
}

.hub-repo-tab.active {
  color: var(--fg-inverse);
  background: var(--accent);
  border-color: var(--accent);
}

.hub-repo-tab.active .ant-tag {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
  color: var(--fg-inverse);
}

.hub-repo-name {
  font-weight: 500;
}

.hub-repo-add {
  border-radius: 16px;
}

.hub-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hub-content {
  display: flex;
  gap: 16px;
  align-items: stretch;
  flex: 1 1 auto;
  height: calc(100vh - 56px - 32px - 64px);
  min-height: 0;
  overflow: visible;
}

.hub-cats {
  width: 200px;
  flex-shrink: 0;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  max-height: 100%;
  overflow-y: auto;
}

.hub-cat-item {
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: var(--fg-secondary);
  transition: all 0.2s;
}

.hub-cat-item:hover {
  background: var(--accent-soft);
}

.hub-cat-item.active {
  background: var(--accent);
  color: var(--fg-inverse);
  font-weight: 600;
}

.hub-list {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 400px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.hub-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.hub-card {
  background: var(--bg-surface);
}

.hub-card-desc {
  font-size: 12px;
  color: var(--fg-secondary);
  line-height: 1.6;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.hub-card-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.hub-pagination {
  margin-top: 16px;
  text-align: right;
}
</style>
