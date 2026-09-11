"""DataOps 数据源 REST 端点（P2 Task 2，prefix /api/v1/dataops）。

安全约定：
- 所有端点要求登录（get_current_user）且用户必须有租户（400 tenant_required）；
- 数据访问一律经 DataSourceService（租户过滤），跨租户访问即 404；
- API 响应永不返回密码，只回 has_password。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.dataops.data_source_service import DataSourceService

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
    source_type: str = Field(..., description="mysql | doris | postgresql")
    host: str
    port: int = Field(..., ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, description="明文只在创建/更新时接收，永不回显")
    database: Optional[str] = None
    charset: str = "utf8mb4"
    is_default: bool = False


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
        removed = svc.delete(source_id)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="数据源删除失败，请稍后重试")
    if not removed:
        raise HTTPException(status_code=404, detail="数据源不存在")


# ====================================================================== #
# 元数据扫描 / 查询 / 写审批（P2 Task 7 / 9 / 10）
# ====================================================================== #
from app.ai.dataops.dialects.registry import get_adapter  # noqa: E402  (置于路由区，便于阅读)
from app.models.dataops.meta import MetaScanJob, MetaTable
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
    database: str = Field(..., description="待扫描库/schema")
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
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    tenant_id = _require_tenant_id(current_user)
    _get_service(db, current_user).get_or_404(source_id)  # 租户隔离校验
    stmt = select(MetaTable).where(
        MetaTable.tenant_id == tenant_id, MetaTable.source_id == source_id
    )
    if database:
        stmt = stmt.where(MetaTable.database == database)
    rows = db.execute(stmt.order_by(MetaTable.table_name)).scalars().all()
    return [
        {
            "id": r.id,
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
from app.services.dataops.relation_inference_service import RelationInferenceService
from app.services.dataops.standard_binding_service import StandardBindingService
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
