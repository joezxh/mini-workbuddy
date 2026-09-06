# taste-skill 技能逐一说明（14 个）

> 逐条整理自各 `SKILL.md` 与仓库 `llms.txt`。每个技能标注：**一句话定位 / 核心规则 / 适用场景**。

---

## 1. taste-skill（design-taste-frontend，v2 默认）
- **定位**：反模板前端技能，用于 landing page、作品集、重设计；不适用于 dashboard / 数据表 / 多步产品 UI。
- **核心规则**
  - **Brief Inference**：动手前先输出一行「Design Read」（页面类型 + 受众 + 调性 + 设计系统倾向），只在需求确实发散时才问**一个**澄清问题。
  - **三大旋钮**：`DESIGN_VARIANCE`(1 对称→10 混乱，默认 8)、`MOTION_INTENSITY`(1 静态→10 电影感，默认 6)、`VISUAL_DENSITY`(1 留白→10 密集，默认 4)；按需求推断而非写死。
  - **设计系统映射**：微软/企业 → Fluent；Google 系 → Material 3；IBM → Carbon；Shopify → Polaris；Atlassian → Atlassian DS；GitHub → Primer；政府 → GOV.UK / USWDS；现代 SaaS → Radix Themes / shadcn；通用 → Tailwind v4。**一个项目一套系统**。
  - **反默认纪律**：禁用 AI 紫蓝渐变、居中英雄区、三等分卡片、全量玻璃拟态、无限循环微动效、Inter+Slate-900。
  - **字体**：默认不用 Inter；用 Geist / Outfit / Cabinet Grotesk / Satoshi。衬线**默认禁用**（尤其 Fraunces、Instrument_Serif 被点名禁用），仅在品牌明确指定或真正 editorial/luxury 时才用，且要在同族内用斜体/粗体做强调，不跨族注入。
  - **颜色**：最多 1 个强调色、饱和度 < 80%；禁用「AI 紫」；同一页面锁定一个调色板（不暖灰冷灰混用）。
  - **布局**：`VARIANCE>4` 时禁用居中英雄区，用分屏/左对齐/非对称留白；用 CSS Grid 而非 flex 百分比数学；整屏区用 `min-h-[100dvh]` 而非 `h-screen`。
  - **卡片/形状**：仅当层级需要时才用卡片；阴影染背景色相；锁定一种圆角体系（全尖/全柔/全胶囊）。
  - **交互状态**：必须实现 hover / active(scale 0.98) / focus ring / loading(骨架屏) / empty / error 全周期。
  - **依赖核查**：导入任何三方库前先查 `package.json`，缺失则先给安装命令。
- **适用**：任何需要从零产出「不像模板」的前端页面时。

---

## 2. taste-skill-v1
- **定位**：v1 旧版，保留以兼容依赖其精确行为的存量项目。
- **适用**：不需要主动使用；仅在旧项目明确绑定 v1 行为时参考。

---

## 3. output-skill（full-output-enforcement）
- **定位**：覆盖 LLM 的「偷懒」默认行为——禁止占位、禁止截断、干净处理超长输出。
- **核心规则**
  - 把每个任务当生产级：局部输出即残次输出，不为简洁优化，为**完整**优化。
  - **禁用模式**：代码块里的 `// ...`、`// TODO`、`// implement here`、`/* ... */`、裸 `...`；正文里的「需要我继续吗」「其余同理」等。
  - **流程**：Scope（数清交付物数量）→ Build（全部完整生成）→ Cross-check（对照需求数一遍）。
  - **超长输出**：不压缩、不跳结论；写到干净的断点（函数/文件/章节末）后输出 `[PAUSED — X of Y complete. Send "continue" to resume from: ...]`，续写时从原处接上，不重复。
- **适用**：本项目所有代码生成（尤其是大文件、多组件页面）；保证交付的 `.vue` / `.ts` 可直接运行，无占位。

---

