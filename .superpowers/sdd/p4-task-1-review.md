# P4.1 本体持久化与租户隔离 —— 任务级评审

- 评审对象：`.superpowers/sdd/p4-task-1-brief.md` / `p4-task-1-report.md` / `p4-task-1-review.diff`
- 评审日期：2026-09-10
- 评审方式：逐条对照简报 + 逐文件精读 + 在真实 PostgreSQL 17 上实测冒烟 + 针对性故障注入

---

## 判定

**Spec 合规：❌ 有缺失或多余**

- 缺失 3 项：TTL 往返一致性在含空节点的真实 OWL 上不成立（验收标准被违反，见 CR-01）；
  `/wiki/owl/articles/{class_uri}` 的真实 SQL 从未被任何测试执行（必过测试第 5 条只做到"桩"级别）；
  `unregister_class` 语义相对改造前退化（约束 2 未完整满足）。
- 多余 1 项：`backend/app/db/extensions.py`（不在简报涉及文件清单、无任何调用点、报告改动清单中未列出）。

**代码质量：Not approved**

- Critical 1 条、Important 7 条、Minor 8 条。
- 阻塞项是 CR-01（TTL 导入导致数据损坏 + `ttl_content` 无界增长），必须修复后才能合入；
  IM-01（PG 回归缺失且"PG 不可用"的前提不成立）必须在关闭任务前补做。

---

## Spec 逐条核对

### A. 涉及文件（简报表格）

| 简报要求 | 判定 | 证据 |
|---|---|---|
| `models/ontology/ontology.py` 新建三表 | ✅ | diff 新建，字段与唯一约束齐全 |
| Alembic 迁移新建三表 | ✅ | `004_add_ontology_tables`，revises `003`，离线 `--sql` 已验证 |
| `routers/wiki/wiki_owl.py` 改按租户 | ✅ | 全局 `_owl_engine` 已删除；`get_owl_engine(tenant_id, db)` |
| `ai/knowledge/owl_engine.py` 换存储后端 | ✅ | 改为可插拔 store，rdflib 只做解析/序列化 |
| `tests/ontology/test_persistence.py` 新建 | ✅ | 另有 hierarchy / ttl / api_regression 三个文件 |
| **无其它文件** | ❌ **多余** | 多出 `backend/app/db/extensions.py`（pgvector 扩展初始化），与本任务无关、无调用点 |

### B. 数据模型约定

| 要求 | 判定 | 证据 |
|---|---|---|
| `Base` 从 `app.db.database` 导入 | ✅ | `ontology.py:36` |
| 三表继承 `TenantMixin` | ✅ | 三个类签名均为 `(Base, TenantMixin)` |
| 审计列 creator/updater/created_at/updated_at | ✅ | 三表齐备 |
| 状态用 `String(32)` + comment，**不用 SAEnum** | ✅ | `status` / `source` / `target_type` 均为 `String(32)` |
| `__table_args__` 具名索引、表名单数、中文注释 | ✅ | PG 实测 DDL 输出确认 |
| `uq_ontology_code (tenant_id, code)` | ✅ | PG 实测 `uq: ['uq_ontology_code']` |
| `uq_ontology_class (ontology_id, uri)` | ✅ | PG 实测 `uq: ['uq_ontology_class']` |
| `parent_uris` / `class_uris` 为 JSONB | ⚠️ 形式满足、语义有坑 | PG 实测列为 `JSONB`，但声明方式导致 `@>` 不可用，见 IM-03 |

### C. 持久化语义（约束 2：10 个方法）

| 方法 | 判定 | 说明 |
|---|---|---|
| `register_class` | ✅ | 空值不覆盖、父类取并集，与旧 rdflib 语义对齐 |
| `unregister_class` | ❌ | **语义退化**：只清理 `parent_uris`，未清理 `ontology_annotation` 中对该类的引用（旧实现会删除所有 `<target> a <uri>` 三元组）。见 IM-04 |
| `get_class` / `list_classes` | ✅ | |
| `get_ancestors` / `get_descendants` | ✅ | visited 集合防循环；返回值由集合无序改为 `sorted`（更确定，非破坏性） |
| `get_hierarchy` | ✅ | 沿祖先链判重截断；已验证旧实现在 `Root→A→B→A` 下确实 RecursionError，修复真实有效 |
| `import_ttl` | ❌ | 含空节点/非白名单 `rdf:type` 时数据损坏且往返不一致。见 **CR-01** |
| `export_ttl` | ⚠️ | 依赖 `import_ttl` 的落库结果，同 CR-01；label 统一 `@zh`（见疑虑 #2） |
| `stats` | ✅ | PG 实测 `{'total_triples': 7, 'class_count': 2}`，与旧实现口径一致 |

