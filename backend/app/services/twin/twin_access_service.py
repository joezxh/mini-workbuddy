"""权限申请闭环（spec §4.5 / §6.1 T12 / §10 Q1-A）。对应 P0-8，验收 W13。

三件事，不多做：
1. 申请单的生死（pending → approved / rejected / expired）；
2. 批准的产物 = 写 `twin_card_share`，**不发一次性令牌**（§3.7）；
3. 可见性与租户闸**一律交给 Task 6 的 `TwinService`**，本层绝不复制第二套 access 算法
   ——两处判据并存必然漂移，而漂移的方向通常是「新写的那份更松」。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, TWIN_ACCESS_ALREADY_GRANTED, TWIN_ACCESS_REQUIRED,
    TWIN_REQUEST_DUPLICATE, TWIN_REQUEST_NOT_FOUND, TWIN_REQUEST_NOT_PENDING,
)
from app.models.twin import TwinAccessRequest, TwinCard, TwinCardShare, TwinPublish
from app.services.twin.twin_publish_service import ACCESS_ROLE
from app.services.twin.twin_service import (
    ACCESS_EDIT, ACCESS_OWNER, ACCESS_READ, TwinService,
)

# 与 Task 1 的 CHECK 约束 `ck_twin_access_status` 逐字一致（四态，§3.8 状态机）
STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_EXPIRED = (
    "pending", "approved", "rejected", "expired")

# W13 要求「含过期时间」，所以缺省**不能是永久**。`twin_*` 的 TIMESTAMP 列不带时区，
# 因此本层全程用应用时钟（仓库同律：`services/sys/sys_notification_service.py:36`），
# 不去混 DB 的 now()：两套时钟写同一列，比较大小会变成运气。**不照抄**
# `services/dataops/write_request_service.py:156` 的 `obj.expires_at < func.now()`，
# 那是把 Python datetime 属性与 SQL 构造子比较，是个隐形错。
DEFAULT_GRANT_DAYS = 30
MAX_GRANT_DAYS = 365
GRANTED_PERM = "read"          # 批准申请单的产物永远是只读：edit 只能 owner 手工授


class TwinAccessService:
    """申请/审批。审批权只认卡片 `owner`（§10 Q1-A）。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 role_codes: Sequence[str] = ()) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")     # 与 query_service.py:34 同一惯例
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        # 传 role_codes 是为了让「靠角色授予已能读」的人也拿到 400，而不是发一张注定自动批准的单子
        self.role_codes = tuple(sorted({r for r in role_codes if r}))

    def _orchestrator(self) -> TwinService:
        return TwinService(self.db, self.tenant_id, self.user_id, self.role_codes)

    # ---------------------------------------------------------------- 内部查询

    def _pending_of(self, card_id: int) -> Optional[TwinAccessRequest]:
        return self.db.execute(
            select(TwinAccessRequest).where(
                TwinAccessRequest.tenant_id == self.tenant_id,
                TwinAccessRequest.card_id == card_id,
                TwinAccessRequest.applicant_id == self.user_id,
                TwinAccessRequest.status == STATUS_PENDING)
        ).scalars().first()

    def _required_role_code_of(self, card_id: int) -> Optional[str]:
        """所需角色 = 该卡已启用、`access=role` 的发布行里的**首个**角色码（无则 NULL）。

        为什么不用另建一列：发布闸已经回答了「哪些角色能看」（spec §3.5），
        工作台与只读页的口径必须同源，否则会出现「能申请的角色」与「能看页的角色」两套答案。
        写入的是**申请时刻的快照**，事后改发布配置不回写历史单据（审计语义）。
        """
        rows = self.db.execute(
            select(TwinPublish.role_codes_json).where(
                TwinPublish.tenant_id == self.tenant_id,
                TwinPublish.card_id == card_id,
                TwinPublish.status == "enabled",
                TwinPublish.access == ACCESS_ROLE)
        ).all()
        for (codes,) in rows:
            for code in (codes or []):
                text_code = str(code).strip()
                if text_code:
                    return text_code[:64]        # 列宽 String(64)，截而不炸
        return None

    def _request_or_404(self, request_id: int) -> TwinAccessRequest:
        row = self.db.get(TwinAccessRequest, request_id)
        if row is None or int(row.tenant_id) != self.tenant_id:
            # 跨租户与不存在同一信号：不得用 403 泄露“这张单子存在”
            raise ApiError(TWIN_REQUEST_NOT_FOUND, "申请单不存在", 404)
        return row

    # ---------------------------------------------------------------- 申请

    def request_access(self, card_id: int, reason: Optional[str] = None) -> dict:
        """提交申请。**已可读就不得申请**，否则抽屉会被注定自动批准的单子淹没。"""
        card = self._orchestrator().get_card(card_id)   # 不可见/跨租 → 已在里层抛 404
        if card["access"] in (ACCESS_OWNER, ACCESS_EDIT, ACCESS_READ):
            raise ApiError(TWIN_ACCESS_ALREADY_GRANTED, "你已具备该卡片的访问权限，无需申请",
                           400, {"card_id": card_id, "access": card["access"]})
        pending = self._pending_of(card_id)
        if pending is not None:
            # 把已在途单号回给前端，它才能直接“查看进度”，而不是只会提示“你提过了”
            raise ApiError(TWIN_REQUEST_DUPLICATE, "已有在途申请，请等待卡片创建者处理", 409,
                           {"pending_id": int(pending.id),
                            "created_at": pending.created_at.isoformat() if pending.created_at else None})
        row = TwinAccessRequest(
            tenant_id=self.tenant_id, card_id=int(card_id), applicant_id=self.user_id,
            reason=(reason or "").strip()[:500] or None,
            required_role_code=self._required_role_code_of(int(card_id)),
            status=STATUS_PENDING)
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            # 并发双提：部分唯一索引 `uq_twin_access_pending` 兜住（Task 1 已建），
            # 这里把它降级成与预查同样的 409，而不是把数据库错抬给用户。
            self.db.rollback()
            pending = self._pending_of(card_id)
            raise ApiError(TWIN_REQUEST_DUPLICATE, "已有在途申请，请等待卡片创建者处理", 409,
                           {"pending_id": int(pending.id) if pending is not None else None}) from None
        self.db.refresh(row)
        return self._row_dict(row, card["name"])

    # ---------------------------------------------------------------- 审批

    def _owner_card_of(self, row: TwinAccessRequest) -> TwinCard:
        """§10 Q1-A：只有卡片 owner 能处理。非 owner 403，卡已不在则与不存在同信号。"""
        card = self.db.get(TwinCard, int(row.card_id))
        if card is None or int(card.tenant_id) != self.tenant_id:
            # CASCADE 会连单子一起删，走到这里只可能是脏数据；不另开一个码
            raise ApiError(TWIN_REQUEST_NOT_FOUND, "申请单不存在", 404)
        if int(card.owner_id) != self.user_id:
            raise ApiError(TWIN_ACCESS_REQUIRED, "仅卡片创建者可处理权限申请", 403,
                           {"request_id": int(row.id), "card_id": int(card.id)})
        return card

    def _pending_row(self, request_id: int) -> "tuple[TwinAccessRequest, TwinCard]":
        """approve / reject 共用的前置闸：存在 → 是我卡 → 还在途。三闸一序不得重排。"""
        self._lazy_expire()
        row = self._request_or_404(request_id)
        card = self._owner_card_of(row)
        if row.status != STATUS_PENDING:
            raise ApiError(TWIN_REQUEST_NOT_PENDING, "申请单已处理，不能重复审批", 400,
                           {"request_id": int(row.id), "status": row.status})
        return row, card

    def _upsert_share(self, card_id: int, applicant_id: int, expires_at: datetime,
                      *, granted_by: int) -> TwinCardShare:
        """同一 (card, user) 只留一行授予：有就续期，没有才插。

        为什么是 upsert 而不是靠唯一键：spec §3.6 写的 `uq_twin_share` 在 Task 1 落库时是
        **普通索引** `idx_twin_share_card`（`grantee_id` / `grantee_code` 二选一，要硬约束
        得拆两条部分唯一索引），所以重复授予由这里兜住。
        **已知限制**：并发双批仍可能插出两行（两个事务都读到“无行”）。影响面说白：
        `_my_shares()` 取 edit 覆盖 read，行为无害，只是脏史。要硬保证时补两条部分唯一索引
        （`WHERE grantee_type='user'` / `='role'`），并把这里的插行改成 ON CONFLICT DO UPDATE。
        Plan 2 一旦开放「手工共享」就必须同时改两处，否则第二插入点会各写各的。
        """
        row = self.db.execute(
            select(TwinCardShare).where(
                TwinCardShare.tenant_id == self.tenant_id,
                TwinCardShare.card_id == card_id,
                TwinCardShare.grantee_type == "user",
                TwinCardShare.grantee_id == applicant_id)
        ).scalars().first()
        if row is None:
            row = TwinCardShare(tenant_id=self.tenant_id, card_id=card_id,
                                grantee_type="user", grantee_id=applicant_id,
                                perm=GRANTED_PERM, source="request",
                                expires_at=expires_at, granted_by=granted_by)
            self.db.add(row)
        else:
            # 回落成 read 是刻意的：让过期 edit 因为一张「申请只读」的单子被静默复活，
            # 等于权限上探。要恢复 edit 只能是 owner 在共享管理里显式动作（Plan 2）。
            row.perm = GRANTED_PERM
            row.source = "request"
            row.expires_at = expires_at
            row.granted_by = granted_by
        return row

    def approve(self, request_id: int, expires_in_days: Optional[int] = None) -> dict:
        days = max(1, min(int(expires_in_days or DEFAULT_GRANT_DAYS), MAX_GRANT_DAYS))
        row, card = self._pending_row(request_id)
        expires_at = datetime.now() + timedelta(days=days)
        # 顺序是故意如此：先改单子、再写授予、**只在最后 commit 一次**。
        # 「单子已 approved 但 share 没写」等于用户看到成功却仍看不了，两者必须同事务
        # （`test_approve_writes_share_and_request_in_one_transaction` 钉住这一条）。
        row.status = STATUS_APPROVED
        row.approver_id = self.user_id
        # 与 Task 8 的 `published_at = func.now()` **不同律**，也不是写错了：
        # reviewed_at 与 expires_at 要互相比较（过期判定、前端算天数），必须共用一个时钟；
        # 一半交给 DB、一半交给应用就会变成比较运气。
        row.reviewed_at = datetime.now()
        row.expires_at = expires_at
        self._upsert_share(int(card.id), int(row.applicant_id), expires_at,
                           granted_by=self.user_id)
        self.db.commit()
        self.db.refresh(row)
        return self._row_dict(row, card.name)

    def reject(self, request_id: int) -> dict:
        row, card = self._pending_row(request_id)
        row.status = STATUS_REJECTED
        row.approver_id = self.user_id
        row.reviewed_at = datetime.now()
        row.expires_at = None          # 驳回不带任何有效期
        self.db.commit()
        self.db.refresh(row)
        return self._row_dict(row, card.name)

    # ------------------------------------------------------------ 列表 / 懒过期

    def _lazy_expire(self) -> int:
        """把已过期却还挂着 approved 的单子翻成 expired（P0 不引定时任务，读时顺带清）。

        只动申请单，**不动 `twin_card_share`**：可见性已由 `_my_shares()` 的
        `expires_at > now()` 闸住（Task 6），share 行留着就是授权史。
        """
        now = datetime.now()
        rows = self.db.execute(
            select(TwinAccessRequest).where(
                TwinAccessRequest.tenant_id == self.tenant_id,
                TwinAccessRequest.status == STATUS_APPROVED,
                TwinAccessRequest.expires_at.is_not(None),
                TwinAccessRequest.expires_at <= now)
        ).scalars().all()
        for r in rows:
            r.status = STATUS_EXPIRED
        if rows:
            self.db.commit()
        return len(rows)

    def list_requests(self) -> Dict[str, Any]:
        """一次给两组：owner 视角的待办 + 我发出的申请。

        **不 join `sys_user`**（自决项 5）：测试库的建表清单 `_tables()` 未 import `sys_user`
        （`tests/ontology/conftest.py:59-69`），姓名由 Plan 2 用现成的
        `GET /api/v1/admin/users`（`routers/sys/__init__.py:114`）在前端补。
        """
        self._lazy_expire()
        rows = self.db.execute(
            select(TwinAccessRequest, TwinCard.name)
            .join(TwinCard, TwinCard.id == TwinAccessRequest.card_id)
            .where(TwinAccessRequest.tenant_id == self.tenant_id,
                   or_(TwinCard.owner_id == self.user_id,
                       TwinAccessRequest.applicant_id == self.user_id))
            .order_by(TwinAccessRequest.created_at.desc(), TwinAccessRequest.id.desc())
        ).all()
        incoming: List[dict] = []
        outgoing: List[dict] = []
        for r, card_name in rows:
            d = self._row_dict(r, card_name)
            # 分派口径写死：先看“是不是我发的”。owner == applicant 在 P0 不可达
            # （owner 申请自己的卡在 request_access 就被 400 挡了），所以两组不会重叠。
            (outgoing if int(r.applicant_id) == self.user_id else incoming).append(d)
        return {"incoming": incoming, "outgoing": outgoing,
                "incoming_pending": sum(1 for d in incoming if d["status"] == STATUS_PENDING)}

    @staticmethod
    def _row_dict(r: TwinAccessRequest, card_name: Optional[str] = None) -> dict:
        return {
            "id": int(r.id), "card_id": int(r.card_id), "card_name": card_name,
            "applicant_id": int(r.applicant_id),
            "approver_id": int(r.approver_id) if r.approver_id is not None else None,
            "status": r.status, "reason": r.reason,
            "required_role_code": r.required_role_code,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        }
