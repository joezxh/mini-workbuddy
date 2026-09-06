# MinWorkBuddy 设计系统文档

> **一句话定义**：MinWorkBuddy 采用「暗色科技风 + 磨砂玻璃」设计语言，以 Indigo-Teal 渐变为品牌色，Orbitron/IBM Plex Sans 字体组合，14-26px 大圆角面板，HUD 仪器面板风格的非对称 bento 网格布局。

---

## 1. 品牌核心

### 1.1 设计理念
- **Agent Nexus**：多智能体协作网络，六边形外框 + 三个互联节点（Agent/Team/Skill）
- **反模板精神**：拒绝 AI 默认审美（三列等宽、渐变背景按钮、圆角卡片），采用故意非对称的 7:5:5:7 bento 网格
- **仪器面板感**：HUD 网格、角标、扫描线等装饰层营造"控制台"氛围，但不改变布局流

### 1.2 配色系统

**品牌色**（brand-kit.html 定义）：
- Indigo `#4F6EF7` → Teal `#22D3AE` 渐变（品牌标识、主视觉）
- Amber `#F5A623`（强调色、警示）

**前端映射**（tokens.css 变量）：
```css
/* Dark skin */
--accent: #4aa3ff;           /* 主操作色 */
--accent-hover: #7fd0ff;     /* 悬停态 */
--accent-2: #f2b66d;         /* 次要强调（琥珀） */
--accent-soft: rgba(74, 163, 255, 0.12);

/* Light skin */
--accent: #3b82f6;
--accent-hover: #2563eb;
--accent-2: #f59e0b;
```

**使用规则**：
- 蓝色（`--accent`）：主按钮、链接、活跃状态、图标高亮
- 琥珀（`--accent-2`）：次要强调、警示、HUD 装饰光晕
- **禁止**：琥珀色用于主操作按钮（仅蓝色可做主按钮）

---

## 2. 字体规范

### 2.1 字体栈
```css
/* Display: 仅用于拉丁文/数字（标题、指标） */
--font-display: 'Orbitron', 'Space Grotesk', 'HarmonyOS Sans SC', 
                'PingFang SC', 'Microsoft YaHei', sans-serif;

/* Body: 正文、界面文本 */
--font-sans: 'IBM Plex Sans', 'Space Grotesk', 'HarmonyOS Sans SC',
             'PingFang SC', 'Microsoft YaHei', system-ui, -apple-system, 
             'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;

/* Tech: 大写标签、数据读出 */
--font-tech: 'Chakra Petch', 'IBM Plex Sans', 'HarmonyOS Sans SC',
             'PingFang SC', 'Microsoft YaHei', sans-serif;

/* Mono: 代码、终端、JSON */
--font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
```

### 2.2 中文回退策略
- Orbitron / Chakra Petch / Space Grotesk **无 CJK 覆盖**，仅用于短词/数字/拉丁标题
- 中文正文自动回退到 HarmonyOS Sans SC → PingFang SC → Microsoft YaHei
- **禁止**：在中文段落使用 `text-transform: uppercase`（仅对拉丁标签生效）

### 2.3 字号层级
| 用途 | 字号 | 字重 | 字体 |
|------|------|------|------|
| Display 标题 | 30px | 600 | Orbitron |
| 页面标题 | 26px | 600 | Orbitron |
| 卡片标题 | 17px | 600 | Orbitron |
| 正文 | 14px | 400 | IBM Plex Sans |
| 辅助文本 | 13px | 400 | IBM Plex Sans |
| Tech 标签 | 12px | 600 | Chakra Petch, uppercase |
| Mono 代码 | 12px | 400 | JetBrains Mono |

---

## 3. 几何与间距

### 3.1 圆角系统
```css
--radius-sm: 10px;   /* 按钮、输入框 */
--radius: 14px;      /* 卡片、面板 */
--radius-lg: 20px;   /* 大面板、模态框 */
--radius-xl: 26px;   /* 品牌展示、特殊容器 */
```

