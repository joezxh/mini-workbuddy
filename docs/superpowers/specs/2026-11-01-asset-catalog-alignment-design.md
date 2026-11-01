# 数据资产目录一期全对齐设计（AF-01~AF-08）

- 日期：2026-11-01
- 状态：待审阅（裁决已全部关闭，无 TBD）
- 原型真源：`docs/prototypes/ontology-asset-catalog-preview.html`
- 上游设计：`docs/superpowers/specs/2026-10-31-ontology-capability-design.md` §3.6 / §4.7 / §6.5
- 范围声明：**一期全对齐**原型 AF-01~AF-08（可见性开关除外——§10 Q1 已裁决 A"本期不做"，不建 visibility 列，目录不做可见性过滤）。

## 0. 决策记录（本次头脑风暴裁决）

| # | 议题 | 裁决 |
|---|------|------|
| Q1 | AF-01 分组事实基础 | **B：物化列**。`meta_data_source` 新增 `external_type` 列（粗分类码枚举），原型页脚"分组依据 meta_data_source.external_type"字面成立 |
| Q2 | 分组映射 | clickhouse/doris/starrocks → warehouse；未知 family 兜底为显式 `other` 节点（9 类 + other = 10 个分组） |
| Q8 | 分期 | 一期全对齐，不留挂账项 |
| Q2b | 回填矩阵 | 内置 11 类按 §1.1 矩阵回填，管理员可手改覆盖 |
| Q3 | security 自动打标 | **钩子 + 按钮都要**：扫描后置钩子自动刷新 + 资产目录页「重新分级」手动按钮（存量初始化） |
| Q4 | draft_scope 回显失效项 | **静默剔除并提示条数** |
| Q5 | 表级探活 | **本期做，含批量限流**：单表按需点击 + 勾选后批量探活（单次上限 20 张、串行） |
| Q6 | kind 参数 | `kind=table\|column` 保持兼容不动；视图过滤走新参数 `table_type` |
| Q7 | 排序选择器 | **一期做满三档**：score（默认）/ updated / rows |

## 1. 数据层与 AF-01 资产类型分组树

### 1.1 `meta_data_source.external_type` 列

- 取值枚举：`rdbms | tsdb | warehouse | graph | kv | vector | search | file | saas | other`；
- `String(32)` + CHECK 限枚举 + `(tenant_id, external_type)` 索引；Alembic 迁移回填存量行，不可解析值落 `other`；
- 语义分工：`source_type` 回答"怎么连"（字典 `data_source_type` + family 方言分派，不动），`external_type` 回答"这是什么资产"；
- **自动填充 + 手改覆盖**：新建/编辑数据源时后端按矩阵派生默认值；管理员在数据源表单可显式改选 external_type，手改值优先（此后不再被派生覆盖，除非用户再次修改）；
- 与 AF-03 无冲突：`meta_table` 重扫不触碰 `meta_data_source`，无连带删除风险。

内置 11 类回填矩阵（`source_types.TYPE_META` 单一真源）：

| source_type | external_type |
|---|---|
| mysql / oracle / postgresql / sqlserver / dm / kingbase | rdbms |
| clickhouse / doris / starrocks | warehouse |
| es | search |
| excel | file |
| （tsdb / graph / kv / vector / saas） | 本期空桶，留给后续接入类型手改归位 |

### 1.2 E40 `assets_tree()` 改造

- 直接按 `DataSource.external_type` 聚合（**废弃**读时 `_FAMILY_TO_KIND` 映射）；
- 输出固定 10 节点、固定顺序：rdbms/tsdb/warehouse/graph/kv/vector/search/file/saas/other（中文 label + 图标码由原型 GROUPS 表提供，前端映射）；
- 空组保留节点，前端显示"暂无连接"；
- 源节点新增探活状态输出（复用既有 `status` online/offline），树渲染绿/灰状态点。

## 2. AF-02 全文检索与三段确定性打分

### 2.1 打分口径修正（对齐原型 `scoreAsset`）

