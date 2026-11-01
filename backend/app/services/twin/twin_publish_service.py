"""发布登记与只读运行（spec §4.4 / §3.5 / P0-7 / W12）。

一句话职责：**把页面配置冻成一行快照**，并按随机 `slug` 对访客放行或拒止。
本层不取数（全部交 Task 7）、不做列脱敏（交出口层）、不生成 SQL（交语义层）。

三条不可妥协的边界（与测试一一对应）：

1. **slug 一律随机**（`secrets.token_urlsafe(18)` = 24 字符）：自增 id 派生等于把
   未发布的孪生页变成可枚举资源。→ `test_new_slug_is_random_and_unpredictable`
2. **访问失败一律同一信号**（403 + 同一 message）：未知 slug / 跨租户 / 已停用 /
   角色不命中共用 `TWIN_ACCESS_REQUIRED`，差异只写进审计的 `reason`，**绝不上响应体**。
   → `test_every_denial_shares_one_code_and_message`
3. **快照只冻结构、不冻数据**：元数据与参数实值回快照，行数据每次直连现查（上游 D2）。
   → `test_metadata_and_params_come_from_snapshot` / `test_run_returns_current_query_output`
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import (
    ApiError, TWIN_ACCESS_REQUIRED, TWIN_NOT_PUBLISHED, TWIN_PUBLISH_FORBIDDEN,
)
from app.models.ontology.query import MetaOntologyQuery
from app.models.sys.sys_user import SysAuditLog
from app.models.twin import TwinCard, TwinPage, TwinPublish, TwinWidget
from app.services.twin.twin_data_service import TwinDataService, WidgetSpec
from app.services.twin.twin_service import WRITABLE_ACCESS, TwinService

logger = logging.getLogger(__name__)

ACCESS_ORG, ACCESS_ROLE = "org", "role"
PUBLISH_ACCESS = (ACCESS_ORG, ACCESS_ROLE)
SLUG_BYTES = 18                  # token_urlsafe(18) → 24 字符：落在 String(32) 内且无 '=' 填充
SNAPSHOT_SCHEMA = 1              # 快照结构版本：Plan 2 的渲染器按它兼容历史发布行
DENY_MESSAGE = "只读页不存在或无权访问"     # 所有拒因共用的一句话（边界 2）
AUDIT_MODULE = "twin:publish"    # 命名律照 `ai:sqlbot_tool`（sqlbot_template_tool.py:50）


def new_slug() -> str:
    """只读页标识：**随机、不可猜、非 id 派生**（边界 1）。"""
    return secrets.token_urlsafe(SLUG_BYTES)


def _now_iso() -> str:
    """与 Task 7 同格式的时间戳。**故意不 import 它的私有 `_now_iso`**：跨模块吃下划线
    函数会把两个服务的改动面焊在一起，两行复制更便宜。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_access(db: Session, *, tenant_id: int, user_id: int, username: str,
                   slug: str, action: str, allowed: bool, reason: str,
                   version: Optional[int]) -> None:
    """把一次只读页访问写进 `sys_audit_log`（spec §4.4「审计日志覆盖每次访问」）。

    三条设计取舍，都是实测结论：

    1. **不走中间件**：`AUDIT_LOG_SKIP_METHODS` 默认 `"GET"`（`app/config/_audit.py:10`），
       而元数据端点是 GET，中间件根本不会记它；改全局默认值会波及所有既有 GET 接口，P0 不动。
    2. **成功也记**：安全事件的价值是「谁在什么时候看过哪一页」，只记 403 等于只记失败。
       `reason` 只落审计，**不上响应体**（否则就是枚举预言机）。
    3. **尽力而为**：用 `db.get_bind()` 开**独立 Session**（不搭请求事务的车：请求失败也要
       留下审计），并吞掉一切异常——审计表缺失不得把只读页打成 500
       （先例同律：`sqlbot_template_tool.py:343-344`）。
    """
    try:
        # `sys_audit_log` 无 `tenant_id` 列（计划缺陷修正：执行时实测，2026-11-01），
        # 因此租户信息落 `request_params.tenantId`，既不虚构列也不丢审计维度。
        with Session(db.get_bind()) as s:
            s.add(SysAuditLog(
                user_id=user_id or None,
                username=username or None,
                operation_type="query",              # 沿用中间件的取值域，不发明新枚举
                operation_module=AUDIT_MODULE,
                operation_desc=f"访问孪生只读页 {slug}（{action}）"
                               + ("" if allowed else "：拒绝"),
                request_params={"tenantId": tenant_id, "slug": slug, "action": action,
                                "allowed": allowed, "reason": reason, "publishVersion": version},
                response_status=200 if allowed else 403,
            ))
            s.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("孪生只读页审计写入失败（已忽略）slug=%s allowed=%s: %s", slug, allowed, exc)