### 3.2 间距规范
- 页面内边距：`28px 40px 36px`（上/左右/下）
- 卡片内边距：`22px 24px`
- 网格间距：`18-24px`（bento 网格用 `clamp(12px, 1.4vw, 22px)`）
- 组件间距：`8px / 12px / 16px / 24px`（4px 基数）

---

## 4. 表面与材质

### 4.1 磨砂玻璃面板
所有面板类组件（`.app-card`、`.stat-tile`、`.data-panel`、`.glass-panel`、`.stat-card`、`.panel`）使用：
```css
background: var(--bg-surface);
backdrop-filter: var(--glass);  /* saturate(140%) blur(18px) */
border: 1px solid var(--border);
box-shadow: var(--shadow);
```

**无障碍降级**：
```css
@media (prefers-reduced-transparency: reduce) {
  background: var(--bg-elevated);
  backdrop-filter: none;
}
```

### 4.2 阴影层级
```css
--shadow-sm: 0 1px 3px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.04);
--shadow: 0 18px 44px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04);
--shadow-lg: 0 28px 64px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
```

### 4.3 HUD 装饰层（opt-in）
- `.hud-grid`：工程网格背景（24px 网格，向下渐隐）
- `.hud-scanlines`：水平扫描线（opacity 0.35）
- `.corner-tick`：L 型角标（左上/右下）
- `.clip-notch`：切角面板
- `.glow-accent`：强调色光晕

**原则**：装饰层不改变布局流，仅通过 `::before/::after` 叠加，可安全移除。

---

## 5. 布局原语

### 5.1 页面结构
```css
.app-page        /* 全高内容区，自带滚动 */
.page-hero       /* kicker + title + subtitle 页头 */
.app-card        /* 磨砂表面面板（基础构建块） */
.data-panel      /* 包裹 Ant Design 表格的面板 */
.toolbar         /* 命令栏（搜索/筛选/操作） */
.seg             /* 分段控制器 */
.stat-grid       /* 指标瓦片网格 */
```

### 5.2 Bento 非对称网格
```css
.bento {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: clamp(12px, 1.4vw, 22px);
}
.bento :nth-child(4n+1) { grid-column: span 7; }
.bento :nth-child(4n+2) { grid-column: span 5; }
.bento :nth-child(4n+3) { grid-column: span 5; }
.bento :nth-child(4n+4) { grid-column: span 7; }
```
**故意打破 3 列等宽模板**，营造编辑式排版节奏。

---

## 6. 动效纪律

### 6.1 允许的属性
- `transform`（translate、scale、rotate）
- `opacity`
- `box-shadow`（仅用于光晕/悬停反馈）

### 6.2 禁止的属性
- `width / height`（用 `transform: scale` 替代）
- `margin / padding`（用 `transform: translate` 替代）
- `background-color`（用 `opacity` 叠加层替代）
- `top / left / right / bottom`（用 `transform: translate` 替代）

### 6.3 过渡时长
```css
--transition: 200ms cubic-bezier(0.4, 0, 0.2, 1);  /* 标准交互 */
/* 页面切换 */
.page-enter-active, .page-leave-active {
  transition: opacity 180ms, transform 180ms;
}
```

### 6.4 减弱动效降级
```css
@media (prefers-reduced-motion: reduce) {
  .page-enter-active, .page-leave-active {
    transition: opacity 120ms linear;
  }
  .page-enter-from, .page-leave-to {
    transform: none;
  }
}
```

---

## 7. 图标库规范

### 7.1 双库共存策略
项目同时使用两套图标库，**按场景隔离**：
- **@ant-design/icons-vue**：admin 管理页、业务表单、表格操作（25+ 文件）
- **@lucide/vue**：assistant 对话流、执行流程图（8 文件）

