/**
 * 菜单彩色图标 —— Emoji 图标集。
 *
 * 来源：super-agent 工作区左侧分组侧栏使用的彩色 emoji
 * （见 src/views/super-agent/SuperAgentWorkspace.vue 的 GROUPS 常量），
 * 另补充一批全局菜单与业务域常用 emoji。
 *
 * 存储约定：`sys_menu.color_icon` 一列同时承载两种取值：
 *   1. `data:image/...` 开头的 data URL —— 用户上传的图片（≤100KB）；
 *   2. 本图标集中的 emoji 字符 —— 由彩色 emoji 字体渲染。
 * 前端统一用 isImageColorIcon() / isEmojiColorIcon() 判定走 <img> 还是 <span>，
 * 二者同时存在时图片优先（与「彩色图标优先于 antd 图标名」的规则一致）。
 */

export interface EmojiIconItem {
  /** emoji 字符（含必要的变体选择符 U+FE0F，否则会退化成单色轮廓） */
  char: string
  /** 中文名称，用于菜单管理界面搜索与悬浮提示 */
  name: string
  /** 额外搜索关键词 */
  keywords?: string[]
}

export interface EmojiIconGroup {
  /** 分组名 */
  group: string
  items: EmojiIconItem[]
}

/** Emoji 图标集（按分组，顺序即菜单管理界面展示顺序）。 */
export const EMOJI_ICON_GROUPS: EmojiIconGroup[] = [
  {
    group: 'SuperAgent',
    items: [
      { char: '📊', name: '看板', keywords: ['dashboard', '看板', '统计', 'chart'] },
      { char: '🎯', name: '目标', keywords: ['goal', '目标', 'demo', '演示'] },
      { char: '📋', name: '工单', keywords: ['detail', '详情', '工单', 'list', 'tickets'] },
      { char: '💬', name: '对话', keywords: ['chat', '对话', '消息', 'message'] },
      { char: '🌊', name: '动态', keywords: ['feed', '动态', '消息流'] },
      { char: '💡', name: '点子', keywords: ['idea', '点子', '创意', 'lightbulb'] },
      { char: '🧠', name: '模型', keywords: ['model', '模型', '大脑'] },
      { char: '🔌', name: '插件', keywords: ['mcp', '插件', '插头', 'plugin'] },
      { char: '🛡️', name: '策略', keywords: ['policy', '策略', '护盾', 'shield'] },
      { char: '📚', name: '知识库', keywords: ['kb', '知识库', '书籍', 'book'] },
      { char: '⚙️', name: '参数', keywords: ['exec', '参数', '设置', 'gear'] },
      { char: '🔒', name: '安全', keywords: ['security', '安全', '锁', 'lock'] },
      { char: '🔗', name: '触发源', keywords: ['source', '源', '链接', 'link'] },
      { char: '🤖', name: 'AI 助手', keywords: ['ai', '机器人', '助手', 'bot'] },
      { char: '⏰', name: '提醒', keywords: ['定时', '提醒', 'alarm', 'schedule'] },
      { char: '✅', name: '审批通过', keywords: ['审批', '通过', 'check', 'done'] },
      { char: '📌', name: '置顶', keywords: ['pin', '置顶'] },
      { char: '🏢', name: '工作空间', keywords: ['workspace', '空间', '公司'] },
      { char: '👀', name: '观察', keywords: ['观察', '展示态', 'eye'] },
      { char: '🐙', name: '代码源', keywords: ['github', '章鱼', 'trigger'] },
      { char: '➕', name: '新建', keywords: ['add', '新建', 'plus'] },
    ],
  },
  {
    group: '通用导航',
    items: [
      { char: '🏠', name: '首页', keywords: ['home', '首页'] },
      { char: '📁', name: '文件夹', keywords: ['folder', '文件', '目录'] },
      { char: '📄', name: '文档', keywords: ['document', '文档'] },
      { char: '🗂️', name: '归档', keywords: ['archive', '归档'] },
      { char: '🧩', name: '模块', keywords: ['module', '模块', '插件'] },
      { char: '🧭', name: '导航', keywords: ['navigate', '导航', '指南针'] },
      { char: '🗺️', name: '地图', keywords: ['map', '地图'] },
      { char: '🖥️', name: '服务', keywords: ['service', '服务', '终端'] },
      { char: '📦', name: '交付物', keywords: ['package', '交付', '打包'] },
      { char: '🗑️', name: '回收站', keywords: ['trash', '删除', '回收'] },
      { char: '🔔', name: '通知', keywords: ['notification', '通知', '铃铛'] },
      { char: '⭐', name: '收藏', keywords: ['star', '收藏', '星'] },
      { char: '❤️', name: '关注', keywords: ['heart', '关注', '喜欢'] },
      { char: '🚀', name: '发布', keywords: ['launch', '发布', '火箭'] },
      { char: '💼', name: '工作台', keywords: ['work', '工作台', '工具箱'] },
      { char: '📅', name: '日程', keywords: ['schedule', '日程', '日历'] },
      { char: '👥', name: '团队', keywords: ['team', '团队', '用户'] },
      { char: '📝', name: '编辑', keywords: ['edit', '编辑', '写作'] },
      { char: '🔍', name: '搜索', keywords: ['search', '搜索'] },
      { char: '⚡', name: '快速', keywords: ['fast', '快速', '闪电'] },
      { char: '🌐', name: '互联网', keywords: ['web', '互联网', '全球'] },
      { char: '🧮', name: '计算', keywords: ['compute', '计算'] },
      { char: '🗓️', name: '计划', keywords: ['plan', '计划', '日程'] },
      { char: '🔢', name: '指标', keywords: ['metric', '指标', '数字'] },
      { char: '🏷️', name: '标签', keywords: ['tag', '标签'] },
      { char: '🪄', name: '智能', keywords: ['magic', '智能', '魔法'] },
      { char: '🏆', name: '成果', keywords: ['trophy', '成果', '奖杯'] },
      { char: '🎓', name: '培训', keywords: ['training', '培训', '学习'] },
      { char: '🛠️', name: '工具', keywords: ['tool', '工具', '扳手'] },
    ],
  },
  {
    group: '业务与数据',
    items: [
      { char: '📈', name: '分析', keywords: ['analytics', '分析', '增长'] },
      { char: '📉', name: '监控', keywords: ['monitoring', '监控', '下降'] },
      { char: '🧾', name: '单据', keywords: ['invoice', '单据', '票据'] },
      { char: '💰', name: '费用', keywords: ['money', '费用', '金额'] },
      { char: '💹', name: '交易', keywords: ['trade', '交易'] },
      { char: '🏦', name: '金融', keywords: ['finance', '金融', '银行'] },
      { char: '🏥', name: '医疗', keywords: ['health', '医疗', '健康'] },
      { char: '🏭', name: '生产', keywords: ['production', '生产', '工厂'] },
      { char: '🛒', name: '电商', keywords: ['ecommerce', '电商', '购物'] },
      { char: '⚖️', name: '合规', keywords: ['compliance', '合规', '法规'] },
      { char: '🚨', name: '告警', keywords: ['alert', '告警', '预警'] },
      { char: '🔐', name: '加密', keywords: ['encrypt', '加密', '密钥'] },
      { char: '📡', name: '采集', keywords: ['collect', '采集', '信号'] },
      { char: '🗃️', name: '存储', keywords: ['storage', '存储', '数据库'] },
      { char: '📤', name: '导出', keywords: ['export', '导出'] },
      { char: '📥', name: '导入', keywords: ['import', '导入'] },
      { char: '🧱', name: '集成', keywords: ['integration', '集成', '积木'] },
      { char: '🧬', name: '推理', keywords: ['dna', '推理', '模型'] },
      { char: '🎲', name: '推演', keywords: ['simulate', '推演', '仿真'] },
      { char: '🧪', name: '实验', keywords: ['experiment', '实验'] },
      { char: '🎨', name: '设计', keywords: ['design', '设计', '画笔'] },
      { char: '🤝', name: '任务派发', keywords: ['task', '任务', '派发'] },
    ],
  },
  {
    group: '状态标记',
    items: [
      { char: '🟢', name: '正常', keywords: ['ok', '正常', 'green'] },
      { char: '🟡', name: '警告', keywords: ['warn', '警告', 'yellow'] },
      { char: '🔴', name: '严重', keywords: ['error', '严重', 'red'] },
      { char: '🔵', name: '信息', keywords: ['info', '信息', 'blue'] },
      { char: '⚪', name: '停用', keywords: ['disabled', '停用'] },
      { char: '⚠️', name: '注意', keywords: ['warning', '注意', '警告'] },
      { char: '♻️', name: '回收', keywords: ['recycle', '回收'] },
      { char: '🔁', name: '循环', keywords: ['loop', '循环', '重试'] },
    ],
  },
]

