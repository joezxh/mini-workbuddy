# taste-skill 技能集 · 文档索引

> 来源仓库：[Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)（本地副本：`D:\projects\github\taste-skill`）
> 定位：一组「反模板（anti-slop）」前端设计与代码生成技能，核心是**先读懂需求、再推断设计方向、最后用统一的设计系统落地**，避免 AI 默认审美（紫色渐变、居中英雄区、三等分卡片、Inter+Slate 等）。

本目录说明文档：

| 文件 | 内容 |
|------|------|
| [skills-reference.md](./skills-reference.md) | 14 个技能逐一说明（用途、关键规则、适用场景） |
| [frontend-best-practices.md](./frontend-best-practices.md) | 结合本仓库前端（`frontend/`）的最佳实践与优化方案 |

---

## 一、这套技能解决什么问题

LLM 生成 UI 时高度趋同：默认跳进某套审美，而不先判断「这是给谁、什么场景、什么品牌」的界面。taste-skill 用三条纪律纠正：

1. **Brief Inference（读懂需求）**：先输出一行「Design Read」——这是什么页面、给谁看、什么调性、倾向哪套设计系统——再动手。
2. **三个旋钮（Dials）**：`DESIGN_VARIANCE`（对称↔混乱）、`MOTION_INTENSITY`（静态↔电影感）、`VISUAL_DENSITY`（留白↔密集），按需求推断取值，而非写死。
3. **真实设计系统优先**：能用官方设计系统（Fluent / Material 3 / Carbon / Polaris / Primer / Atlassian / GOV.UK / USWDS / Radix Themes / shadcn / Tailwind）就直接用，**不要手搓它的 CSS**；一个项目只用一套系统。

## 二、技能分类

| 类型 | 技能 |
|------|------|
| **主技能（通用）** | `taste-skill`（v2 默认）、`taste-skill-v1`（旧版兼容） |
| **输出纪律** | `output-skill`（禁止占位/截断）、`redesign-skill`（改造存量项目） |
| **美学风格** | `minimalist-skill`、`soft-skill`（高端视觉）、`brutalist-skill`、`high-end-visual-design` |
| **工作流/工具** | `stitch-skill`（生成 Stitch 用的 DESIGN.md）、`image-to-code-skill`（图→代码） |
| **仅出图（不写码）** | `imagegen-frontend-web`、`imagegen-frontend-mobile`、`brandkit` |
| **特定模型** | `gpt-taste`（面向 GPT 的高端前端/GSAP 技能） |

## 三、在本项目里怎么用

本仓库前端是 Vue 3 + Ant Design Vue 的**产品型工作台（dashboard / 数据密集）**，不是 landing page。
因此：

- **可直接套用**：`output-skill`（生成完整代码、无占位）、`redesign-skill`（审计与优化存量页面）、`minimalist-skill` / `soft-skill`（提升新页面的视觉完成度）、`stitch-skill` 的「DESIGN.md 规范」思路（产出团队级设计令牌文档）。
- **需谨慎套用**：`taste-skill` 的「landing / portfolio」偏好（反居中英雄区、强动效）对数据密集界面要克制，应以 `VISUAL_DENSITY` 偏高、`MOTION_INTENSITY` 偏低解读。
- **不适用的**：三个 `imagegen-*` 仅出参考图、不写代码，除非你做品牌/营销页。

> 提示：这些技能目前以仓库形式放在 `D:\projects\github\taste-skill`，并未注册进 CodeBuddy 的 `~/.codebuddy/skills/`。若要让 IDE 在生成前端代码时自动调用，需把各 `skills/<name>/SKILL.md` 复制到 `~/.codebuddy/skills/<name>/`（用每个 SKILL.md 的 `name:` 作为目录名）。需要我帮你做这步注册，告诉我即可。
