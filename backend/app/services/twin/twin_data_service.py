"""批量取数编排（spec §2.2 一次页面刷新 / §4.3 扇出闸门 / §4.6 错误处理）。

四层职责在本文件的落点（任何一条被破坏即视为架构违规）：

- **不生成 SQL、不改 SQL**：编译产物 `compiled_sql` 属于语义层（Task 4）；
- **不开第二条取数通道**：一律经 `ReadonlyQueryService.run`（执行层，Task 3 已扩 `params`）；
- **不自己掩码**：值位替换交给 `apply_masking`（出口层纯函数），本层只决定 `state`；
- **不重做形状**：归一复用 Task 4 的模块级 `shape_result()`，设计期预览与运行期取数共用一份。

⚠️ **安全不变量（R3 / W11）**：缓存键**必须**包含访问者角色签名。
漏掉即等于把豁免角色的**未脱敏**结果命中给普通用户，脱敏形同虚设。
构造入口唯一：:func:`data_cache_key`；回归：`test_cache_key_includes_role_signature`。
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.tool_manager.masking import apply_masking
from app.ai.tool_manager.sqlbot_tool_config import MaskingConfig
from app.ai.tool_manager.tool_context import ToolUserContext
from app.core.api_error import (
    ApiError, QUERY_COMPILE_FAILED, QUERY_NOT_FOUND, TWIN_ACCESS_REQUIRED,
    TWIN_DATA_FAILED, TWIN_DATA_TIMEOUT, TWIN_QUERY_DISABLED,
)
from app.core.cache import TTLCache, make_key
from app.db.database import SessionLocal
from app.models.ontology.query import MetaOntologyQuery
from app.models.twin import TwinWidget
from app.services.dataops.query_service import ReadonlyQueryService
from app.services.ontology.ontology_query_service import shape_result
from app.services.twin.twin_service import ACCESS_RESTRICTED, TwinService

logger = logging.getLogger(__name__)

# 扇出闸门（spec §4.3）。本仓库路由一律是同步 `def`，因此每请求
# `asyncio.Semaphore(4)` 的等价物是**进程级**线程池：`max_workers=4` 比“每请求 4”更保守
# （多页并发刷新时后来者排队，而不是把源库并发推高），符合 R2 的缓解方向。
# 先例：`services/ontology/ontology_build_service.py:97`（同为模块级 ThreadPoolExecutor）。
FANOUT_MAX = 4
QUERY_TIMEOUT_S = 5.0          # 对齐原型 `getSensorStream` 超时文案（prototype:460）
PAGE_DEADLINE_S = 8.0          # 整页 deadline：到点即把未完成组件回 error，**绝不整页 500**
CACHE_TTL_S = 10.0
CACHE_MAXSIZE = 256
DATA_ROW_LIMIT = 200           # 与语义层 preview 同一上限，不给运行期“看到更多行”的后门

STATE_OK, STATE_EMPTY, STATE_ERROR, STATE_MASKED = "ok", "empty", "error", "masked"
REASON_UNBOUND, REASON_ZERO_ROWS = "unbound", "zero_rows"

_EXECUTOR = ThreadPoolExecutor(max_workers=FANOUT_MAX, thread_name_prefix="twin_data")


def _new_cache() -> TTLCache:
    return TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL_S)


_data_cache: TTLCache = _new_cache()


def reset_data_cache() -> None:
    """清缓存。**只给测试用**（用例之间必须隔离，否则上一个用例的未脱敏命中会假装本用例通过）。"""
    global _data_cache
    _data_cache = _new_cache()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def param_sha(values: Optional[Dict[str, Any]]) -> str:
    """参数实值摘要。`sort_keys` 保证同值不同录入顺序得到同一摘要；`default=str`
    兜住 `Decimal`/`datetime`（驱动返回的类型不稳定，不兜就会偶尔 `TypeError` 直接掉整个缓存）。"""
    payload = json.dumps(values or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def role_signature(ctx: Optional[ToolUserContext]) -> str:
    """角色签名：`apply_masking` 的豁免判定只看 `role_codes` 与 `is_admin`（`masking.py:112-117`），
    因此签名只取这两项；多取（如 region）只会无谓碎化缓存命中率。"""
    if ctx is None:
        return "anon"
    roles = ",".join(sorted({r for r in ctx.role_codes if r})) or "-"
    digest = hashlib.sha1(roles.encode("utf-8")).hexdigest()[:12]
    return f"{'a' if ctx.is_admin else 'u'}:{digest}"


def data_cache_key(tenant_id: int, query_id: int, param_digest: str,
                   sql_sha256: Optional[str], role_sig: str) -> str:
    """缓存键的**唯一**构造入口（spec §4.3 四元组 + `sql_sha256`）。

    为何还拼 `sql_sha256`：重编译后同一 `query_id` 的定义已变，不拼摘要就会把
    旧结果当新结果端出去最多 TTL 时长；拼上则“改一句话立即失效”，无需写主动刷缓存。
    """
    return make_key(tenant_id, query_id, param_digest, sql_sha256 or "-", role_sig)


@dataclass
class WidgetSpec:
    """一个组件的取数请求（**与 ORM 无关**：T8/T9 走行记录，T11 发布快照走 `from_snapshot`）。"""

    widget_id: int
    widget_key: str
    title: str
    query_id: Optional[int] = None
    param_values: Dict[str, Any] = field(default_factory=dict)
    grid: Dict[str, Any] = field(default_factory=dict)
    refresh: Dict[str, Any] = field(default_factory=dict)
    # 页面级参数底（仅 T8 填入）：到 `_precheck` 才按各查询的声明裁剪，因为那时才拿到定义行。
    base_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, w: TwinWidget) -> "WidgetSpec":
        return cls(widget_id=int(w.id), widget_key=w.widget_key, title=w.title,
                   query_id=int(w.query_id) if w.query_id else None,
                   param_values=dict(w.param_values_json or {}),
                   grid=dict(w.grid_json or {}), refresh=dict(w.refresh_json or {}))

    @classmethod
    def from_snapshot(cls, d: Dict[str, Any]) -> "WidgetSpec":
        """发布快照条目（Task 8 写 `snapshot_json.widgets` 的结构与此对称）。"""
        return cls(widget_id=int(d.get("widget_id") or 0), widget_key=str(d.get("widget_key") or ""),
                   title=str(d.get("title") or ""),
                   query_id=int(d["query_id"]) if d.get("query_id") else None,
                   param_values=dict(d.get("param_values_json") or {}),
                   grid=dict(d.get("grid_json") or {}), refresh=dict(d.get("refresh_json") or {}))


def _blank_item(spec: WidgetSpec) -> Dict[str, Any]:
    """结果项模板：**每个分支都从此出发**，因而 15 个键不可能漏。"""
    return {
        "widget_id": spec.widget_id, "widget_key": spec.widget_key, "title": spec.title,
        "query_id": spec.query_id, "state": STATE_OK, "reason": None, "result_shape": None,
        "columns": [], "data": {"records": []}, "row_count": 0, "truncated": False,
        "masked_fields": [], "error": None, "cached": False, "updated_at": _now_iso(),
    }


class TwinDataService:
    """页面/组件级批量取数（T8 / T9）。Task 8 的只读发布通道复用 `execute_specs`。"""

    def __init__(self, db: Session, tenant_id: Optional[int], user_id: int,
                 ctx: Optional[ToolUserContext] = None,
                 session_factory: Optional[Callable[[], Session]] = None) -> None:
        if tenant_id is None:
            raise ValueError("tenant_required")
        self.db = db
        self.tenant_id = int(tenant_id)
        self.user_id = int(user_id or 0)
        self.ctx = ctx
        self.role_codes = tuple(sorted({r for r in (ctx.role_codes if ctx else ()) if r}))
        self._role_sig = role_signature(ctx)
        # 工作线程**绝不复用** self.db：SQLAlchemy Session 不是线程安全的。
        # 缺省用应用引擎（与 SessionLocal 同一个连接池）；测试注入绑定到测试引擎的工厂。
        self._session_factory: Callable[[], Session] = session_factory or SessionLocal
        self._orch = TwinService(db, self.tenant_id, self.user_id, self.role_codes)

    # ------------------------------------------------------------ 端点入口

    def _assert_readable(self, card) -> None:
        """取数前的可读门：不可读 404（由 `get_card` 给），🔒 受限 403。

        受限卡只能看徽标与申请入口（§4.5），**不能把取数当旁路读别人的业务数据**。
        """
        access = self._orch.get_card(int(card.id))["access"]
        if access == ACCESS_RESTRICTED:
            raise ApiError(TWIN_ACCESS_REQUIRED, "受限卡片：需先取得访问权限", 403,
                           {"card_id": int(card.id), "access": access})

    def load_page(self, page_id: int,
                  page_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T8：整页刷新只发 1 个请求（W8）。"""
        page, card = self._orch.page_with_card(page_id)
        self._assert_readable(card)
        rows = self.db.execute(
            select(TwinWidget).where(TwinWidget.page_id == int(page.id))
            .order_by(TwinWidget.sort_order, TwinWidget.id)
        ).scalars().all()
        specs = [WidgetSpec.from_row(w) for w in rows]
        base = dict(page_params or {})
        for s in specs:
            s.base_params = base            # 具体哪些键能落地，由 `_precheck` 按声明裁剪
        items = self.execute_specs(specs)
        return {"page_id": int(page.id), "card_id": int(card.id),
                "runtime_state": card.runtime_state, "refresh": page.refresh_json,
                "collected_at": _now_iso(), "count": len(items), "items": items}

    def load_widget(self, widget_id: int,
                    params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """T9：单组件刷新 / error 态 ↻ 重试。不传 `params` 时**只用已存实值**（不偏离 spec）。"""
        w = self._orch.widget_or_404(widget_id)
        _page, card = self._orch.page_with_card(int(w.page_id))
        self._assert_readable(card)
        spec = WidgetSpec.from_row(w)
        if params:
            spec.param_values = {**spec.param_values, **params}
        return self.execute_specs([spec])[0]

    # ------------------------------------------------------------ 扇出执行

    def execute_specs(self, specs: List[WidgetSpec]) -> List[Dict[str, Any]]:
        """未绑定 / 不可运行 / 缓存命中全部在主线程解决，**只把真需要跑 SQL 的送进线程池**。"""
        if not specs:
            return []
        wanted = sorted({s.query_id for s in specs if s.query_id})
        defs: Dict[int, MetaOntologyQuery] = {}
        if wanted:
            defs = {int(r.id): r for r in self.db.execute(
                select(MetaOntologyQuery).where(
                    MetaOntologyQuery.tenant_id == self.tenant_id,
                    MetaOntologyQuery.id.in_(wanted))
            ).scalars().all()}

        results: Dict[int, Dict[str, Any]] = {}
        pending: List[Tuple[WidgetSpec, str, MetaOntologyQuery]] = []
        for spec in specs:
            item, cache_key = self._precheck(spec, defs)
            if item is not None:
                results[spec.widget_id] = item
            else:
                pending.append((spec, cache_key, defs[int(spec.query_id)]))

        # 一次性提交全部待执行项：线程池排队本身即是 Semaphore(4) 的同步等价物。
        futures = [(spec, _EXECUTOR.submit(self._run_one, spec, q, key))
                   for spec, key, q in pending]
        deadline = time.monotonic() + PAGE_DEADLINE_S
        for spec, fut in futures:
            wait = max(min(QUERY_TIMEOUT_S, deadline - time.monotonic()), 0.0)
            try:
                results[spec.widget_id] = fut.result(timeout=wait)
            except FutureTimeout:
                fut.cancel()
                logger.warning("孪生取数超时 widget_id=%s wait=%.3fs", spec.widget_id, wait)
                results[spec.widget_id] = self._error_item(
                    spec, TWIN_DATA_TIMEOUT, f"取数超时（>{QUERY_TIMEOUT_S:.0f}s）")
            except ApiError as exc:
                results[spec.widget_id] = self._error_item(spec, exc.code, exc.message)
            except Exception as exc:  # noqa: BLE001 — 单组件失败不得波及整页（spec §4.3）
                logger.warning("孪生取数失败 widget_id=%s: %s", spec.widget_id, exc)
                results[spec.widget_id] = self._error_item(spec, TWIN_DATA_FAILED, str(exc)[:200])
        return [results[s.widget_id] for s in specs]

    def _precheck(self, spec: WidgetSpec,
                  defs: Dict[int, MetaOntologyQuery]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """返回 `(item, None)`（可直接回前端）或 `(None, cache_key)`（需要真跑 SQL）。"""
        if spec.query_id is None:
            item = _blank_item(spec)
            item.update(state=STATE_EMPTY, reason=REASON_UNBOUND)
            return item, None
        q = defs.get(int(spec.query_id))
        if q is None:
            return self._error_item(spec, QUERY_NOT_FOUND,
                                    "绑定的查询定义不存在或不属于本租户"), None
        # 页面级参数只在该查询声明了同名参数时才生效（spec §2.2 的 `{params}` 是**可选覆盖**，
        # 不是广播）；组件已存实值永远覆盖页面级。未声明的键交给 Task 3 的 `validate_params` 拒。
        declared = {str(d.get("name")) for d in (q.params_json or [])
                    if isinstance(d, dict) and d.get("name")}
        spec.param_values = {**{k: v for k, v in spec.base_params.items() if k in declared},
                             **spec.param_values}
        if q.status != "enabled":
            return self._error_item(spec, TWIN_QUERY_DISABLED, f"查询 {q.code} 已被 owner 停用"), None
        if q.verify_status != "verified" or not q.compiled_sql or not q.source_id:
            return self._error_item(
                spec, QUERY_COMPILE_FAILED,
                f"查询 {q.code} 无可用编译产物（verify_status={q.verify_status}）"), None
        key = data_cache_key(self.tenant_id, int(q.id), param_sha(spec.param_values),
                             q.sql_sha256, self._role_sig)
        hit = _data_cache.get(key)
        if hit is None:
            return None, key
        # 缓存项是**查询结果**，不带组件身份：同一查询被两个组件绑定时共用一条记录，
        # 因此身份四字段必须按当前请求重写——忘了这一步就会把 A 组件的 widget_id 回给 B。
        item = dict(hit)
        item.update(widget_id=spec.widget_id, widget_key=spec.widget_key,
                    title=spec.title, query_id=spec.query_id, cached=True)
        return item, None

    def _run_one(self, spec: WidgetSpec, q: MetaOntologyQuery,
                 cache_key: str) -> Dict[str, Any]:
        """在工作线程里跑一个组件：独立 Session → 出口脱敏 → 形状归一 → 回填缓存。"""
        cfg = self._masking_of(q)          # 先解析脱敏配置：**坏配置直接拒，不先跑 SQL**
        session = self._session_factory()
        try:
            out = ReadonlyQueryService(session, self.tenant_id).run(
                int(q.source_id), q.compiled_sql, limit=DATA_ROW_LIMIT,
                params=spec.param_values, params_declared=q.params_json or [])
        finally:
            session.close()
        columns = list(out["columns"])
        records = [dict(zip(columns, r)) for r in out["rows"]]
        records, masked_fields = apply_masking(records, cfg, self.ctx)   # §4.5 出口层
        item = _blank_item(spec)
        item.update(result_shape=q.result_shape, columns=columns,
                    data=shape_result(q.result_shape, records, columns),
                    row_count=int(out.get("row_count", len(records))),
                    truncated=bool(out.get("truncated")), masked_fields=list(masked_fields))
        if masked_fields:
            item["state"] = STATE_MASKED          # §6.4：任一列被脱敏即 masked（值位 🔒）
        elif not records:
            item["state"], item["reason"] = STATE_EMPTY, REASON_ZERO_ROWS
        else:
            item["state"] = STATE_OK
        # 失败永远到不了这一行（异常已抛出）：**error 态不入缓存**，否则一次抽风会把 error
        # 钉住整个 TTL，前端的 ↻ 重试永远重试不掉。
        _data_cache.set(cache_key, item)
        return item

    @staticmethod
    def _masking_of(q: MetaOntologyQuery) -> MaskingConfig:
        """`mask_rules_json` 必须是可直接 `MaskingConfig.model_validate` 的形状（Task 1 §3.1 已定）。"""
        if not q.mask_rules_json:
            return MaskingConfig(enabled=False, rules=[])
        try:
            return MaskingConfig.model_validate(q.mask_rules_json)
        except ValidationError as exc:
            # fail-closed：宁可回 error，也不把“脱敏配置坏了”降级成“返回真值”。
            # http_status 此处不参与渲染（异常被 execute_specs 收敛为组件 error 态），取 400。
            raise ApiError(TWIN_DATA_FAILED, "查询的脱敏配置非法，已拒绝返回数据", 400,
                           {"query_id": int(q.id), "errors": str(exc)[:300]}) from exc

    @staticmethod
    def _error_item(spec: WidgetSpec, code: str, message: str) -> Dict[str, Any]:
        item = _blank_item(spec)
        # W6：错误态必须回显“错误码 + 人话原因”，不得只给“接口异常”。
        item.update(state=STATE_ERROR, error={"code": code, "message": message})
        return item
