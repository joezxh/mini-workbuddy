# KG 知识库 · 原型对齐清单（kg-knowledge-base-preview.html）

> 生成日期：2026-11-24。逐项对照 `docs/prototypes/kg-knowledge-base-preview.html`
> 与当前实现，标注【原型行为】/【实现状态】/【本次改动】。
> 状态：✅ 已对齐（本次补齐） · ✔ 既有一致 · ➖ 原型未涉及。

## 一、关系（Tab: relations / KgTripleTable.vue）

| # | 原型行为 | 实现状态 | 本次改动 |
|---|---|---|---|
| R1 | 工具栏：关系类型筛选 / 状态筛选 / 权重三档 / 批量接受 / 新建关系 | ✔ 既有一致 | — |
| R2 | 批量评审（接受）走一次批量请求 | ✅ 本次补齐 | 新增 `POST /{kid}/graph/relations/batch-review`（kg.py），前端 `onBatchAccept` 改调批量端点，逐条容错返回明细 |
| R3 | 批量驳回 | ✅ 本次补齐 | 同上端点 + `batchReviewRelations`，工具栏新增「批量驳回」按钮 |
| R4 | 批量删除 | ✅ 本次补齐 | 新增 `POST /{kid}/graph/relations/batch-delete` + 工具栏「批量删除」（带确认） |
| R5 | 新建关系可设权重与证据原文 | ✅ 本次补齐 | 新建弹窗补 `weight`（0–1 步进 0.05）与 `evidence`（textarea → `{"text": ...}`）；`KgRelationPayload` 增 weight/evidence |
| R6 | 关系可编辑（类型/谓词/权重/证据，端点不可变） | ✅ 本次补齐 | 新增 `PATCH /{kid}/graph/relations/{id}`（kg.py `update_relation` + kg_service.update_triple，权重越界 422、relation_code 超 64 字符 422、Neo4j 投影重建）；表格行新增「编辑」，编辑态端点锁定 |
| R7 | 关系行展示复核结论徽标 | ✅ 本次补齐（新增能力，原型无） | LLM 二次证据复核：kg_triple 增 review_verdict/review_note/reviewed_at（迁移 2026_11_24_0000_kg_review）；列表/详情透出；状态列下方徽标（绿=支撑/黄=存疑/红=不支撑/灰=失败），悬浮显示复核理由 |
| R8 | 手动触发关系复核 | ✅ 本次补齐（新增能力） | `POST /{kid}/graph/relations/review-batch`（按状态/指定条目/全状态）；构建完成后自动跑一轮（`relation_review_enabled`，默认开）；工具栏「关系复核」按钮 + 完成摘要提示 |
| R9 | 权重条三色 + 悬空边不入库 | ✔ 既有一致 | — |
| R10 | 检视面板：关系评审（接受/驳回） | ✔ 既有一致 | — |

## 二、实体（Tab: entities / KgEntityTable.vue）

| # | 原型行为 | 实现状态 | 本次改动 |
|---|---|---|---|
| E1 | 搜索 / 类型筛选 / 状态筛选 / 仅看待评审 / 8 张统计卡 | ✔ 既有一致 | — |
| E2 | 批量接受 / 批量改类型 / 批量删除（一次批量请求） | ✅ 本次补齐 | 新增 `entities/batch-review`、`entities/batch-set-type`、`entities/batch-delete`（单事务逐条容错，`{results, ok_count, failed_count}`）；前端三个批量操作全部切换，部分失败提示成功/失败计数 |
| E3 | 新建/编辑实体弹窗含别名 | ✔ 既有一致 | — |
| E4 | 编辑弹窗含属性（properties 键值对） | ✅ 本次补齐 | 编辑弹窗新增属性键值编辑器（增删行，空键跳过，值原样保留字符串）；`EntityUpdateBody.properties` 后端既有支持，本次前端接线；检视面板编辑弹窗同步实现 |
| E5 | 属性列摘要展示 | ✔ 既有一致 | — |
| E6 | 检视面板：实体接受 / 删除 | ✅ 本次补齐 | KgInspector 头部操作区：suggested 实体显示「接受」+「删除」（后端实体无 reject 态，删除即清理）；保存后刷新画布/统计 |
| E7 | 检视面板：实体编辑入口 | ✅ 本次补齐 | KgInspector 头部新增「编辑」→ 弹窗（名称/类型/别名/属性）→ `updateEntity` |
| E8 | 分布图点击下钻到实体表（预置类型筛选） | ✅ 本次补齐 | KgOverview 实体分布行可点击 → 切到实体 Tab 并按类型预置筛选（KbGraphPane `onDrill` + KgEntityTable `initial-type-filter`） |

## 三、溯源（Tab: provenance / KgProvenance.vue）

