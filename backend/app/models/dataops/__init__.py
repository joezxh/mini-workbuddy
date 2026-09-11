"""DataOps ORM 模型（P2）。

全部继承 ``TenantMixin``（租户行级隔离），表名单数，状态用 ``String(32)`` +
comment（不用 SAEnum），审计列 ``creator_id/updater_id/created_at/updated_at``。
"""
