# P4.1 修复回合复审报告（第二轮）

- **复审日期**：2026-09-10
- **复审范围**：**工作区未提交改动**（`HEAD = 660aa78`，未执行任何 commit；复核前后 `git diff --stat -- backend/` 均为 `19 files changed, 2985 insertions(+), 178 deletions(-)`，与复审开始时逐字节一致）
- **验证环境**：
  - 数据库：**PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2)**，库名 **`minworkbuddy_test`**（我自行连库 `select version()` 核实，非引用报告结论）
  - 解释器：`d:\projects\MinWorkBuddy\backend\.venv\Scripts\python.exe`
  - 命令：`.venv\Scripts\python.exe -m pytest tests/ontology -v`
- **基线自测**：`55 passed, 3 warnings in 21.63s / 23.58s / 23.78s`（跑 3 次全绿，0 skipped、0 xfail）→ 报告中「55 passed / 22.43s」属实。
- **方法**：逐条读代码 + **10 组变异测试**（每组变异后确认目标用例 RED，随后还原并用 `git diff --stat` 核对）+ 真实 PG 一次性探针（脚本放 `D:\tmp\`，已删除）+ 空库实跑 004 迁移。

## 总体结论：**DONE_WITH_CONCERNS**

**理由**：

1. 第一轮的 **CR-01 + IM-01~IM-07 共 8 条，全部有真实代码改动，且 7 条经变异测试证明「去掉修复就 RED」**——修复不是纸面的。IM-01（PG 回归）、IM-02（真实 SQL + 租户过滤）、IM-03（裸 JSONB）、IM-04（单事务 unregister）、IM-06（删除 extensions.py）均可判定 FIXED。
2. **但 CR-01 采用的 B 案（`ttl_content` 改为「全量原文 + 索引」）引入了 3 个新缺陷**，其中 R2-01 是**数据丢失**（常见路径下用户通过 API 注册的 label / 父类在导出时静默消失），R2-02 让 `unregister_class` 在 TTL 导入的类上**退化回 IM-04 之前的状态**。这两条直接冲击简报约束 2「保留 `WikiOwlEngine` 全部对外方法语义」和约束 3「端点对外行为不变」。
3. 因此不能给 DONE：修复回合把「空节点数据损坏」换成了「内容与索引一致性未收敛」。**R2-01 建议按 Blocker 处理后再合入。**

---

## 1. 第一轮问题修复验证

| ID | 问题 | 判定 | 证据（命令 + 关键输出） |
|---|---|---|---|
| **CR-01** | TTL 导入对空节点与非白名单 `rdf:type` 处理错误 | **PARTIALLY_FIXED** | 原 4 类症状**全部消除**且经变异验证：① 空节点不再是假父类——变异 M2（`_reindex` 去掉 `isinstance(o, URIRef)` 守卫）→ `FAILED test_blank_node_is_not_persisted_as_parent_uri`；② 幂等/不增长——变异 M3（`_canonicalize` 退化为恒等）→ `FAILED test_repeated_import_of_blank_node_ttl_is_idempotent`；变异 M9（`set_ttl_content` 改回 `append_ttl_content`）→ 同一条用例 FAILED；③ 白名单改前缀——`grep _NON_ANNOTATION_TYPES` 全仓 0 命中，现为 `_is_standard_vocabulary()`（RDF/RDFS/OWL/XSD 前缀）；④ 往返同构——`test_ttl_roundtrip_preserves_blank_nodes`（`rdflib.compare.isomorphic`）PASSED。**但** B 案引入 3 个新缺陷 R2-01 / R2-02 / R2-03（见第 2 节），其中 R2-01 会造成真实数据丢失，故判 PARTIALLY_FIXED。 |
| **IM-01** | 测试全跑 SQLite，"PG 不可用"前提不成立 | **FIXED** | 自测：`.venv\Scripts\python.exe -c "...from tests.ontology.conftest import IS_POSTGRES, TEST_DB_URL..."` → `IS_POSTGRES= True`、`URL= postgresql+psycopg2:***@localhost:5432/minworkbuddy_test`、`SERVER= PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2)`。conftest 改为 schema-per-test + `engine_for()` 重建连接池；`test_postgres_contract.py::test_tests_run_against_postgresql` 把「必须 PG」固化为断言。55 条在 PG 上全绿。 |
| **IM-02** | `/articles/{class_uri}` 用桩会话、端点未用 `tenant_id` | **FIXED** | 代码：`wiki_owl.py:204` 显式 `.where(WikiArticle.tenant_id == tenant_id)`。`_StubSession`/`_StubResult` 全仓 0 命中。**变异 M1**（删掉该行）→ `FAILED tests/ontology/test_api_regression.py::test_articles_by_class_endpoint_is_tenant_scoped`；`1 failed, 3 passed`。4 条用例均走真实 PG 的 `@>`。 |
| **IM-03** | `JsonList = JSON().with_variant(JSONB,"postgresql")` 使 `.contains()` 退化成 LIKE | **FIXED** | 代码：`ontology.py:41` `JsonList = JSONB`（无 `with_variant`，全仓仅注释里出现）。**变异 M5**（改回 with_variant）→ `FAILED test_contains_operator_compiles_to_jsonb_containment` + `FAILED test_jsonb_containment_query_actually_runs`（`2 failed, 2 passed`）。空库实跑 004 后 `information_schema` 实测：`[('ontology_class','parent_uris','jsonb'), ('ontology_annotation','class_uris','jsonb')]`。 |
| **IM-04** | `unregister_class` 未清理 `ontology_annotation` 引用 | **FIXED**（索引层面） | 代码：`ontology_repository.py:255-266` `unregister()` 在单事务内「删类 + 摘父类 + 摘标注」，**只 `_commit()` 一次**。**变异 M4**（注释掉 `_remove_class_reference_rows`）→ `E AssertionError: 类已删除，不应再有指向它的标注 / assert ['wiki://arti...://article-2'] == []`。**残留**：`ttl_content` 里的同名类删不掉 → R2-02。 |
| **IM-05** | 每次写都提交整个会话 → 导入非原子；非 ValueError 异常漏成 500 | **PARTIALLY_FIXED** | ① `auto_commit=False` **机制真实有效**：PG 探针 T2（同一 schema、全新会话读）——`auto_commit=True: 失败导入前 ttl_content_len=158 → 失败后=2207 ❌ 残留部分写入` / `auto_commit=False: 158 → 158 ✅ 无残留`。② 长度校验生效：**变异 M7**（`_validate_uri` 直接 return）→ `FAILED test_register_class_with_oversized_uri_returns_400`，detail 变成 `(psycopg2.errors.StringDataRightTruncation) value too long...`。③ `except (ValueError, SQLAlchemyError)` 生效：M7 下去掉校验仍是 **400 不是 500**。④ **但**「回滚」这条**没有有效用例守护**：**变异 M6**（路由 `auto_commit=False` → `True`）→ `3 passed`，`test_failed_import_leaves_no_partial_data` 仍绿（见 R2-06）。⑤ 附带发现 400 响应泄漏内部 SQL/参数（R2-04）。 |
| **IM-06** | `backend/app/db/extensions.py` 越界且无调用点 | **FIXED** | `Test-Path backend\app\db\extensions.py` → `False`（工作区已删）；`git cat-file -e HEAD:backend/app/db/extensions.py` → 该文件**从未进过 HEAD**（第一轮说它是「本次 diff 的未披露改动 A」属实，`git status` 的 `R` 是 git 的重命名启发式）。全仓搜 `ensure_pgvector_extension\|db\.extensions\|app\.db\.extensions` → **Found 0 matching results**。测试库 pgvector 由 conftest `CREATE EXTENSION IF NOT EXISTS vector` 引导，无 `DROP TYPE ... CASCADE`。 |
| **IM-07** | `tenant_id` 为空落到 NULL 分区、静默共享 | **FIXED**（按「最小可接受动作」） | 代码：`ontology_repository.py:89-95`（构造时 WARN）+ `wiki_owl.py:76-82`（`_tenant_id_of` WARN）。**变异 M8**（把守卫改成 `if False`）→ `FAILED test_tenant_id_none_is_logged_as_shared_partition`。告警确实会打出来。**未做**的仍是：不返回 400（需简报授权，见第 5 节）。 |

---

## 2. 新发现的问题

| ID | 严重度 | 文件:行 | 问题 | 复现/证据 | 建议修法 |
|---|---|---|---|---|---|
| **R2-01** | **Blocker** | `backend/app/ai/knowledge/owl_engine.py:382-392`（`_build_graph`） | **导入 TTL 后，通过 `POST /classes` 注册的 `label` / `comment` / `parent_uris` 从 `export_ttl()` 中静默消失。** `if (subj, RDF.type, OWL.Class) in graph: continue` 的判定粒度是「类」，一旦发现原文声明过 `<X> a owl:Class`，就**整类跳过**，索引里原文没有的增量（label/comment/父类）不再补出。 | PG 探针 P1/P2（真实库）：<br>`register_class(A, label="风险")` → `export` 含 `"风险"@zh` = **True**；再 `import_ttl("<A> a owl:Class .")` → 索引里 `A.label` 仍是 `风险`，但 `export` 含 `"风险"@zh` = **False**。<br>P2：`register_class(C, parent=[P])` → `C.parents=['…#P']`；导入 `<C> a owl:Class .` 后 `C.parents` 仍是 `['…#P']`，但导出里 `(C, rdfs:subClassOf, P)` = **False**。<br>旧实现 `graph.add(...)` 是"加"不是"替换"，不会丢 → 属**行为变更 + 数据丢失**。 | 把跳过粒度从「类」细化到「三元组」：内容已有就不重复加，内容没有的从索引补。<br>```python<br>for record in self._store.list_classes():<br>    subj = URIRef(record.uri)<br>    graph.add((subj, RDF.type, OWL.Class))<br>    if record.label and graph.value(subj, RDFS.label) is None:<br>        graph.add((subj, RDFS.label, Literal(record.label, lang="zh")))<br>    if record.comment and graph.value(subj, RDFS.comment) is None:<br>        graph.add((subj, RDFS.comment, Literal(record.comment, lang="zh")))<br>    have = set(graph.objects(subj, RDFS.subClassOf))<br>    for p in record.parent_uris:<br>        if URIRef(p) not in have:<br>            graph.add((subj, RDFS.subClassOf, URIRef(p)))<br>```<br>并补用例：`注册 → 导入仅含 a owl:Class 的 TTL → 导出仍含 label/父类`。 |
| **R2-02** | **Major** | `backend/app/ai/knowledge/owl_engine.py:366-401`；`backend/app/services/ontology/ontology_repository.py:255-266` | **`unregister_class()` 对"TTL 导入进来的类"不生效**：只删索引行，`ttl_content`（全量原文）里的三元组删不掉，于是类删除后仍出现在 `export_ttl()` 与 `stats()` 里。违反约束 2——旧实现 `unregister_class` 会删 `(subj,None,None)` 与 `(None,None,subj)`，即**所有**三元组。 | PG 探针 P3：导入 `X a owl:Class; Y subClassOf X` → `unregister_class(X)` 返回 **True**，`list_classes()` 只剩 `Y`，但 `export` 里 `(X, a, owl:Class)` = **True**，`stats()` = `{'total_triples': 6, 'class_count': 1}`（X 被计入 total）。索引说删了、导出说还在，接口自相矛盾。 | 方案 a（推荐）：`unregister()` 时把 `uri` 记入"已注销"集合（如 `ontology_class` 墓碑行或 `ontology.tombstones` JSONB），`_build_graph()` 读图后剔除这些 URI 的全部三元组；<br>方案 b：`unregister()` 里重建 `ttl_content`（`_content_graph()` → 删除该类三元组 → `set_ttl_content()`）。<br>补用例：`unregister` 后 `export_ttl()` 不含该类。 |
| **R2-03** | **Major** | `backend/app/ai/knowledge/owl_engine.py:328-331`（`import_ttl`） | **跨导入的"结构相同但语义不同"的空节点被合并成一个。** 实现先对存储侧与新增侧**各自** `to_canonical_graph()` 再做集合并集；规范化给结构相同的空节点相同标签，于是两次导入里两个不同的空节点被并成同一个。 | PG 探针 P6：A、B 各自 `subClassOf [a owl:Restriction; owl:onProperty ex:p]`，两次导入后导出里 A 与 B 的父类是**同一个**空节点 `na1f5964…`。<br>纯 rdflib 探针：单次导入两个相同空节点 → 规范化后仍是 **2 个**（✅ 单次安全）；两次导入 → 合集后只剩 **1 个**（❌）：`('cb0', ex:name, '启动会')`、`(doc1, ex:mentions, cb0)`、`(doc2, ex:mentions, cb0)` —— 两个独立 Event 被并成一个。 | 不要用"规范化标签相等"做集合去重。改用同构感知差集：`rdflib.compare.graph_diff(incoming, stored)` 求"新增部分"，或对连通分量逐一 `isomorphic` 判定后再合并；合并时对来自不同图的空节点做重命名以保留独立性。保留 `added == 0` 幂等语义即可。 |
| **R2-04** | Minor | `backend/app/routers/wiki/wiki_owl.py:106`、`:156` | 400 响应把 SQLAlchemy 异常原文回显给客户端，**包含完整 SQL 语句与绑定参数（含 `tenant_id`）**（CWE-209 信息泄漏）。 | 变异 M7 下实测响应体：`"(psycopg2.errors.StringDataRightTruncation) value too long for type character varying(1000)\n\n[SQL: INSERT INTO onto...reator_id': None, 'updater_id': None, 'tenant_id': 100}]"` | `ValueError` 可回原文（是客户端错误）；`SQLAlchemyError` 只回固定文案（如 `"本体写入失败，请稍后重试"`），异常体写 `logger.exception`。同时 `OperationalError`（库连不上）应回 503 而非 400。 |
| **R2-05** | Minor | `ontology.py:17-18`、`:62`；`alembic/.../004_...py:72`；`ontology_repository.py:7-8`、`:310` | **CR-01 改了 `ttl_content` 语义，但模型/迁移/仓储的注释仍写旧语义**（"非类/非标注的残余三元组"），且仍声称"SQLite 退化为 JSON"（`JsonList` 已是裸 JSONB，无 variant）、"写操作立即 commit"（现受 `auto_commit` 控制）。 | 直接读文件可见；实际语义为"规范化后的全量原文"。 | 同步更正 4 处注释；尤其 `ttl_content` 的语义说明直接影响第 5 节"旧数据是否需要迁移"的决策。 |
| **R2-06** | Minor | `backend/tests/ontology/test_api_regression.py:366-392` | **IM-05 的"回滚"没有有效用例守护**：该用例只断言 `/classes`（索引），不断言 `ttl_content`。而失败发生在 `_reindex`（`_validate_uri`）阶段、`set_ttl_content` 已 flush 之后——**真正会被部分写入的正是 `ttl_content`**。 | **变异 M6**：把路由 `auto_commit=False` 改成 `True` → `3 passed`（`test_failed_import_leaves_no_partial_data` 仍绿）。<br>对比探针 T2：同一场景下 `auto_commit=True` 确实残留 158→2207。⇒ 该用例**测不出**事务边界是否成立。 | 在用例里增加"失败导入后导出内容与失败前**逐字节一致**"的断言（覆盖 `ttl_content`），或新增 `GET /export-ttl` 前后一致的断言。 |
| **R2-07** | Minor | `backend/app/models/ontology/ontology.py:78`；`alembic/.../004_...py:80-81` | MI-04 未修：`ontology.tenant_id` 上同时存在 `ix_ontology_tenant_id`（TenantMixin 的 `index=True`）与 `idx_ontology_tenant`，另两表只有前者，三表风格不一致。 | 空库实跑 004 后 PG 实测索引清单同时含 `idx_ontology_tenant` 与 `ix_ontology_tenant_id`。 | 从模型与迁移中删掉 `idx_ontology_tenant`。 |
| **R2-08** | Minor | `conftest.py:370-381`；`test_persistence.py:110`、`:184`；`test_ttl_roundtrip.py:149`；`ontology_repository.py:313-327`、`:434-574` | 测试卫生与死代码（第一轮 MI-06，报告未改）：① `_reset_legacy_singleton` 仍 `setattr(wiki_owl, "_owl_engine", None)`，给**已删除**的全局单例凭空造属性，读者会以为它还在；② 2 处 `pytest.importorskip` 残留；③ 函数体内 `import pytest`；④ `append_ttl_content()`（两个实现）在 B 案后**已无任何调用方**；⑤ `InMemoryOntologyStore` 与 `OntologyRepository` 行为不一致：不做长度校验、`tenant_id=None` 不告警、`upsert_annotation` 直接返回内部对象而非副本——将来若有人走内存后端会绕过 IM-05/IM-07 的保护。 | 直接读文件 + `grep append_ttl_content` 仅命中定义处。 | 清理 ①②③；删除 `append_ttl_content` 或加 `# noqa` 显式标注保留理由；给 `InMemoryOntologyStore` 补长度校验与 None 告警，或删除该回退（对应 MI-02）。 |

