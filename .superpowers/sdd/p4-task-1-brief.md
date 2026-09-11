# Task 1（P4.1 · 最高优先级）: 本体持久化与租户隔离

来源计划：`docs/superpowers/plans/2026-09-10-p4-ontology.md`
来源 Spec：`docs/superpowers/specs/2026-09-10-ontology-layer-design.md` §1、§5.1

## 背景：这是一个缺陷修复，不是加功能

当前实现：

```python
# backend/app/routers/wiki/wiki_owl.py
_owl_engine = None

def get_owl_engine():
    global _owl_engine
    if _owl_engine is None:
        from app.ai.knowledge.owl_engine import WikiOwlEngine
        _owl_engine = WikiOwlEngine()      # 进程级单例
    return _owl_engine
```

`WikiOwlEngine`（`backend/app/ai/knowledge/owl_engine.py`）内部是 `rdflib.Graph` **内存存储**
（模块 docstring 明确写「使用 rdflib.Graph 做内存本体存储」）。

因此当前存在两个缺陷：
1. **重启即丢失**
2. **跨租户共享数据**（全局单例，无 `tenant_id`）—— MinWorkBuddy 是多租户系统，这是数据串租户

## 目标

把本体从"进程内内存单例"改为**按租户持久化到数据库**，并保持 `/api/v1/wiki/owl/*` 现有端点的对外语义不变。

## 涉及文件

| 路径 | 动作 |
|---|---|
| `backend/app/models/ontology/ontology.py` | 新建：`ontology` / `ontology_class` / `ontology_annotation` |
| Alembic 迁移 | 新建：三张表 |
| `backend/app/routers/wiki/wiki_owl.py` | 修改：去掉全局单例，改为按租户构造 |
| `backend/app/ai/knowledge/owl_engine.py` | 修改：由内存态改为持久化后端 |
| `backend/tests/ontology/test_persistence.py` | 新建：测试 |

## 数据模型（全部继承 `TenantMixin`）

遵循 MinWorkBuddy 现有约定：
- `Base` 从 `app.db.database` 导入
- 租户表继承 `app.models.tenant_mixin.TenantMixin`（`tenant_id BigInteger nullable index`）
- 审计列 `creator_id / updater_id / created_at / updated_at`
- 状态用 `String(32)` + `comment` 或 `Integer` + `comment`，**不用 SAEnum**（PG ENUM 后期变更困难）
- `__table_args__` 具名索引，表名单数
- 中文注释

三张表：

```
ontology            code · name · description · namespace_uri · version(Integer)
                    · status(draft|published|archived) · ttl_content(Text)
                    · source(manual|ttl_import|build)
                    唯一约束 uq_ontology_code (tenant_id, code)

ontology_class      ontology_id(FK) · uri · label · comment · parent_uris(JSONB)
                    · status · display_order
                    唯一约束 uq_ontology_class (ontology_id, uri)

ontology_annotation ontology_id · target_type(article|segment|table|column)
                    · target_id(String —— 各类目标主键类型不一致，统一用字符串存)
                    · class_uris(JSONB)
```

## 需要实现的持久化语义

`WikiOwlEngine` 现有能力（来自 `owl_engine.py`）必须全部保留，只是换存储后端：

| 方法 | 语义 |
|---|---|
| `register_class(uri, label, comment, parent_uris)` | 写入 `ontology_class` |
| `unregister_class(uri)` | 删除 |
| `get_class(uri)` / `list_classes()` | 读 |
| `get_ancestors(uri)` / `get_descendants(uri)` / `get_hierarchy()` | 基于 `parent_uris` 递归，需防循环 |
| `import_ttl(ttl_content)` / `export_ttl()` | TTL 导入导出 |
| `stats()` | 统计 |

## 路由改造要求

`get_owl_engine()` 不再返回全局单例，改为按当前用户租户构造，例如：

```python
def get_owl_engine(tenant_id: int, db: Session) -> WikiOwlEngine:
    """按租户构造；不再使用全局单例。"""
    return WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))
```

所有 `/wiki/owl/*` 端点需注入 `tenant_id`（从 `current_user` 取）。

## 必须通过的测试

1. **先写一条暴露缺陷的测试**（改造前运行应失败）：
   租户 A 注册一个 OWL 类后，租户 B 列表应为空
2. 重启/新建引擎实例后，数据仍在（持久化）
3. TTL 导入 → 导出 往返一致
4. 层级查询：`get_ancestors` / `get_descendants` / `get_hierarchy` 正确，且**存在循环父类时不死循环**
5. **全量回归 `/api/v1/wiki/owl/*` 所有端点**（改造是行为变更）

## 验收标准

| 项 | 标准 |
|---|---|
| 持久化 | 重启不丢 |
| 租户隔离 | 租户 A 看不到租户 B 的本体 |
| 回归 | `/api/v1/wiki/owl/*` 全部端点行为与改造前一致 |
| 循环保护 | 循环父类不死循环 |
| TTL | 导入导出往返一致 |

## 边界（本 Task 不做）

- 不做完整 SHACL 校验
- 不做推理机
- 不做 PROV-O 溯源
- 不做回滚
- 不引入新依赖（`rdflib` 已在用）

## 变更授权（用户拍板 2026-09-10）

以下变更**超出原约束 3「端点对外行为不变」**，经用户确认予以授权，原约束在这些项上豁免：

1. **IM-07**：`tenant_id` 为空的请求**不再落到 NULL 分区共享**，改为返回 `400 tenant_required`。
2. **R2-01 / R2-02**：采用**「单一真相源」重构** —— `ttl_content` 为唯一真相源，
   类/标注索引降级为**纯派生**（可随时从原文 `_reindex()` 重建）；
   允许重写 `WikiOwlEngine` 的写路径，即使 `export_ttl()` 输出字节与改造前不同，
   **只要语义等价即可**。
3. **R2-03**：允许把空节点去重策略由 `to_canonical_graph` 集合并集，
   改为**同构感知差集**（`rdflib.compare.graph_diff` 或逐连通分量 `isomorphic`）。

依据：`.superpowers/sdd/p4-task-1-review-r2.md`（第二轮复审）。