### D. 路由改造要求（约束 3）

| 端点 | 判定 | 说明 |
|---|---|---|
| `POST /classes` | ✅ | 注入 tenant_id |
| `GET /classes` | ✅ | 同上；返回顺序由 rdflib 无序变为按 URI 排序（更确定） |
| `GET /hierarchy` | ✅ | |
| `POST /import-ttl` | ✅ | |
| `GET /export-ttl` | ✅ | |
| `GET /stats` | ✅ | |
| `GET /articles/{class_uri}` | ❌ | 注入了 `current_user` 但**未使用** tenant_id（`wiki_owl.py:153-166`）；租户过滤完全依赖全局 `do_orm_execute` 拦截器；且真实 SQL 从未被执行（见 IM-02） |

### E. 必须通过的测试

| # | 要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | 先写暴露跨租户可见的缺陷测试并确认失败 | ✅ | 报告给出 RED 输出与断言原文，可信 |
| 2 | 重启/新实例后数据仍在 | ⚠️ | 仅在 **SQLite 文件库**上验证，未在 PostgreSQL 上验证（见 IM-01） |
| 3 | TTL 导入→导出往返一致 | ❌ | 测试用例的 TTL 样本全部无空节点、无白名单外 `rdf:type`，绕过真实场景；实测往返不一致（CR-01） |
| 4 | 层级正确 + 循环不死循环 | ✅ | 12 条用例，覆盖引擎层/API 层/落库重读 |
| 5 | 全量回归 `/api/v1/wiki/owl/*` 所有端点 | ❌ | 16 条契约用例中 14 条跑在 SQLite；`/articles` 2 条用 `_StubSession`，断言的是桩返回的固定行 |

### F. 验收标准与绑定约束

| 项 | 判定 | 说明 |
|---|---|---|
| 持久化：重启不丢 | ⚠️ | 语义正确，实证环境错（SQLite）。PG 实测通过，但任务自检证据不合格 |
| 租户隔离：A 看不到 B | ✅ | PG 实测 `OTHER_TENANT_LIST: []`；但 `tenant_id=None` 仍共享 NULL 分区（IM-07） |
| 回归：端点行为一致 | ⚠️ | 6/7 端点一致；`/articles` 未真正回归 |
| 循环保护 | ✅ | |
| TTL 往返一致 | ❌ | CR-01 |
| 约束 1 不新增依赖 | ✅ | 仅用 rdflib / SQLAlchemy / Alembic |
| 约束 5 循环不死循环 | ✅ | |
| 约束 6 两处唯一约束 | ✅ | |
| 约束 7 禁用 SAEnum | ✅ | |
| 约束 8 不提交 git | ✅ | 报告声明，工作区保留改动 |
| 边界：不做 SHACL / 推理 / PROV-O / 回滚 | ✅ | 未越界 |

---

## 发现

### Critical

#### CR-01：TTL 导入对空节点与非白名单 `rdf:type` 处理错误 → 数据损坏、往返不一致、`ttl_content` 无界增长

**文件：** `backend/app/ai/knowledge/owl_engine.py:353-402`（`_persist_parsed_graph`），`:51`（`_NON_ANNOTATION_TYPES`）

**问题：** 拆分逻辑只按"主语是否为 `owl:Class` 主语 / 宾语是否在白名单"二分，没有处理 rdflib 的 `BNode`，也没有覆盖白名单外的本体元词汇。后果有四类：

1. **空节点被当成 URI 写进 `parent_uris`。**
   `owl_engine.py:363-371` 中 `parents = [str(o) for o in parsed.objects(subj, RDFS.subClassOf)]`，宾语若是 `BNode`，`str(o)` 得到 `n38afbef…` 这类内部 ID，被当作合法父类 URI 持久化。
