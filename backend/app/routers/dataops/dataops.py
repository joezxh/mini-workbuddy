"""DataOps 数据源 REST 端点（P2 Task 2，prefix /api/v1/dataops）。

安全约定：
- 所有端点要求登录（get_current_user）且用户必须有租户（400 tenant_required）；
- 数据访问一律经 DataSourceService（租户过滤），跨租户访问即 404；
- API 响应永不返回密码，只回 has_password。
"""
from __future__ import annotations

from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.dataops.data_source_service import DataSourceService, enabled_types

router = APIRouter(prefix="/api/v1/dataops", tags=["DataOps 数据源"])

TENANT_REQUIRED_DETAIL = "tenant_required"


def _require_tenant_id(current_user: SysUser) -> int:
    """取当前用户租户 ID；为空则拒绝（不落 NULL 分区共享）。"""
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)
    return tenant_id


def _get_service(db: Session, current_user: SysUser) -> DataSourceService:
    return DataSourceService(db, _require_tenant_id(current_user))


class DataSourceCreate(BaseModel):
    name: str = Field(..., description="显示名称")
    source_type: str = Field(..., description="数据源类型（字典 data_source_type 启用项 item_code）")
    host: str = Field(default="", description="主机（excel 型可空）")
    port: int = Field(default=0, ge=0, le=65535, description="端口（excel 型可 0）")
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, description="明文只在创建/更新时接收，永不回显")
    database: Optional[str] = None
    charset: str = "utf8mb4"
    is_default: bool = False
    config: Optional[dict] = Field(default=None, description="类型特有参数（dbSchema/mode/timeout 等，禁含凭据）")


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, description="空串/缺省=不改")
    database: Optional[str] = None
    charset: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None
    config: Optional[dict] = Field(default=None, description="整体替换类型特有参数；缺省=不改")