| 分档 | 新口径 | 现状问题 |
|---|---|---|
| 3 | 表名子串 ∪ **库名（MetaTable.database）** ∪ **表注释** | 库名完全未参与；表注释未进 3 分档 |
| 2 | 字段名命中 | 已对 |
| 1 | **仅**字段注释命中 | 表注释与列注释混在 1 分路径 |

- 同分按 `table_name` 字典序（不变）；
- **硬纪律**：永久禁 `similarity()` / `word_similarity()`；`gin_trgm_ops` 四索引（迁移 0007 已就位）仅加速 `LIKE '%kw%'`；测试加 SQL 守卫断言"执行语句不含 similarity("。

### 2.2 实现优化与参数扩展

- 消除 N+1：候选表打分改一次批量查询（`table_id IN (...)` 按表分组取 name_hit / comment_hit），打分在纯内存完成；函数保持纯函数接口，为后续"打分下推 SQL"（方案 B 预案）留缝；
- 新参数 `table_type`（`BASE TABLE` | `VIEW`，透传 `MetaTable.table_type`）承接原型"仅表/仅视图"过滤；`kind=table|column` 语义不动（兼容既有调用方）；
- 新参数 `sort`：`score`（默认）| `updated`（updated_at 新→旧）| `rows`（row_count 多→少）；
- 分页契约不变：`page/size`，默认 50、上限 200（路由 Query 硬校验保持）；前端加 size 切换器；
- 响应头 `X-Asset-Search: trgm-like`：可选，本期不做（原型演示性标记，无消费方）。

## 3. AF-08 勾选送数闭环

### 3.1 服务端单源校验（当前盲区，本期堵上）

`put_draft_scope`（mode=tables）新增校验，违规抛 `BUILD_SCOPE_SINGLE_SOURCE`：

1. scope 内 `source_id` 必填；
2. `tables[]` 逐名实查 `meta_table`（tenant + source_id 过滤）：任一表名在该源不存在 → 拒绝；
3. 跨源勾选由前端即时拦截（toast 文案带错误码 `BUILD_SCOPE_SINGLE_SOURCE`），后端为最终防线。

其余既有拦截维持：空清单且非显式 clear → `DRAFT_SCOPE_EMPTY`；本体 `stopped` → `ONTOLOGY_STOPPED`；送数**只写 `draft_scope_json`，绝不写结构表**。

### 3.2 回显与恢复

- `AssetPickerPanel.activate()` 时 GET E33 draft-scope：按目标本体的 `draft_scope_json.tables[]` 还原勾选态（跨页保留逻辑已有）；
- 回显时校验各表是否仍存在于当前元数据（无外键悬空设计下的失效项）：**静默剔除并在下次送数成功提示中并入"N 张表已不在当前元数据中，已从作用域剔除"**；剔除只影响前端勾选态，不主动改写库内 draft_scope（下次 PUT 全量覆盖自然收敛）。

### 3.3 幂等键

`_default_idem_key` 现含 ontology_id|mode|source_id|排序后 tables|日期，tables 模式已满足"含展开后 tables[]"。补一条防御：tags/catalog 模式创建构建任务前，服务端先 `_resolve_scope` 展开为表名列表再入键（防同本体不同标签命中同表集产生双任务）。

## 4. AF-06/07 卡片操作

### 4.1 表级探活（新端点）

- `POST /sources/{sid}/tables/{tid}/test`：经既有 adapter 凭据链路对真实源执行 `SELECT 1 FROM <table> LIMIT 1`（方言引号由 adapter 处理）；
- 失败码区分：连接不可达 → `SOURCE_UNREACHABLE`；连接可达但表读失败 → `TABLE_NOT_READABLE`；
- 批量探活：选择条「批量探活」按钮，单次上限 **20 张表**、串行执行、逐表回显结果；前端超出 20 张时提示分批。

### 4.2 元数据编辑（新端点）

- `PUT /sources/{sid}/tables/{tid}`：编辑表注释与列名/列注释（写 `meta_table`/`meta_column`，属扫描元数据表而非结构表，不违反"送数不写结构表"纪律）；
- 卡片"编辑"按钮弹窗承载，保存后卡片即时刷新。

## 5. AF-03 标签体系