2. **一个空节点的三元组被劈成两个不相关的节点。**
   `<bnode> a owl:Restriction` 因 `owl:Restriction` 不在 `_NON_ANNOTATION_TYPES`（`:51`，只列了 Class/Ontology/ObjectProperty/DatatypeProperty/AnnotationProperty/NamedIndividual/Property/List/Class/Datatype）被当成"文章标注"写入 `ontology_annotation`；而 `owl:onProperty` / `owl:someValuesFrom` 落入 `ttl_content` 并附上**新的**空节点。原 `owl:Restriction` 结构被彻底破坏。
3. **往返不一致（验收标准直接被违反）。**
4. **`ttl_content` 无界增长、幂等失效。** `existing_triples` 去重只对 URIRef 稳定；空节点每轮重新生成 ID，所以每次导入都判定为"新增"，第 3 类去重形同失效 —— 这正是报告"自审 #5"声称已修复的问题，但修复只在无空节点时成立。

**实测证据（同一份 TTL 连续导入 3 次）：**

```
pass 1 added = 8 | ttl_content_len = 136
pass 2 added = 6 | ttl_content_len = 274
pass 3 added = 6 | ttl_content_len = 412
PARENTS_A: ['nf99cbf8…', 'nf1c1389…', 'n4f8e4608…']      ← 每次导入多一个假父类
```

导出结果（原文件是 `ex:A rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:p ; owl:someValuesFrom ex:B ]`）：

```turtle
ex:A a owl:Class ; rdfs:label "A"@zh ; rdfs:subClassOf <n38afbef…> .
<n38afbef…> a owl:Restriction .
[] owl:onProperty ex:p ; owl:someValuesFrom ex:B .        ← 被劈成另一个节点
```

**为什么现有测试全绿却漏掉：** `test_ttl_roundtrip.py` / `test_api_regression.py` 的 3 份 TTL 样本全部是
`ex:X a owl:Class ; rdfs:label "…" ; rdfs:subClassOf ex:Y` 的扁平结构，既无空节点也无白名单外类型。测试用例只覆盖了实现能跑通的形状。

**修复建议（推荐 B 案）：**

A 案（最小改动）：在 `_persist_parsed_graph` 中全面加 `isinstance(x, URIRef)` 守卫 ——
类识别、父类收集、标注识别三处都只接受 `URIRef`；含任何 `BNode` 的图整体进 `ttl_content`；
同时把 `_NON_ANNOTATION_TYPES` 从白名单改为"主语必须是 URIRef 且不在白名单才当标注"，
并补充 `owl:Restriction / owl:AllDifferent / owl:TransitiveProperty / owl:FunctionalProperty …`。

B 案（更稳妥，推荐）：把 `ttl_content` 的语义改为**存规范化后的全量原文**（`parsed.serialize(format="turtle")`），
`ontology_class` / `ontology_annotation` 只作为**查询索引**冗余抽取。
`export_ttl` 直接返回全量原文 + 索引中"原文没有"的增量。这样往返天然一致、天然幂等，`ttl_content` 不会增长。

无论哪案，都必须补一条**含 `owl:Restriction` 空节点**的往返测试用例。

---

### Important

#### IM-01：41 条测试全部跑在 SQLite；"本机 PostgreSQL 未启动"的前提不成立

**文件：** `backend/tests/ontology/conftest.py:1605-1622`（docstring），报告 §5.2

**问题：** 报告称 `localhost:5432` 连接被拒、只能在 SQLite 上验证。
评审时实测：**PostgreSQL 17.11 可用且可连接**（`5432` 由 `com.docker.backend` 转发）。

```
netstat -ano | findstr :5432
  TCP    0.0.0.0:5432    0.0.0.0:0    LISTENING    12000   (com.docker.backend)

>>> sqlalchemy create_engine("postgresql+psycopg2://postgres:***@localhost:5432/miniworkbuddy")
CONNECTED PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2) on x86_64-pc-linux-gnu
```

我在该库上以**单事务内执行 + 最终 rollback**（不落库）的方式跑了完整冒烟，结果如下：

