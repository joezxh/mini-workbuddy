# P1 执行简报：知识库内核（AgentScope RAG Service + PGVector）

来源计划：`docs/superpowers/plans/2026-09-10-p1-kb-pgvector.md`
依赖：无（地基）。被依赖：P4 Task 7（本体驱动检索）、P2、P3
上游风险（计划已标记）：`app.mount("/agentscope", ...)` 后子应用 lifespan 是否执行

## 环境已核验（2026-09-11）
| 依赖 | 状态 |
|---|---|
| `pgvector` 0.5.0（Python 包） | ✅ |
| `agentscope` 2.0.7.post1（锁定版本，未升级） | ✅ |
| `redis` 5.0.1 + Redis 服务 `localhost:6379` PONG | ✅ |
| GPUStack Embedding（Qwen3-Embedding-4B, 768 维）已配置 | ✅ |
| 测试库 `minworkbuddy_test` 已装 pgvector 0.8.6 + pg_trgm 可用性待迁移启用 | ✅ |

## 范围决策（解锁 Task 7 的最小切片）

P1 计划 11 个任务。与「解锁 Task 7（本体驱动检索）」直接相关的是：
**Task 1（建表/迁移/ORM）+ Task 2~4（PGVectorStore 核心：collection/insert/delete/search）
+ Task 5（中文混合检索）+ Task 6（租户隔离）+ Task 7（embedding 配置）+ Task 9（kb_ref）**，
外加一个**前向字段**：`kb_segment.class_uris`（JSONB）—— P4 Task 7 用它按本体类过滤检索，
P1 计划未含，本简报在 Task 1 迁移里一并加入，避免二次迁移。

**最高风险 = Task 8（mount 子应用）**：计划明确「先单独验证 mount 后 lifespan 是否执行；
若不执行改独立服务（Task 8b）」。**本简报在 Task 8 设硬检查点**——完成 Task 1~7、9 后，
先跑最小 mount 验证脚本，确认 lifespan 执行再继续；不带着未验证的风险往前做。

## 与计划的偏差（提前声明）
1. `kb_segment` 增加 `class_uris JSONB`（前向兼容 Task 7），在 Task 1 迁移一并建。
2. 向量维度用 `Vector(768)`（当前 GPUStack 默认）；多维度并存按计划交给 `kb_collection.dimensions` 运行时真值，不写死（维度混用验收项）。
3. 不引入计划外的第三方库（pgvector / agentscope / redis 已在环境内）。
4. **不执行任何 git 写操作**——改动留工作区，每任务结束报告，由用户 commit。
5. 复审沿用 P4 纪律：`gsd-code-reviewer` 派发（不派会强制 commit 的 fixer/executor）。

## 验收（逐 Task 对齐计划「验收标准」）
| 项 | 标准 |
|---|---|
| 契约 | `PGVectorStore` 满足 `VectorStoreBase` 方法语义（create/delete/has/insert/delete-doc/list/search） |
| 中文检索 | 混合检索召回 ≥ 纯向量（pg_trgm + RRF） |
| 幂等 | 重复入库 `kb_segment` 不增行（on_conflict_do_update） |
| 租户隔离 | 租户 A 伪造 collection 名也读不到 B；无 tenant_id 抛异常不放行 |
| 维度混用 | 768 与 1024 两 KB 并存互不影响 |
| mount | `/agentscope/knowledge_bases/*` 可达且 storage 已初始化（Task 8 检查点验证） |

## 任务清单（本简报驱动）
- [x] Task 1：pg_trgm 扩展 + kb 三表迁移（含 class_uris）+ ORM + KB_BLOB_DIR + init_models 注册
- [x] Task 2：PGVectorStore 骨架 + collection 管理（+ 测试，7 项全过）
- [x] Task 3：insert/delete（文档级）/ list_documents + 幂等 + **embedding 接入（KbIngestService，向量生成经 embed_fn 注入，含维度校验，4 项测试）**
- [x] Task 4：向量检索 + HNSW（`PGVectorStore.search` 余弦距离 + HNSW 索引；`KbRetrievalService.search_by_text` 文本检索，5 项测试）
- [x] Task 5：中文混合检索（`PGVectorStore.hybrid_search`：向量召回 + 中文子串关键词召回（trigram-GIN 加速的 LIKE，因本环境 `pg_trgm.similarity()` 对 CJK 恒返回 0）+ RRF 融合；`KbRetrievalService.hybrid_search_by_text` 文本入口；迁移 006 已建 `ix_kb_segment_content_trgm` GIN 索引与 pg_trgm 扩展；4 项测试含召回 ≥ 纯向量）
- [x] Task 6：租户隔离（`app.services.kb.user_id_mapper.UserIdMapper` 把 tenant_id 确定性映射为 as_user_id 命名空间；接入 `KbRefService`；PGVectorStore/KbRefService 构造缺 tenant_id 即拒；4 项测试）
- [x] Task 7：Embedding 配置映射（`app.services.kb.embedding_config`：gpustack/nvidia→OpenAI 兼容协议、dashscope→原生协议，api_key 脱敏；**补齐 config.py 缺失的 NVIDIA_* 字段**——.env 实际用 `EMBEDDING_PROVIDER=nvidia` 但原先未定义、静默回退 GPUStack；`embedding_client` 补 nvidia 分支；`kb_app` 新增 `GET /embedding_models`；5 项测试）
- [x] Task 8：【检查点】`/agentscope/knowledge_bases` 挂载 + lifespan 验证（Starlette 不自动触发子应用 lifespan，KB 初始化改由主应用 lifespan 兜底 `app.state.kb_ready`；3 项检查点测试）
- [x] Task 9：kb_ref 服务 + 端点（`KbRefService` + `kb_router`：POST/GET/GET{id}/DELETE `/kb`，强制 `X-Tenant-Id` 隔离，挂载进 `kb_app`；服务层 5 项 + 端点层 5 项测试）
- [x] Task 10：QaChunker（`app.services.kb.qa_chunker.QaChunker` 实现 agentscope `ChunkerBase` 契约：表/列描述→问答对、Q/A 透传、未识别行兜底、DataBlock 透传；注册进 `kb_app` 的 `CHUNKER_REGISTRY` 并暴露 `GET /chunkers`；6 项测试）
- [x] Task 11：端到端 + 性能基线（`backend/scripts/kb_perf_baseline.py`：e2e 建 KB→入库→向量/混合检索命中→计数回写全链路 OK；性能基线实测 **10 万切片 768 维：纯向量 P50/P95=54.5/63.6ms，混合 P50/P95=60.4/63.0ms**，已写入 spec §3.5；脚本支持 `--segments 100000` 复测）
