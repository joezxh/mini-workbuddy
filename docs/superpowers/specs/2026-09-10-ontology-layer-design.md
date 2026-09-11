# P4 · 本体层设计（分层混合路线）

> 状态：待评审
> 日期：2026-09-10
> 路线：**路线 3 · 分层混合** —— 自研本体建模与治理（借鉴 ontomind），图谱构建 / 推理 / 溯源能力延后，按需引入天枢本体
> 前端（管理台）设计：见 `2026-09-10-knowledge-governance-frontend-design.md` §10（菜单项：知识治理 → 本体）
> 依赖：P1（本体驱动检索需 P1 的 `kb_segment`）、P2（本体构建的原料来源）
> 设计原则：充分利用 AgentScope 2.x 原生能力

---

## 1. 现状：一个必须先修的缺陷

```python
# backend/app/routers/wiki/wiki_owl.py
_owl_engine = None

def get_owl_engine():
    global _owl_engine
    if _owl_engine is None:
        _owl_engine = WikiOwlEngine()      # 进程级单例
    return _owl_engine
```

`WikiOwlEngine`（`app/ai/knowledge/owl_engine.py`）内部是 `rdflib.Graph` **内存存储**（docstring 明确写"使用 rdflib.Graph 做内存本体存储"）。因此当前本体：

- **重启即丢失**
- **跨租户共享**（全局单例，无 `tenant_id`）—— 多租户下会串数据
- 只有类层级与文章标注，无 SHACL 校验、无版本、无评审

**P4.1 阶段必须先把这个修掉**，它不只是能力缺失，是缺陷。

---

## 2. 路线选择说明

| | 路线 1 天枢 sidecar | 路线 2 完全自研 | **路线 3 分层混合（选定）** |
|---|---|---|---|
| 本体治理流程（CQ/评审/版本） | 需自建（天枢无） | 需自建 | 需自建（借鉴 ontomind） |
| 图谱构建 / 推理 / 溯源 | 天枢全套 | 需自建，工作量极大 | **延后**，按需引入天枢 |
| 新增中间件 | sidecar 服务 | 无 | 无（除非后续引入） |
| 首期工作量 | 中 | 大 | **可控** |

**选择理由**：
1. 目标是"企业本体**构建与管理**"，核心是**治理流程**（能力问题 CQ 驱动、评审、版本、映射）——这恰是 ontomind 有、天枢没有的，自研更贴合
2. 图谱构建 / 推理 / 溯源是另一个量级的工程，不该在首期拖累本体落地
3. 天枢是**本组织自有产品**（`gitlab.hztianque.com/tianQAI/tianque-ontology`），随时可后补；先自研本体层不会做无用功
4. 能立刻修掉 §1 的缺陷

---

### 2.1 与「天枢优先」路线的对比论证（v2 新增）

Qoder 方案建议"天枢优先整合"（评分 5/5）。本节明确说明为何本 spec 不采用，供评审对照。

| 维度 | 天枢能提供 | 天枢**不能**提供 | 本阶段是否需要 |
|---|---|---|---|
| 实体/关系抽取、冲突检测、去重 | ✅ | | 需要，但可延后 |
| 图分析、KG 构建 | ✅ | | 需要，但可延后 |
| 推理（Rete/Datalog/SPARQL） | ✅ | | **延后到 P4.4** |
| PROV-O 溯源、决策审计 | ✅ | | **延后到 P4.4** |
| **CQ（能力问题）驱动建模** | ❌ | 无此概念 | **本阶段核心** |
| **评审工作流**（suggested→accepted/rejected） | ❌ | | **本阶段核心** |
| **版本快照与变更审计** | ❌ | | **本阶段核心** |
| **对象类型 ↔ 物理表/列映射** | ❌ | 天枢面向文档抽取，不做数仓映射 | **本阶段核心**（依赖 P2） |
| **多租户隔离** | ❌ | 非租户感知，需自建 | **本阶段核心**（且是现存缺陷） |

**结论**：天枢补的是「图谱与推理」，本阶段要的是「治理流程」，两者交集很小。
先引入天枢会：① 新增 sidecar 中间件与运维成本 ② 仍需自建全部治理流程 ③ 其非租户感知特性还要额外包一层隔离。