```
DDL：ontology / ontology_class / ontology_annotation 创建成功
  ontology             id=BIGSERIAL  tenant_id=BIGINT
  ontology_class       json=JSONB    idx=[idx_ontology_class_ontology, idx_ontology_class_status, ix_ontology_class_tenant_id, uq_ontology_class]
  ontology_annotation  json=JSONB    uq=[uq_ontology_annotation]
LIST: ['http://ex.org/o#OpRisk', 'http://ex.org/o#Risk']
ANCESTORS: ['http://ex.org/o#Risk']   DESC: ['http://ex.org/o#OpRisk']
HIER: [{'uri': …#Risk, 'label':'风险', 'children':[{'uri': …#OpRisk, …}]}]
STATS: {'total_triples': 7, 'class_count': 2}
EXPORT_LEN: 388 | HAS_ZH: True
TTL_ADDED: 4 | 其它租户 LIST: []  STATS: {'total_triples': 1, 'class_count': 0}
UNREG: True
ROLLED_BACK_OK
```

**结论：** 实现本身在 PostgreSQL 上是可用的，因此本条**不升级为 Critical**；
但"仅在 SQLite 上通过"**不能算满足"持久化到 PostgreSQL"的验收要求** —— 因为验收证据跑的不是目标数据库，
而目标数据库当时（及评审时）是可用的。实现者未做二次确认即把环境问题当成不可逾越的阻塞，属于验证不充分。

**修复建议：** 在关闭任务前必须做一次 PG 全量回归。最低成本做法是把 `conftest.py` 的 engine 改为读环境变量：

```python
DB_URL = os.getenv("MINWORKBUDDY_TEST_DB_URL", f"sqlite:///{db_path.as_posix()}")
eng = create_engine(DB_URL)
```

有 PG 时跑 PG（可去掉 `@compiles(JSONB,"sqlite")` / `@compiles(BigInteger,"sqlite")` 分支），无 PG 时退回 SQLite。

---

#### IM-02：`/articles/{class_uri}` 用桩会话，真实 SQL 从未被任何测试执行；端点未使用 `tenant_id`

**文件：** `backend/tests/ontology/test_api_regression.py:2020-2086`，`backend/app/routers/wiki/wiki_owl.py:153-166`

**问题：**
1. `_StubSession.execute()` 无条件返回固定行。这两条用例断言的是"桩喂进去的数据原样返回"，
   与端点真实 SQL（`WikiArticle.owl_class_uris.contains([class_uri])`）**零关联** ——
   即使 SQL 写错、`contains` 语义反转、过滤器删掉，测试照样全绿。属于"测试了实现细节（其实是测试了桩）而非行为"。
2. 端点注入了 `current_user` 却完全没用，租户过滤依赖全局 `do_orm_execute` 拦截器
   （`app/core/tenant_interceptor.py`）。这在 JWT 链路上成立，但：
   拦截器在 `tenant_id is None` 或 `is_ignore()`（超管）时**直接跳过过滤**，端点自身没有任何兜底。
   简报要求"所有 `/wiki/owl/*` 端点需注入 tenant_id"，此处只注入了对象没注入过滤。
3. 顺带澄清：该端点的 `@>` 在 PG 上是正常的（实测编译结果 `WHERE wiki_article.owl_class_uris @> %(…)s::JSONB`），
   因为 `WikiArticle.owl_class_uris` 用的是裸 `JSONB`。真正有 `@>` 问题的是新模型（见 IM-03）。

**修复建议：** 至少补一条在真实 SQLite/PG 会话上、针对 `owl_class_uris` 的过滤用例
（SQLite 可用 JSON 文本匹配或改用 Python 侧过滤断言）；并在端点里显式加
`.where(WikiArticle.tenant_id == _tenant_id_of(current_user))`，不把隔离寄托在全局拦截器上。

---

#### IM-03：`JsonList = JSON().with_variant(JSONB, "postgresql")` 使 `.contains()` 在 PG 上退化成 `LIKE`

**文件：** `backend/app/models/ontology/ontology.py:39`

**问题：** 变体类型在表达式构建期按**默认类型** `JSON` 选取 comparator，
`JSON.Comparator` 未覆写 `contains`，因此继承 `String.Comparator.contains` → 渲染成 `LIKE '%' || … || '%'`。
实测在 PostgreSQL 上直接报错：

