/**
 * 本体工作台 i18n 资源（单点注入，spec §6.3 / R3 文案）。
 *
 * 设计：本体子视图所有可见文案经 `t2(中文原文)` 收口（见 views/data-source/ontology/ontologyText.ts）。
 * 这里以「中文原文为键」登记各语言译文，`t2` 依 vue-i18n 当前 locale 查表：
 * - zh-CN：不登记（键即简体原文，直接返回）；
 * - zh-TW：缺省回落简体原文（同属中文，避免劣化翻译）；
 * - en-US / ja-JP：命中返回译文，未命中回落 `en-US`，再回落原文（中文）。
 *
 * 这样新增语言只需补本表，组件层零改动；未翻译串优雅回退，不会崩、不会显示 undefined。
 * 错误码文案（R3 契约）见 `ONTOLOGY_ERRORS`，由 `utils/apiErrorCodes.ts` 按 locale 消费。
 * 注意：对象键统一加引号（含空格/全角标点/符号如 ① （） ？ 的中文键非合法标识符）。
 */

/** 中文原文 → en-US 译文（导航 / 动作 / 标签为主，长句回落中文即可） */
const UI_EN: Record<string, string> = {
  '选择本体': 'Select ontology',
  '新建本体': 'New ontology',
  '请选择或新建一个本体开始建模': 'Select or create an ontology to start modeling',
  '总览': 'Overview',
  '构建': 'Build',
  '审阅台': 'Review',
  '图谱': 'Graph',
  '检视': 'Inspector',
  '版本': 'Versions',
  '应用发布': 'App Publishing',
  // 表单通用
  '编码': 'Code',
  '编码 code': 'Code',
  '名称': 'Name',
  '描述': 'Description',
  '颜色': 'Color',
  '类型': 'Type',
  '标识': 'Identifier',
  '字段': 'Field',
  '建议值': 'Suggested value',
  '操作': 'Action',
  '元素类型': 'Element type',
  '刷新': 'Refresh',
  '取消': 'Cancel',
  '添加': 'Add',
  '执行': 'Run',
  '查询': 'Search',
  '重置': 'Reset',
  '详情': 'Details',
  '阶段': 'Phase',
  // 元数据 / 送数
  '元数据浏览': 'Metadata Browse',
  '资产送数': 'Asset Scoping',
  '全部来源': 'All sources',
  '暂无已接入数据源': 'No connected data sources',
  '搜索表名 / 字段名 / 注释': 'Search table / column / comment',
  '按标签筛选': 'Filter by tag',
  '表': 'Table',
  '新建标签': 'New tag',
  '标签已创建': 'Tag created',
  '租户内唯一': 'Unique within tenant',
  'code 与名称必填': 'Code and name are required',
  '已勾选': 'Selected',
  '张表': 'table(s)',
  '来源': 'Source',
  '选择目标本体': 'Target ontology',
  '送入本体建模': 'Send to modeling scope',
  '清空勾选': 'Clear selection',
  '已映射': 'Mapped',
  '（无字段摘要）': '(no column digest)',
  '列': 'cols',
  '行': 'rows',
  '共': 'total',
  '条': 'item(s)',
  // 构建
  '构建模式': 'Build mode',
  '仅规则': 'Rules only',
  '规则 + AI 语义补全': 'Rules + AI semantic',
  '开始构建': 'Start build',
  '构建中…': 'Building…',
  '构建完成': 'Build completed',
  '构建失败': 'Build failed',
  'AI 语义补全不可用，已按规则构建': 'AI semantic completion unavailable, built by rules only',
  '命中既有任务（幂等），复用其进度': 'Hit existing job (idempotent), reusing its progress',
  // 审阅
  '待审': 'Pending',
  '已采纳': 'Accepted',
  '已驳回': 'Rejected',
  '全部类型': 'All types',
  '规则': 'Rule',
  '采纳': 'Accept',
  '采纳选中': 'Accept selected',
  '驳回选中': 'Reject selected',
  '全部采纳': 'Accept all',
  '确认采纳全部待审项？': 'Accept all pending items?',
  '未脱敏': 'Unmasked',
  // 版本 / 发布
  '发布': 'Publish',
  '发布新版本': 'Publish new version',
  '变更说明（可选）': 'Change note (optional)',
  '发布被门禁阻断': 'Publish blocked by gate',
  '版本时间线': 'Version timeline',
  '尚无发布版本': 'No published versions yet',
  '对象': 'Object',
  '关系': 'Relation',
  '属性': 'Property',
  '映射': 'Mapping',
  '选择版本查看详情': 'Select a version to view details',
  '门禁结论（5 项）': 'Gate results (5 checks)',
  '登记发布目标': 'Register publish target',
  '当前版本': 'Current version',
  '版本落后': 'Stale',
  '最新': 'Latest',
  '目标类型': 'Target type',
  '目标标识': 'Target code',
  '目标侧唯一标识': 'Unique id on target side',
  // 检视 / 证据 / 语义
  '证据链': 'Evidence',
  '该元素暂无留痕证据': 'No evidence recorded for this element',
  'AI 语义建议': 'AI semantic suggestion',
  '为此元素生成语义补全': 'Generate semantic completion',
  '语义建议已采纳': 'Semantic suggestion adopted',
  '无可用建议': 'No suggestion available',
  // 图谱
  '工作流视图（表→对象）': 'Workflow view (table→object)',
  '架构视图（对象↔关系）': 'Architecture view (object↔relation)',
  // 助手
  '建模助手': 'Modeling Assistant',
  '询问': 'Ask',
  '解释': 'Explain',
  '圈定': 'Scope',
  '草拟': 'Draft',
  '候选预览': 'Candidate preview',
  '幻觉丢弃': 'Hallucinations dropped',
  'AI 不可用，已降级': 'AI unavailable, degraded',
  '① 预览': '1. Preview',
  '② 确认提交': '2. Commit',
  '元素': 'Element',
  '已提交': 'Committed',
  '无候选': 'No candidates',
}