**后续引入路径不变**：P4.4 阶段通过 AgentScope 原生的 `mcp` 模块挂载天枢 MCP Server 即可（AgentScope 侧零改动）。为降低届时的映射成本，**本阶段数据结构应贴近 W3C 标准语义**（OWL/RDFS），已在 §5 体现。

### 2.2 领域片段模板（可选能力）

参考 ontomind `ontology_fragments.py`：预定义领域本体骨架（ontomind 为消费金融的 14 个对象类型 + 11 个关系类型），作为新建本体的起点，新数据对齐到模板。

- **机制可复用，内容需自定义** —— MWB 领域为风险管控 / 政务，不能照搬消金骨架
- 作为**可选**能力，不阻塞 P4.1–P4.3 主流程
- 与 §5.3 的"标准项种子"是两回事：前者是**本体结构骨架**，后者是**字段级标准项**

---

## 3. 借鉴 ontomind 的本体治理模型

ontomind 的 `ontology_build_service.py`（1100+ 行）与 `backend/app/db/models/ontology_model.py` 提供了一套完整的企业本体建模方法：

```
ontologies                本体
ontology_object_types     对象类型（类）
ontology_properties       属性
ontology_link_types       关系类型
ontology_mappings         到物理表/列的映射
ontology_cqs              能力问题（Competency Question）
ontology_versions         版本
ontology_metrics          质量指标
```

构建作业状态机（`_run_build`）：
```
_extract_via_rules  ┐
                    ├→ _align_delta → rule_judge / _llm_judge_optional → _merge_delta
_extract_via_llm    ┘
```

**借鉴点**：CQ 驱动、双通道抽取（规则 + LLM）、`delta → 对齐 → 判定 → 合并` 的状态机、版本与评审。

**不借鉴点**：本阶段**不实现 LLM 抽取通道**（参照 P2 spec 的一致决定），只保留 `rule` 与 `human` 来源，LLM 通道留待后续。

---

## 4. 分阶段交付

| 阶段 | 交付 | 依赖 |
|---|---|---|
| **P4.1** 持久化与租户隔离 | 替掉内存单例；本体落库 + `tenant_id` 隔离；TTL 导入导出保留 | 无（**可立即开工，优先级最高**） |
| **P4.2** 本体建模与治理 | 六张表 + CQ 驱动 + 评审 + 版本 + 映射 | P4.1 |
| **P4.3** 本体驱动检索 | OWL 类标注 `kb_segment`，按类过滤检索 | P4.1 + P1 |
| **P4.4**（后续）图谱与推理 | 实体级 KG、SHACL 完整校验、推理、溯源 | 评估引入天枢 |

---

## 5. 数据模型

全部继承 `TenantMixin`，遵循现有约定（表名单数、审计列、具名索引）。

### 5.1 P4.1 —— 本体持久化

| 表 | 字段 |
|---|---|
| `ontology` | `code(unique per tenant) · name · description · namespace_uri · version(Integer) · status(draft/published/archived) · ttl_content(Text) · source(String: manual|ttl_import|build)` |
| `ontology_class` | `ontology_id(FK) · uri · label · comment · parent_uris(JSONB) · status · display_order` |
| `ontology_annotation` | `ontology_id · target_type(article\|segment\|table\|column) · target_id(String，因各类目标主键类型不一致，统一用字符串存) · class_uris(JSONB)` |

唯一约束：`uq_ontology_code (tenant_id, code)`、`uq_ontology_class (ontology_id, uri)`

> `ontology_annotation` 取代现有"文章 OWL 类标注"的内存关联，并扩展到 `kb_segment`（P4.3 需要）。

### 5.2 P4.2 —— 建模与治理

| 表 | 字段 |
|---|---|
| `ontology_object_type` | `ontology_id · code · name · description · parent_id · status(suggested/accepted/rejected) · source(rule/human) · confidence · evidence_json` |
| `ontology_property` | `object_type_id · code · name · data_type · required · semantic_type · status · source · confidence` |
| `ontology_link_type` | `ontology_id · code · name · source_type_id · target_type_id · cardinality · status · source · confidence · evidence_json` |
| `ontology_mapping` | `ontology_id · object_type_id · target_type(table|column) · source_id · database · table_name · column_name · status · source · confidence` |
| `ontology_cq` | `ontology_id · question · answer_hint · status · linked_object_types(JSONB)` |
| `ontology_version` | `ontology_id · version · snapshot_json(JSONB) · change_note · author_user_id` |