```
VARIANT_CONTAINS_SQL: … WHERE (ontology_class.parent_uris LIKE '%%' || %(parent_uris_1)s::JSONB || '%%')
sqlalchemy.exc.DataError: (psycopg2.errors.InvalidTextRepresentation) invalid input syntax for type json
LINE 3: WHERE (ontology_class.parent_uris LIKE '%' || '["http://ex.o...
```

对比项目既有写法 `Column(JSONB, …)`（`wiki_article.py:31`）渲染正常：`WHERE wiki_article.owl_class_uris @> …::JSONB`。

**影响：** 目前无生产代码对新列用 `.contains()`，所以尚未爆发；但报告把"JSONB `@>` 真实过滤"明确列为待 PG 验证项，
后续任何人按报告的建议去补 `@>` 过滤，第一次运行就会 `DataError`。这是一颗埋好的雷，且与项目既有惯例不一致。

**修复建议：** 直接用 `Column(JSONB, …)` 与 `WikiArticle` 保持一致；测试侧的 SQLite 兼容已由 conftest 的
`@compiles(JSONB, "sqlite") -> "JSON"` 解决，`with_variant` 并非必需。若必须保留变体，则所有 `.contains()` 处改写为
`sa.type_coerce(OntologyClass.parent_uris, JSONB).contains([...])`。

---

#### IM-04：`unregister_class` 未清理 `ontology_annotation` 中对该类的引用，语义相对改造前退化

**文件：** `backend/app/ai/knowledge/owl_engine.py:165-176`，`backend/app/services/ontology/ontology_repository.py:206`

**问题：** 旧实现 `unregister_class` 的文档与行为是"移除一个 OWL Class **及其所有三元组**"，
其中包含 `self._graph.triples((None, None, subj))` —— 即删除所有 `<target> rdf:type <uri>` 标注。
新实现只调用 `remove_parent_reference()`（`ontology_repository.py:206`），它只改 `parent_uris`，
完全不动 `ontology_annotation.class_uris`。结果是：类被删除后，
`engine.get_articles_by_class(uri)` 仍返回指向已删除类的文章 —— 悬挂引用。
违反约束 2「保留 `WikiOwlEngine` 现有全部对外方法语义」。

**补充：** `delete_class()` 与 `remove_parent_reference()` 各自 `_commit()`，两步之间不具备原子性。

**修复建议：** 在 `OntologyRepository` 增加 `remove_class_reference(uri)`，把 `uri` 从所有
`ontology_annotation.class_uris` 中摘除；`unregister_class` 在同一事务内完成"删类 + 摘父类 + 摘标注"；
补一条 `unregister_class` 后 `get_articles_by_class(uri) == []` 的用例。

---

#### IM-05：仓储每次写都提交整个请求会话 → TTL 导入非原子；非 `ValueError` 的 DB 异常在路由层漏成 500

**文件：** `backend/app/services/ontology/ontology_repository.py:322`（`_commit`），`backend/app/routers/wiki/wiki_owl.py:115-118`

**问题：**
1. `_commit()` 提交的是 FastAPI 请求级共享会话。`import_ttl` 内部对每个类、每条标注、以及
   `append_ttl_content` 各提交一次 —— 一次 POST 里产生 N 次提交。中途任何失败（超长 URI、
   连接抖动）都会留下**部分导入的本体**，而 `import_ttl` 的返回值 `added` 还是按"解析成功"算的。
2. 路由只 `except ValueError`。SQLAlchemy 的 `DataError`（如 `uri` 超过 1000 字符）、
   `IntegrityError`、`OperationalError` 均不属于 `ValueError`，会直接冒泡成 **500**，
   且此时前面的写入**已经提交**。改造前（纯内存图）是先解析再整体 `graph.parse`，失败即无副作用。

**修复建议：** 路由层改为 `except (ValueError, SQLAlchemyError)` 并统一回滚；
或让仓储支持"外部事务"模式（提供 `flush()` 版本），由路由在一个显式事务里完成整个导入。

---

#### IM-06：`backend/app/db/extensions.py` 超出任务范围、无任何调用点（死代码）

**文件：** `backend/app/db/extensions.py`（整个文件，67 行）