## 4. redesign-skill（redesign-existing-projects）
- **定位**：改造**存量**网站/应用，审计当前设计、识别通用 AI 模式、在不破坏功能的前提下提升质感。与既有技术栈协作，不重写、不换框架。
- **核心规则（审计清单）**
  - **排版**：浏览器默认/Inter 全局 → 换有性格的字体；标题缺分量 → 加大、收紧字距、降行高；正文过宽 → 限 65ch、加行高；只用 400/700 → 引入 500/600；数字 → 等宽或 `tabular-nums`；用 `text-wrap: balance/pretty` 修孤字。
  - **颜色**：纯黑背景 → 近黑/炭灰；过饱和强调色 → 饱和度 < 80%；多强调色 → 只留一个；暖灰冷灰混用 → 统一色相；AI 紫蓝渐变 → 中性底+单强调色；通用 `box-shadow` → 按背景染色；纯平无纹理 → 加噪点/微图案；整页突然插一段反色区块 → 统一或只用同色系微差。
  - **布局**：全居中对称 → 打破；三等分卡片特征行 → 2 列 zig-zag / 非对称网格 / 横滚 / masonry；`100vh` → `100dvh`；flex 百分比数学 → Grid；无 max-width → 加 1200–1440px 容器；卡片等高 → 允许变化或 masonry；统一圆角 → 内层紧、外层柔；无重叠/景深 → 负边距；对称上下 padding → 光学调整（下略大）；侧栏死板 → 试顶部导航/命令面板。
  - **交互/状态**：缺 hover/active → 补；瞬时过渡 → 加 200–300ms；缺 focus ring → 补（a11y 必需）；无 loading → 骨架屏；无 empty → 组合式「开始引导」；无 error → 行内错误（别用 `alert`）；死链 `#` → 真链接或禁用；导航无当前态 → 高亮。
  - **内容**：通用名（John Doe / Acme）→ 真实感名字；整数百分比/价格 → 有机杂乱数据；占位文案/Lorem → 真实草稿；标题全大写 → sentence case；AI 套话（Elevate/Seamless/Unleash）→ 平实具体。
  - **代码质量**：div 汤 → 语义标签；内联样式 → 收进样式系统；硬编码 px → 相对单位；缺 alt → 补；任意 `z-9999` → 建立 z 轴尺度；死代码 → 删；导入幻觉 → 核对依赖；缺 meta → 补。
  - **优先级**：字体替换 → 配色清理 → hover/active → 布局间距 → 替换通用组件 → 补 loading/empty/error → 收尾排版。
- **适用**：对 `frontend/` 存量页面做质量审计与提升（见 `frontend-best-practices.md`）。

---

## 5. minimalist-skill（minimalist-ui）
- **定位**：干净、编辑式的极简界面（Notion / Linear 风），暖色单色 + 排版对比 + 扁平 bento + 柔和粉彩点缀；无渐变、无重阴影。
- **核心规则**：禁用 Inter/Roboto/Open Sans；禁用 Lucide/Feather/Heroicons（用 Phosphor / Radix Icons 且统一描边粗细）；禁用 Tailwind 重阴影（`shadow-md` 以上）、主色大色块、渐变/霓虹/玻璃（导航栏模糊除外）、大容器/按钮 `rounded-full`、emoji、占位名/Lorem、AI 套话。排版用强对比（衬线标题 + 无衬线正文 + 等宽元数据），正文近黑非纯黑（`#111`/`#2F3437`），次文 `#787774`。卡片 `1px solid #EAEAEA`、圆角 8–12px、内距 24–40px。动效隐形（IntersectionObserver 入场、hover 微位移、`transform`/`opacity` 仅）。
- **适用**：需要「文档感 / 高级克制」的内部工具页或设置页。

---

