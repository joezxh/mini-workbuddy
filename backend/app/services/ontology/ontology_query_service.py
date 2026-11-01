"""本体查询编译（spec 孪生方案 §4.1：7 步，全程 fail-closed）。

安全边界：
- 只读快照输入（``onto_ontology_version.snapshot_json``），绝不跟随 ``onto_ontology.current_version``；
- 只认快照内逐行 ``review_status='accepted'`` 的元素（**比发布更严**：发布按
  ``onto_ontology_build_item.status`` 整批放行，本模块按元素结论，宁可拒绝也不放行未采纳元素）；
- 敏感列复用 ``sensitive_covered()``，与发布门禁 5 同一真源；
- 产物为无注释单语句 + ``:p_n`` 绑定参数，执行仍走 ``ReadonlyQueryService`` 单一取数口。

版本快照是唯一真源，形状由 ``OntologyPublishService.build_snapshot``
（``ontology_publish_service.py:175-212``）决定，解析必须按下列实测事实写：

- ``objects[]`` = ``{id, code, name, domain, aliases, source, review_status, confidence}``；
- ``relations[]`` = ``{id, code, name, from_object_id, to_object_id, relation_type, source,
  review_status}``——**只有对象 id、没有连接键**，``via_attribute_ids`` 要回查 ``meta_object_relation``；
- ``properties[]`` = ``{id, object_id, standard_id, required, review_status}``——**没有属性 code**，
  属性身份 = 标准项 ``meta_standard.code``，需回查取名；
- ``mappings.table[]`` / ``mappings.column[]`` 已由 build_snapshot 按 ``status='accepted'`` 过滤
  （``:141-166``），故编译期**不再查** ``meta_table_standard``/``meta_column_standard``，
  只按 ``table_id``/``column_id`` 回查 ``meta_table``/``meta_column`` 取物理名。

两个易错列名（实测）：``meta_table`` 的 schema 在 ``database`` 列（**无** ``schema_name`` 列）；
投影一律 ``AS`` 成标准项 code，使结果集键、脱敏 ``field`` 与 ``spec_json`` 引用三者同源。
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import sqlglot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.api_error import (
    ApiError, ONTOLOGY_NOT_FOUND, QUERY_COMPILE_FAILED, QUERY_DRAFT_FORBIDDEN,
    QUERY_ELEMENTS_UNREVIEWED, QUERY_JOIN_AMBIGUOUS, QUERY_MAPPING_MISSING,
    QUERY_NOT_FOUND, QUERY_SENSITIVE_UNCOVERED, QUERY_TOO_MANY_OBJECTS, WIDGET_IN_USE,
)
from app.models.dataops.data_source import DataSource
from app.models.dataops.meta import MetaColumn, MetaTable
from app.models.dataops.standard import MetaStandard
from app.models.dataops.standard_cdm import MetaObjectRelation
from app.models.ontology.ontology import MetaOntology, MetaOntologyVersion
from app.models.ontology.query import MetaOntologyQuery
from app.services.dataops.query_service import ReadonlyQueryService, _dialect_of
from app.services.dataops.sql_guard import SqlGuard
from app.services.dataops.sql_placeholder import normalize_placeholders
from app.services.ontology.ontology_publish_service import is_sensitive, sensitive_covered

SHAPES = ("kpi", "trend", "bar", "donut", "table", "entity_set", "graph")
AGG_OPS = ("sum", "avg", "min", "max", "count")
FILTER_OPS = {"eq": "=", "ne": "<>", "gt": ">", "ge": ">=", "lt": "<", "le": "<=",
              "in": "IN", "like": "LIKE"}
MAX_OBJECTS = 2      # P0 硬限制（对象 ≤2 ⇒ JOIN ≤1 跳，无需单独的 MAX_JOINS）
MAX_LIMIT = 5000
SUPPORTED_DIALECTS = ("postgres",)   # §10 U6：P0 只支持 PG 族（时间窗用 PG 的 INTERVAL 语法）


def _quote(ident: str) -> str:
    """双引号包裹并转义标识符。

    物理表/列名来自元数据而非用户输入，但扫描器/人工都无法保证上游干净，
    因此仍按注入面处理：内部 ``"`` 双写，外层一律带引号（大小写保留）。
    """
    return '"' + str(ident).replace('"', '""') + '"'


_PARAM_TYPES = {int: "int", float: "float", str: "str", bool: "bool"}


def _param_type(value: Any) -> str:
    """编译期根据字面量推断参数声明类型（不支持的类型直接拒）。"""
    t = _PARAM_TYPES.get(type(value))
    if t is None:
        raise ApiError(QUERY_COMPILE_FAILED,
                       f"不支持的过滤值类型: {type(value).__name__}", 400)
    return t


def time_window_expr(col: str, ph: str) -> str:
    """相对时间窗 → PG 语法（§10 U6 取默认 A：P0 仅支持 PG 族）。

    天数走绑定参数，因此不能写成 ``INTERVAL ':n day'``（驱动不绑定引号内）；
    改为乘法形式，已实测 sqlglot 可解析且渲染为 ``INTERVAL '1 DAY'``。
    """
    return f"{col} >= CURRENT_DATE - (:{ph} * INTERVAL '1 day')"


def _require_supported_dialect(source_type: str) -> str:
    """数据源类型 → sqlglot 方言；非 PG 族一律拒编译（而不是编出只能跑错的 SQL）。"""
    dialect = _dialect_of(source_type)
    if dialect not in SUPPORTED_DIALECTS:
        raise ApiError(QUERY_COMPILE_FAILED,
                       f"P0 仅支持 PostgreSQL 族数据源，当前为 {source_type}", 400,
                       {"source_type": source_type, "dialect": dialect})
    return dialect


def shape_result(shape: str, records: List[dict], columns: List[str]) -> dict:
    """按 result_shape 在后端归一，前端 renderer 不再二次整形（spec §6.2）。

    ``columns`` 即投影别名（标准项 code），``records`` 的键与之一致。
    **模块级、无实例状态**：`preview`（本文件）与批量取数（Task 7 的
    :mod:`app.services.twin.twin_data_service`）共用本函数，设计期预览与运行期取数
    因此不可能出现两套形状。
    """
    if shape == "kpi":
        first = records[0] if records else {}
        return {"value": first.get(columns[0]) if columns else None, "records": records}
    if shape in ("trend", "bar"):
        return {"records": records, "t": columns[0], "values": columns[1:]}
    if shape == "donut":
        return {"records": records, "parts": columns[:2]}
    return {"records": records}


class OntologyQueryService:
    """查询定义的创建、编译、预览与生命周期。"""

    def __init__(self, db: Session, tenant_id: Optional[int]) -> None:
        if tenant_id is None:
            raise ValueError("OntologyQueryService 要求 tenant_id，禁止无租户操作")
        self.db = db
        self.tenant_id = tenant_id
        self._guard = SqlGuard()

    # ------------------------------------------------------------------ CRUD

    def create(self, *, ontology_id: int, version: int, code: str, name: str,
               result_shape: str, spec_json: dict, params_json: Optional[list] = None,
               description: Optional[str] = None) -> dict:
        if result_shape not in SHAPES:
            raise ApiError(QUERY_COMPILE_FAILED, f"非法 result_shape: {result_shape}", 400,
                           {"result_shape": result_shape})
        self._ontology_or_404(ontology_id)
        row = MetaOntologyQuery(
            tenant_id=self.tenant_id, ontology_id=ontology_id, version=version, code=code,
            name=name, description=description, result_shape=result_shape, spec_json=spec_json,
            params_json=params_json or [],
            status="disabled" if int(version or 0) == 0 else "enabled",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        # 创建即尝试编译：失败信息直接回给调用方（前端绑定抽屉据此提示）
        # 例外：version=0 的草稿不自动编译——草稿必须存得下来（spec §3.1），
        # 编译是显式动作，否则 create 会当场抛 QUERY_DRAFT_FORBIDDEN 而无处保存。
        if int(version or 0) != 0:
            self.compile_query(row.id)
        return self.get(row.id)

    def get(self, qid: int) -> dict:
        return self._serialize(self._row_or_404(qid))

    def list_for_ontology(self, ontology_id: int, shape: Optional[str] = None,
                          kw: Optional[str] = None, verified_only: bool = False) -> List[dict]:
        stmt = select(MetaOntologyQuery).where(
            MetaOntologyQuery.tenant_id == self.tenant_id,
            MetaOntologyQuery.ontology_id == ontology_id,
        )
        if shape:
            stmt = stmt.where(MetaOntologyQuery.result_shape == shape)
        if kw:
            stmt = stmt.where(MetaOntologyQuery.name.ilike(f"%{kw}%"))
        if verified_only:
            stmt = stmt.where(MetaOntologyQuery.verify_status == "verified")
        rows = self.db.execute(stmt.order_by(MetaOntologyQuery.code)).scalars().all()
        return [self._serialize(r) for r in rows]

    def update(self, qid: int, patch: dict) -> dict:
        row = self._row_or_404(qid)
        for f in ("name", "description", "spec_json", "params_json", "result_shape"):
            if f in patch:
                setattr(row, f, patch[f])
        row.verify_status = "pending"
        self.db.commit()
        if int(row.version or 0) != 0:   # 同上：草稿改动不触发自动编译
            self.compile_query(qid)
        return self.get(qid)

    def bindings(self, qid: int) -> List[dict]:
        from app.models.twin import TwinWidget
        self._row_or_404(qid)
        rows = self.db.execute(
            select(TwinWidget.id, TwinWidget.title).where(
                TwinWidget.tenant_id == self.tenant_id, TwinWidget.query_id == qid
            )
        ).all()
        return [{"widget_id": int(w), "title": t} for w, t in rows]

    def delete(self, qid: int) -> dict:
        row = self._row_or_404(qid)
        used = self.bindings(qid)
        if used:
            raise ApiError(
                WIDGET_IN_USE, f"该查询被 {len(used)} 个组件绑定中，请先解绑", 409,
                {"widgets": used},
            )
        self.db.delete(row)
        self.db.commit()
        return {"deleted": True, "id": qid}

    # -------------------------------------------------------------- 编译 7 步

    def compile_query(self, qid: int) -> dict:
        """①~⑥ 全量重编译；任一步失败先回写 failed 再原样抛出（fail-closed）。"""
        row = self._row_or_404(qid)
        try:
            sql, source_id, params_json, mask_rules, projection = self._compile(row)
        except ApiError as exc:
            detail: Dict[str, Any] = {"blocked_code": exc.code}
            if isinstance(exc.detail, dict):
                detail.update(exc.detail)
            row.compiled_sql = None
            row.sql_sha256 = None
            row.verify_status = "failed"
            row.verify_detail_json = detail
            self.db.commit()
            raise
        row.compiled_sql = sql
        row.sql_sha256 = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        row.source_id = source_id
        row.params_json = params_json
        row.mask_rules_json = {"enabled": bool(mask_rules), "rules": mask_rules}
        row.verify_status = "verified"
        row.verify_detail_json = {"compiled": True, "projection": projection}
        self.db.commit()
        self.db.refresh(row)
        return self._serialize(row)

    def _compile(self, row: MetaOntologyQuery):
        """编译正文：不写库、不提交，失败一律抛 :class:`ApiError`。

        :return: ``(sql, source_id, params_json, mask_rules, projection)``
        """
        # ① 版本解析：只认已发布版本快照，草稿一律拒绝
        version = int(row.version or 0)
        if version == 0:
            raise ApiError(QUERY_DRAFT_FORBIDDEN, "草稿版本查询不可编译，请先发布本体", 400)
        snap = self._snapshot(row.ontology_id, version)

        # ② 元素解析：对象按 code、属性按标准项 code
        acc = self._accepted(snap)
        spec = row.spec_json or {}
        objects = [str(c) for c in (spec.get("objects") or [])]
        attrs = [str(c) for c in (spec.get("attributes") or [])]
        if not objects or not attrs:
            raise ApiError(QUERY_COMPILE_FAILED, "spec 至少需引用 1 个对象与 1 个属性", 400,
                           {"objects": objects, "attributes": attrs})
        if len(objects) > MAX_OBJECTS:
            raise ApiError(QUERY_TOO_MANY_OBJECTS, f"P0 最多 {MAX_OBJECTS} 个对象", 400,
                           {"objects": objects})
        elements = [c for c in attrs if c not in acc["attr_codes"]]
        elements += [c for c in objects if c not in acc["obj_codes"]]
        if elements:
            raise ApiError(QUERY_ELEMENTS_UNREVIEWED, "引用了未采纳元素", 400,
                           {"elements": elements})

        # ③ 对象→物理表
        untabled = [c for c in objects if c not in acc["table"]]
        if untabled:
            raise ApiError(QUERY_MAPPING_MISSING, "对象未完成物理映射", 400,
                           {"objects": untabled})

        # ③′ JOIN 消歧：先于属性归属判定，路径不唯一时把候选交还用户（不猜）
        joins: List[dict] = []
        if len(objects) == 2:
            joins = self._resolve_join(acc, objects[0], objects[1], spec.get("join"))

        # ③″ 属性→物理列（含归属消歧）
        bound = self._bind_columns(acc, objects, attrs)

        # ④ 敏感闸（与发布门禁 5 同源）
        blocked = self._check_sensitive(bound)
        if blocked:
            raise ApiError(QUERY_SENSITIVE_UNCOVERED, f"{len(blocked)} 个敏感列缺脱敏覆盖", 400,
                           {"blocked_columns": blocked})

        # ⑤ 执行目标定死：全部对象同属一个数据源（P0 不做跨源 JOIN）
        source_ids = sorted({int(acc["table"][c]["source_id"]) for c in objects})
        if len(source_ids) > 1:
            raise ApiError(QUERY_COMPILE_FAILED, "P0 不支持跨数据源 JOIN", 400,
                           {"source_ids": source_ids})
        source_id = source_ids[0]
        ds = self.db.get(DataSource, source_id)
        if ds is None or int(ds.tenant_id) != int(self.tenant_id):
            raise ApiError(QUERY_MAPPING_MISSING, "数据源缺失或跨租户", 400,
                           {"source_id": source_id})
        dialect = _require_supported_dialect(ds.source_type)

        # ⑥ SQL 生成 + 参数化（值一律落 :p_n 占位符）
        sql, params_json, mask_rules = self._render(
            acc, objects, attrs, bound, joins, spec, list(row.params_json or []), dialect)
        sql = normalize_placeholders(sql)
        if not self._guard.is_readonly(sql, dialect):
            raise ApiError(QUERY_COMPILE_FAILED, "编译产物未通过只读校验", 400, {"sql": sql})
        return sql, source_id, params_json, mask_rules, [a for a in attrs if a in bound]

    # ------------------------------------------------------------------ 预览

    def preview(self, qid: int, params: Optional[dict] = None, limit: int = 200) -> dict:
        row = self._row_or_404(qid)
        if not row.compiled_sql:
            self.compile_query(qid)
            row = self._row_or_404(qid)
        source_id = int(row.source_id or 0)   # 编译期已定死，运行期不再解析快照
        if not source_id:
            raise ApiError(QUERY_MAPPING_MISSING, "编译产物缺少 source_id，请重新编译", 400)
        svc = ReadonlyQueryService(self.db, self.tenant_id)
        try:
            out = svc.run(source_id, row.compiled_sql, limit=min(int(limit), 200),
                          params=params or {}, params_declared=row.params_json or [])
        except Exception as exc:  # noqa: BLE001 — 预览失败一律回写 failed，供绑定抽屉展示原因
            row.verify_status = "failed"
            row.verify_detail_json = {"error": str(exc)[:400]}
            self.db.commit()
            raise
        records = [dict(zip(out["columns"], r)) for r in out["rows"]]
        shape = shape_result(row.result_shape, records, out["columns"])
        row.verify_status = "verified"
        row.verify_detail_json = {"columns": out["columns"], "row_count": out["row_count"],
                                 "truncated": out["truncated"]}
        self.db.commit()
        return {"query_id": qid, "result_shape": row.result_shape, **shape,
                "row_count": out["row_count"], "columns": out["columns"]}

    # ------------------------------------------------------------------ 内部

    def _serialize(self, r: MetaOntologyQuery) -> dict:
        return {
            "id": int(r.id), "ontology_id": int(r.ontology_id), "version": int(r.version),
            "code": r.code, "name": r.name, "description": r.description,
            "result_shape": r.result_shape, "spec_json": r.spec_json,
            "params_json": r.params_json or [], "compiled_sql": r.compiled_sql,
            "sql_sha256": r.sql_sha256, "source_id": r.source_id,
            "mask_rules_json": r.mask_rules_json,
            "verify_status": r.verify_status,
            "verify_detail_json": r.verify_detail_json, "status": r.status,
        }

    def _ontology_or_404(self, ontology_id: int) -> MetaOntology:
        row = self.db.get(MetaOntology, ontology_id)
        if row is None or int(row.tenant_id) != int(self.tenant_id):
            raise ApiError(ONTOLOGY_NOT_FOUND, "本体不存在", 404)
        return row

    def _row_or_404(self, qid: int) -> MetaOntologyQuery:
        row = self.db.get(MetaOntologyQuery, qid)
        if row is None or int(row.tenant_id) != int(self.tenant_id):
            raise ApiError(QUERY_NOT_FOUND, "查询不存在", 404)
        return row

    def _snapshot(self, ontology_id: int, version: int) -> dict:
        """版本快照是唯一真源：缺失即拒绝，绝不回落到 current_version。"""
        row = self.db.execute(
            select(MetaOntologyVersion).where(
                MetaOntologyVersion.tenant_id == self.tenant_id,
                MetaOntologyVersion.ontology_id == ontology_id,
                MetaOntologyVersion.version == version,
            )
        ).scalar()
        if row is None or not row.snapshot_json:
            raise ApiError(QUERY_COMPILE_FAILED, f"版本快照缺失：v{version}", 400,
                           {"ontology_id": ontology_id, "version": version})
        return row.snapshot_json

    def _accepted(self, snap: dict) -> dict:
        """把「只冻结 id」的快照补成可按 code 索引的编译输入。

        :return: {
          "obj_codes": set, "obj_ids": {obj_code: id},
          "attr_codes": set, "std_ids_by_code": {attr_code: standard_id},
          "prop_pairs": {(standard_id, object_id)},
          "table": {obj_code: {"table_id", "qname", "source_id"}},
          "col_by_std_table": {(standard_id, table_id): {"column_name", "pii_level",
                          "security_level_override", "mask_rule", "column_id"}},
          "relations": [{"id", "code", "from_code", "to_code", "via_std_ids"}],
        }
        """
        objs = [o for o in (snap.get("objects") or []) if o.get("review_status") == "accepted"]
        obj_ids = {str(o["code"]): int(o["id"]) for o in objs if o.get("code")}
        if not obj_ids:
            raise ApiError(QUERY_ELEMENTS_UNREVIEWED, "快照内无 accepted 对象", 400)
        code_by_obj = {v: k for k, v in obj_ids.items()}

        # 属性身份 = 标准项 code（快照只有 standard_id，名称回查 meta_standard）
        props = [p for p in (snap.get("properties") or []) if p.get("review_status") == "accepted"]
        std_ids = sorted({int(p["standard_id"]) for p in props if p.get("standard_id")})
        code_by_std: Dict[int, str] = {}
        mask_by_std: Dict[int, Optional[str]] = {}
        if std_ids:
            for sid, scode, srule in self.db.execute(
                select(MetaStandard.id, MetaStandard.code, MetaStandard.mask_rule).where(
                    MetaStandard.tenant_id == self.tenant_id, MetaStandard.id.in_(std_ids))
            ).all():
                code_by_std[int(sid)] = str(scode)
                mask_by_std[int(sid)] = srule
        prop_pairs = {(int(p["standard_id"]), int(p["object_id"])) for p in props
                      if p.get("standard_id") and p.get("object_id")}

        # 表绑定：快照已由 build_snapshot 按 status='accepted' 过滤，不再重查绑定表
        table_ids_by_obj: Dict[str, List[int]] = {}
        for tm in (snap.get("mappings") or {}).get("table") or []:
            oc = code_by_obj.get(int(tm.get("object_standard_id") or 0))
            if oc:
                table_ids_by_obj.setdefault(oc, []).append(int(tm["table_id"]))
        multi = [c for c, v in table_ids_by_obj.items() if len(v) > 1]
        if multi:
            raise ApiError(QUERY_COMPILE_FAILED, "对象有多个 accepted 表绑定，P0 不消歧", 400,
                           {"objects": sorted(multi)})
        tids = sorted({v[0] for v in table_ids_by_obj.values() if v})
        tables = {int(t.id): t for t in self.db.execute(
            select(MetaTable).where(MetaTable.tenant_id == self.tenant_id,
                                    MetaTable.id.in_(tids))).scalars().all()} if tids else {}
        table_map: Dict[str, dict] = {}
        for code, ids in table_ids_by_obj.items():
            t = tables.get(ids[0])
            if t is None or not t.source_id:
                continue
            # schema 存在 database 列（PG 族）；无 schema_name 列
            table_map[code] = {"table_id": int(t.id),
                               "qname": f"{_quote(t.database)}.{_quote(t.table_name)}",
                               "source_id": int(t.source_id)}

        # 列绑定：一个标准可绑多表多列，故键为 (standard_id, table_id) 而非 standard_id
        col_maps = list((snap.get("mappings") or {}).get("column") or [])
        cids = sorted({int(cm["column_id"]) for cm in col_maps})
        cols = {int(c.id): c for c in self.db.execute(
            select(MetaColumn).where(MetaColumn.tenant_id == self.tenant_id,
                                     MetaColumn.id.in_(cids))).scalars().all()} if cids else {}
        ovr_by_col = {int(cm["column_id"]): cm.get("security_level_override") for cm in col_maps}
        col_by_std_table: Dict[Tuple[int, int], dict] = {}
        for cm in col_maps:
            c = cols.get(int(cm["column_id"]))
            if c is None:
                continue
            col_by_std_table[(int(cm["standard_id"]), int(c.table_id))] = {
                "column_id": int(c.id), "column_name": c.column_name,
                "pii_level": c.pii_level, "mask_rule": mask_by_std.get(int(cm["standard_id"])),
                "security_level_override": ovr_by_col.get(int(c.id)),
            }

        # 关系：快照无连接键，via_attribute_ids 回查实表（一次批量查，不逐行查）
        rel_snap = [r for r in (snap.get("relations") or []) if r.get("review_status") == "accepted"]
        via_by_id: Dict[int, List[int]] = {}
        rids = [int(r["id"]) for r in rel_snap if r.get("id")]
        if rids:
            for rid, via in self.db.execute(
                select(MetaObjectRelation.id, MetaObjectRelation.via_attribute_ids).where(
                    MetaObjectRelation.tenant_id == self.tenant_id,
                    MetaObjectRelation.id.in_(rids))
            ).all():
                via_by_id[int(rid)] = [int(x) for x in (via or [])]
        relations = []
        for r in rel_snap:
            f = code_by_obj.get(int(r.get("from_object_id") or 0))
            t = code_by_obj.get(int(r.get("to_object_id") or 0))
            if not f or not t:
                continue
            relations.append({"id": int(r["id"]), "code": r.get("code"), "from_code": f,
                              "to_code": t, "via_std_ids": via_by_id.get(int(r["id"]), [])})
        return {"obj_codes": set(obj_ids), "obj_ids": obj_ids,
                "attr_codes": set(code_by_std.values()), "std_ids_by_code":
                {v: k for k, v in code_by_std.items()},
                "prop_pairs": prop_pairs, "table": table_map,
                "col_by_std_table": col_by_std_table, "relations": relations}

    def _bind_columns(self, acc: dict, objects: List[str], attrs: List[str]) -> Dict[str, dict]:
        """③″ 属性→物理列，并消歧归属对象；缺失或多归属一律 fail-closed。

        属性可用需同时命中两条链：``properties``（属性挂在该对象上）与列绑定落在
        该对象的物理表上。命中 0 个→未映射，命中≥2 个对象→P0 不猜归属。
        """
        bound: Dict[str, dict] = {}
        missing: List[str] = []
        ambiguous: List[str] = []
        for code in attrs:
            std_id = acc["std_ids_by_code"].get(code)
            hits: Dict[str, dict] = {}
            if std_id:
                for oc in objects:
                    if (std_id, acc["obj_ids"][oc]) not in acc["prop_pairs"]:
                        continue
                    info = acc["col_by_std_table"].get((std_id, acc["table"][oc]["table_id"]))
                    if info:
                        hits[oc] = dict(info, obj_code=oc)
            if not hits:
                missing.append(code)
            elif len(hits) > 1:
                ambiguous.append(code)
            else:
                bound[code] = next(iter(hits.values()))
        if missing:
            raise ApiError(QUERY_MAPPING_MISSING, "属性未完成物理映射", 400,
                           {"attributes": missing})
        if ambiguous:
            raise ApiError(QUERY_COMPILE_FAILED, "属性同时归属查询涉及的多个对象", 400,
                           {"attributes": ambiguous})
        return bound

    def _resolve_join(self, acc: dict, a: str, b: str, hint: Optional[str]) -> List[dict]:
        """③′ 路径唯一才返回；不唯一则把候选交给用户消歧（不猜）。

        方向无关：``{from_code, to_code} == {a, b}``——同一对对象的双向关系算两条。
        ON 子句不在本方法生成（需别名，交给 `_join_on`）。
        """
        cands = [r for r in acc["relations"] if {r["from_code"], r["to_code"]} == {a, b}]
        if hint:
            cands = [r for r in cands if r.get("code") == hint]
        if not cands:
            raise ApiError(QUERY_MAPPING_MISSING, f"{a} 与 {b} 之间无已采纳关系", 400,
                           {"objects": [a, b]})
        if len(cands) > 1:
            raise ApiError(QUERY_JOIN_AMBIGUOUS, "关系路径不唯一，请在 spec.join 指定关系编码", 400,
                           {"candidates": sorted(str(c.get("code")) for c in cands)})
        return [cands[0]]

    def _check_sensitive(self, bound: Dict[str, dict]) -> List[str]:
        """④ 敏感闸：只调 `sensitive_covered()`，与发布门禁 5 同一真源。

        ``exempt`` 恒为 False：编译期不知道运行者身份，豁免只能在出口脱敏时按角色
        判定（Task 7）；本步只做「有没有登记过脱敏规则」这一结构性检查。
        ``security_level_override`` 也从快照 mapping 行读，与门禁 5 完全同宽：上游
        ``build_snapshot:201-205`` 未写入该键（恒为 None），孪生刻意不提前修正，
        以免出现「发布拦下、孪生放行」的单向放宽。
        """
        return [code for code, v in bound.items()
                if not sensitive_covered(v.get("pii_level"), v.get("mask_rule"),
                                         v.get("security_level_override"), exempt=False)]

    def _join_on(self, acc: dict, rel: dict, alias: Dict[str, str]) -> str:
        """关系的 ``via`` 标准 id → 两侧物理列名（快照无连接键，全靠实表）。"""
        parts: List[str] = []
        for std_id in rel["via_std_ids"]:
            lhs = acc["col_by_std_table"].get((std_id, acc["table"][rel["from_code"]]["table_id"]))
            rhs = acc["col_by_std_table"].get((std_id, acc["table"][rel["to_code"]]["table_id"]))
            if not lhs or not rhs:
                raise ApiError(QUERY_MAPPING_MISSING, "关系连接键在对象表上无 accepted 列绑定",
                               400, {"relation": rel["code"], "standard_id": std_id})
            parts.append(f'{_quote(alias[rel["from_code"]])}.{_quote(lhs["column_name"])} = '
                         f'{_quote(alias[rel["to_code"]])}.{_quote(rhs["column_name"])}')
        if not parts:
            raise ApiError(QUERY_COMPILE_FAILED, "关系缺少连接键（via_attribute_ids 为空）", 400,
                           {"relation": rel["code"]})
        return " AND ".join(parts)

    def _render(self, acc: dict, objects: List[str], attrs: List[str],
                bound: Dict[str, dict], joins: List[dict], spec: dict,
                declared: List[dict], dialect: str) -> Tuple[str, List[dict], List[dict]]:
        """⑤⑥ 生成单语句、参数声明与出口脱敏规则。

        组装策略：先收集 WHERE 片段，一次拼出 SQL 文本，再交 ``sqlglot.parse_one``
        规范化渲染（顺带语法复检），最后由调用方 ``normalize_placeholders`` 收尾；
        **禁止字符串切片回写 SQL**。两个注入面各自封口：标识符走 :func:`_quote`
        双写转义，值一律落 ``:p_n`` 占位符（执行期由 ``validate_params`` 校验类型）。

        投影统一 ``AS`` 成标准项 code，因此结果集键、脱敏 ``field`` 与
        ``spec_json.attributes`` 三者同源；也避开同名列（两侧都有 ``dev_code``）互相覆盖。

        :return: ``(sql, params_json, mask_rules)``
        """
        alias = {c: f"t{i}" for i, c in enumerate(objects)}

        def col_of(code: str) -> str:
            v = bound[code]
            return f'{_quote(alias[v["obj_code"]])}.{_quote(v["column_name"])}'

        # 聚合与分组：算子白名单 + group_by 必为 attributes 子集
        agg = spec.get("agg")
        group = [str(g) for g in (spec.get("group_by") or [])]
        outside = [g for g in group if g not in attrs]
        if outside:
            raise ApiError(QUERY_COMPILE_FAILED, "group_by 必须是 attributes 的子集", 400,
                           {"group_by": outside})
        op = ""
        agg_col: Optional[str] = None
        if agg is not None:
            op = str(agg.get("op") or "").lower()
            agg_col = str(agg.get("attribute") or "")
            if op not in AGG_OPS:
                raise ApiError(QUERY_COMPILE_FAILED, f"非法聚合算子: {op}", 400, {"agg_op": op})
            if agg_col not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "聚合属性未完成物理映射", 400,
                               {"attributes": [agg_col]})
            if agg_col in group:
                raise ApiError(QUERY_COMPILE_FAILED, "聚合属性不可同时出现在 group_by", 400,
                               {"attribute": agg_col})
            for code in attrs:
                if code != agg_col and code not in group:
                    raise ApiError(QUERY_COMPILE_FAILED, "聚合查询下非聚合属性必须 group_by",
                                   400, {"attributes": [code]})

        sel = [f'{op}({col_of(code)}) AS {_quote(code)}' if code == agg_col
               else f'{col_of(code)} AS {_quote(code)}' for code in attrs]
        base = objects[0]
        sql = f'SELECT {", ".join(sel)} FROM {acc["table"][base]["qname"]} AS {_quote(alias[base])}'
        for j in joins:
            to = j["to_code"]
            sql += (f' JOIN {acc["table"][to]["qname"]} AS {_quote(alias[to])}'
                    f' ON {self._join_on(acc, j, alias)}')
        if group:
            sql += " GROUP BY " + ", ".join(col_of(g) for g in group)

        # 过滤与时间窗 → 一律占位符；占位符名不得与已声明参数冲突
        params_json = [dict(p) for p in declared]
        taken = {str(p.get("name")) for p in params_json}
        state = {"n": 0}

        def next_ph() -> str:
            while True:
                state["n"] += 1
                cand = f"p_{state['n']}"
                if cand not in taken:
                    taken.add(cand)
                    return cand

        where_bits: List[str] = []
        for f in (spec.get("filters") or []):
            code = str(f.get("attribute") or "")
            fop = str(f.get("op") or "").lower()
            if code not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "过滤属性未完成物理映射", 400,
                               {"attributes": [code]})
            if fop not in FILTER_OPS:
                raise ApiError(QUERY_COMPILE_FAILED, f"非法过滤算子: {fop}", 400, {"filter_op": fop})
            val = f.get("value")
            if fop == "in":
                if not isinstance(val, list) or not val:
                    raise ApiError(QUERY_COMPILE_FAILED, "in 过滤需非空数组", 400,
                                   {"attribute": code})
                subs = [next_ph() for _ in val]
                where_bits.append(f'{col_of(code)} IN ({", ".join(":" + s for s in subs)})')
                params_json += [{"name": s, "type": _param_type(v), "source": "compiled"}
                                for s, v in zip(subs, val)]
            else:
                ph = next_ph()
                where_bits.append(f'{col_of(code)} {FILTER_OPS[fop]} :{ph}')
                params_json.append({"name": ph, "type": _param_type(val), "source": "compiled"})

        tw = spec.get("time_window")
        if tw:
            code = str(tw.get("attribute") or "")
            days = tw.get("days")
            if code not in bound:
                raise ApiError(QUERY_MAPPING_MISSING, "时间窗属性未完成物理映射", 400,
                               {"attributes": [code]})
            if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
                raise ApiError(QUERY_COMPILE_FAILED, "时间窗天数须为 1~3650 的整数", 400,
                               {"days": days})
            ph = next_ph()
            where_bits.append(time_window_expr(col_of(code), ph))
            params_json.append({"name": ph, "type": "int", "source": "compiled"})
        if where_bits:
            sql += " WHERE " + " AND ".join(where_bits)

        limit = min(max(int(spec.get("limit") or 100), 1), MAX_LIMIT)
        sql += f" LIMIT {limit}"

        # 出口脱敏规则：编译期只知道「哪些列是敏感的」，保留位数给 0 即全掩码（fail-safe）
        mask_rules = [{"field": code, "strategy": "mask", "keep_prefix": 0, "keep_suffix": 0,
                       "exempt_roles": []}
                      for code, v in bound.items() if is_sensitive(v.get("pii_level"))]
        try:
            tree = sqlglot.parse_one(sql, dialect=dialect)
        except Exception as exc:  # noqa: BLE001 — 复检不过一律归为编译失败
            raise ApiError(QUERY_COMPILE_FAILED, "编译产物语法复检失败", 400,
                           {"error": str(exc)[:300], "sql": sql}) from exc
        return tree.sql(dialect=dialect), params_json, mask_rules