**问题：**
1. 不在简报"涉及文件"清单内，也不在报告的"改动文件清单"里 —— 属于**未被披露的改动**。
2. 全仓库搜索 `ensure_pgvector_extension` / `db.extensions` / `import extensions` **零调用点**，是纯死代码。
3. 内容与本任务（本体持久化）无关，是 pgvector 扩展初始化，明显是其它任务的工作被混进本次 diff。
4. 其中 `DROP TYPE IF EXISTS vector CASCADE` 属于高危 DDL，若将来被误接进启动路径，会连带删除依赖对象。

**修复建议：** 从本次改动中移除该文件（或明确归属到它自己的任务并提供调用点）。

---

#### IM-07：`tenant_id` 为空的用户落到 NULL 分区，跨租户共享缺陷对其仍然存在

**文件：** `backend/app/routers/wiki/wiki_owl.py:55-57`，`backend/app/services/ontology/ontology_repository.py`

**问题：** `_tenant_id_of()` 对 `tenant_id=None` 直接返回 `None`，仓储以 `tenant_id == None` 过滤，
于是所有无租户用户（含 API Key 场景、`SysUser.tenant_id` 为 NULL 的账号）共享同一个 NULL 分区 ——
行为与改造前的"全局共享"**完全等价**，即本次要修复的缺陷对这部分用户仍未修复。
同时 `app/core/tenant_interceptor.py:35` 在 `tenant_id is None` 时也跳过过滤，无兜底。

**修复建议：** 与产品确认后二选一：`tenant_id` 为空时返回 `400 tenant_required`；
或保留 NULL 分区但在仓储/服务层显式记录 WARN 并在 API 文档中标注。当前"静默共享"不应作为默认。

---

### Minor

#### MI-01：疑虑 #2 —— TTL 导入的 label/comment 语言标记退化为 `@zh`
**文件** `owl_engine.py:339-341, 600-603`。schema 无语言列，属结构性后果，`register_class` 路径改造前就是 `@zh`，
一致性可接受。**但**改造前 TTL 导入路径保留原文（无 lang），改造后统一 `@zh`，属**行为变更**，
仅由 `test_export_ttl_label_uses_zh_lang_tag` 固化了"新行为"，没有对比旧行为的说明。
建议：P4.2 加 `label_lang` / `comment_lang` 列；或在导入时保留 `Literal.language` 并在导出时还原。

#### MI-02：疑虑 #4 —— `WikiOwlEngine()` 无参构造仍退化到内存后端
**文件** `owl_engine.py:120-131`，`ontology_repository.py:341`（`InMemoryOntologyStore`）。
当前无生产调用方（`get_owl_engine` 始终传 store），但它是生产代码里的一个静默数据丢失陷阱，
且 `InMemoryOntologyStore` 除该回退外**无任何调用方**（测试也没用），属 YAGNI + 死代码。
建议：删除无参回退，改为 `store` 必填（或至少 `logger.error` 而非 `warning`）。

#### MI-03：`_NON_ANNOTATION_TYPES` 白名单不完整
**文件** `owl_engine.py:51`。缺 `owl:Restriction` / `owl:AllDifferent` / `owl:TransitiveProperty` /
`owl:FunctionalProperty` / `owl:InverseFunctionalProperty` / `owl:SymmetricProperty` /
`owl:AsymmetricProperty` / `owl:ReflexiveProperty` / `owl:IrreflexiveProperty` / `owl:NamedIndividual` 之外的个体类。
后果：这些类型出现时，`<x> a owl:TransitiveProperty` 会被当成"文章标注"写进
`ontology_annotation`（`target_type='article'`），污染标注表。与 CR-01 同源，建议一并修。

#### MI-04：`ontology` 表 `tenant_id` 上有两个重复索引
**文件** `ontology.py:31, 105`。`TenantMixin.tenant_id` 已带 `index=True` → 自动产生 `ix_ontology_tenant_id`，
`__table_args__` 又显式声明 `Index("idx_ontology_tenant", "tenant_id")`。PG 实测：
`idx: ['idx_ontology_status', 'idx_ontology_tenant', 'ix_ontology_tenant_id', 'uq_ontology_code']`。
另两表只有 mixin 的那一个 —— 三表风格不一致。建议删除 `idx_ontology_tenant`。

