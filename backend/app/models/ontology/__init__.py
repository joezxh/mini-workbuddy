"""本体治理 ORM 模型（本体注册/版本/构建/候选/能力问题/证据/语义/发布登记 + 资产标签）。

全部继承 ``TenantMixin``（租户行级隔离），表名 ``onto_*`` 单数，状态用 ``String`` + comment。
设计真源：docs/superpowers/specs/2026-10-31-ontology-capability-design.md §3.2。
"""
