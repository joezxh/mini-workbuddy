"""编排层（spec §2.1 第 2 层）：卡片 / 页面 / 组件的结构与绑定关系。

本层**不做**的事：生成 SQL、连数据源、判断脱敏、归一形状——它们分属语义层（Task 4）
与执行/出口层（Task 7）。本层唯一的业务判断是**形状配对**：某个 `widget_key`
能不能吃某个 `result_shape`。

只维护**一张**配对表（widget_key → 允许的 result_shape）：绑定校验、错误回执与后续的
AI 受限生成（T14）都从同一张表反推候选，反向表一旦并存就会 drift。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, QUERY_COMPILE_FAILED, QUERY_NOT_FOUND,
    QUERY_SHAPE_MISMATCH, TWIN_ACCESS_REQUIRED, TWIN_BINDING_MISMATCH,
    TWIN_CARD_NOT_FOUND, TWIN_LAYOUT_INVALID, TWIN_NAME_DUPLICATE,
    TWIN_PAGE_NOT_FOUND, TWIN_TEMPLATE_UNKNOWN, TWIN_WIDGET_NOT_FOUND,
)
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinCard, TwinCardShare, TwinPage, TwinWidget
from app.models.twin.widget import WIDGET_KEYS

# 卡片可见性四档。restricted = 原型 🔒「受限」（只能看徽标与申请入口，不可取数）
ACCESS_OWNER, ACCESS_EDIT, ACCESS_READ, ACCESS_RESTRICTED = "owner", "edit", "read", "restricted"
WRITABLE_ACCESS = (ACCESS_OWNER, ACCESS_EDIT)
# 他人可见范围：live 与 paused 都是“已对外”的卡（paused = 停轮询但页面仍可访问，§10 Q3-A）
PUBLIC_STATES = ("live", "paused")

# 唯一的配对表。空元组 = 该模块不吃任何查询：scene2d 读卡片自身的 scene_key，
# scene3d 属 P1（T3），绑了就是后门，因此一律拒。
WIDGET_KEY_TO_SHAPES: Dict[str, Tuple[str, ...]] = {
    "kpi": ("kpi",),
    "trend": ("trend",),
    "bar": ("bar",),
    "donut": ("donut",),
    "alert_table": ("table", "entity_set"),
    "graph": ("graph",),
    "scene2d": (),
    "scene3d": (),
}

# 离散栅格（P0 不做自由拖拽，spec §1.2）：w 只允许 3/6/12，且不得溢出 12 列——
# “拖不动到非法位”在服务端就成立，而不是靠前端按钮藏起来。
#
# 计划原文另要求「x 必须是 w 的整数倍」，实测**自相矛盾**已删：内置模板 ops-line
# 自己的第二个组件就是 x=3/w=6（3+6=9、9 之后放 w=3 正好铺满 12 列），按该规则会被
# 自己的 `_clean_grid()` 判成 TWIN_LAYOUT_INVALID，`from-template` 必然建卡失败。
# 该规则的收益（限制对齐位）远小于它否决合法紧凑布局的代价，故闸门保留“离散宽度 +
# 不溢出 + h 在范围内 + y 非负”，不再约束 x 与 w 的整除关系。
GRID_W_ALLOWED = (3, 6, 12)
GRID_H_RANGE = (1, 24)
GRID_COLS = 12

REFRESH_MODES = ("interval", "manual", "off")
REFRESH_INTERVALS = (10, 30, 0)          # off ⇒ interval_seconds=0
DEFAULT_REFRESH: Dict[str, Any] = {"mode": "interval", "interval_seconds": 10}

# T3 内置模板：只搭骨架（全部组件 query_id=NULL，回到原型「待绑定」空态）。
# 模板**不预建查询**：查询属于语义层且必须逐一 preview，预绑会把 R1 风险藏到运行期。
TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ops-line": {
        "name": "产线运行看板", "scene_key": "factory",
        "pages": [{"name": "总览", "widgets": [
            {"widget_key": "kpi", "title": "综合效率 OEE", "grid": {"x": 0, "y": 0, "w": 3, "h": 4}},
            {"widget_key": "trend", "title": "产量趋势", "grid": {"x": 3, "y": 0, "w": 6, "h": 4}},
            {"widget_key": "alert_table", "title": "告警列表", "grid": {"x": 9, "y": 0, "w": 3, "h": 4}},
        ]}],
    },
    "energy-park": {
        "name": "园区能耗看板", "scene_key": "park",
        "pages": [
            {"name": "能耗总览", "widgets": [
                {"widget_key": "kpi", "title": "今日电费", "grid": {"x": 0, "y": 0, "w": 3, "h": 4}},
                {"widget_key": "donut", "title": "分项占比", "grid": {"x": 3, "y": 0, "w": 3, "h": 4}},
                {"widget_key": "scene2d", "title": "园区平面", "grid": {"x": 6, "y": 0, "w": 6, "h": 4}},
            ]},
            {"name": "趋势对比", "widgets": [
                {"widget_key": "trend", "title": "24h 负荷曲线", "grid": {"x": 0, "y": 0, "w": 12, "h": 6}},
            ]},
        ],
    },
}


class TwinService:
    """卡片/页面/组件的租户隔离 CRUD。写操作要求 owner 或 edit 授予。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 role_codes: Sequence[str] = ()) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.role_codes = tuple(sorted({r for r in role_codes if r}))

    # ------------------------------------------------------------- 可见性

    def _my_shares(self) -> Dict[int, TwinCardShare]:
        """我对本租户卡片的有效授予（card_id -> share）：已过期的不算，edit 覆盖 read。"""
        conds = [and_(TwinCardShare.grantee_type == "user",
                      TwinCardShare.grantee_id == self.user_id)]
        if self.role_codes:
            conds.append(and_(TwinCardShare.grantee_type == "role",
                              TwinCardShare.grantee_code.in_(list(self.role_codes))))
        rows = self.db.execute(
            select(TwinCardShare)
            .where(TwinCardShare.tenant_id == self.tenant_id, or_(*conds),
                   # 用 DB 侧 now() 比较，不把应用时区带进 naive TIMESTAMP 列
                   or_(TwinCardShare.expires_at.is_(None), TwinCardShare.expires_at > func.now()))
        ).scalars().all()
        best: Dict[int, TwinCardShare] = {}
        for s in rows:
            key = int(s.card_id)
            if key not in best or (best[key].perm != "edit" and s.perm == "edit"):
                best[key] = s
        return best

    @staticmethod
    def _access_of(card: TwinCard, shares: Dict[int, TwinCardShare],
                   user_id: int) -> Optional[str]:
        if int(card.owner_id) == user_id:
            return ACCESS_OWNER
        sh = shares.get(int(card.id))
        if sh is not None:
            return ACCESS_EDIT if sh.perm == "edit" else ACCESS_READ
        if (card.runtime_state or "") in PUBLIC_STATES:
            return ACCESS_RESTRICTED
        return None          # 他人的 draft：不入任何列表

    def _current_versions(self, ontology_ids: set) -> Dict[int, int]:
        if not ontology_ids:
            return {}
        rows = self.db.execute(
            select(MetaOntology.id, MetaOntology.current_version)
            .where(MetaOntology.id.in_(ontology_ids))
        ).all()
        return {int(r[0]): int(r[1] or 0) for r in rows}

    def _card_dict(self, c: TwinCard, access: Optional[str],
                   current_versions: Dict[int, int]) -> dict:
        # stale：卡片钉的版落后于本体最新版（R5：只提示不自动跟随）
        cur = current_versions.get(int(c.ontology_id), 0)
        return {
            "id": int(c.id), "name": c.name, "icon": c.icon, "description": c.description,
            "source_template_key": c.source_template_key,
            "ontology_id": int(c.ontology_id), "ontology_version": int(c.ontology_version or 0),
            "ontology_current_version": cur, "stale": cur > int(c.ontology_version or 0),
            "scene_key": c.scene_key, "runtime_state": c.runtime_state,
            "owner_id": int(c.owner_id), "access": access,
            "restricted": access == ACCESS_RESTRICTED,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    def card_or_404(self, card_id: int) -> TwinCard:
        row = self.db.get(TwinCard, card_id)
        if row is None or int(row.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return row

    def _writable_card(self, card_id: int) -> TwinCard:
        card = self.card_or_404(card_id)
        access = self._access_of(card, self._my_shares(), self.user_id)
        if access not in WRITABLE_ACCESS:
            raise ApiError(TWIN_ACCESS_REQUIRED, "无权编辑该卡片", 403,
                           {"card_id": int(card.id), "access": access})
        return card

    # ------------------------------------------------------------- 卡片

    def list_cards(self) -> Dict[str, List[dict]]:
        shares = self._my_shares()
        rows = self.db.execute(
            select(TwinCard).where(TwinCard.tenant_id == self.tenant_id)
            .order_by(TwinCard.updated_at.desc(), TwinCard.id.desc())
        ).scalars().all()
        current = self._current_versions({int(r.ontology_id) for r in rows})
        out: Dict[str, List[dict]] = {"mine": [], "shared": [], "restricted": []}
        for c in rows:
            acc = self._access_of(c, shares, self.user_id)
            if acc is None:
                continue
            d = self._card_dict(c, acc, current)
            if acc == ACCESS_OWNER:
                out["mine"].append(d)
            elif acc == ACCESS_RESTRICTED:
                out["restricted"].append(d)
            else:
                out["shared"].append(d)
        return out

    def get_card(self, card_id: int) -> dict:
        card = self.card_or_404(card_id)
        acc = self._access_of(card, self._my_shares(), self.user_id)
        if acc is None:
            # 非 owner / 非共享 / 非对外：与跨租户同一信号，不用 403 泄露存在性
            raise ApiError(TWIN_CARD_NOT_FOUND, "卡片不存在", 404)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}))

    def _require_published_version(self, ontology_id: int, version: int) -> None:
        ont = self.db.get(MetaOntology, ontology_id)
        if ont is None or int(ont.tenant_id) != self.tenant_id:
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404, {"ontology_id": ontology_id})
        hit = self.db.execute(
            select(MetaOntologyVersion.id).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == version)
        ).scalar_one_or_none()
        if hit is None:
            # 卡片只能钉已发布版本：只有发布才会写 onto_ontology_version 快照，
            # 钉一个不存在的版本等于允诺一个永远编译不过的卡片。
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体版本不存在（仅已发布版本有快照）", 400,
                           {"ontology_id": ontology_id, "version": version})

    def create_card(self, payload: Dict[str, Any]) -> dict:
        ontology_id = int(payload["ontology_id"])
        version = int(payload["ontology_version"])
        self._require_published_version(ontology_id, version)
        card = TwinCard(
            tenant_id=self.tenant_id, name=str(payload["name"]).strip(),
            icon=payload.get("icon"), description=payload.get("description"),
            source_template_key=None, ontology_id=ontology_id, ontology_version=version,
            scene_key=payload.get("scene_key"), runtime_state="draft", owner_id=self.user_id,
        )
        self.db.add(card)
        self._commit_unique_or_409()
        self.db.refresh(card)
        return self._card_dict(card, ACCESS_OWNER, self._current_versions({ontology_id}))

    def update_card(self, card_id: int, patch: Dict[str, Any]) -> dict:
        card = self._writable_card(card_id)
        if "ontology_id" in patch or "ontology_version" in patch:
            oid = int(patch.get("ontology_id") or card.ontology_id)
            ver = int(patch.get("ontology_version") or card.ontology_version)
            self._require_published_version(oid, ver)
        # 非法 runtime_state 必须在 setattr **之前**拒：否则脏值已挂在 session 对象上，
        # 本次虽未 commit，同会话的后续 flush 会把它写进库并撞上 ck_twin_card_state。
        if "runtime_state" in patch and patch["runtime_state"] not in ("draft", "live", "paused"):
            raise ApiError(TWIN_LAYOUT_INVALID, "runtime_state 取值非法", 400,
                           {"runtime_state": patch["runtime_state"]})
        allowed = {"name", "icon", "description", "scene_key", "runtime_state",
                   "ontology_id", "ontology_version"}
        for k, v in patch.items():
            if k in allowed:
                setattr(card, k, v)
        self._commit_unique_or_409()
        acc = self._access_of(card, self._my_shares(), self.user_id)
        return self._card_dict(card, acc, self._current_versions({int(card.ontology_id)}))

    def delete_card(self, card_id: int) -> None:
        card = self._writable_card(card_id)
        # 页面/组件/发布/共享/申请单均由 FK CASCADE 带走，不在应用层逐表删
        self.db.delete(card)
        self.db.commit()

    def create_from_template(self, template_key: str, name: str,
                             ontology_id: Optional[int] = None) -> dict:
        """T3：模板只搭骨架，卡片钉住哪个本体是调用方的事。

        `ontology_id` 省略时默认取本租户“最新已发布本体”（按 ontology_id 倒序取第一个
        有发布版本者）——演示路径上零参数可用；生产接入时前端必须显式传。
        """
        tpl = TEMPLATES.get(template_key)
        if tpl is None:
            raise ApiError(TWIN_TEMPLATE_UNKNOWN, "模板不存在", 400,
                           {"template_key": template_key, "available": sorted(TEMPLATES)})
        if ontology_id is not None:
            ont = self.db.get(MetaOntology, int(ontology_id))
            if ont is None or int(ont.tenant_id) != self.tenant_id:
                raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404, {"ontology_id": ontology_id})
            version = self.db.execute(
                select(func.max(MetaOntologyVersion.version))
                .where(MetaOntologyVersion.ontology_id == ont.id)
            ).scalar_one_or_none()
        else:
            row = self.db.execute(
                select(MetaOntology, func.max(MetaOntologyVersion.version).label("v"))
                .join(MetaOntologyVersion, MetaOntologyVersion.ontology_id == MetaOntology.id)
                .where(MetaOntology.tenant_id == self.tenant_id)
                .group_by(MetaOntology.id)
                .order_by(MetaOntology.id.desc()).limit(1)
            ).first()
            if row is None:
                raise ApiError(ONTOLOGY_NOT_FOUND, "本租户无已发布本体，无法套模板", 400)
            ont, version = row[0], row[1]
        if not version:
            raise ApiError(ONTOLOGY_NOT_FOUND, "该本体尚未发布任何版本", 400,
                           {"ontology_id": int(ont.id)})
        card = TwinCard(tenant_id=self.tenant_id, name=name.strip(), icon=None,
                        description=f"由模板 {template_key} 创建",
                        source_template_key=template_key, ontology_id=int(ont.id),
                        ontology_version=int(version), scene_key=tpl["scene_key"],
                        runtime_state="draft", owner_id=self.user_id)
        self.db.add(card)
        self.db.flush()
        for pi, page_spec in enumerate(tpl["pages"]):
            page = TwinPage(tenant_id=self.tenant_id, card_id=int(card.id),
                            name=page_spec["name"], sort_order=pi,
                            refresh_json=dict(DEFAULT_REFRESH))
            self.db.add(page)
            self.db.flush()
            for wi, wspec in enumerate(page_spec["widgets"]):
                self.db.add(TwinWidget(
                    tenant_id=self.tenant_id, page_id=int(page.id),
                    widget_key=wspec["widget_key"], title=wspec["title"],
                    query_id=None, param_values_json={}, display_json={},
                    grid_json=dict(wspec["grid"]), refresh_json=None, sort_order=wi,
                ))
        self._commit_unique_or_409()
        self.db.refresh(card)
        return self._card_dict(card, ACCESS_OWNER, self._current_versions({int(ont.id)}))

    def _commit_unique_or_409(self) -> None:
        """把两个唯一约束的数据库报错翻译成人话（不外抛 500）。"""
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ApiError(TWIN_NAME_DUPLICATE, "名称重复（同租户同人卡片名/同卡页面名必须唯一）",
                           409, {"error": str(exc.orig)[:200]}) from exc

    # ------------------------------------------------------------- 页面

    def page_with_card(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page = self.db.get(TwinPage, page_id)
        if page is None or int(page.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页面不存在", 404)
        return page, self.card_or_404(int(page.card_id))

    def _writable_page(self, page_id: int) -> Tuple[TwinPage, TwinCard]:
        page, card = self.page_with_card(page_id)
        self._writable_card(int(card.id))
        return page, card

    @staticmethod
    def _page_dict(p: TwinPage, widget_count: int = 0) -> dict:
        return {"id": int(p.id), "card_id": int(p.card_id), "name": p.name,
                "sort_order": int(p.sort_order or 0), "refresh_json": p.refresh_json,
                "widget_count": widget_count,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None}

    def list_pages(self, card_id: int) -> List[dict]:
        self.get_card(card_id)                      # 可读校验（不可读 → 404）
        rows = self.db.execute(
            select(TwinPage, func.count(TwinWidget.id))
            .outerjoin(TwinWidget, TwinWidget.page_id == TwinPage.id)
            .where(TwinPage.card_id == card_id)
            .group_by(TwinPage.id)
            .order_by(TwinPage.sort_order, TwinPage.id)
        ).all()
        return [self._page_dict(r[0], int(r[1])) for r in rows]

    def create_page(self, card_id: int, name: str,
                    refresh_json: Optional[dict] = None) -> dict:
        self._writable_card(card_id)
        page = TwinPage(tenant_id=self.tenant_id, card_id=card_id, name=name.strip(),
                        sort_order=int(self.db.query(func.count(TwinPage.id))
                                       .filter(TwinPage.card_id == card_id).scalar() or 0),
                        refresh_json=self._clean_refresh(refresh_json))
        self.db.add(page)
        self._commit_unique_or_409()
        self.db.refresh(page)
        return self._page_dict(page)

    def update_page(self, page_id: int, patch: Dict[str, Any]) -> dict:
        page, _ = self._writable_page(page_id)
        if "name" in patch:
            page.name = str(patch["name"]).strip()
        if "refresh_json" in patch:
            page.refresh_json = self._clean_refresh(patch["refresh_json"])
        self._commit_unique_or_409()
        self.db.refresh(page)
        return self._page_dict(page)

    def delete_page(self, page_id: int) -> None:
        page, _ = self._writable_page(page_id)
        self.db.delete(page)
        self.db.commit()

    def reorder_pages(self, card_id: int, page_ids: List[int]) -> List[dict]:
        self._writable_card(card_id)
        existing = {int(p.id) for p in self.db.execute(
            select(TwinPage).where(TwinPage.card_id == card_id)
        ).scalars().all()}
        wanted = [int(x) for x in page_ids]
        unknown = [x for x in wanted if x not in existing]
        if unknown:
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页序包含非本卡页面", 400,
                           {"unknown": unknown, "expected": sorted(existing)})
        if len(set(wanted)) != len(existing):
            raise ApiError(TWIN_PAGE_NOT_FOUND, "页序必须覆盖该卡全部页面且不重复", 400,
                           {"given": wanted, "existing_count": len(existing)})
        for idx, pid in enumerate(wanted):
            self.db.execute(TwinPage.__table__.update().where(TwinPage.id == pid)
                            .values(sort_order=idx))
        self.db.commit()
        # Core 批量 UPDATE 不会同步 ORM identity map（上面 `select(TwinPage)` 已把行载入），
        # 而 SessionLocal 是 `expire_on_commit=False`——不显式 expire 就会把内存里的旧 sort_order
        # 当作重读结果返回（计划缺陷修正：执行时实测）。
        self.db.expire_all()
        return self.list_pages(card_id)

    @staticmethod
    def _clean_refresh(raw: Optional[dict]) -> dict:
        """刷新档位只能落在三档上（§4.3：“实时”= 最短 10s 轮询，不是推送）。"""
        if not raw:
            return dict(DEFAULT_REFRESH)
        mode = str(raw.get("mode", "interval"))
        if mode not in REFRESH_MODES:
            raise ApiError(TWIN_LAYOUT_INVALID, "refresh.mode 取值非法", 400,
                           {"mode": mode, "allowed": list(REFRESH_MODES)})
        secs = int(raw.get("interval_seconds", 10))
        if mode == "interval" and secs not in (10, 30):
            raise ApiError(TWIN_LAYOUT_INVALID, "interval 仅允许 10/30 秒", 400,
                           {"interval_seconds": secs, "allowed": [10, 30]})
        if mode in ("manual", "off"):
            secs = 0
        return {"mode": mode, "interval_seconds": secs}

    # ------------------------------------------------------------- 组件

    @staticmethod
    def _widget_dict(w: TwinWidget) -> dict:
        return {"id": int(w.id), "page_id": int(w.page_id), "widget_key": w.widget_key,
                "title": w.title, "query_id": int(w.query_id) if w.query_id else None,
                "param_values_json": w.param_values_json, "display_json": w.display_json,
                "grid_json": w.grid_json, "refresh_json": w.refresh_json,
                "sort_order": int(w.sort_order or 0),
                "updated_at": w.updated_at.isoformat() if w.updated_at else None}

    def list_widgets(self, page_id: int) -> List[dict]:
        page, card = self.page_with_card(page_id)
        self.get_card(int(card.id))                 # 可读校验
        rows = self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page.id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all()
        return [self._widget_dict(w) for w in rows]

    @staticmethod
    def _clean_grid(grid: Optional[dict]) -> dict:
        g = grid or {}
        x, y, w, h = (int(g.get("x", 0)), int(g.get("y", 0)),
                      int(g.get("w", 6)), int(g.get("h", 4)))
        bad: Dict[str, Any] = {}
        if w not in GRID_W_ALLOWED:
            bad["w"] = f"{w} 不在 {GRID_W_ALLOWED}"
        if not (GRID_H_RANGE[0] <= h <= GRID_H_RANGE[1]):
            bad["h"] = f"{h} 不在 {GRID_H_RANGE}"
        if x < 0:
            bad["x"] = f"{x} 不得为负"
        elif x + w > GRID_COLS:
            bad["x"] = f"x={x} 与 w={w} 溢出 {GRID_COLS} 列"
        if y < 0:
            bad["y"] = f"{y} 不得为负"
        if bad:
            raise ApiError(TWIN_LAYOUT_INVALID, "栅格位非法", 400,
                           {"grid": {"x": x, "y": y, "w": w, "h": h}, "violations": bad})
        return {"x": x, "y": y, "w": w, "h": h}

    def _validate_binding(self, card: TwinCard, widget_key: str,
                          query_id: Optional[int]) -> Tuple[Optional[MetaOntologyQuery], Tuple[str, ...]]:
        """绑定三验：同一个本体+版本 → 已编译通过 → 形状配对（§5.2 第 2/3 闸）。"""
        allowed_shapes = WIDGET_KEY_TO_SHAPES[widget_key]
        if query_id is None:
            return None, allowed_shapes
        q = self.db.get(MetaOntologyQuery, int(query_id))
        if q is None or int(q.tenant_id) != self.tenant_id:
            raise ApiError(QUERY_NOT_FOUND, "查询定义不存在", 404, {"query_id": query_id})
        if int(q.ontology_id) != int(card.ontology_id) or int(q.version) != int(card.ontology_version):
            raise ApiError(TWIN_BINDING_MISMATCH, "查询不属于卡片钉住的本体+版本", 400,
                           {"query_id": int(q.id), "query_ontology": int(q.ontology_id),
                            "query_version": int(q.version),
                            "card_ontology": int(card.ontology_id),
                            "card_version": int(card.ontology_version)})
        if q.verify_status != "verified" or not q.compiled_sql:
            raise ApiError(QUERY_COMPILE_FAILED, "查询未通过编译，请先 preview", 400,
                           {"query_id": int(q.id), "verify_status": q.verify_status,
                            "verify_detail": q.verify_detail_json})
        return q, allowed_shapes

    def add_widget(self, page_id: int, payload: Dict[str, Any]) -> dict:
        page, card = self._writable_page(page_id)
        widget_key = str(payload["widget_key"])
        if widget_key not in WIDGET_KEYS:
            raise ApiError(QUERY_SHAPE_MISMATCH, "模块类型不存在", 400,
                           {"widget_key": widget_key, "allowed": list(WIDGET_KEYS)})
        q, allowed_shapes = self._validate_binding(card, widget_key, payload.get("query_id"))
        if q is not None and q.result_shape not in allowed_shapes:
            # W9：错误原因必须可读——给出不匹配的两个值 + 本查询可用的组件清单
            raise ApiError(QUERY_SHAPE_MISMATCH,
                           f"查询结果形状 {q.result_shape} 与组件 {widget_key} 不配对", 400,
                           {"widget_key": widget_key, "result_shape": q.result_shape,
                            "expected_shapes": list(allowed_shapes),
                            "compatible_widgets": self._widgets_for_shape(q.result_shape),
                            "query_code": q.code, "query_name": q.name})
        w = TwinWidget(
            tenant_id=self.tenant_id, page_id=int(page.id), widget_key=widget_key,
            title=str(payload.get("title") or (q.name if q else widget_key)).strip(),
            query_id=int(q.id) if q else None,
            param_values_json=payload.get("param_values_json") or {},
            display_json=payload.get("display_json") or {},
            grid_json=self._clean_grid(payload.get("grid_json")),
            refresh_json=(self._clean_refresh(payload["refresh_json"])
                          if payload.get("refresh_json") else None),
            sort_order=int(self.db.query(func.count(TwinWidget.id))
                           .filter(TwinWidget.page_id == int(page.id)).scalar() or 0),
        )
        self.db.add(w)
        self.db.commit()
        self.db.refresh(w)
        return self._widget_dict(w)

    @staticmethod
    def _widgets_for_shape(shape: str) -> List[str]:
        return sorted(k for k, v in WIDGET_KEY_TO_SHAPES.items() if shape in v)

    def widget_or_404(self, widget_id: int) -> TwinWidget:
        w = self.db.get(TwinWidget, widget_id)
        if w is None or int(w.tenant_id) != self.tenant_id:
            raise ApiError(TWIN_WIDGET_NOT_FOUND, "组件不存在", 404)
        return w

    def update_widget(self, widget_id: int, patch: Dict[str, Any]) -> dict:
        w = self.widget_or_404(widget_id)
        _, card = self._writable_page(int(w.page_id))
        # PATCH 语义：exclude_unset 而非 exclude_none——前端清空绑定会显式发 query_id=null
        if "query_id" in patch:
            q, allowed_shapes = self._validate_binding(card, w.widget_key, patch["query_id"])
            if q is not None and q.result_shape not in allowed_shapes:
                raise ApiError(QUERY_SHAPE_MISMATCH, "改绑后形状不配对", 400,
                               {"widget_key": w.widget_key, "result_shape": q.result_shape,
                                "compatible_widgets": self._widgets_for_shape(q.result_shape)})
            w.query_id = int(q.id) if q else None
            if q is None:
                w.param_values_json = {}            # 解绑同时丢实值，避免旧参数默默长在新绑定上
        for src, dst in (("title", "title"), ("widget_key", "widget_key"),
                         ("param_values_json", "param_values_json"),
                         ("display_json", "display_json")):
            if src in patch:
                setattr(w, dst, patch[src])
        if "grid_json" in patch:
            w.grid_json = self._clean_grid(patch["grid_json"])
        if "refresh_json" in patch:
            w.refresh_json = self._clean_refresh(patch["refresh_json"]) if patch["refresh_json"] else None
        self.db.commit()
        self.db.refresh(w)
        return self._widget_dict(w)

    def delete_widget(self, widget_id: int) -> None:
        w = self.widget_or_404(widget_id)
        self._writable_page(int(w.page_id))
        self.db.delete(w)
        self.db.commit()

    def save_layout(self, page_id: int, items: List[Dict[str, Any]]) -> List[dict]:
        """T7：拖拽/自动布局/AI 应用共用同一个写入口（确定性的批量写）。"""
        self._writable_page(page_id)
        # 两阶段：先全量校验后落库，自然得到原子性（无需中途 rollback）
        cleaned = []
        for it in items:
            wid = int(it["widget_id"])
            w = self.widget_or_404(wid)
            if int(w.page_id) != int(page_id):
                raise ApiError(TWIN_WIDGET_NOT_FOUND, "组件不属于该页面", 400,
                               {"widget_id": wid, "page_id": int(w.page_id)})
            cleaned.append((wid, self._clean_grid(it["grid_json"])))
        for wid, grid in cleaned:
            self.db.execute(TwinWidget.__table__.update().where(TwinWidget.id == wid)
                            .values(grid_json=grid))
        self.db.commit()
        # 同 reorder_pages：校验期的 `widget_or_404()` 已把这些组件载入 identity map，
        # 而 session 配了 `expire_on_commit=False`，不 expire 就会返回旧的栅格位。
        self.db.expire_all()
        return self.list_widgets(page_id)