#### MI-05：若干无调用方的 API 参数与方法
`ontology_repository.py:241` `set_ttl_content()`（两个实现都无人调用）；
`merge_parents` / `merge` 参数从未传 `False`；`code` / `target_type` 参数无外部传值；
引擎的 `annotate_article` / `get_article_classes` / `get_articles_by_class` 无任何测试覆盖。
建议按 YAGNI 收敛，至少给三个标注方法补测试（它们是约束 2 要求保留的对外方法）。

#### MI-06：测试卫生问题
- `test_api_regression.py:2020-2086` 的 `_StubSession` 断言桩数据（见 IM-02）。
- `test_persistence.py` 保留 `pytest.importorskip("app.models.ontology.ontology")`、
  `conftest._tables()` 保留 `try/except ImportError`、`_reset_legacy_singleton` 仍 `setattr(wiki_owl, "_owl_engine", None)`
  —— 均为 TDD RED 阶段脚手架，实现落地后应清理，否则读者会误以为仍存在旧单例。
- `test_ttl_roundtrip.py:2588` 在函数体内 `import pytest`（模块级未导入）。
- 无一条用例覆盖 `unregister_class` 后的标注清理（与 IM-04 互为因果）。
- 无一条用例覆盖"无租户用户"的行为（与 IM-07 互为因果）。

#### MI-07：`uri String(1000)` 参与 btree 唯一索引，多字节 URI 可能超 PG 索引上限
`uq_ontology_class (ontology_id, uri)` 在 PG 上以 btree 实现，单条索引项上限 2704 字节。
纯 ASCII 的 1000 字符安全（1000 B），但含中文的 URI 按 UTF-8 最坏 3000+ 字节会触发
`index row size … exceeds btree maximum`。建议把 `uri` 收到 512 并在入库前做长度校验/拒绝。

#### MI-08：类型注解与实际不符
`wiki_owl.py:47` `def get_owl_engine(tenant_id: int, db: Session)` —— 实际会传 `None`，应为 `Optional[int]`；
且缺返回类型标注（简报示例里有 `-> WikiOwlEngine`）。
`owl_engine.py` 中 `store: Optional["OntologyRepository"]` 实际会塞入 `InMemoryOntologyStore`，
后者并非其子类，类型提示失真。建议抽一个 `OntologyStore` Protocol。

#### MI-09：报告证据描述轻微不一致
报告 §3.1 称 RED 阶段"16 passed 中包含 15 条契约回归用例"，而 §3.2 GREEN 阶段的
`test_api_regression.py` 实际是 **16** 条。数字对不上（可能是实现过程中新增了一条）。
不影响结论，但降低证据可追溯性，建议校正。

---

## 对三条疑虑的判定

### 疑虑 1：仅 SQLite 验证，JSONB `@>` 与 JSONB DDL 未在 PG 实跑

| 维度 | 判定 |
|---|---|
| 是否违反绑定约束 | **是（部分）**。约束 3「全量回归 `/api/v1/wiki/owl/*`」与验收标准「持久化」要求的证据跑在 SQLite 上，不是目标数据库。 |
| 前提是否成立 | **不成立。** 评审实测 `localhost:5432` 处于 LISTENING（Docker 转发），PostgreSQL **17.11** 可正常连接并建库建表。 |
| 严重度 | **Important**（不升级 Critical：我在 PG 上实测了 DDL、三表结构、租户隔离、层级、TTL、stats、export，全部通过）。 |
| 实际风险 | 经实测为零 —— 但这是"运气好"，不是"验证过"。`/articles/{class_uri}` 的真实 `@>` 我在 PG 上也确认正常（`WHERE wiki_article.owl_class_uris @> …::JSONB`）。 |
| 是否必须本任务内修复 | **是。** 必须在关闭任务前用 PG 跑一次全量回归（改 `conftest` 支持 `MINWORKBUDDY_TEST_DB_URL` 即可，成本 <1 小时）。不接受"环境不具备"作为豁免理由 —— 环境具备。 |

### 疑虑 2：TTL 导入的 label/comment 语言标记退化为 `@zh`