/** 扁平化后的全部 emoji 图标。 */
export const EMOJI_ICONS: EmojiIconItem[] = EMOJI_ICON_GROUPS.flatMap(g => g.items)

/**
 * 彩色 emoji 字体栈见 `src/styles/tokens.css` 的 `--emoji-font` 变量
 * （同时含 @font-face 声明，指向 public/fonts/mbw-emoji.woff2 自托管字体子集）。
 * 组件统一用 `var(--emoji-font)`，此处不再重复定义，避免双来源漂移。
 */

/** 是否为图片型彩色图标（data URL）。 */
export function isImageColorIcon(value?: string | null): boolean {
  return !!value && /^data:image\//i.test(value.trim())
}

/** 是否为 emoji 型彩色图标（emoji 字符，非 data URL）。 */
export function isEmojiColorIcon(value?: string | null): boolean {
  if (!value) return false
  const text = value.trim()
  if (!text || isImageColorIcon(text)) return false
  return /\p{Extended_Pictographic}/u.test(text)
}

/** 按关键字过滤 emoji 图标分组（大小写不敏感，匹配名称与关键词）。 */
export function filterEmojiIconGroups(keyword: string): EmojiIconGroup[] {
  const kw = keyword.trim().toLowerCase()
  if (!kw) return EMOJI_ICON_GROUPS
  return EMOJI_ICON_GROUPS
    .map(group => ({
      group: group.group,
      items: group.items.filter(
        item =>
          item.name.toLowerCase().includes(kw) ||
          item.char.includes(kw) ||
          (item.keywords || []).some(k => k.toLowerCase().includes(kw)),
      ),
    }))
    .filter(group => group.items.length > 0)
}