---

## 3. 简报验收标准复核

统一命令（工作目录 `d:\projects\MinWorkBuddy\backend`）：`.venv\Scripts\python.exe -m pytest tests/ontology -q -k "<关键字>"`

| 验收项 | 结论 | 验证命令与结果 |
|---|---|---|
| **持久化：重启不丢** | ✅ | `-k "survive or across"` → **`4 passed`**：`test_classes_survive_new_engine_instance`（`engine_for()` **重建 engine/连接池**，非复用连接）、`test_classes_survive_across_sessions`、`test_unregister_is_persisted`、`test_ttl_roundtrip_across_engine_instances`。库为 PG 17.11 `minworkbuddy_test`（已独立核实）。 |
| **租户隔离：A 看不到 B** | ✅ | `-k "tenant"` → **`6 passed`**：`test_tenant_b_cannot_see_tenant_a_classes`、`test_tenant_a_cannot_see_tenant_b_classes`、`test_same_tenant_sees_own_classes`、`test_articles_by_class_endpoint_is_tenant_scoped`、`test_api_ttl_is_tenant_scoped`、`test_tenant_id_none_is_logged_as_shared_partition`。<br>另做**变异 M11**（`get_or_create_ontology` 去掉 `Ontology.tenant_id` 过滤）→ `FAILED test_api_ttl_is_tenant_scoped`；且类级、标注级还有两道 `tenant_id` 过滤（纵深防御，去掉任一道其余仍生效）。 |
| **回归：`/api/v1/wiki/owl/*` 端点行为一致** | ⚠️ **有条件通过** | `-k "contract or endpoint or all_owl"` → **`15 passed`**，含 `test_all_owl_endpoints_are_covered`（路由表 6 个路径全覆盖）。<br>**但** R2-01 证明在「先 `POST /classes` 再 `POST /import-ttl`」的混合路径上导出行为**与改造前不一致**（丢 label / 丢父类），该路径无任何用例覆盖。另外 `wiki_owl` 在 `router_registry.py` 中 `enabled=False`（已知事项），所有端点验证都在测试专用 app 上完成。 |
| **循环保护：循环父类不死循环** | ✅ | `-k "cycle or hierarchy or ancestors or descendants"` → **`14 passed`**，覆盖引擎层（ancestors/descendants/hierarchy）、API 层、落库后重读、自环、根下环、根间环。 |
| **TTL：导入导出往返一致** | ⚠️ **有条件通过** | `-k "ttl or blank_node"` → **`15 passed`**，含 `test_ttl_roundtrip_preserves_blank_nodes`（`isomorphic` 同构）、`test_repeated_import_of_blank_node_ttl_is_idempotent`（3 次导入 `added==0`、导出字节一致）。探针 P5 实测：`pass1 added=8 len=333 / pass2 added=0 len=333 / pass3 added=0 len=333` —— 不增长成立。<br>**但** R2-03 证明跨导入的结构相同空节点被错误合并（`added==0` 的代价），且 R2-01/02 会让"往返"在混合使用场景下不一致。 |

