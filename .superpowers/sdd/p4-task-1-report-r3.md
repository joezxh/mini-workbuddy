# P4.1 第三轮修复报告（单一真相源重构）

- 修复依据：`.superpowers/sdd/p4-task-1-review-r2.md`（第二轮复审）+ 用户拍板（简报「变更授权」）
- 执行日期：2026-09-10
- 结论：**DONE**（R2-01 / R2-02 / R2-03 / IM-07 / R2-04 / R2-05 / R2-06 全部完成，60 passed）
- 未执行 `git commit`（改动保留在工作区）

## 0. 执行过程说明

本回合由实施 subagent 执行，中途被中断（`code=10003`）。中断时**实现代码已全部落盘**
（`owl_engine.py` / `wiki_owl.py` / `ontology_repository.py` / `ontology.py`），
但**守护用例、变异验证、报告**未完成。主 agent 接管收尾：核对实现与设计一致 →
补齐 5 条新用例 → 5 组变异测试 → 报告。

> 卡死根因：`gsd-code-fixer` 的 agent 定义强制「git worktree + 每修复单独 commit +
> ff-merge 回用户分支」，与本项目「禁止 git 写操作、改动全在工作区」冲突，
> 其隔离流程退化后在主工作区改代码并被中断。**后续此类任务不再使用该 agent。**

## 1. R2-01 / R2-02：单一真相源重构（Blocker + Major）

**改前架构**：`ttl_content` = 全量原文（权威），类/标注索引可写；
但写操作只改索引不改原文 → 导出时「索引补增量」遇原文已声明的类整类跳过
→ API 注册的 label/父类静默丢失（R2-01）、注销的类仍留在导出（R2-02）。

**改后架构**（`backend/app/ai/knowledge/owl_engine.py`）：

| 路径 | 行为 |
|---|---|
| `_persist(graph)` | **先** `set_ttl_content()` 写原文，**再** `_reindex(graph)` 覆盖重建索引（顺序保证 `auto_commit=False` 时 `ttl_content` 也受事务保护，R2-06） |
| `register_class` | 改原文图（label/comment `graph.set`，父类并集）→ `_persist` |
| `unregister_class` | 删原文所有相关三元组（`(subj,?,?)` + `(?, ?, subj)`）→ `store.unregister()` → `_persist` |
| `annotate_article` | 改原文 → `_persist` |
| `import_ttl` | `_merge_graphs` → `_persist` |
| `export_ttl` / `_build_graph` | = 基础公理 + 全量原文，**「索引补增量」逻辑已删除** |

**写语义对齐改造前**：父类并集（不是替换）、label/comment 为空不覆盖、
`register_class` 路径保持 `Literal(label, lang="zh")`。

守护用例（`tests/ontology/test_ttl_roundtrip.py`，变异验证见 §5）：
- `test_registered_label_survives_ttl_import`（R2-01）
- `test_registered_parent_survives_ttl_import`（R2-01）
- `test_unregister_removes_class_from_export`（R2-02）

## 2. R2-03：空节点跨导入合并（Major）

`_merge_graphs()` 弃用「规范化标签相等」的集合并集，改为**同构感知差集**：

1. `_connected_components()`：按共享节点把图切成连通分量；
2. 不含空节点的分量：纯集合并集（URI/Literal 天然去重，`added == 0` 幂等）；
3. 含空节点的分量：仅当库中已存在**同构**分量（`rdflib.compare.isomorphic`，
   只重映射空节点、不重映射 URIRef）才跳过；否则 `_rename_blank_nodes()`
   换新标签**整分量**并入。

守护用例：`test_same_structure_blank_nodes_from_two_imports_stay_distinct`
（两次导入结构相同、主体不同的匿名限制 → 导出后仍是两个独立空节点）。

## 3. IM-07：无租户请求返回 `400 tenant_required`（用户授权）

`wiki_owl.py`：新增 `_require_tenant_id()` 统一拦截（读/写路径都过它），
`get_owl_engine()` 二次防御；错误码固定 `tenant_required`，不泄漏内部细节。
`OntologyRepository(tenant_id=None)` 保留 WARNING —— HTTP 入口已拦，
走到仓储的是**内部调用方**，NULL 分区语义仅对内部开放。