| # | 原型行为 | 实现状态 | 本次改动 |
|---|---|---|---|
| P1 | 左：实体/关系 → 提及它的切片；右：文档 → 贡献 + 失败切片 + 重试 | ✔ 既有一致 | — |
| P2 | 切片行展示正文摘录 | ✅ 本次补齐 | 提及行新增 content 摘录（前 80 字，可展开全量，后端 `content` 既有返回） |
| P3 | 切片行展示抽取依据（evidence） | ✅ 本次补齐 | 展开后显示 evidence 文本（{text/quote/sentence/content} 或字符串） |
| P4 | 候选列表搜索全量（不截断 12+8 条） | ✅ 本次补齐 | 去掉 `.slice(0, 12)` / `.slice(0, 8)`，关键词过滤保留 |
| P5 | 「在图谱中定位」 | ✅ 本次补齐 | 源切片标题栏新增按钮 → emit `locate-graph` → 切图谱 Tab 并 selectEntity/selectEdge（KgGraphView.selectEdge 增强：当前视图无边时以起点实体为种子子图） |
| P6 | 关系溯源下钻用关系自身提及（而非 from_entity_id 近似） | ✅ 本次补齐 | KgInspector 关系形态「溯源」改为 emit `provenance-edge`（KgGraphView/KbGraphPane 透传），KgProvenance 支持 `initial-selection` 自动定位；关系检视面板内联列出该关系自身的提及切片（可点开 SegmentDetail） |
| P7 | 撤销文档贡献 / 重试失败抽取 | ✔ 既有一致 | — |

## 四、图谱视图（Tab: graph / KgGraphView.vue）

| # | 原型行为 | 实现状态 | 本次改动 |
|---|---|---|---|
| G1 | 三模式（全库图 / 按类型过滤 / 种子子图）+ 类型/关系筛选 + 跳数 + 节点上限 + 隐藏 Chunk | ✔ 既有一致 | 「按类型过滤」经 `GET /graph/full?type_code=...` 服务端真实过滤（非客户端假过滤） |
| G2 | 导出 JSON / CSV / GraphML | ✅ 本次补齐 | 后端 export 新增 `fmt=graphml`（节点 label/type/status，边 relation/weight，XML 转义，可被 yEd/Gephi 读取）；前端导出菜单新增 GraphML |
| G3 | 悬空边丢弃 / 检视面板联动 | ✔ 既有一致 | — |

## 五、概览 / 文档 / 配置

| # | 原型行为 | 实现状态 | 本次改动 |
|---|---|---|---|
| O1 | CDM 三色卡 + 明细列表 | ✔ 既有一致 | — |
| O2 | CDM 明细展开全部 | ✅ 本次补齐 | 默认前 6 条 + 「展开全部（N 条）/收起」 |
| O3 | 文档列表搜索 + 分页 | ✅ 本次补齐 | 文档名搜索 + 每 10 条分页（客户端，文档量小场景） |
| O4 | 配置页：抽取模型 / 约束三来源 / 并发 / 超时 / 检索参数 | ✔ 既有一致 | — |
| O5 | 配置页新增抽取预算类参数 | ✅ 本次补齐（支撑抽取修复） | `max_output_tokens`（默认 4096）、`max_text_chars`（12000）、`max_entities`（60）、`max_relations`（120）、`max_continuation_rounds`（3）、`relation_review_enabled` / `review_batch_size` / `review_concurrency` 全部可配可存（越界钳制 500–50000 / 5–500 / 5–1000 / 1–10） |
| O6 | 「查看生效提示词」 | ✅ 本次补齐（新增能力） | `GET /{kid}/graph/prompt-preview`（按当前配置拼装 build_prompt 实际提示词，含 schema_hint 与正文占位）+ 配置页抽屉展示（含配置回显） |
| O7 | free_text 约束一键填充供应链模板 | ✅ 本次补齐 | 「填充供应链模板」按钮（10 实体类型 + 15 关系类型 + 抽取纪律，与 docs/prototypes/supply-chain-kg/free-text-schema-constraint.md 同源） |

## 六、抽取链路（原型要求「完整抽取实体、关系及属性」）

| # | 问题 | 本次修复 |
|---|---|---|
| X1 | 输出预算 1024 撞顶，关系全在截断点之后被裁（274 切片仅 91 条关系） | `DEFAULT_MAX_OUTPUT_TOKENS` 1024→4096，可配置；截断续抽 1 轮→有界多轮（默认 3，无新增即停） |
| X2 | 正文硬切 6000 字符静默丢尾（246/274 切片触发 input_truncated） | `MAX_TEXT_CHARS` 6000→12000，可配置（500–50000） |
| X3 | 悬空边端点只按 name 精确匹配，别名不参与（模型常用简称输出端点） | `_resolve_endpoint` 增两层别名匹配：片段级别名表 + 库级别名索引（懒构建缓存，O(1) 解析防 N+1）；别名命中照样补写提及与投影 |
| X4 | 提示词「宁可不标」抑制关系召回 | 类型约束保留严格但改为「类型受约束但关系宁多勿漏」；新增属性抽取要求（数字/日期/金额/型号进 properties 不建成实体）；禁止自环；上限 40/60→60/120 |
| X5 | 抽取模型为 0.8B 级小模型（自造类型/属性建成实体/echo 占位文本） | 模型管理登记 GPUStack qwen3-32b（register_gpustack_qwen32b.py）；KB 12 配置切至该模型 |
| X6 | 小模型时代预算默认值不适配大窗口模型 | 全部抽取参数可配置（见 O5），默认按 qwen3-32b（32k 窗口）调优 |
| X7 | 当前提示词不可见 | prompt-preview 端点 + docs/kg-prompt-current.md 快照文档 |

## 七、验证

- 后端：`tests/kb + tests/unit` **954 passed / 1 skipped**（含本次新增：多轮续抽、别名匹配、复核判定与落库、批量端点、关系 PATCH、graphml 导出、prompt-preview）
- 前端：`vitest` **303 passed**（唯一失败 `audioDsp.spec.ts` 为既有问题，与本模块无关）；`vue-tsc` 本模块改动文件 0 错误
- 重跑与前后对比：见 `docs/kg-supply-chain-extraction-report.md`