## 6. soft-skill（高端视觉设计 / high-end-visual-design）
- **定位**：以代理公司（Awwwards 级）标准做高端视觉——实体景深、电影感空间节奏、执念级微交互、流畅动效。内容即 `SKILL.md` 的 `name: high-end-visual-design`。
- **核心规则**：禁用 Inter/Roboto/Arial、粗描边 Lucide/FontAwesome、通用 1px 灰边、硬黑阴影、贴顶 sticky 导航、对称无聊 3 列网格、线性/ease 过渡、瞬时状态。内置**差异引擎**：从 Vibe（Ethereal Glass / Editorial Luxury / Soft Structuralism）与布局（Asymmetrical Bento / Z-Axis Cascade / Editorial Split）各选其一，移动端统一回退单列。**双包边（Double-Bezel）**结构：外壳 + 内核同心圆角；按钮 nesting 图标；宏观留白 `py-24~40`；动效用自定义 `cubic-bezier`、magnetic hover、`IntersectionObserver` 入场；性能上只动 `transform`/`opacity`，`backdrop-blur` 仅用于 fixed/sticky，噪点仅挂 fixed 伪元素。
- **适用**：营销页 / 品牌页要「贵气」时；产品 UI 取其中「景深、留白、微交互」的子集。

---

## 7. brutalist-skill
- **定位**：原始机械感界面、瑞士排版、极端字号对比（Beta）。
- **适用**：需要粗野/实验性表达的活动页或品牌页；慎用于数据产品。

---

## 8. stitch-skill（stitch-design-taste）
- **定位**：生成给 Google Stitch 用的 `DESIGN.md`——把反模板指令翻译成 Stitch 能理解的语义设计语言（视觉氛围、配色含 hex、排版、组件行为、布局、动效、反模式清单）。
- **核心规则**：密度/方差/动效三档；最多 1 强调色、饱和度 < 80%、禁 AI 紫、禁纯黑、统一调色板；Inter 在高端/创意禁用（用 Geist/Outfit/Satoshi），衬线仅限 distinctive modern serif 且 dashboard 内禁用；英雄区用「行内图片排版」、禁重叠/填充文案/居中（高方差时）；组件（按钮 tactile、卡片仅表层级、骨架屏 loading、组合式 empty）；布局用 Grid、max-width 约束、`min-h-[100dvh]`、<768px 单列；动效 spring physics + 错峰 + 仅 `transform`/`opacity`；列出显式反模式（禁 emoji、禁 Inter、禁纯黑、禁霓虹、禁三等分、禁通用名/假整数/套话）。
- **适用**：要用 Google Stitch 批量产出一致界面的团队；其「DESIGN.md 规范」思路可直接借来写本项目的团队级设计令牌文档。

---

## 9. image-to-code-skill
- **定位**：图优先——生成高端网站参考图、深度解析、再实现匹配的代码。
- **适用**：有视觉参考（截图/竞品）要「照着做」时。

---

## 10. imagegen-frontend-web
- **定位**：仅出图——生成高端网页设计参考图，**不写代码**。
- **适用**：品牌/营销视觉探索阶段。

---

## 11. imagegen-frontend-mobile
- **定位**：仅出图——生成高端移动 App 界面概念与流程，**不写代码**。
- **适用**：移动端视觉探索。

---

## 12. brandkit
- **定位**：仅出图——生成品牌包总览图（logo 概念、识别系统、配色、字体、样机）。**不写代码**。
- **适用**：品牌识别探索。

---

## 13. gpt-taste
- **定位**：面向 GPT 的精英级（Awwwards）前端设计与 GSAP 动效技能，强调确定性、反 slop 的 UI 生成。
- **适用**：在 GPT 系列模型上做高端前端/强动效时参考其 GSAP 写法与纪律。

---

## 14. （附）llms.txt 全局摘要
仓库根 `skills/llms.txt` 给出一行式索引，可作为 Agent 快速路由依据：
taste-skill（默认）、taste-skill-v1（兼容）、gpt-taste（GPT+GSAP）、image-to-code-skill（图→码）、imagegen-frontend-web、imagegen-frontend-mobile、brandkit（三者仅出图）、redesign-skill（改造存量）、soft-skill（柔和高端）、output-skill（禁偷懒）、minimalist-skill（极简编辑式）、brutalist-skill（粗野 Beta）、stitch-skill（Stitch DESIGN.md）。