### 5.1 前端补齐

- **修 bug**：`AssetSearchBar.doCreateTag` 现发 `tag_kind:'table'`（非法值被后端静默降级 custom）→ 改发真实类别；
- 新建标签弹窗补：tag_kind 下拉（biz/security/quality/custom）+ 色板（7 色，对齐原型 COLORS）；
- 卡片"＋标签"、选择条"打标签"接通已封装但零调用的 `bindAssetTag`（POST /asset-tags/bind，幂等）；
- 标签筛选下拉补 tag_kind 标识与绑定计数。

### 5.2 security 规则自动打标（钩子 + 按钮）

- 扫描后置钩子：元数据扫描完成时，对 `max(meta_column.pii_level) >= L2` 的表绑定租户内 `tag_kind='security'` 且 code=`pii` 的标签，`source='rule'`；标签不存在则跳过（不自动建标签，避免租户命名冲突）；
- 手动「重新分级」按钮：资产目录页触发同一规则全量重跑（存量初始化/规则调整后用）；
- 幂等与人工保护：重跑前先删该标签下 `source='rule'` 的绑定再重打；**`source='human'` 的绑定永不清理**（对齐"不连带删人工标签"的无外键设计初衷）。

## 6. AF-05 卡片渲染

- score 分档徽章（s3 绿 / s2 蓝 / s1 黄，数据已有）；
- 已映射标识显示对象码：`已映射 {bound_object_code}`（数据已有、纯渲染缺失）；
- PII 分级配色：L2/L3 红、L1 黄（现为统一红 tag）；
- 元信息行补：来源名 / 库 / `table_type` / 行数（万/亿格式化）；
- 关键词高亮（表名/注释/digest 内 `<mark>`）；digest 点击展开/收起：默认维持后端前 6 列摘要，展开时按需单查该表全量列（降低列表载荷）。

## 7. 边界与不做项

- **可见性开关**：不建 visibility 列、目录不做可见性过滤（§10 Q1 裁决 A）；原型按钮仅界面形态复刻；
- **PII 门禁位置**：卡片只回显 pii_max_level；拦截发生在自动打标（≥L2）与发布门禁（敏感列脱敏覆盖，publish_service 已有第 5 项）；**送数环节不设 PII 拦截**；
- **不新建资产表**：资产目录始终是 `meta_table/meta_column` 元数据的投影；
- **不新增字典项**：external_type 是代码枚举 + 物化列，不进 `sys_dictionary`。

## 8. 测试计划

| 层 | 用例 |
|---|---|
| 后端单测 | 三段打分矩阵（3/2/1/同分字典序/库名命中）；`BUILD_SCOPE_SINGLE_SOURCE` 跨源与不存在表名两分支；tag bind 幂等 + human/rule 分治；external_type 派生与手改优先 |
| 迁移测试 | 0007 之后新迁移：加列 + 回填矩阵 + CHECK；空库与存量库双路径幂等重跑 |
| SQL 守卫 | E28 执行语句不含 `similarity(`（禁回归） |
| 探活 | mock adapter：ok / SOURCE_UNREACHABLE / TABLE_NOT_READABLE；批量 ≤20 串行 |
| 前端组件 | AssetCardList 跨源禁选与拦截文案带错误码；draft_scope 回显还原 + 失效剔除提示；新建标签 tag_kind 正确下发 |

## 9. 改动落点速览

- 后端：`models/dataops/data_source.py`（加列）、新 Alembic 迁移、`services/ontology/ontology_service.py`（assets_tree 重写）、`services/ontology/ontology_asset_service.py`（打分/校验/批量查询）、`routers/ontology/ontology.py`（search 新参数、探活/编辑端点）、`services/dataops/scan_service.py`（打标钩子）、`services/ontology/ontology_tag_service.py`（rule 重打方法）
- 前端：`views/data-source/asset/` 四组件全动 + 新建标签/编辑元数据弹窗、`api/dataops.ts`（新端点封装）
- 文档：原型页脚 external_type 表述保留（已字面成立）；`2026-10-31-ontology-capability-design.md` 如需增补以本文档为准引用