/** 中文原文 → ja-JP 译文（核心导航，其余回落 en/中文） */
const UI_JA: Record<string, string> = {
  '选择本体': 'オントロジー選択',
  '新建本体': '新規オントロジー',
  '总览': '概要',
  '构建': '構築',
  '审阅台': 'レビュー',
  '图谱': 'グラフ',
  '检视': 'インスペクタ',
  '版本': 'バージョン',
  '应用发布': 'アプリ公開',
  '元数据浏览': 'メタデータ閲覧',
  '资产送数': 'アセットスコープ',
  '刷新': '更新',
  '取消': 'キャンセル',
  '名称': '名称',
  '描述': '説明',
}

/** code → en-US 文案（与后端 app/core/api_error.py 常量严格一致，21 项全覆盖） */
const ERR_EN: Record<string, string> = {
  'ONTOLOGY_NOT_FOUND': 'Ontology not found',
  'ONTOLOGY_CODE_DUPLICATED': 'Ontology code already exists',
  'ONTOLOGY_STOPPED': 'Ontology is stopped; operation rejected',
  'ONTOLOGY_HAS_VERSIONS': 'Ontology has published versions and cannot be deleted',
  'BUILD_SCOPE_EMPTY': 'Build scope is empty',
  'BUILD_ALREADY_RUNNING': 'A build job is already running',
  'REVIEW_ITEM_NOT_FOUND': 'Review item not found',
  'PUBLISH_BLOCKED_PENDING_REVIEW': 'Publish blocked: pending review items exist',
  'PUBLISH_BLOCKED_REGRESSION': 'Publish blocked: regression vs previous version',
  'PUBLISH_BLOCKED_INTEGRITY': 'Publish blocked: structural integrity check failed',
  'PUBLISH_BLOCKED_MASK_COVERAGE': 'Publish blocked: sensitive-column masking insufficient',
  'PUBLISH_BLOCKED_UNREVIEWED_SOURCE': 'Publish blocked: snapshot has unreviewed LLM-sourced items',
  'SEMANTIC_UNAVAILABLE': 'AI semantic service unavailable',
  'EXPORT_EMPTY': 'Export content is empty',
  'DRAFT_SCOPE_EMPTY': 'Scope is empty',
  'ASSET_TAG_IN_USE': 'Tag is still bound to assets and cannot be deleted',
  'TAG_CODE_DUPLICATED': 'Tag code already exists',
  'PUBLISH_TARGET_NOT_FOUND': 'Publish target not found or invalid',
  'ASSISTANT_INTENT_UNSUPPORTED': 'Assistant does not support this intent',
  'ASSISTANT_BUILD_PREVIEW_STALE': 'Preview expired or fingerprint mismatch; re-preview then commit',
  'ASSISTANT_BUILD_EMPTY': 'Model produced no parseable candidates',
}

export const ONTOLOGY_UI: Record<string, Record<string, string>> = {
  'en-US': UI_EN,
  'ja-JP': UI_JA,
}

export const ONTOLOGY_ERRORS: Record<string, Record<string, string>> = {
  'en-US': ERR_EN,
}

/**
 * 依当前 locale 解析本体 UI 文案。中文变体（zh-*）优先原文，非中文回落 en 再回落原文。
 */
export function translateOntology(zh: string, locale: string): string {
  if (locale.startsWith('zh')) {
    return ONTOLOGY_UI[locale]?.[zh] ?? zh
  }
  return ONTOLOGY_UI[locale]?.[zh] ?? ONTOLOGY_UI['en-US']?.[zh] ?? zh
}
