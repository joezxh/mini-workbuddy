# 结合 taste-skill 的前端最佳实践与优化方案

> 评估对象：`frontend/`（Vue 3 + Vite + Ant Design Vue 4 + Pinia + vue-i18n + ECharts/AntV + Vue Flow）
> 设计系统现状：已有一套高度自洽的 **「explorer / mission-control」暗色科技风**——蓝 `#4aa3ff` + 琥珀 `#f2b66d` 双强调、Orbitron/Chakra Petch HUD 字体、磨砂玻璃面板、HUD 网格/角标、bento 非对称网格、14–26px 大圆角。这套系统与 taste-skill 的「反模板」精神**高度一致**，不是 AI 默认审美，已经做得不错。

本方案分两部分：**已做对的（保持）** + **可改进的具体项（执行）**。

---

## 一、已对齐 taste-skill 纪律（请保持）

| taste-skill 规则 | 当前前端 | 位置 |
|---|---|---|
| 不用 Inter / AI 紫 | 用 Orbitron/Chakra Petch/IBM Plex Sans，主色蓝非紫 | `src/styles/tokens.css` |
| 单/双色调色板一致 | 蓝+琥珀同属蓝橙色系，未混冷暖灰 | `tokens.css` |
| 真实设计系统优先 | 基于 Ant Design Vue 官方 + 仅 override CSS 变量，未手搓组件样式 | `tokens.css` 末段 Ant 变量 remap |
| 锁定圆角体系 | `--radius-sm/md/lg/xl` 统一 | `tokens.css:31-34` |
| 全交互状态 | hover/active/focus-visible、loading(骨架屏)已规划 | `global.css:297` |
| 非对称布局 | `.bento` 7/5 错落网格 | `global.css:557` |
| 降级优先 | `prefers-reduced-motion`、`prefers-reduced-transparency`(部分) | `global.css:440,531` |

---

## 二、具体优化项（按优先级）

### P0 — 必须修（潜在 bug / 体验硬伤）

**1. `.reveal` 是「会隐藏内容的死代码」，需补触发或删除**
`src/styles/global.css:619-635` 定义了 `.reveal:not(.is-in){opacity:0;transform:translateY(18px)}`，注释说「GSAP 或其它 observer 切换 `.is-in`」。但 `package.json` **没有 GSAP**，全仓也没有任何 `class="reveal"` 的模板使用（该规则当前是死 CSS）。
- 风险：一旦未来某页面写了 `class="reveal"` 又没 JS 触发 `.is-in`，元素将**永久透明不可见**——是个隐形陷阱。
- 修复（二选一）：
  - 加一个轻量 composable `useReveal()`，用 `IntersectionObserver` 给进入视口的元素加 `.is-in`（推荐，零重依赖），让它真正可用；
  - 或删除 `.reveal` 相关规则，避免误用。

**2. `100vh` 在移动端会跳动**
`src/layouts/AppLayout.vue:28,37` 用 `height: 100vh`。taste-skill / redesign-skill 明确建议用 `100dvh`。
- 修复：两处 `100vh` → `100dvh`（桌面无影响，移动端避免地址栏伸缩导致的布局跳动）。

### P1 — 体验与一致性提升

**3. 磨砂面板缺「降级透明度」兜底**
`global.css` 里仅 `.glass-panel`（`:531`）做了 `prefers-reduced-transparency` 降级；但 **`.app-card`、`.stat-tile`、`.data-panel`** 都用了 `backdrop-filter: var(--glass)` 却没有兜底。
- 修复：给这三个类补 `@media (prefers-reduced-transparency: reduce)` 分支，将 background 改为不透明的 `--bg-elevated` 并去掉 backdrop-filter（与 `.glass-panel` 同款写法）。

**4. 图标双库混用**
`package.json` 同时有 `@ant-design/icons-vue` 与 `@lucide/vue`。两套描边/视觉语言不同，违反 minimalist/soft 技能的「图标族统一」原则。
- 建议：以 Ant Design icons 为主（与组件库一致），新页面不再引入 lucide；存量页面逐步替换，或在设计令牌里固定一套描边宽度。

**5. 数据类页面的「空/错/加载」三态**
redesign-skill 要求 loading/empty/error 全周期。当前 `.empty-hint`(`:276`) 已存在，但需确认每张数据表/列表在请求中、空数据、出错时都用了对应态，而非裸 `v-if` 或 `null`。
- 建议：封装一个 `<StateWrapper :loading :error :empty>` 或在 `app-card` 体系内统一三态插槽，避免各页面各写一套。