> `source` 的 `llm` 取值**本阶段保留但不实现**（与 P2 spec 保持一致）。

### 5.3 与 P2 的接口

P2 的元数据产出直接作为本体构建的候选来源：

| P2 产出 | → | 本体元素 |
|---|---|---|
| `meta_table` | → | `ontology_object_type` 候选 |
| `meta_column` | → | `ontology_property` 候选 |
| `overlap_ratio` 高的列对 | → | `ontology_link_type` 候选 |
| `meta_column_standard`（字段↔标准绑定） | → | `ontology_mapping` + `semantic_type` |

---

## 6. 与 AgentScope 的集成

| 阶段 | 集成方式 |
|---|---|
| P4.1 | `rdflib` 图作为纯数据，不涉 AgentScope |
| P4.2 | 注册 Tool：`ontology_query`（查类层级/属性/关系）、`ontology_answer_cq`（用 CQ 校验本体覆盖度）、`ontology_suggest`（基于 P2 元数据给出对象类型/属性建议） |
| P4.3 | 检索 Tool 增加 `class_uris` 过滤参数，实现"按本体类限定检索范围" |
| P4.4 | 评估：天枢的 MCP Server 可直接挂到 AgentScope 的 `mcp` 模块，无需改 AgentScope 侧代码 |

---

## 7. OWL / SHACL 的范围界定（避免过度设计）

| 能力 | 本阶段 |
|---|---|
| TTL 导入 / 导出 | ✅ 保留（现有 `import_ttl` / `export_ttl` 迁移到持久化存储） |
| 类层级、祖先/后代查询 | ✅ 保留 |
| OWL 一致性基础校验 | ✅ 用 `rdflib` 做基础检查（悬空父类、循环继承、URI 冲突） |
| **完整 SHACL 校验** | ❌ 本阶段不做（需 `pyshacl` 依赖与形状语言支持） |
| **推理机（Rete/Datalog/SPARQL 推理）** | ❌ 明确延后到 P4.4 |
| **W3C PROV-O 溯源** | ❌ 明确延后到 P4.4 |

**边界要说清楚**：本阶段交付的是"可建、可评、可版本化、可持久化、租户隔离的企业本体"，**不是**推理引擎。避免实施时范围膨胀。

---

## 8. 测试

- **P4.1**：持久化后重启不丢；租户 A 看不到租户 B 的本体；TTL 导入导出往返一致
- **P4.2**：CQ 覆盖度统计正确；评审状态流转（suggested → accepted/rejected）；版本快照可回滚
- **P4.2 与 P2 联动**：`meta_table` → 对象类型候选 → 人工接受 → 落 `ontology_object_type` 全链路
- **P4.3**：按 `class_uris` 过滤检索，结果不越界

---

## 9. 影响面

| 项 | 说明 |
|---|---|
| **修改** | `routers/wiki/wiki_owl.py` 从全局单例改为按租户读库；`owl_engine.py` 由内存态改为持久化后端 |
| 新增表 | P4.1 三张 + P4.2 六张，同步 `docs/sql/init.sql` + `app/db/init_models.py` |
| 新增依赖 | P4.1–P4.3 **无**（`rdflib` 已在用） |
| 兼容性 | 现有 `/api/v1/wiki/owl/*` 路由语义保持不变，仅底层存储改为持久化 |

---

## 10. 风险

1. **`WikiOwlEngine` 改造是行为变更** —— 现有调用方若依赖"进程内共享"语义会受影响；需回归所有 OWL 相关接口
2. **TTL 往返可能不保真** —— rdflib 序列化可能丢失部分构造（如空白节点顺序）；需往返测试
3. **P4.2 工作量易膨胀** —— 六张表 + 状态机 + 评审流程，建议再拆为"建模 CRUD"与"构建作业状态机"两个子任务
4. **P4.4 引入天枢时的适配成本** —— 本体已自研，届时需要在"自研本体"与"天枢本体"之间做映射或取舍；本阶段数据结构应尽量贴近 W3C 标准（OWL/RDFS 语义）以降低未来映射成本