| 维度 | 判定 |
|---|---|
| 是否违反绑定约束 | **不违反。** 约束 2 只要求保留方法语义；简报给定的表结构里没有语言列，`@zh` 是"与 `register_class` 历史行为一致"的合理降级。约束 3 要求端点行为一致 —— 严格说这里**变了**（改造前 TTL 导入保留原文无 lang，改造后统一 `@zh`），但属于**有文档、有测试固化**的已知变更。 |
| 严重度 | **Minor**（MI-01）。 |
| 是否必须本任务内修复 | **否。** 加语言列属 schema 变更，超出简报给定的表结构，应放到 P4.2。本任务只需保证该偏差被显式记录（已由 `test_export_ttl_label_uses_zh_lang_tag` 固化），建议再补一句"改造前后差异说明"。 |

### 疑虑 3：`WikiOwlEngine()` 无参退化到内存；`tenant_id` 为空落到 NULL 分区

| 维度 | 判定 |
|---|---|
| 是否违反绑定约束 | **不直接违反**（约束 2 只约束方法语义；简报未规定 `tenant_id` 为空如何处理）。但**与任务目标冲突**：本任务的存在理由就是消灭"跨租户共享"，NULL 分区把该缺陷原样保留给无租户用户。 |
| 严重度 | 无参回退 → **Minor**（MI-02，无生产调用方，属 YAGNI + 静默陷阱）；NULL 分区 → **Important**（IM-07，缺陷未修复的人群）。 |
| 是否必须本任务内修复 | 无参回退：**否**，但建议删除或改为必填 store（否则将来任何人 `WikiOwlEngine()` 就静默退回被修复前的缺陷）。NULL 分区：**建议是** —— 至少需要明确决策（返回 400，或显式 WARN + 文档标注），不应以"静默共享"作为默认。简报未授权改行为，所以最小可接受动作是：加显式日志 + 在报告中作为遗留风险登记，由你拍板是否 400。 |

---

## 建议

**必须修复（合入前）**

1. **CR-01**：重写 `_persist_parsed_graph` 的空节点/类型识别（推荐 B 案：`ttl_content` 存规范化全量原文，类与标注只作索引）。补一条含 `owl:Restriction` 空节点的往返用例。
2. **IM-01**：把 `conftest.py` 的 engine 改为可切换 PG，在 PostgreSQL 17 上跑一次 41 条全量回归，并把输出贴进报告。
3. **IM-06**：从本次改动中移除 `backend/app/db/extensions.py`（或明确归属它自己的任务并补调用点）。

**应当修复（本任务内）**

4. **IM-04**：`unregister_class` 同步清理 `ontology_annotation.class_uris`，并合并为单事务。
5. **IM-03**：`JsonList` 改为裸 `JSONB`（与 `WikiArticle` 一致），或在 `.contains()` 处用 `type_coerce`。
6. **IM-05**：路由捕获 `SQLAlchemyError` 并回滚；URI 入库前做长度校验，超限返回 400 而非 500。
7. **IM-02**：给 `/articles/{class_uri}` 补真实会话用例，并在端点显式加 `tenant_id` 过滤。
8. **IM-07**：对 `tenant_id is None` 做出明确决策（400 / 显式 WARN + 文档），不留静默共享。

**可以延后（记入 P4.2 待办）**

9. MI-01 语言列（`label_lang` / `comment_lang`）。
10. MI-04 删除 `idx_ontology_tenant` 重复索引。
11. MI-05 收敛无调用方的参数/方法，补三个标注方法的测试。
12. MI-06 清理 TDD 脚手架（`importorskip` / `_tables()` 的 try-except / `_reset_legacy_singleton`）。

**流程建议**

13. 报告中的"环境阻塞"类结论，应附一条可复现的探测命令与输出（如 `netstat`/`pg_isready`）。
    本次若当时真跑过，`5432 LISTENING` 是能看出来的 —— 一条一行命令就能避免把"没试过"写成"不可用"。
14. `wiki_owl` 当前在 `router_registry.py:161-164` 是 `enabled=False`（历史状态，报告已披露，不计缺陷）。
    这意味着本次所有"端点回归"都是在**测试专用 app** 上完成的。启用该模块时需要再跑一次真实 app 的端到端验证。

---

_评审人：任务级评审者_
_评审日期：2026-09-10_
_验证手段：静态逐文件精读 + PostgreSQL 17.11 事务内冒烟（已回滚）+ 空节点/重复导入故障注入_