### 7.2 使用规则
- **禁止**在同一组件混用两套库
- 新增 admin/业务页面 → 使用 `@ant-design/icons-vue`
- 新增 assistant/流程页面 → 使用 `@lucide/vue`
- 通用组件（StateWrapper 等）→ 优先 `@ant-design/icons-vue`

---

## 8. 组件规范

### 8.1 StateWrapper 三态容器
统一处理 loading / empty / error 状态，避免重复 `v-if/v-else`：
```vue
<StateWrapper 
  :loading="isLoading" 
  :error="errorMsg" 
  :empty="data.length === 0"
  @retry="fetchData"
>
  <DataTable :data="data" />
</StateWrapper>
```

**插槽**：
- `#default`：正常内容
- `#loading`：自定义加载 UI（默认用 LoadingSpinner）
- `#error="{ error }"`：自定义错误 UI
- `#empty`：自定义空状态 UI

### 8.2 LoadingSpinner
纯加载动画，支持 `fullscreen` 和 `text` props。

### 8.3 按钮层级
| 类型 | 类名 | 用途 |
|------|------|------|
| 主按钮 | `.ant-btn-primary` | 页面主操作（蓝色渐变） |
| 次按钮 | `.ant-btn` | 次要操作 |
| 幽灵按钮 | `.ant-btn-ghost` | 低优先级操作 |
| 品牌按钮 | `.btn-primary` | Landing 页 CTA |

---

## 9. 品牌资产

### 9.1 Logo 文件
- `logo-icon.svg`：纯图标（64x64 viewBox，六边形 + 三节点）
- `logo-full.svg`：图标 + 文字组合（320x64 viewBox）
- `favicon.svg`：网站图标

### 9.2 品牌规范页
访问 `/brand/brand-kit.html` 查看完整 3x3 网格展示（9 个面板）。

### 9.3 使用规则
- Logo 周围留白 ≥ 图标高度的 25%
- 深色背景使用标准版，浅色背景使用反白版
- **禁止**：拉伸、旋转、添加投影、改变渐变色

---

## 10. 检查清单

### P0 已完成
- [x] 删除 `.reveal` 死代码（global.css，无任何元素使用）
- [x] 主布局 `100vh` → `100dvh`（AppLayout.vue 两处）

### P1 已完成
- [x] 磨砂玻璃降级兜底（5 个面板类补 `prefers-reduced-transparency`）
- [x] 封装 StateWrapper 三态组件（components/common/StateWrapper.vue）

### P2 已确认
- [x] 字体回退策略正确（Orbitron 无 CJK，中文自动回退 HarmonyOS/PingFang/YaHei）
- [x] 动效纪律已遵守（仅用 transform/opacity，页面切换 180ms）

### 待办
- [ ] 统一图标库（admin 页 25+ 文件用 Ant，assistant 页 8 文件用 Lucide，已隔离但需文档化）
- [ ] 双强调色收敛（蓝主琥珀点缀，需审查是否有琥珀用于主操作）
- [ ] 其他页面 `100vh` → `100dvh`（SkillManagement.vue 9 处，AiSessionPanel.vue 1 处，优先级低）

---

## 11. 设计决策依据

### 11.1 为什么用双图标库？
- Ant Design icons 与 Ant Design Vue 组件库深度集成，admin 页已大量使用
- Lucide icons 在 assistant 流程中提供更轻量的线性风格
- 强行统一需重构 30+ 文件，ROI 低

### 11.2 为什么 bento 网格是 7:5:5:7？
- 打破 AI 默认的"三列等宽"模板
- 营造编辑式排版的视觉节奏
- 符合 taste-skill 反模板精神

### 11.3 为什么 Orbitron 仅用于拉丁/数字？
- Orbitron 无 CJK 覆盖
- 几何字形适合指标数字（tabular-nums）
- 中文正文用 IBM Plex Sans + HarmonyOS Sans SC 回退

---

**文档版本**：v1.0  
**最后更新**：2026-09-06  
**维护者**：MinWorkBuddy 前端团队