---

## 4. 约束遵守

| # | 约束 | 判定 | 说明 |
|---|---|---|---|
| 1 | 不引入新依赖（除 rdflib / SQLAlchemy / Alembic） | ✅ | `owl_engine.py` 只依赖 rdflib（含 `rdflib.compare`）、`ontology_repository.py` / `ontology.py` 只依赖 SQLAlchemy、迁移只依赖 Alembic。<br>⚠️ 工作区 `backend/requirements.txt` 有 `+websockets>=12.0`、`config.py` 有 `+SKILLHUB_*`——经比对属 **SkillHub 云市场任务**（`app/ai/skills/hub/git_hub.py`、`categories.py` 同批改动），**与 P4.1 无关**，但同在工作区，合入前需确认归属。 |
| 2 | 保留 `WikiOwlEngine` 全部对外方法语义 | ❌ | 13 个方法**签名齐全**（register/unregister/get/list/ancestors/descendants/hierarchy/annotate/get_article_classes/get_articles_by_class/import/export/stats）。但 `unregister_class` 对 TTL 导入的类**不再删除其全部三元组**（R2-02），与改造前语义不等价；`get_article_classes` 也不再过滤 `OWL.Class` / `RDF.type`（差异极小，属边界）。 |
| 3 | `/api/v1/wiki/owl/*` 端点对外行为不变 | ❌ | 状态码 / 响应结构 / 字段全部一致（15 条契约用例 + `test_all_owl_endpoints_are_covered`）。但 **R2-01 在「API 注册 + TTL 导入」混合路径上改变了导出结果**（丢 label、丢父类），是真实的行为变更且无用例覆盖。 |
| 4 | 循环父类不死循环 | ✅ | 14 条循环/层级用例全绿；`get_ancestors`/`get_descendants` 用 visited 集合，`get_hierarchy` 沿祖先链判重截断。 |
| 5 | 状态字段禁用 SAEnum | ✅ | 空库实跑 004 后 `information_schema` 实测：`('ontology','status','character varying')`、`('ontology','source','character varying')`、`('ontology_class','status','character varying')`、`('ontology_annotation','target_type','character varying')` —— 无 ENUM。 |
| 6 | 不执行 `git commit` | ✅ | 复审全程未执行 `git commit` / `add` / `checkout` / `stash`；结束前 `git status --porcelain` 与复审开始时一致，无我方残留文件（临时脚本在 `D:\tmp\` 且已删除）。 |
| 7 | 不做 SHACL / 推理机 / PROV-O / 回滚 | ✅ | 未越界；`ttl_content` 全量原文方案反而更"不做推理"。 |

---

## 5. 遗留风险与需用户拍板事项

1. **【需拍板·高】R2-01 / R2-02 的修法二选一**
   - (a) 保留 B 案（`ttl_content` = 全量原文），则必须补「索引增量补出」+「已注销 URI 剔除」两条规则（见 R2-01/R2-02 建议），并接受"原文是不可分割的最小粒度、无法按类删除"这一约束；
   - (b) 回到 A 案（索引为真源、`ttl_content` 只存无法索引的残余），则 `unregister` 语义天然正确，但**必须另找空节点幂等方案**（不能靠 canonical 标签相等，否则 R2-03 换个位置复现）。
   我倾向 (a) + 两处补丁，改动面更小。
2. **【需拍板】IM-07 是否改成 `400 tenant_required`**：当前是"显式 WARN + NULL 分区共享"。**本任务的核心目标就是消灭跨租户共享，NULL 分区把该缺陷原样保留给所有无租户/API Key 用户**。修法一行（在 `_tenant_id_of` 抛 400），但属行为变更，需简报授权。
3. **【需拍板】`ttl_content` 语义变更的旧数据迁移**：报告称该表尚未上线故不做迁移脚本。若已有环境跑过旧版，`ttl_content` 里是"残余三元组"——不会报错，但导出会**缺类/标注**（索引里仍有，导出会补）。请确认"表未上线"这一前提，否则需要一次性重导入脚本。
4. **【需确认】`extensions.py` 已删除**：pgvector 的启动期初始化目前**无任何调用点**。若 P1（kb-pgvector 任务）依赖它，需从 git 暂存区恢复并补调用点。
5. **【需确认】`wiki_owl` 仍是 `enabled=false`**：启用该模块前需在**真实 app** 上再跑一次端到端（本次全部在测试专用 app 上验证）。
6. **【遗留·Minor】MI-07 字节长度**：`_validate_uri` 按**字符数**校验（`len(uri) > 1000`），中文 URI 1000 字符 ≈ 3000 字节，仍可能触发 PG btree 索引项 2704 字节上限。建议按 `len(uri.encode("utf-8"))` 校验，或把 `uri` 列宽收到 512。
7. **【观察·非 P4.1 缺陷】迁移链 003 在空库上失败**：`alembic upgrade head` 在全新库上跑到 `003_add_sys_dictionary_tenant_id` 时报 `relation "sys_user" does not exist`（001/002 不建表，项目依赖 `AUTO_CREATE_TABLES`）。我用 `alembic stamp 003` 后单独跑 `003→004` 验证通过。**这是既有问题**，但意味着 004 在"纯迁移驱动"的环境里上线前需先解决。
8. **【已知事项·非缺陷】** conftest 的 `DROP SCHEMA` 已带 `lock_timeout=5s` / `statement_timeout=30s`。本轮 6 次全量运行耗时 21.6s ~ 24.5s，未出现 `LockNotAvailable`；若偶发锁等待失败，是外部连接持锁所致。

---

## 6. 测试有效性评估

### 6.1 变异测试汇总（10 组，全部已还原）

| # | 变异 | 目标 | 结果 |
|---|---|---|---|
| M1 | 删 `wiki_owl.py` 的 `.where(WikiArticle.tenant_id == tenant_id)` | IM-02 | **RED** ✅（`test_articles_by_class_endpoint_is_tenant_scoped`） |
| M2 | `_reindex` 父类收集去掉 `isinstance(o, URIRef)` | CR-01① | **RED** ✅（`test_blank_node_is_not_persisted_as_parent_uri`） |
| M3 | `_canonicalize` 退化为恒等函数 | CR-01② | **RED** ✅（`test_repeated_import_of_blank_node_ttl_is_idempotent`） |
| M4 | `unregister()` 去掉 `_remove_class_reference_rows` | IM-04 | **RED** ✅（`test_unregister_clears_annotation_references`） |
| M5 | `JsonList` 改回 `JSON().with_variant(JSONB,"postgresql")` | IM-03 | **RED** ✅（2 条：`contains` 编译 + `@>` 实跑） |
| M6 | 路由 `auto_commit=False` → `True` | IM-05 回滚 | **仍绿** ❌ ⇒ `test_failed_import_leaves_no_partial_data` **假测试**（R2-06） |
| M7 | `_validate_uri` 直接 return | IM-05 长度校验 | **RED** ✅（`test_register_class_with_oversized_uri_returns_400`） |
| M8 | `OntologyRepository` 的 None 告警守卫改 `if False` | IM-07 | **RED** ✅（`test_tenant_id_none_is_logged_as_shared_partition`） |
| M9 | `set_ttl_content` → `append_ttl_content` | CR-01② | **RED** ✅（`test_repeated_import_of_blank_node_ttl_is_idempotent`） |
| M11 | `get_or_create_ontology` 去掉 `tenant_id` 过滤 | 租户隔离 | **RED** ✅（`test_api_ttl_is_tenant_scoped`） |

> M7 首次尝试时我误写了 `if False: ... elif ...`（`elif` 仍会执行，变异无效），已重做为 `return` 并复跑确认 —— 记录以免后续复现者踩同一坑。

### 6.2 真断言（变异下确实会红）

`test_articles_by_class_endpoint_is_tenant_scoped`、`test_articles_by_class_endpoint_filters_by_containment`（真实 PG `@>`）、`test_blank_node_is_not_persisted_as_parent_uri`、`test_repeated_import_of_blank_node_ttl_is_idempotent`、`test_ttl_roundtrip_preserves_blank_nodes`（`isomorphic` 同构，表达力强于逐三元组）、`test_unregister_clears_annotation_references`、`test_contains_operator_compiles_to_jsonb_containment`、`test_jsonb_containment_query_actually_runs`、`test_register_class_with_oversized_uri_returns_400`、`test_tenant_id_none_is_logged_as_shared_partition`、`test_api_ttl_is_tenant_scoped`、`test_tests_run_against_postgresql`（把"必须 PG"固化为断言，防止重演 IM-01）。

### 6.3 弱 / 假测试

- **`test_failed_import_leaves_no_partial_data`** —— 名义上验证"导入失败整体回滚"，实际只断言 `/classes`；M6 变异下仍绿。**没有守护 `ttl_content` 这条真正会被部分写入的路径**（R2-06）。
- **`test_failed_import_returns_400_not_500`** —— 只断言 `status_code == 400`，不断言"是 400 而不是 500 的**原因**"；在 `_validate_uri` 存在时其实走的是 `ValueError` 分支，**并未真正覆盖 `SQLAlchemyError` → 400** 这条路径（真正的覆盖是 M7 变异暴露出来的）。
- **`test_json_list_columns_are_real_jsonb`** —— M5 变异下仍绿（只查 DDL 类型，`with_variant` 在 DDL 上仍渲染 JSONB）。分工合理（编译/执行由另两条覆盖），但单独看它对 IM-03 的守护力有限。
- **`test_stats_contract`** —— 只断言 `total_triples >= class_count` 与 `class_count == 2`，未锁定具体口径；R2-02 那种"索引说 1 个类、导出说 6 条三元组"的矛盾它测不出来。

### 6.4 完全未被覆盖的行为（本轮新缺陷即出在这些缺口）

1. 「API 注册 → 导入 TTL → 导出」的混合路径（R2-01）。
2. 「TTL 导入 → unregister → 导出 / stats」（R2-02）。
3. 「两次导入各含结构相同空节点」是否保持独立（R2-03）。
4. 400 响应体内容是否泄漏内部信息（R2-04）。
5. `InMemoryOntologyStore` 的所有行为（除被 `WikiOwlEngine()` 无参回退间接触及）。

---

_复审人：第二轮代码复审者_
_复审日期：2026-09-10_
_验证手段：逐条精读 + 10 组变异测试（RED 后还原，`git diff --stat` 核对）+ 真实 PostgreSQL 17.11 一次性探针 + 空库实跑 004 迁移_