class SourceTestRequest(BaseModel):
    """未保存表单探活（新建/编辑弹窗「测试连接」）。"""
    source_type: str
    host: str = ""
    port: int = Field(default=0, ge=0, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    config: Optional[dict] = None


@router.post("/sources", status_code=201)
def create_source(
    body: DataSourceCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    try:
        obj = svc.create(
            name=body.name,
            source_type=body.source_type,
            host=body.host,
            port=body.port,
            username=body.username,
            password=body.password,
            database=body.database,
            charset=body.charset,
            is_default=body.is_default,
            creator_id=getattr(current_user, "user_id", None),
            config=body.config,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="数据源创建失败，请稍后重试")
    return DataSourceService.to_dict(obj)


@router.get("/sources")
def list_sources(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = _get_service(db, current_user)
    return [DataSourceService.to_dict(o) for o in svc.list_sources()]


@router.get("/sources/{source_id}")
def get_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    try:
        obj = svc.get_or_404(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return DataSourceService.to_dict(obj)


@router.put("/sources/{source_id}")
def update_source(
    source_id: int,
    body: DataSourceUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    try:
        obj = svc.update(
            source_id,
            updater_id=getattr(current_user, "user_id", None),
            **body.model_dump(),
        )
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="数据源更新失败，请稍后重试")
    return DataSourceService.to_dict(obj)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    svc = _get_service(db, current_user)
    try:
        obj = svc.get(source_id)
        source_type = obj.source_type if obj else None
        removed = svc.delete(source_id)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="数据源删除失败，请稍后重试")
    if not removed:
        raise HTTPException(status_code=404, detail="数据源不存在")
    # Excel/CSV 型：连带清理其隔离落库 schema（尽力而为，失败不阻断删除）
    if source_type == "excel":
        from app.db.database import engine as system_engine
        from app.ai.dataops.dialects.excel_pg import schema_name_for
        from app.services.dataops.excel_ingest_service import ExcelIngestService
        try:
            ExcelIngestService(system_engine, schema_name_for(source_id)).drop_schema()
        except Exception:  # noqa: BLE001
            pass


# ====================================================================== #
# 类型字典 / 探活（类型体系扩展新增）
# ====================================================================== #
@router.get("/source-types")
def list_source_types(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """数据字典 data_source_type 启用项（含动态表单 fields），前端下拉与展示同源。"""
    tenant_id = _require_tenant_id(current_user)
    types = enabled_types(db, tenant_id)
    return [
        {"code": code, **meta}
        for code, meta in sorted(types.items(), key=lambda kv: (kv[1].get("sort") or 0, kv[0]))
    ]


@router.post("/sources/test")
def test_source_draft(
    body: SourceTestRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """未保存参数探活：不落库，只回 (ok, error)。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        ok, error = svc.test_draft(
            source_type=body.source_type, host=body.host, port=body.port,
            username=body.username, password=body.password,
            database=body.database, config=body.config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": ok, "error": error}


@router.post("/sources/{source_id}/test")
def test_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """已保存数据源探活；结果同步回写 status（online/offline）。"""
    tenant_id = _require_tenant_id(current_user)
    ds_svc = _get_service(db, current_user)
    try:
        ds = ds_svc.get_or_404(source_id)
        ok, error = MetaScanService(db, tenant_id).test_saved(source_id)
        ds.status = "online" if ok else "offline"
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except Exception as exc:  # noqa: BLE001 - 建连异常面向管理员，保留原因摘要
        db.rollback()
        raise HTTPException(status_code=500, detail=f"探活异常：{str(exc)[:300]}")
    return {"ok": ok, "error": error, "status": ds.status}


# ====================================================================== #
# 元数据扫描 / 查询 / 写审批（P2 Task 7 / 9 / 10）
# ====================================================================== #
from app.ai.dataops.dialects.registry import get_adapter  # noqa: E402  (置于路由区，便于阅读)
from app.models.dataops.meta import MetaColumn, MetaScanJob, MetaTable
from app.models.dataops.write_request import DataWriteRequest
from app.services.dataops.query_service import ReadonlyQueryService
from app.services.dataops.scan_service import MetaScanService
from app.services.dataops.write_request_service import DataWriteRequestService


def _scan_job_to_dict(o: MetaScanJob) -> dict:
    return {
        "id": o.id,
        "source_id": o.source_id,
        "database": o.database,
        "job_kind": o.job_kind,
        "status": o.status,
        "progress": o.progress,
        "with_profile": bool(o.with_profile),
        "tables": o.tables_json,
        "stats": o.stats_json,
        "error_detail": o.error_detail,
        "duration_ms": o.duration_ms,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "finished_at": o.finished_at.isoformat() if o.finished_at else None,
    }


def _write_request_to_dict(o: DataWriteRequest) -> dict:
    # 永不返回 sql_text 全文与 token 之外还需避免 token 泄露；此处不返回 token
    return {
        "id": o.id,
        "source_id": o.source_id,
        "database": o.database,
        "statement_type": o.statement_type,
        "status": o.status,
        "sql_preview": (o.sql_text[:200] + "…") if len(o.sql_text) > 200 else o.sql_text,
        "applicant_id": o.applicant_id,
        "approver_id": o.approver_id,
        "token_consumed": bool(o.token_consumed),
        "expires_at": o.expires_at.isoformat() if o.expires_at else None,
        "executed_at": o.executed_at.isoformat() if o.executed_at else None,
        "result": o.result_json,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


class ScanRequest(BaseModel):
    database: str = Field(..., description="待扫描库/schema（PG 族=schema）")
    connect_database: Optional[str] = Field(
        default=None, description="PG 族跨物理库扫描时的连接目标覆盖（缺省连数据源配置库）")
    with_profile: bool = Field(default=False, description="是否顺带列画像")


class QueryRequest(BaseModel):
    sql: str = Field(..., description="单条只读查询（SqlGuard 校验）")
    limit: int = Field(default=100, ge=1, le=5000)


class WriteRequestCreate(BaseModel):
    source_id: int
    sql_text: str = Field(..., description="写语句（INSERT/UPDATE/DELETE/DDL）")
    database: Optional[str] = None


class WriteExecute(BaseModel):
    token: str = Field(..., description="批准后发放的一次性令牌")


@router.post("/sources/{source_id}/scan", status_code=201)
def scan_source(
    source_id: int,
    body: ScanRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        job = svc.start_scan(
            source_id, body.database, with_profile=body.with_profile,
            creator_id=getattr(current_user, "user_id", None),
            connect_database=body.connect_database,
        )
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="扫描失败，请稍后重试")
    return _scan_job_to_dict(job)


@router.get("/sources/{source_id}/tables")
def list_tables(
    source_id: int,
    database: Optional[str] = None,
    db_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """已入库表快照查询：可按 database (schema) + db_name (物理库) 过滤。"""
    tenant_id = _require_tenant_id(current_user)
    _get_service(db, current_user).get_or_404(source_id)  # 租户隔离校验
    stmt = select(MetaTable).where(
        MetaTable.tenant_id == tenant_id, MetaTable.source_id == source_id
    )
    if database:
        stmt = stmt.where(MetaTable.database == database)
    if db_name:
        stmt = stmt.where(MetaTable.db_name == db_name)
    rows = db.execute(stmt.order_by(MetaTable.table_name)).scalars().all()
    return [
        {
            "id": r.id,
            "db_name": r.db_name,
            "database": r.database,
            "table_name": r.table_name,
            "table_type": r.table_type,
            "table_comment": r.table_comment,
            "row_count": r.row_count,
            "column_count": r.column_count,
            "domain": r.domain,
            "profiled_at": r.profiled_at.isoformat() if r.profiled_at else None,
        }
        for r in rows
    ]


@router.get("/sources/{source_id}/tables/{table_id}/columns")
def list_meta_columns(
    source_id: int,
    table_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """已入库的列快照（meta_column）：按表 ID 查，供元数据浏览右侧列信息面板。"""
    tenant_id = _require_tenant_id(current_user)
    _get_service(db, current_user).get_or_404(source_id)  # 租户隔离校验
    mt = db.execute(
        select(MetaTable).where(
            MetaTable.id == table_id,
            MetaTable.tenant_id == tenant_id,
            MetaTable.source_id == source_id,
        )
    ).scalar_one_or_none()
    if mt is None:
        raise HTTPException(status_code=404, detail="表快照不存在")
    rows = db.execute(
        select(MetaColumn)
        .where(MetaColumn.table_id == mt.id, MetaColumn.tenant_id == tenant_id)
        .order_by(MetaColumn.ordinal, MetaColumn.column_name)
    ).scalars().all()
    return [
        {
            "id": c.id,
            "column_name": c.column_name,
            "ordinal": c.ordinal,
            "data_type": c.data_type,
            "column_type": c.column_type,
            "nullable": bool(c.nullable),
            "column_key": c.column_key,
            "column_default": c.column_default,
            "extra": c.extra,
            "column_comment": c.column_comment,
            "biz_name": c.biz_name,
            "semantic_type": c.semantic_type,
            "pii_level": c.pii_level,
            "profile_json": c.profile_json,
        }
        for c in rows
    ]


# ---------------------------------------------------------------------- #
# 远端浏览 / 选表导入（类型体系扩展新增，SQLBot 式先探后选再导入）
# ---------------------------------------------------------------------- #
class ImportTablesRequest(BaseModel):
    database: str = Field(..., description="远端作用域（库/schema/owner，按类型语义；PG 族为物理库名）")
    schema_name: Optional[str] = Field(default=None, alias="schema",
                                       description="PG 族三级导入的模式名（非 PG 族忽略）")
    tables: List[str] = Field(..., min_length=1, description="勾选导入的表名列表")
    with_profile: bool = Field(default=False, description="导入时顺带列画像")

    model_config = {"populate_by_name": True}


@router.get("/sources/{source_id}/remote/databases")
def list_remote_databases(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """实时列出远端可扫描作用域（库/schema/owner；ES 返回单伪作用域）。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        return svc.list_remote_databases(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 连不上时把原因回给管理员
        raise HTTPException(status_code=500, detail=f"远端访问失败：{str(exc)[:300]}")


@router.get("/sources/{source_id}/remote/schemas")
def list_remote_schemas(
    source_id: int,
    database: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """PG 族导入向导第二级：按所选物理库重连，列出该库的用户 schema。非 PG 族返回空列表。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        return svc.list_remote_schemas(source_id, database)
    except KeyError:
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"远端访问失败：{str(exc)[:300]}")


@router.get("/sources/{source_id}/remote/tables")
def list_remote_tables(
    source_id: int,
    database: str,
    schema: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """实时列出远端表（导入前的勾选清单，不写元数据快照）。

    PG 族：``database``=物理库（按其重连）、``schema``=表所在模式；
    其余族沿用 ``database`` 作限定作用域（向后兼容）。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        return svc.list_remote_tables(source_id, database, schema=schema)
    except KeyError:
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"远端访问失败：{str(exc)[:300]}")


@router.get("/sources/{source_id}/remote/columns")
def list_remote_columns(
    source_id: int,
    database: str,
    table: str,
    schema: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """实时列出远端单表字段（导入前预览；PG 族三级语义同 tables）。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        return svc.list_remote_columns(source_id, database, table, schema=schema)
    except KeyError:
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"远端访问失败：{str(exc)[:300]}")


@router.post("/sources/{source_id}/import-tables", status_code=201)
def import_tables(
    source_id: int,
    body: ImportTablesRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """SQLBot 式选表导入：把勾选表的表/列快照写入 meta_table/meta_column。"""
    svc = MetaScanService(db, _require_tenant_id(current_user))
    try:
        return svc.import_tables(
            source_id, body.database, body.tables, with_profile=body.with_profile,
            creator_id=getattr(current_user, "user_id", None),
            schema=body.schema_name,
        )
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - 导入失败原因面向管理员
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入失败：{str(exc)[:300]}")


# ---------------------------------------------------------------------- #
# Excel/CSV 上传入库（类型体系扩展 P5）
# ---------------------------------------------------------------------- #
@router.post("/sources/{source_id}/excel/ingest", status_code=201)
async def ingest_excel(
    source_id: int,
    file: UploadFile = File(..., description=".csv/.xlsx/.xls，每个工作表落一张 PG 表"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Excel/CSV 型数据源上传入库：解析后写入隔离 schema ``excel_ds_<id>``。"""
    from app.db.database import engine as system_engine
    from app.ai.dataops.dialects.excel_pg import schema_name_for
    from app.services.dataops.excel_ingest_service import (
        ExcelIngestService, load_frames, save_original,
    )

    tenant_id = _require_tenant_id(current_user)
    ds = _get_service(db, current_user).get_or_404(source_id)  # 租户隔离校验
    if ds.source_type != "excel":
        raise HTTPException(status_code=400, detail="仅 Excel/CSV 型数据源支持文件上传入库")
    content = await file.read()
    try:
        frames = load_frames(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 解析库异常（损坏文件等）
        raise HTTPException(status_code=400, detail=f"文件解析失败：{str(exc)[:300]}")
    schema = schema_name_for(ds.id)
    try:
        summary = ExcelIngestService(system_engine, schema).ingest(frames)
    except Exception as exc:  # noqa: BLE001 - 建表/写入失败回给管理员
        raise HTTPException(status_code=500, detail=f"入库失败：{str(exc)[:300]}")
    stored = save_original(Path(settings.UPLOAD_DIR), tenant_id, ds.id,
                           file.filename or "unnamed", content)
    return {"schema": schema, "tables": summary, "stored_path": stored}


@router.post("/sources/{source_id}/query")
def run_query(
    source_id: int,
    body: QueryRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = ReadonlyQueryService(db, _require_tenant_id(current_user))
    try:
        result = svc.run(source_id, body.sql, body.limit)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="查询执行失败，请稍后重试")
    return {
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
    }


@router.post("/write-requests", status_code=201)
def create_write_request(
    body: WriteRequestCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = DataWriteRequestService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create_request(
            body.source_id, body.sql_text, body.database,
            applicant_id=getattr(current_user, "user_id", None),
        )
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="写申请创建失败，请稍后重试")
    return _write_request_to_dict(obj)


@router.get("/write-requests")
def list_write_requests(
    source_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = DataWriteRequestService(db, _require_tenant_id(current_user))
    return [_write_request_to_dict(o) for o in svc.list_requests(source_id)]


@router.get("/write-requests/{request_id}")
def get_write_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = DataWriteRequestService(db, _require_tenant_id(current_user))
    try:
        obj = svc.get_or_404(request_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="写申请不存在")
    return _write_request_to_dict(obj)


@router.post("/write-requests/{request_id}/approve", status_code=200)
def approve_write_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = DataWriteRequestService(db, _require_tenant_id(current_user))
    try:
        obj = svc.approve(request_id, approver_id=getattr(current_user, "user_id", None))
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="写申请不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="审批失败，请稍后重试")
    return _write_request_to_dict(obj)


@router.post("/write-requests/{request_id}/execute", status_code=200)
def execute_write_request(
    request_id: int,
    body: WriteExecute,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = DataWriteRequestService(db, _require_tenant_id(current_user))
    try:
        obj = svc.execute(request_id, body.token, executor_id=getattr(current_user, "user_id", None))
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="写申请不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="执行失败，请稍后重试")
    return _write_request_to_dict(obj)


# ====================================================================== #
# 标准项 / 标准绑定 / 关系推断（P2 Task 11 / Task 13）
# ====================================================================== #
from app.models.dataops.standard import MetaStandard  # noqa: E402
from app.services.dataops.object_standard_service import MetaObjectStandardService  # noqa: E402
from app.services.dataops.relation_inference_service import RelationInferenceService
from app.services.dataops.standard_binding_service import StandardBindingService
from app.services.dataops.standard_catalog_service import MetaStandardCatalogService  # noqa: E402
from app.services.dataops.standard_service import MetaStandardService


class StandardCreate(BaseModel):
    code: str
    name: str
    aliases: Optional[list] = None
    semantic_type: Optional[str] = None
    security_level: Optional[str] = None
    data_type_expect: Optional[str] = None
    domain: Optional[str] = None


class BindRequest(BaseModel):
    database: Optional[str] = None


class InferRequest(BaseModel):
    database: Optional[str] = None
    with_overlap: bool = False


@router.post("/standards/seed", status_code=201)
def seed_standards(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardService(db, _require_tenant_id(current_user))
    try:
        created = svc.seed_builtins()
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="标准种子失败，请稍后重试")
    return {"created": created}


@router.get("/standards")
def list_standards(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = MetaStandardService(db, _require_tenant_id(current_user))
    return [MetaStandardService.serialize(s) for s in svc.list_standards()]


@router.post("/standards", status_code=201)
def create_standard(
    body: StandardCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create(
            body.code, body.name, aliases=body.aliases,
            semantic_type=body.semantic_type, security_level=body.security_level,
            data_type_expect=body.data_type_expect, domain=body.domain,
            creator_id=getattr(current_user, "user_id", None),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="标准创建失败，请稍后重试")
    return MetaStandardService.serialize(obj)


class StandardUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    aliases: Optional[list] = None
    semantic_type: Optional[str] = None
    security_level: Optional[str] = None
    data_type_expect: Optional[str] = None
    domain: Optional[str] = None


@router.put("/standards/{standard_id}")
def update_standard(
    standard_id: int,
    body: StandardUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.update(
            standard_id,
            **body.model_dump(exclude_none=True),
        )
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="标准项不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="标准更新失败，请稍后重试")
    return MetaStandardService.serialize(obj)


@router.delete("/standards/{standard_id}")
def delete_standard(
    standard_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardService(db, _require_tenant_id(current_user))
    try:
        svc.delete(standard_id)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="标准项不存在")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="标准删除失败，请稍后重试")
    return {"deleted": standard_id}


# ---------------------------------------------------------------------- #
# 标准中心（CDM）：目录/场景 + 对象标准 + 引用属性
# ---------------------------------------------------------------------- #
class CatalogCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    description: Optional[str] = None


class CatalogUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class CatalogMove(BaseModel):
    parent_id: Optional[int] = None


class ObjectAttrRef(BaseModel):
    standard_id: int
    required: bool = False
    sort_order: Optional[int] = None
    security_level_override: Optional[str] = None
    note: Optional[str] = None


class ObjectCreate(BaseModel):
    code: str
    name: str
    catalog_id: Optional[int] = None
    aliases: Optional[list] = None
    domain: Optional[str] = None
    description: Optional[str] = None


class ObjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    catalog_id: Optional[int] = None
    aliases: Optional[list] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ObjectAttributesBody(BaseModel):
    items: List[ObjectAttrRef]


@router.get("/standards/catalogs")
def list_catalogs(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    return svc.list_tree()


@router.post("/standards/catalogs", status_code=201)
def create_catalog(
    body: CatalogCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create(
            body.code, body.name, parent_id=body.parent_id, icon=body.icon,
            description=body.description,
            creator_id=getattr(current_user, "user_id", None),
        )
        db.commit()
    except (KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="目录创建失败，请稍后重试")
    return MetaStandardCatalogService.serialize(obj)


@router.put("/standards/catalogs/{catalog_id}")
def update_catalog(
    catalog_id: int,
    body: CatalogUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.update(catalog_id, **body.model_dump(exclude_none=True))
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="目录不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="目录更新失败，请稍后重试")
    return MetaStandardCatalogService.serialize(obj)


@router.put("/standards/catalogs/{catalog_id}/move")
def move_catalog(
    catalog_id: int,
    body: CatalogMove,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        obj = svc.move(catalog_id, body.parent_id)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="目录不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="目录移动失败，请稍后重试")
    return MetaStandardCatalogService.serialize(obj)


@router.delete("/standards/catalogs/{catalog_id}")
def delete_catalog(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaStandardCatalogService(db, _require_tenant_id(current_user))
    try:
        svc.delete(catalog_id)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="目录不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="目录删除失败，请稍后重试")
    return {"deleted": catalog_id}


@router.get("/standards/objects")
def list_objects(
    catalog_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    return [MetaObjectStandardService.serialize(o) for o in svc.list(catalog_id)]


@router.post("/standards/objects", status_code=201)
def create_object(
    body: ObjectCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.create(
            body.code, body.name, catalog_id=body.catalog_id, aliases=body.aliases,
            domain=body.domain, description=body.description,
            creator_id=getattr(current_user, "user_id", None),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="对象标准创建失败，请稍后重试")
    return MetaObjectStandardService.serialize(obj)


@router.get("/standards/objects/{object_id}")
def get_object(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.get_or_404(object_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="对象标准不存在")
    data = MetaObjectStandardService.serialize(obj)
    data["attributes"] = svc.get_attributes(object_id)
    return data


@router.put("/standards/objects/{object_id}")
def update_object(
    object_id: int,
    body: ObjectUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        obj = svc.update(object_id, **body.model_dump(exclude_none=True))
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="对象标准不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="对象标准更新失败，请稍后重试")
    return MetaObjectStandardService.serialize(obj)


@router.put("/standards/objects/{object_id}/attributes")
def set_object_attributes(
    object_id: int,
    body: ObjectAttributesBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        svc.set_attributes(object_id, [it.model_dump() for it in body.items])
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="对象标准不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="属性引用更新失败，请稍后重试")
    return {"attributes": svc.get_attributes(object_id)}


@router.delete("/standards/objects/{object_id}")
def delete_object(
    object_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = MetaObjectStandardService(db, _require_tenant_id(current_user))
    try:
        svc.delete(object_id)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="对象标准不存在")
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="对象标准删除失败，请稍后重试")
    return {"deleted": object_id}


@router.post("/sources/{source_id}/bind", status_code=200)
def bind_source(
    source_id: int,
    body: BindRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = StandardBindingService(db, _require_tenant_id(current_user))
    try:
        report = svc.bind_source(source_id, body.database)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="绑定失败，请稍后重试")
    return {
        "tables": report.tables,
        "columns": report.columns,
        "annotated": report.annotated,
        "bound": report.bound,
        "updated": report.updated,
        "skipped_human": report.skipped_human,
        "details": report.details,
    }


@router.post("/sources/{source_id}/infer-relations", status_code=200)
def infer_relations(
    source_id: int,
    body: InferRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = RelationInferenceService(db, _require_tenant_id(current_user))
    try:
        report = svc.infer(source_id, body.database, with_overlap=body.with_overlap)
        db.commit()
    except KeyError:
        db.rollback()
        raise HTTPException(status_code=404, detail="数据源不存在")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="关系推断失败，请稍后重试")
    return {
        "scanned_pairs": report.scanned_pairs,
        "relations": report.relations,
        "pairs": [vars(p) for p in report.pairs],
        "details": report.details,
    }