class TwinPublishService:
    """T10 发布/停用 + T11 只读页元数据与取数。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 ctx: Optional[ToolUserContext] = None,
                 session_factory: Optional[Callable[[], Session]] = None) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")      # Global Constraints：服务构造必带租户
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.ctx = ctx
        self._session_factory = session_factory
        self._orch = TwinService(db, self.tenant_id, self.user_id,
                                 tuple(ctx.role_codes) if ctx else ())

    # ------------------------------------------------------------ 写权限门

    def _assert_writable_card(self, card_id: int) -> None:
        """发布是**写操作**：owner 或 edit 授予才能发。

        刻意不伸进 `TwinService._writable_card()`（私有实现），而是复用公开的 `get_card()`：
        它已经把「不可读→404 / 非写→无权」两步口径收在一处，两个服务各写一遍内部判断迟早 drift。
        """
        access = self._orch.get_card(int(card_id))["access"]
        if access not in WRITABLE_ACCESS:
            raise ApiError(TWIN_ACCESS_REQUIRED, "无权发布该卡片的页面", 403,
                           {"card_id": int(card_id), "access": access})

    def _assert_writable_page(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page, card = self._orch.page_with_card(page_id)      # 不存在或跨租户 → 404
        self._assert_writable_card(int(card.id))
        return page, card

    def _widgets_of(self, page_id: int) -> List[TwinWidget]:
        return list(self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page_id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all())

    # ------------------------------------------------------------ T10 发布

    @staticmethod
    def _clean_role_codes(access: str,
                          role_codes: Optional[Sequence[str]]) -> Optional[List[str]]:
        """`access=org` 时**不存角色码**：留着值会被误读成「还有角色限制」。"""
        codes = sorted({str(c).strip() for c in (role_codes or []) if str(c).strip()})
        if access == ACCESS_ROLE:
            if not codes:
                raise ApiError(TWIN_PUBLISH_FORBIDDEN, "access=role 必须至少给出一个角色码", 400,
                               {"access": access, "role_codes": list(role_codes or [])})
            return codes
        return None

    def _assert_bindings_runnable(self, widgets: List[TwinWidget]) -> None:
        """发布前置闸：**绑了就必须能跑**。

        未绑定（`query_id IS NULL`）合法——`scene2d` 天生不吃查询（Task 6 配对表里它的形状集
        为空），拒未绑定会把整个场景模块打成不可发布；运行期由四态里的 empty/unbound 表达。
        """
        qids = sorted({int(w.query_id) for w in widgets if w.query_id})
        defs: Dict[int, MetaOntologyQuery] = {}
        if qids:
            defs = {int(r.id): r for r in self.db.execute(
                select(MetaOntologyQuery).where(
                    MetaOntologyQuery.tenant_id == self.tenant_id,
                    MetaOntologyQuery.id.in_(qids))
            ).scalars().all()}
        bad: List[Dict[str, Any]] = []
        for w in widgets:
            if not w.query_id:
                continue
            q = defs.get(int(w.query_id))
            if q is None:
                bad.append({"widget_id": int(w.id), "reason": "查询定义不存在或不属于本租户"})
            elif q.status != "enabled":
                bad.append({"widget_id": int(w.id), "reason": f"查询 {q.code} 已被 owner 停用"})
            elif q.verify_status != "verified" or not q.compiled_sql or not q.source_id:
                bad.append({"widget_id": int(w.id),
                            "reason": f"查询 {q.code} 尚未 preview 通过"
                                      f"（verify_status={q.verify_status}）"})
        if bad:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, "存在不可运行的绑定：逐条 preview 通过后再发布",
                           400, {"widgets": bad})

    def _build_snapshot(self, page: TwinPage, card: TwinCard,
                        widgets: List[TwinWidget]) -> Dict[str, Any]:
        """发布时冻结的配置。**键名与 `WidgetSpec.from_snapshot`（Task 7）逐字对称**：
        两侧字段名不一致就会出现「只读页把编辑期实值当快照值用」这类难查 bug。
        """
        return {
            "schema": SNAPSHOT_SCHEMA,
            "card": {"id": int(card.id), "name": card.name, "icon": card.icon,
                     "description": card.description, "scene_key": card.scene_key,
                     "ontology_id": int(card.ontology_id),
                     "ontology_version": int(card.ontology_version or 0)},
            "page": {"id": int(page.id), "name": page.name,
                     "sort_order": int(page.sort_order or 0), "refresh_json": page.refresh_json},
            "widgets": [{
                "widget_id": int(w.id), "widget_key": w.widget_key, "title": w.title,
                "query_id": int(w.query_id) if w.query_id else None,
                "param_values_json": dict(w.param_values_json or {}),
                "grid_json": dict(w.grid_json or {}),
                "refresh_json": dict(w.refresh_json or {}),
                "display_json": dict(w.display_json or {}),
                "sort_order": int(w.sort_order or 0),
            } for w in widgets],
        }

    def _latest_row(self, page_id: int) -> Optional[TwinPublish]:
        """该页**最近一版**发布记录（**不限 status**：disabled 的行重发布时沿用同 slug）。"""
        return self.db.execute(
            select(TwinPublish)
            .where(TwinPublish.tenant_id == self.tenant_id, TwinPublish.page_id == int(page_id))
            .order_by(TwinPublish.version.desc(), TwinPublish.id.desc()).limit(1)
        ).scalar_one_or_none()

    def _unique_slug(self) -> str:
        """生成本租户未占用的 slug。24 字符随机串的碰撞概率可忽略，但唯一约束在库侧，
        重试只是把一个难看的 500 变成一次静默重来。"""
        for _ in range(5):
            slug = new_slug()
            taken = self.db.execute(
                select(TwinPublish.id).where(TwinPublish.tenant_id == self.tenant_id,
                                             TwinPublish.slug == slug)
            ).scalar_one_or_none()
            if taken is None:
                return slug
        raise ApiError(TWIN_PUBLISH_FORBIDDEN, "slug 生成失败（极小概率碰撞），请重试发布", 409)

    @staticmethod
    def _publish_dict(row: TwinPublish, widget_count: int) -> Dict[str, Any]:
        snap = row.snapshot_json or {}
        return {
            "publish_id": int(row.id), "page_id": int(row.page_id), "card_id": int(row.card_id),
            "slug": row.slug,
            # 两个路径字段缺一不可：`url` 是前端路由，`api_path` 是后端调用路径（nginx 只代理 /api/）
            "url": f"/twin-p/{row.slug}",
            "api_path": f"/api/v1/twin-p/{row.slug}",
            "version": int(row.version or 1), "access": row.access,
            "role_codes": row.role_codes_json, "status": row.status,
            "widget_count": widget_count,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "snapshot_schema": int(snap.get("schema") or 0),
        }

    def publish(self, page_id: int, *, access: str = ACCESS_ORG,
                role_codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """发布/重发布：写权限门 → 前置闸 → 冻快照 → 插新行或版本+1。

        同页重复发布**沿用 slug**（已分发出去的外链不能因一次重发布而作废），
        `version` 继续 +1，`snapshot_json` 整体重写。已停用的行被重新发布时回到 enabled。
        """
        page, card = self._assert_writable_page(page_id)
        if access not in PUBLISH_ACCESS:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, f"access 只支持 {ACCESS_ORG} 或 {ACCESS_ROLE}",
                           400, {"access": access})
        codes = self._clean_role_codes(access, role_codes)
        widgets = self._widgets_of(int(page.id))
        if not widgets:
            raise ApiError(TWIN_PUBLISH_FORBIDDEN, "页面还没有任何模块，发布出去只是一张空页",
                           400, {"page_id": int(page.id), "widget_count": 0})
        self._assert_bindings_runnable(widgets)
        snapshot = self._build_snapshot(page, card, widgets)
        row = self._latest_row(int(page.id))
        if row is None:
            row = TwinPublish(tenant_id=self.tenant_id, card_id=int(card.id),
                              page_id=int(page.id), slug=self._unique_slug(), access=access,
                              role_codes_json=codes, snapshot_json=snapshot, version=1,
                              status="enabled", published_by=self.user_id)
            self.db.add(row)
        else:
            # 不改 row.slug：这就是“外链不失效”的全部实现（故意不写 `row.slug = row.slug`）
            row.version = int(row.version or 1) + 1
            row.status = "enabled"
            row.access = access
            row.role_codes_json = codes
            row.snapshot_json = snapshot          # JSONB 列直接赋新 dict：整体重写，不做 merge
            row.published_by = self.user_id
            row.published_at = func.now()         # DB 侧 now()：不把应用时区带进 naive TIMESTAMP 列
        self.db.commit()
        self.db.refresh(row)
        logger.info("孪生页面发布 card=%s page=%s slug=%s version=%s access=%s",
                    int(card.id), int(page.id), row.slug, row.version, access)
        return self._publish_dict(row, len(widgets))

    def unpublish(self, publish_id: int) -> None:
        """停用：**改 status，不删行**。

        删行会让 slug 可被他人复用（历史链接指向新内容），且审计日志里的
        `publishVersion` 失去可追溯的记载。行由卡片/页面删除时的 FK CASCADE 自然带走。

        重复停用回 **404**：已停用的行不再是「可被撤下的发布」（计划缺陷修正：执行时实测，
        2026-11-01，计划 Step 6 原稿缺这一道闸门，会得到幂等式 204 而与
        `test_unpublish_revokes_and_keeps_row` 的期望相矛盾）。
        """
        row = self.db.get(TwinPublish, publish_id)
        if row is None or int(row.tenant_id or 0) != self.tenant_id:
            raise ApiError(TWIN_NOT_PUBLISHED, "发布记录不存在", 404, {"publish_id": int(publish_id)})
        if str(row.status) != "enabled":
            raise ApiError(TWIN_NOT_PUBLISHED, "发布记录已停用", 404,
                           {"publish_id": int(publish_id), "status": str(row.status)})
        self._assert_writable_card(int(row.card_id))
        row.status = "disabled"
        self.db.commit()
        logger.info("孪生只读页停用 publish_id=%s slug=%s", int(row.id), row.slug)

    # ------------------------------------------------------------ T11 只读页

    def _role_hit(self, codes: Optional[Sequence[str]]) -> bool:
        if self.ctx is None:
            return False            # 上下文构造失败 = 最小权限（tool_context.py:13-15 的红线）
        if self.ctx.is_admin:
            return True
        # `has_any_role([])` 本身返回 False（tool_context.py:61-62），所以空角色集天然 fail-closed
        return self.ctx.has_any_role(list(codes or []))

    def _verdict(self, row: Optional[TwinPublish]) -> Tuple[bool, str]:
        """返回 `(allowed, reason)`。**reason 只进审计，永远不上响应体**（边界 2）。"""
        if row is None:
            # 未知 slug / 跨租户 / 已停用——三者在查行阶段就合并成同一个信号，不区分
            return False, "not-found"
        if str(row.access) == ACCESS_ROLE and not self._role_hit(row.role_codes_json):
            return False, "role-miss"
        return True, "granted"

    def _grant_or_deny(self, slug: str, *, action: str) -> TwinPublish:
        """访问校验链（spec §4.4）：`slug → status=enabled → access(org/role) → 放行`。

        租户过滤与 `status='enabled'` 全部写进**同一条查询**：把「不存在」与「已停用」
        在代码里分成两个分支，就是给枚举留差异化信号。
        """
        row = self.db.execute(
            select(TwinPublish).where(TwinPublish.tenant_id == self.tenant_id,
                                      TwinPublish.slug == slug,
                                      TwinPublish.status == "enabled")
        ).scalar_one_or_none()
        allowed, reason = self._verdict(row)
        _record_access(self.db, tenant_id=self.tenant_id, user_id=self.user_id,
                       username=(self.ctx.username if self.ctx else ""),
                       slug=slug, action=action, allowed=allowed, reason=reason,
                       version=int(row.version) if row is not None else None)
        if not allowed:
            raise ApiError(TWIN_ACCESS_REQUIRED, DENY_MESSAGE, 403,
                           {"slug": slug, "action": action})
        return row

    def get_by_slug(self, slug: str) -> Dict[str, Any]:
        """T11 元数据：**一律回快照**，绝不回表读 `twin_widget`。

        否则「发布后继续编辑」会静默改掉已发布页面的结构，而编辑者并不认为自
        己发布了新版本——这正是只读页最难排查的一类问题。
        """
        row = self._grant_or_deny(slug, action="metadata")
        snap = dict(row.snapshot_json or {})
        page = dict(snap.get("page") or {})
        return {
            "slug": row.slug, "version": int(row.version or 1), "access": row.access,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "card": dict(snap.get("card") or {}),
            "page": page,
            "widgets": list(snap.get("widgets") or []),
            "refresh": page.get("refresh_json"),       # 前端轮询档位（快照值，非实时）
            "snapshot_schema": int(snap.get("schema") or 0),
        }

    def _data_service(self) -> TwinDataService:
        """取数直接交给 Task 7：四态、15 键契约、扇出闸门、角色签名缓存与出口脱敏
        在编辑态与运行态**逐字相同**，前端因此只需一套 `WidgetShell`（§6.3 承重原则）。"""
        return TwinDataService(self.db, self.tenant_id, self.user_id, self.ctx,
                               session_factory=self._session_factory)

    def run_by_slug(self, slug: str,
                    page_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T11 取数：**结构来自快照，数据来自直连**（每次访问现查，不落任何物化行）。

        访客身份驱动出口脱敏：发布**从不放大未脱敏值**——无豁免角色的访客得到的仍是
        `state=masked` 的结果，与他在工作台里看到的完全一致。
        """
        row = self._grant_or_deny(slug, action="data")
        specs = [WidgetSpec.from_snapshot(w)
                 for w in ((row.snapshot_json or {}).get("widgets") or [])]
        base = dict(page_params or {})
        for s in specs:
            s.base_params = base        # 与 T8 同律：只在查询声明过的键上落地，不是广播
        items = self._data_service().execute_specs(specs)
        return {"slug": row.slug, "version": int(row.version or 1),
                "page_id": int(row.page_id), "card_id": int(row.card_id),
                "collected_at": _now_iso(), "count": len(items), "items": items}
