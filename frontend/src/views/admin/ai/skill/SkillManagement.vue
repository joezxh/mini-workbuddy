<template>
  <div class="skill-management">
    <!-- 顶部工具栏：标题 + 主 Tab 切换 + 操作按钮（单行，不增加高度） -->
    <div class="page-header">
      <div class="header-main">
        <h2 class="page-title">🔧 技能管理</h2>
        <div class="top-tab-bar">
          <div class="top-tab" :class="{ active: activeMainTab === 'packages' }" @click="activeMainTab = 'packages'">技能包管理</div>
          <div class="top-tab" :class="{ active: activeMainTab === 'hub' }" @click="activeMainTab = 'hub'">技能仓库</div>
        </div>
      </div>
      <div class="header-actions">
        <template v-if="activeMainTab === 'packages'">
          <a-button @click="handleImport">
            <UploadOutlined /> 导入 ZIP
          </a-button>
          <a-button type="primary" @click="openPackageForm()">
            <PlusOutlined /> 新建技能包
          </a-button>
        </template>
        <a-button v-else type="primary" @click="openRepoModal">
          <PlusOutlined /> 添加仓库
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
            placeholder="搜索包名称..."
            allow-clear
            @search="loadPackages"
          />
        </div>

        <a-spin v-if="loading" class="loading-wrap" />
        <div v-else-if="!groupedPackages.size" class="empty-hint">
          暂无可用技能包
        </div>
        <div v-else class="package-list">
          <div
            v-for="[cat, pkgs] in groupedPackages"
            :key="cat"
            class="category-group"
          >
            <div class="cat-header" @click="toggleCat(cat)">
              <span>{{ categoryLabel(cat) }} ({{ pkgs.length }})</span>
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
                <a-tag v-if="!pkg.enabled" color="default" size="small">禁用</a-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧:包详情 + 触发规则 Tabs -->
      <div class="right-panel">
        <div v-if="!selected" class="detail-placeholder">
          <span>← 从左侧选择一个技能包</span>
        </div>
        <div v-else class="detail-content">
          <!-- 包头部信息 -->
          <div class="detail-header">
            <div class="detail-title">
              <span class="detail-icon">{{ iconLabel(selected.icon) }}</span>
              <span>{{ selected.name }}</span>
            </div>
            <div class="detail-actions">
              <a-button size="small" @click="openPackageForm(selected)">编辑</a-button>
              <a-button size="small" @click="toggleEnabled(selected)">
                {{ selected.enabled ? '禁用' : '启用' }}
              </a-button>
              <a-button size="small" @click="handleExport(selected)">导出</a-button>
              <a-popconfirm title="确定删除该技能包？" @confirm="handleDelete(selected)">
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>
            </div>
          </div>

          <!-- Tabs: 包详情 / 触发规则 -->
          <a-tabs v-model:activeKey="activeTab" class="detail-tabs">
            <!-- Tab 1: 包详情 -->
            <a-tab-pane key="detail" tab="包详情">
              <a-descriptions :column="2" size="small" class="detail-meta">
                <a-descriptions-item label="包 ID">{{ selected.package_id }}</a-descriptions-item>
                <a-descriptions-item label="类目">{{ categoryLabel(selected.category) }}</a-descriptions-item>
                <a-descriptions-item label="版本">{{ selected.version }}</a-descriptions-item>
                <a-descriptions-item label="状态">
                  <a-tag :color="selected.enabled ? 'green' : 'default'">
                    {{ selected.enabled ? '启用' : '禁用' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="路径">{{ selected.file_path }}</a-descriptions-item>
                <a-descriptions-item label="创建时间">{{ selected.created_at }}</a-descriptions-item>
                <a-descriptions-item label="描述" :span="2">{{ selected.description || '—' }}</a-descriptions-item>
              </a-descriptions>

              <a-divider>脚本列表</a-divider>

              <div class="script-list">
                <div v-if="!selected.scripts?.length" class="script-empty">
                  该包暂无脚本
                </div>
                <div
                  v-for="s in selected.scripts"
                  :key="s.script_id"
                  class="script-item"
                >
                  <div class="script-info">
                    <div class="script-name">
                      <span :class="{ 'text-disabled': !s.enabled }">{{ s.name }}</span>
                      <a-tag v-if="!s.enabled" color="default" size="small">禁用</a-tag>
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
                    <a-button size="small" type="text" @click="openScriptForm(s)">编辑</a-button>
                    <a-popconfirm title="确定删除？" @confirm="handleDeleteScript(s)">
                      <a-button size="small" type="text" danger>删除</a-button>
                    </a-popconfirm>
                  </div>
                </div>
              </div>

              <div class="script-footer">
                <a-button type="dashed" @click="openScriptForm()">
                  <PlusOutlined /> 新建脚本
                </a-button>
              </div>
            </a-tab-pane>

            <!-- Tab 2: 触发规则 -->
            <a-tab-pane key="rules" tab="触发规则">
              <div class="rules-toolbar">
                <a-button type="primary" size="small" @click="openCreateRule">
                  <PlusOutlined /> 新建规则
                </a-button>
                <a-button size="small" @click="loadRules">
                  <ReloadOutlined :spin="rulesLoading" /> 刷新
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
                          <EditOutlined /> 编辑
                        </a-button>
                        <a-popconfirm
                          title="确认删除该规则？"
                          ok-text="确认"
                          cancel-text="取消"
                          @confirm="handleDeleteRule(record)"
                        >
                          <a-button type="link" size="small" danger>
                            <DeleteOutlined /> 删除
                          </a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="!rulesLoading && rules.length === 0" description="暂无触发规则" />
              </a-spin>
            </a-tab-pane>

            <!-- Tab 3: SKILL.md 文档 -->
            <a-tab-pane key="markdown" tab="SKILL.md">
              <div class="markdown-toolbar">
                <a-space v-if="!markdownEditing">
                  <a-button size="small" type="primary" @click="startEditMarkdown">
                    <EditOutlined /> 编辑
                  </a-button>
                  <a-button size="small" @click="loadMarkdown">
                    <ReloadOutlined :spin="markdownLoading" /> 刷新
                  </a-button>
                </a-space>
                <a-space v-else>
                  <a-button size="small" type="primary" :loading="markdownSaving" @click="saveMarkdown">
                    保存
                  </a-button>
                  <a-button size="small" :disabled="markdownSaving" @click="cancelEditMarkdown">
                    取消
                  </a-button>
                </a-space>
                <span v-if="markdownSource" class="markdown-source-tag">
                  来源：{{ markdownSourceLabel }}
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
                    placeholder="请输入 SKILL.md 内容"
                    :auto-size="{ minRows: 18, maxRows: 36 }"
                  />
                  <pre v-else-if="markdownContent" class="markdown-pre">{{ markdownContent }}</pre>
                  <a-empty v-else-if="!markdownLoading" description="SKILL.md 内容为空" />
                </a-spin>
              </div>
            </a-tab-pane>

            <!-- Tab 4: 进化配置 -->
            <a-tab-pane key="evolution" tab="进化配置">
              <a-spin :spinning="evoLoading">
                <!-- 指标概览 -->
                <div class="evo-metrics">
                  <a-row :gutter="12">
                    <a-col :span="6">
                      <a-statistic title="成功率" :value="(evoMetrics.success_rate * 100).toFixed(1)" suffix="%" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic title="平均延迟" :value="evoMetrics.avg_latency.toFixed(2)" suffix="s" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic title="执行次数" :value="evoMetrics.execution_count" />
                    </a-col>
                    <a-col :span="6">
                      <a-statistic title="用户评分" :value="evoMetrics.user_rating.toFixed(2)" />
                    </a-col>
                  </a-row>
                </div>

                <!-- 进化状态 -->
                <a-alert
                  v-if="evoScore < evoConfig.threshold"
                  type="warning"
                  show-icon
                  :message="`综合得分 ${evoScore.toFixed(3)} 低于阈值 ${evoConfig.threshold}，建议触发进化`"
                  class="evo-alert"
                />
                <a-alert
                  v-else
                  type="success"
                  show-icon
                  :message="`综合得分 ${evoScore.toFixed(3)} ≥ 阈值 ${evoConfig.threshold}，性能良好`"
                  class="evo-alert"
                />

                <!-- 操作按钮 -->
                <div class="evo-actions">
                  <a-button type="primary" :loading="evoTriggering" @click="handleTriggerEvolution">
                    <ThunderboltOutlined /> 手动触发进化
                  </a-button>
                  <a-button @click="loadEvolutionData">
                    <ReloadOutlined /> 刷新指标
                  </a-button>
                </div>

                <!-- 配置表单 -->
                <a-divider>进化参数</a-divider>
                <a-form layout="inline" class="evo-config-form">
                  <a-form-item label="评估阈值">
                    <a-input-number
                      v-model:value="evoConfig.threshold"
                      :min="0.1" :max="1.0" :step="0.05"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item label="成功率权重">
                    <a-input-number
                      v-model:value="evoConfig.weight_success"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item label="延迟权重">
                    <a-input-number
                      v-model:value="evoConfig.weight_latency"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item label="评分权重">
                    <a-input-number
                      v-model:value="evoConfig.weight_user_rating"
                      :min="0" :max="1" :step="0.1"
                      @change="saveEvoConfig"
                    />
                  </a-form-item>
                  <a-form-item label="自动进化">
                    <a-switch v-model:checked="evoConfig.is_auto_enabled" @change="saveEvoConfig" />
                  </a-form-item>
                  <a-form-item label="进化模型">
                    <a-select
                      v-model:value="evoConfig.model_code"
                      placeholder="默认模型"
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
                <a-divider>版本历史</a-divider>
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
                        {{ record.is_stable ? '稳定' : '历史' }}
                      </a-tag>
                    </template>
                    <template v-else-if="column.key === 'action'">
                      <a-popconfirm
                        v-if="!record.is_stable"
                        :title="`确认回滚到版本 ${record.version_number}？`"
                        @confirm="handleRollback(record.version_number)"
                      >
                        <a-button type="link" size="small">回滚</a-button>
                      </a-popconfirm>
                      <span v-else class="text-disabled">当前</span>
                    </template>
                  </template>
                </a-table>
                <a-empty v-if="evoVersions.length === 0" description="暂无版本记录" />

                <!-- 进化日志 -->
                <a-divider>进化日志</a-divider>
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
                <a-empty v-if="evoLogs.length === 0" description="暂无进化记录" />
              </a-spin>
            </a-tab-pane>

            <!-- Tab 5: 对话记录 -->
            <a-tab-pane key="conversations" tab="对话记录">
              <div class="conversations-container">
                <a-row :gutter="[16, 0]">
                  <!-- 左侧：会话列表 -->
                  <a-col :span="8">
                    <div class="session-list-panel">
                      <div class="panel-header">
                        <span>执行历史 ({{ sessionPagination.total }})</span>
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
                              <span class="session-title">{{ session.session_title || '无标题' }}</span>
                              <span class="session-time">{{ formatTime(session.updated_at) }}</span>
                            </div>
                            <div class="session-info">
                              <span class="session-user">用户 ID: {{ session.user_id }}</span>
                              <span class="session-msg-count">消息：{{ session.message_count }}</span>
                            </div>
                          </div>
                          
                          <a-empty v-if="!sessions.length && !sessionsLoading" description="暂无执行记录" />
                          
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
                        <span>会话消息详情</span>
                        <a-button size="small" @click="clearCurrentSession">清空</a-button>
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
                              {{ msg.role === 'user' ? '用户' : 'AI 回复' }}
                            </a-tag>
                            <span class="message-time">{{ formatTime(msg.created_at) }}</span>
                          </div>
                          <div class="message-content">
                            {{ msg.content }}
                          </div>
                          
                          <!-- 工具调用信息 -->
                          <div v-if="msg.tool_calls" class="tool-calls">
                            <a-divider plain>工具调用</a-divider>
                            <pre class="json-preview">{{ JSON.stringify(msg.tool_calls, null, 2) }}</pre>
                          </div>
                          
                          <!-- 工具结果信息 -->
                          <div v-if="msg.tool_results" class="tool-results">
                            <a-divider plain>工具结果</a-divider>
                            <pre class="json-preview">{{ JSON.stringify(msg.tool_results, null, 2) }}</pre>
                          </div>
                        </div>
                        
                        <a-spin v-if="messagesLoading" :style="{ textAlign: 'center', padding: '20px' }" />
                        <a-empty v-if="!messages.length && !messagesLoading && currentSessionId" description="暂无消息" />
                      </div>
                      
                      <!-- 加载更多 -->
                      <div v-if="messages.length > 0" class="load-more-wrapper">
                        <a-button 
                          block 
                          @click="loadMoreMessages" 
                          :loading="messagesLoading"
                          v-if="messages.length >= 50"
                        >
                          加载更多
                        </a-button>
                      </div>
                    </div>
                    
                    <div v-else class="messages-placeholder">
                      <span>← 选择一条会话查看详细消息</span>
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
                <a-tag v-if="r.is_official" color="blue" size="small">官方</a-tag>
              </div>
              <a-button type="dashed" size="small" class="hub-repo-add" @click="openRepoModal()">
                <PlusOutlined /> 管理仓库
              </a-button>
            </div>
            <div class="hub-toolbar-right">
              <a-input-search
                v-model:value="hubKeyword"
                placeholder="搜索 skill 名称 / 描述 / 标签"
                allow-clear
                style="width: 280px"
                @search="loadHubSkills(true)"
              />
              <a-button @click="handleRefreshHubRepo" :loading="hubRefreshing">
                <ReloadOutlined /> 刷新仓库
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
                全部 ({{ hubSkillTotal }})
              </div>
              <div
                v-for="c in hubCategories"
                :key="c.key"
                class="hub-cat-item"
                :class="{ active: hubActiveCat === c.key }"
                @click="selectHubCat(c.key)"
              >
                {{ c.name }} ({{ c.count }})
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
                        安装
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
                <a-empty v-if="!hubLoading && !hubSkills.length" description="该分类下暂无技能" />
                <div class="hub-pagination" v-if="hubSkillTotal > hubPageSize">
                  <a-pagination
                    v-model:current="hubPage"
                    v-model:page-size="hubPageSize"
                    :total="hubSkillTotal"
                    show-size-changer
                    :show-total="(t: number) => `共 ${t} 个`"
                    @change="loadHubSkills(false)"
                  />
                </div>
              </a-spin>
            </div>
          </div>
          <a-empty v-else description="请先选择或添加技能仓库" />
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
      title="技能仓库管理"
      @ok="saveRepo"
      :confirm-loading="repoSaving"
      :ok-text="repoEditingId ? '保存' : '添加'"
    >
      <a-form layout="vertical">
        <a-form-item label="仓库名称">
          <a-input v-model:value="repoForm.name" placeholder="如：官方仓库 / 第三方仓库" />
        </a-form-item>
        <a-form-item label="Git 地址">
          <a-input
            v-model:value="repoForm.url"
            placeholder="https://github.com/anbeime/skill.git"
            :disabled="repoForm.is_official"
          />
        </a-form-item>
        <a-form-item label="分支">
          <a-input v-model:value="repoForm.branch" :disabled="repoForm.is_official" />
        </a-form-item>
      </a-form>
      <a-divider>已配置仓库</a-divider>
      <a-list size="small" :data-source="hubRepos">
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta :description="item.url">
              <template #title>
                {{ item.name }}
                <a-tag v-if="item.is_official" color="blue" size="small">官方</a-tag>
              </template>
            </a-list-item-meta>
            <template #actions>
              <a v-if="!item.is_official" @click="editRepo(item)">编辑</a>
              <a-popconfirm
                v-if="!item.is_official"
                title="确认删除该仓库？"
                @confirm="deleteRepo(item)"
              >
                <a style="color:#ff4d4f">删除</a>
              </a-popconfirm>
              <span v-if="item.is_official" class="text-disabled">不可删除</span>
            </template>
          </a-list-item>
        </template>
      </a-list>
    </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
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
    case 'db': return '数据库'
    case 'workspace': return '工作区'
    case 'file': return '文件系统'
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
    message.success('SKILL.md 已保存（数据库优先）')
  } catch (e: any) {
    message.error('保存失败：' + (e?.data?.detail || e?.message || '未知错误'))
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
  { title: '版本号', dataIndex: 'version_number', key: 'version_number', width: 80 },
  { title: '状态', key: 'is_stable', width: 80 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 80 },
]

const logColumns = [
  { title: '触发类型', dataIndex: 'trigger_type', key: 'trigger_type', width: 100 },
  { title: '版本变化', key: 'version_change', width: 120,
    customRender: ({ record }: any) => `${record.from_version ?? '-'} → ${record.to_version ?? '-'}` },
  { title: '结果', key: 'result', width: 100 },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
]

const ruleColumns = [
  { title: '规则名称', dataIndex: 'name', key: 'name', width: 180 },
  { title: '所属专家', dataIndex: 'agent_name', key: 'agent_name', width: 150 },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '触发条件', key: 'conditions', width: 240 },
  { title: '状态', dataIndex: 'is_active', key: 'is_active', width: 80 },
  { title: '操作', key: 'action', width: 150, fixed: 'right' as const },
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
    message.error('加载失败：' + (e?.data?.detail || e?.message || String(e)))
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
    console.log('[hub-debug] loadHubRepos ->', repos)
    hubRepos.value = repos || []
    if (!hubActiveRepoId.value && hubRepos.value.length) {
      hubActiveRepoId.value = hubRepos.value[0].id
      await loadHubCategoriesAndSkills()
    }
  } catch (e: any) {
    message.error('加载技能仓库失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
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
    console.log('[hub-debug] cats ->', cats, '| skills ->', list.items, '| total ->', list.total)
  } catch (e: any) {
    message.error('加载技能列表失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
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
    message.success('仓库已刷新')
    await loadHubCategoriesAndSkills()
  } catch (e: any) {
    message.error('刷新失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    hubRefreshing.value = false
  }
}

async function handleInstallHubSkill(item: HubSkillItem) {
  if (!hubActiveRepoId.value) return
  item._installing = true
  try {
    const res = await installHubSkill(hubActiveRepoId.value, item.id)
    message.success(`已安装：${res.name || item.name}`)
    loadPackages()
  } catch (e: any) {
    message.error('安装失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
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
    message.warning('请填写仓库名称与 Git 地址')
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
    message.success('仓库已保存')
    repoModalVisible.value = false
    await loadHubRepos()
  } catch (e: any) {
    message.error('保存失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
  } finally {
    repoSaving.value = false
  }
}

async function deleteRepo(r: HubRepo) {
  try {
    await deleteHubRepo(r.id)
    message.success('仓库已删除')
    if (hubActiveRepoId.value === r.id) {
      hubActiveRepoId.value = null
      hubSkills.value = []
    }
    await loadHubRepos()
  } catch (e: any) {
    message.error('删除失败：' + (e?.response?.data?.detail || e?.message || '未知错误'))
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
    message.error('加载规则失败：' + (e.message || '未知错误'))
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
      markdownError.value = '该技能包目录下不存在 SKILL.md 文件'
    } else {
      markdownError.value = '读取失败：' + (e?.data?.detail || e?.message || '未知错误')
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
    message.error('加载进化数据失败：' + (e.message || '未知错误'))
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
    message.success('进化配置已保存')
  } catch (e: any) {
    message.error('保存失败：' + (e.message || '未知错误'))
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
    message.error('进化失败：' + (e?.data?.detail || e.message || '未知错误'))
  } finally {
    evoTriggering.value = false
  }
}

async function handleRollback(version: number) {
  if (!selected.value) return
  try {
    await rollbackVersion(selected.value.package_id, version)
    message.success(`已回滚到版本 ${version}`)
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
    message.success(pkg.enabled ? '已启用' : '已禁用')
  } catch (e: any) {
    message.error(e?.data?.detail || '操作失败')
  }
}

async function toggleScriptEnabled(s: SkillScript, enabled: boolean) {
  if (!selected.value) return
  try {
    await updateScript(selected.value.package_id, s.script_id, { enabled })
    s.enabled = enabled
    selected.value = { ...selected.value }
    message.success(enabled ? '已启用' : '已禁用')
  } catch (e: any) {
    message.error(e?.data?.detail || '操作失败')
  }
}

async function handleDelete(pkg: SkillPackage) {
  try {
    await deleteSkillPackage(pkg.package_id)
    if (selected.value?.package_id === pkg.package_id) selected.value = null
    await loadPackages()
    message.success('已删除')
  } catch (e: any) {
    message.error(e?.data?.detail || '删除失败')
  }
}

async function handleDeleteScript(s: SkillScript) {
  if (!selected.value) return
  try {
    await apiDeleteScript(selected.value.package_id, s.script_id)
    selected.value.scripts = (selected.value.scripts || []).filter(
      x => x.script_id !== s.script_id
    )
    message.success('已删除')
  } catch (e: any) {
    message.error(e?.data?.detail || '删除失败')
  }
}

// ── 对话记录操作 ────────────────────────────────────────────────────────────────

async function loadSessions() {
  if (!selected.value?.package_id) return
  
  console.log('开始加载会话列表:', selected.value.package_id)
  sessionsLoading.value = true
  messages.value = []
  currentSessionId.value = null
  
  try {
    const req: GetSessionsRequest = {
      skill_id: selected.value.package_id,
      page: sessionPage.value,
      page_size: sessionPageSize.value,
    }
    console.log('请求参数:', req)
    const res = await postSessions(req)
    console.log('响应结果:', res)
    sessions.value = res.sessions || []
    sessionPagination.value.total = res.total || 0
    console.log(`成功加载 ${sessions.value.length} 条会话`)
  } catch (e: any) {
    console.error('加载会话列表失败:', e)
    message.error(e?.data?.detail || e?.message || String(e))
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
    message.error(e?.data?.detail || '加载消息失败')
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
    message.error(e?.data?.detail || '加载更多失败')
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
    message.success(val ? '已启用' : '已禁用')
  } catch (e: any) {
    message.error('更新失败：' + (e.message || '未知错误'))
  }
}

async function handleDeleteRule(record: SkillRule) {
  try {
    await deleteSkillRule(record.id)
    message.success('删除成功')
    loadRules()
  } catch (e: any) {
    message.error('删除失败：' + (e.message || '未知错误'))
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
    title: '导入确认',
    content: `确定导入 ${file.name}？`,
    okText: '导入',
    onOk: async () => {
      try {
        const res = await importSkillPackage(file)
        const d = res.data
        message.success(`导入成功: ${d.name}（${d.scripts_count} 个脚本）`)
        await loadPackages()
        const newly = packages.value.find(p => p.package_id === d.package_id)
        if (newly) selectPackage(newly)
      } catch (e: any) {
        message.error(e?.data?.detail || '导入失败')
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
    message.success('导出成功')
  } catch (e: any) {
    message.error(e?.data?.detail || '导出失败')
  }
}

// ── 工具 ─────────────────────────────────────────────────────────────────────

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
  background: #f5f5f5;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
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
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.top-tab:hover {
  color: #1890ff;
}

.top-tab.active {
  color: #1890ff;
  font-weight: 600;
  border-bottom-color: #1890ff;
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
  background: #fff;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-box {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.loading-wrap {
  margin: 24px auto;
  display: block;
}

.empty-hint {
  padding: 24px;
  text-align: center;
  color: #999;
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
  color: #666;
  cursor: pointer;
  user-select: none;
}

.cat-header:hover {
  background: #f5f5f5;
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
  color: #333;
  border-radius: 0;
}

.package-item:hover {
  background: #f0f7ff;
}

.package-item.active {
  background: #e6f4ff;
  color: #1677ff;
  border-right: 2px solid #1677ff;
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
  background: #fafafa;
}

.detail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
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
  background: #fff;
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
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 3px;
  color: #333;
}

.script-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.script-empty {
  text-align: center;
  color: #999;
  padding: 16px;
  background: #fff;
  border-radius: 6px;
}

.script-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px 12px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
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
  color: #bbb;
  text-decoration: line-through;
}

.script-cmd {
  font-size: 12px;
  color: #888;
  font-family: monospace;
  margin-top: 2px;
}

.script-desc {
  font-size: 12px;
  color: #666;
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
  background: #fff;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
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
  color: #333;
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
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.markdown-source-tag {
  font-size: 12px;
  color: #888;
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
  background: #fafafa;
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
  color: #999;
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
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 8px;
  border-radius: 4px 4px 0 0;
}

.panel-header span {
  font-weight: 600;
  font-size: 13px;
}

.session-list-panel {
  background: #fff;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
  height: calc(100vh - 380px);
  overflow-y: auto;
}

.session-list {
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  margin-bottom: 6px;
  background: #fafafa;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.session-item:hover {
  background: #e6f7ff;
  border-color: #91d5ff;
}

.session-item.active {
  background: #e6f7ff;
  border-color: #1890ff;
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
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: calc(100% - 60px);
}

.session-time {
  font-size: 12px;
  color: #999;
}

.session-info {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #666;
}

.session-user, .session-msg-count {
  flex-shrink: 0;
}

.pagination-wrapper {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.messages-panel {
  background: #fff;
  border-radius: 4px;
  border: 1px solid #f0f0f0;
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
  background: #fafafa;
  border-radius: 4px;
  border-left: 3px solid #f0f0f0;
}

.message-item.user {
  border-left-color: #1890ff;
}

.message-item.assistant {
  border-left-color: #52c41a;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.message-time {
  font-size: 12px;
  color: #999;
}

.message-content {
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
}

.tool-calls, .tool-results {
  margin-top: 8px;
}

.json-preview {
  background: #f5f5f5;
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
  border-top: 1px solid #f0f0f0;
}

.messages-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
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
  border: 1px solid #d9d9d9;
  border-radius: 16px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  background: #fafafa;
  transition: all 0.2s;
  white-space: nowrap;
}

.hub-repo-tab:hover {
  color: #1890ff;
  border-color: #91d5ff;
}

.hub-repo-tab.active {
  color: #fff;
  background: #1890ff;
  border-color: #1890ff;
}

.hub-repo-tab.active .ant-tag {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.4);
  color: #fff;
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
  background: #fafafa;
  border: 1px solid #f0f0f0;
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
  color: #555;
  transition: all 0.2s;
}

.hub-cat-item:hover {
  background: #e6f7ff;
}

.hub-cat-item.active {
  background: #1890ff;
  color: #fff;
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
  background: #fff;
}

.hub-card-desc {
  font-size: 12px;
  color: #666;
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