### P2 — 视觉完成度（取 soft-skill 子集，产品 UI 用低强度）

**6. 双强调色的高饱和收敛**
当前 `--accent-2: #f2b66d`(琥珀) 作为第二强调色没问题，但 taste-skill 建议「最多 1 个强调色」。对数据密集界面，保留双色是合理选择；只需确保**琥珀仅用于次要/警示/点缀**，主操作一律走蓝。已在 `.ant-btn-primary` 用蓝渐变（`:332`），保持即可。

**7. 字体在中文下的回退**
Orbitron/Chakra Petch **无 CJK 字形**，中文会回退到 `HarmonyOS Sans SC / PingFang SC`。这已在 `tokens.css:19` 注释说明且顺序正确。
- 建议：HUD 数字/标签用 Orbitron 效果很好；但**整段中文正文**不要挂 `--font-display`(Orbitron)，会让中文走 fallback 且字符宽度跳变。确认 `.hero-title`/`.stat-value` 里的中文是短词/数字为主（现状符合）。

**8. 动效纪律**
现有页面切换 180ms（`:482`）克制得当。新增动效时遵守 soft-skill：仅动 `transform`/`opacity`、用自定义 `cubic-bezier`、错峰入场、移动端降级。勿加无限循环微动效。

---

## 三、工程化建议（让 AI 生成代码持续一致）

### 1. 沉淀团队级 DESIGN.md（借 stitch-skill 思路）
当前设计语言散落在 `tokens.css` + `global.css` 注释里。建议新增 `frontend/DESIGN.md`，用一句话定义本项目设计系统，供后续（包括 taste-skill 类生成）遵循：

```markdown
# Frontend Design System — MinWorkBuddy 工作台
- 风格：explorer / mission-control 暗色科技风（高完成度、克制动效）
- 字体：display=Orbitron(仅拉丁/数字)，body=IBM Plex Sans→HarmonyOS Sans SC
- 配色：强调 蓝 #4aa3ff(+hover #7fd0ff)，点缀 琥珀 #f2b66d；背景深蓝 #07111f/#0b1322
- 圆角：sm10 / 14 / lg20 / xl26 统一；面板用 lg，按钮用 sm
- 表面：磨砂玻璃(.app-card/.data-panel)，1px 描边，柔阴影
- 布局：.app-page / .page-hero / .bento(7-5 错落) / .stat-grid
- 反模式：禁止 AI 紫渐变、禁止纯黑、禁止 Inter、禁止三等分对称、禁止 emoji、禁止占位名/Lorem、禁止 ::v-deep 滥用
- 组件库：Ant Design Vue，仅通过 tokens.css 的 --ant-* 变量改色，不手搓组件 CSS
```

### 2. 落地 output-skill 纪律
在给 AI 生成 `.vue`/`.ts` 时，显式要求：输出**完整代码、零占位**；多文件时按 `frontend-best-practices.md` 的优先级一次给全；超长文件写到干净断点后 `[PAUSED ...]` 续写。新建页面必须实现 hover/active/focus/loading/empty/error。

### 3. 建立布局基线（redesign-skill）
所有新页面套用：`.app-page`（整体栅格与 padding）→ `.page-hero`（标题区）→ `.stat-grid`/`.bento`（内容区）→ `.data-panel`（表格）。避免直接在 `AppLayout` 里写裸 flex 百分比布局。

---

## 四、速查：本前端 vs taste-skill 默认偏好

| 维度 | taste-skill 默认偏好 | 本前端做法 | 结论 |
|---|---|---|---|
| 字体 | 禁用 Inter，用 Geist/Outfit | 用 Orbitron+IBM Plex（刻意 HUD 感） | ✅ 已避默认 |
| 强调色 | ≤1，饱和度<80% | 蓝+琥珀双色 | ⚠️ 产品 UI 可接受，主操作锁蓝 |
| 圆角 | 统一一种 | 已统一 4 档 | ✅ |
| 英雄区 | 高方差时反居中 | 产品页无英雄区，用 page-hero 左对齐 | ✅ |
| 卡片 | 仅表层级 | .app-card 统一 | ✅ |
| 动效 | 可电影感 | 克制 180ms | ✅（产品 UI 正确选择） |
| 玻璃 | 禁用整页 | 仅面板/导航 | ✅ |

**总评**：前端设计完成度高、与 taste-skill 反模板精神一致；主要待办是「修 `.reveal` 死代码、100vh→dvh、补玻璃降级、统一图标库、封装三态」，并沉淀 `DESIGN.md` 让后续 AI 生成保持同一套语言。