守护用例：`test_api_without_tenant_returns_400`（GET/POST/import-ttl 三路径均 400）。

## 4. Minor：R2-04 / R2-05 / R2-06

- **R2-04（CWE-209）**：`_write_error_response()` —— `OperationalError` → 503；
  其它 `SQLAlchemyError` → 400 固定文案 + `logger.exception`；
  `ValueError`（客户端错误）→ 400 原文。SQL 与绑定参数不再回显。
- **R2-05（注释同步）**：`ontology.py`（含列 COMMENT，建表日志可见
  "TTL 原文（唯一真相源…）"）、迁移 `004`、`ontology_repository.py`、
  `owl_engine.py` docstring 均已按新语义更正。
- **R2-06（假测试）**：`test_failed_import_leaves_no_partial_data` 增加导出
  **全文对比**断言。修复前该用例在 `auto_commit` 退化为 True 时仍绿
  （只比较类集合，抓不到 `ttl_content` 残留）；增强后可捕获（变异 V5 RED）。

## 5. 测试

### 全量（PG 17.11 / minworkbuddy_test / schema-per-test）

```
60 passed, 3 warnings in ~26s
```

（55 旧 + 5 新：R2-01×2、R2-02、R2-03、IM-07；R2-06 为原用例增强）

### 变异测试（每组变异后跑对应用例，验证后**全部还原**，残留检查 = 0）

| 变异 | 模拟 | 结果 |
|---|---|---|
| V1 `register_class` 只 upsert 索引、不 persist | R2-01 根因 | 2 条用例 **RED** ✅ |
| V2 `unregister_class` 不删原文三元组 | R2-02 | **RED** ✅ |
| V3 `_merge_graphs` 退回 `to_canonical_graph` 并集 | R2-03 | **RED** ✅（幂等用例仍绿，符合预期） |
| V4 拆除两处 `tenant_required` 拦截 | IM-07 回退 | **RED** ✅ |
| V5 路由 `auto_commit=False` → `True` | R2-06 回退 | **RED** ✅ |

## 6. 约束遵守

| 约束 | 结论 |
|---|---|
| 1 不引入新依赖 | ✅ 仅 `rdflib.compare`（已在用） |
| 2 保留 WikiOwlEngine 方法语义 | ✅ 且 `unregister_class` 恢复了「删全部相关三元组」的旧语义 |
| 3 端点对外行为不变 | ✅（IM-07 的 400 已由用户在简报「变更授权」豁免） |
| 4 循环父类不死循环 | ✅ 12 条层级/循环用例全绿 |
| 5 禁用 SAEnum | ✅ 未触碰 |
| 6 不执行 git commit | ✅ 未执行任何 git 写操作（含变异验证的还原） |
| 7 不做 SHACL/推理机/PROV-O/回滚 | ✅ 未越界 |

## 7. 遗留事项与拍板结果（用户已确认 2026-09-10）

| 事项 | 结论 |
|---|---|
| `extensions.py` 是否被 P1 依赖 | **不依赖，维持删除。** P1 计划 Step 1 明确用 Alembic 迁移内 `op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")` 自带初始化路径（vector 扩展同理走迁移），不依赖启动期代码；且该文件全仓 0 调用点、从未进过 HEAD。其 `DROP TYPE IF EXISTS vector CASCADE` 属高危 DDL，删除是正确的 |
| `requirements.txt` 的 `websockets` | **保留。** 归属 websocket 语音双工能力，与 SkillHub 无关 |
| 复审剩余 Minor（重复索引、测试卫生等） | **挂 P4.2**，已追加到 P4 计划 Task 4 的「附带输入」小节 |

仍开放（不阻塞）：
- `ttl_content` 语义变更（B 案）：若已有环境写入过旧版数据，需重导一次（表未上线，影响有限）
- `wiki_owl` 路由仍 `enabled=False`：启用时需跑一次真实 app 端到端验证
- 备注：本机 PG 中无名为 `minworkbuddy` 的库（`settings.DB_NAME` 默认值，实际以 `.env` 覆盖为准）；`minworkbuddy_test` 中 vector 0.8.6 已就绪
