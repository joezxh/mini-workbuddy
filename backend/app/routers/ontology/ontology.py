"""本体治理 REST 端点（P0-2：E1/E2/E3 注册 CRUD + E40 资产目录树）。

前缀 ``/api/v1/dataops`` 由父 router（``dataops.py``）提供，本模块用相对路径，
经 ``dataops.router.include_router(ontology_router)`` 单点挂载，保持 router_registry
清单不变（§6.1：并入既有 router，不新增挂载项）。

错误契约（R3）：领域错误由服务抛 :class:`ApiError`，main.py 处理器输出
``{code, message, detail?}``；本模块仅在“缺租户”这一框架前置守卫上沿用既有
``HTTPException(400, detail='tenant_required')``（非业务错误码，前端回落 detail）。
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.sys.sys_user import SysUser
from app.services.ontology.ontology_build_service import OntologyBuildService, submit_build
from app.services.ontology.ontology_agent_service import OntologyAgentService
from app.services.ontology.ontology_apppublish_service import OntologyAppPublishService
from app.services.ontology.ontology_asset_service import OntologyAssetService
from app.services.ontology.ontology_assistant_service import OntologyAssistantService
from app.services.ontology.ontology_graph_service import OntologyGraphService
from app.services.ontology.ontology_publish_service import OntologyPublishService
from app.services.ontology.ontology_review_service import OntologyReviewService
from app.services.ontology.ontology_semantic_service import OntologySemanticService
from app.services.ontology.ontology_service import OntologyService
from app.services.ontology.ontology_tag_service import OntologyTagService

router = APIRouter(tags=["DataOps 本体治理"])

TENANT_REQUIRED_DETAIL = "tenant_required"


def _require_tenant_id(current_user: SysUser) -> int:
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail=TENANT_REQUIRED_DETAIL)
    return tenant_id


def _get_service(db: Session, current_user: SysUser) -> OntologyService:
    return OntologyService(db, _require_tenant_id(current_user))


class OntologyCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, description="租户内唯一编码")
    name: str = Field(..., min_length=1, max_length=200, description="本体名称")
    description: Optional[str] = None
    namespace_uri: Optional[str] = Field(default=None, description="缺省按 urn:mwb:ontology:{code} 生成")
    root_catalog_id: Optional[int] = None


class OntologyUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    namespace_uri: Optional[str] = None
    status: Optional[str] = Field(default=None, description="draft|published|archived|stopped")
    root_catalog_id: Optional[int] = None


# ------------------------------------------------------------------ E1 列表

@router.get("/ontologies")
def list_ontologies(
    status: Optional[str] = Query(default=None, description="按状态过滤"),
    keyword: Optional[str] = Query(default=None, description="code/name 模糊"),
    sort: str = Query(default="updated_at_desc", pattern="^(updated_at_desc|name_asc)$"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = _get_service(db, current_user)
    return svc.list_ontologies(status=status, keyword=keyword, sort=sort)


# ------------------------------------------------------------------ E2 新建

@router.post("/ontologies", status_code=201)
def create_ontology(
    body: OntologyCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    obj = svc.create(
        code=body.code,
        name=body.name,
        description=body.description,
        namespace_uri=body.namespace_uri,
        root_catalog_id=body.root_catalog_id,
        creator_id=getattr(current_user, "user_id", None),
    )
    db.commit()
    return OntologyService.serialize(obj)


# --------------------------------------------------------- E40 资产目录树（须在 {id} 之前无冲突，路径不同）

@router.get("/assets/tree")
def assets_tree(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = _get_service(db, current_user)
    return svc.assets_tree()


# ------------------------------------------------------- E28 资产全文检索（P0-9）

@router.get("/assets/search")
def assets_search(
    kw: Optional[str] = Query(default=None, description="表名/列名/注释关键词（LIKE 加速，禁 similarity）"),
    source_id: Optional[int] = Query(default=None),
    tag_ids: Optional[List[int]] = Query(default=None, description="按标签过滤（可多个）"),
    kind: str = Query(default="table", pattern="^(table|column)$"),
    table_type: Optional[str] = Query(default=None, pattern="^(BASE TABLE|VIEW)$", description="对象类型过滤（AF-07；BASE TABLE 含历史 NULL 行）"),
    sort: str = Query(default="score", pattern="^(score|updated|rows)$", description="排序：相关度/更新时间/行数"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """表/字段/注释全文检索（AF-02）：返回表卡片含 ``column_digest``/``pii_max_level``/``tags``/``score``。"""
    svc = OntologyAssetService(db, _require_tenant_id(current_user))
    return svc.search(kw=kw, source_id=source_id, tag_ids=tag_ids, kind=kind,
                      page=page, size=size, table_type=table_type, sort=sort)


# -------------------------------------------------------------- E3 详情/改/删

@router.get("/ontologies/{ontology_id}")
def get_ontology(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    obj = svc.get_or_404(ontology_id)
    stats = svc._stats_for([ontology_id]).get(ontology_id)
    return OntologyService.serialize(obj, stats)


@router.put("/ontologies/{ontology_id}")
def update_ontology(
    ontology_id: int,
    body: OntologyUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = _get_service(db, current_user)
    obj = svc.update(
        ontology_id,
        updater_id=getattr(current_user, "user_id", None),
        **body.model_dump(exclude_unset=True),
    )
    db.commit()
    stats = svc._stats_for([ontology_id]).get(ontology_id)
    return OntologyService.serialize(obj, stats)


@router.delete("/ontologies/{ontology_id}", status_code=204, response_class=Response)
def delete_ontology(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Response:
    svc = _get_service(db, current_user)
    svc.delete(ontology_id)
    db.commit()
    return Response(status_code=204)


# ============================================================ E4-E8 构建任务（P0-3）


class BuildJobCreate(BaseModel):
    mode: str = Field(default="rules", description="rules | rules+semantic")
    scope: dict = Field(default_factory=dict, description="{mode,source_id,database,tables[],tag_ids[],catalog_ids[]}")
    idempotency_key: Optional[str] = Field(default=None, description="缺省服务端按 (本体+表集+模式+日) 派生")


def _default_idem_key(ontology_id: int, scope: dict, mode: str) -> str:
    tables = sorted(scope.get("tables") or [])
    parts = f"{ontology_id}|{mode}|{scope.get('source_id')}|{';'.join(tables)}|{date.today().isoformat()}"
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:64]


def _sse(event: str, data: Optional[dict] = None) -> str:
    lines = [f"event: {event}"]
    if data is not None:
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


@router.post("/ontologies/{ontology_id}/build-jobs")
def create_build_job(
    ontology_id: int,
    body: BuildJobCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> JSONResponse:
    svc = OntologyBuildService(db, _require_tenant_id(current_user))
    idem = body.idempotency_key or _default_idem_key(ontology_id, body.scope, body.mode)
    job, created = svc.create_build_job(
        ontology_id, mode=body.mode, scope=body.scope, idempotency_key=idem
    )
    db.commit()
    if created:
        submit_build(job.id, job.tenant_id)
    return JSONResponse(
        status_code=201 if created else 200,
        content={"job": OntologyBuildService.serialize_job(job), "created": created},
    )


@router.get("/ontologies/{ontology_id}/build-jobs")
def list_build_jobs(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = OntologyBuildService(db, _require_tenant_id(current_user))
    return svc.list_build_jobs(ontology_id)


@router.get("/build-jobs/{job_id}")
def get_build_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyBuildService(db, _require_tenant_id(current_user))
    return svc.get_build_job(job_id)


@router.post("/build-jobs/{job_id}/cancel")
def cancel_build_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyBuildService(db, _require_tenant_id(current_user))
    job = svc.cancel_build_job(job_id)
    db.commit()
    return OntologyBuildService.serialize_job(job)


@router.get("/build-jobs/{job_id}/stream")
def stream_build_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> StreamingResponse:
    """SSE 进度流（§6.2）：每秒轮询 job 行，phase/progress 变化即推送，终态收尾。"""
    tenant_id = _require_tenant_id(current_user)
    OntologyBuildService(db, tenant_id)._job_or_404(job_id)  # 早校验，缺失即 404

    def gen():
        from app.db.database import SessionLocal
        sdb = SessionLocal()
        try:
            esvc = OntologyBuildService(sdb, tenant_id)
            last_phase = last_progress = None
            t0 = last_ping = time.monotonic()
            while True:
                snap = esvc.job_snapshot(job_id)
                if snap is None:
                    yield _sse("error", {"code": "ONTOLOGY_NOT_FOUND", "message": "job not found"})
                    return
                if snap["phase"] != last_phase or snap["progress"] != last_progress:
                    last_phase, last_progress = snap["phase"], snap["progress"]
                    yield _sse("phase", {"phase": snap["phase"], "progress": snap["progress"]})
                st = snap["status"]
                if st == "succeeded":
                    yield _sse("done", {"status": "succeeded", "stats": snap["stats"]})
                    return
                if st in ("failed", "cancelled"):
                    yield _sse("error", {"code": snap["error_code"] or "BUILD_FAILED", "message": st})
                    return
                if time.monotonic() - t0 > 3600:
                    yield _sse("error", {"code": "BUILD_TIMEOUT", "message": "stream timeout"})
                    return
                if time.monotonic() - last_ping >= 15:
                    yield _sse("ping")
                    last_ping = time.monotonic()
                time.sleep(1)
        finally:
            sdb.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ============================================================ E9-E10 审阅台（P0-4）


class ReviewItem(BaseModel):
    id: int = Field(..., description="build_item 主键")
    action: str = Field(..., description="accept | reject")


class ReviewBody(BaseModel):
    items: List[ReviewItem] = Field(default_factory=list)
    accept_all: bool = False
    reject_all: bool = False


@router.get("/ontologies/{ontology_id}/review-queue")
def review_queue(
    ontology_id: int,
    kind: Optional[str] = Query(default=None, description="object|property|relation|mapping"),
    status: str = Query(default="suggested"),
    origin: Optional[str] = Query(default=None, description="rule|llm"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyReviewService(db, _require_tenant_id(current_user))
    return svc.review_queue(ontology_id, kind=kind, status=status, origin=origin, page=page, size=size)


@router.post("/ontologies/{ontology_id}/review")
def review(
    ontology_id: int,
    body: ReviewBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyReviewService(db, _require_tenant_id(current_user))
    result = svc.review(
        ontology_id,
        items=[i.model_dump() for i in body.items],
        accept_all=body.accept_all,
        reject_all=body.reject_all,
        reviewed_by=getattr(current_user, "user_id", None),
    )
    db.commit()
    return result


# ============================================================ E11-E13 发布与版本（P0-5）


class PublishBody(BaseModel):
    change_note: Optional[str] = Field(default=None, description="变更说明")
    override_pending: bool = Field(default=False, description="忽略 N 条待审，仅发布已采纳（门禁 1）")
    mask_exemptions: List[int] = Field(default_factory=list, description="门禁 5 豁免的 column_id 列表（留痕）")


@router.post("/ontologies/{ontology_id}/publish")
def publish_ontology(
    ontology_id: int,
    body: PublishBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """发布：D3 出口层断言先行 → 5 项门禁 → 版本快照 + diff → current_version 自增。"""
    svc = OntologyPublishService(db, _require_tenant_id(current_user))
    result = svc.publish(
        ontology_id,
        change_note=body.change_note,
        author_user_id=getattr(current_user, "user_id", None),
        override_pending=body.override_pending,
        mask_exemptions=body.mask_exemptions,
    )
    db.commit()
    return result


@router.get("/ontologies/{ontology_id}/versions")
def list_versions(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = OntologyPublishService(db, _require_tenant_id(current_user))
    return svc.list_versions(ontology_id)


@router.get("/ontologies/{ontology_id}/versions/{version}")
def get_version(
    ontology_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyPublishService(db, _require_tenant_id(current_user))
    return svc.get_version(ontology_id, version)


# ============================================================ E16-E17 消费面（P0-6）


@router.get("/ontologies/{ontology_id}/graph")
def get_graph(
    ontology_id: int,
    view: str = Query(default="workflow", pattern="^(workflow|architecture)$",
                       description="workflow=表→对象拓扑 | architecture=对象↔关系力导向"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """schema 图（nodes/edges）：取 ``review_status=accepted`` 对象/关系，``status`` 不参与。"""
    svc = OntologyGraphService(db, _require_tenant_id(current_user))
    return svc.graph(ontology_id, view=view)


@router.get("/ontologies/{ontology_id}/evidence")
def get_evidence(
    ontology_id: int,
    element_kind: Optional[str] = Query(default=None, description="object|property|relation|mapping"),
    element_code: Optional[str] = Query(default=None, description="元素 code 精确过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """证据链：按元素检索 ``onto_ontology_evidence`` 原始依据（可复核）。"""
    svc = OntologyGraphService(db, _require_tenant_id(current_user))
    return svc.evidence(ontology_id, element_kind=element_kind, element_code=element_code)


# ==================================================== E24-E26 Agent 只读导航（P0-7）


class BrowseBody(BaseModel):
    query: Optional[str] = Field(default=None, description="非空检索词；空则拒绝全量枚举")


class ResolveBody(BaseModel):
    codes: List[str] = Field(default_factory=list, description="待解析对象 code（≤5）")


@router.get("/ontologies/{ontology_id}/manifest")
def agent_manifest(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Agent 自述（版本/对象概览/关系统计/CQ 通过率）；无版本时 ``needs_build=true``。"""
    svc = OntologyAgentService(db, _require_tenant_id(current_user))
    return svc.manifest(ontology_id)


@router.post("/ontologies/{ontology_id}/semantics/browse")
def agent_browse(
    ontology_id: int,
    body: BrowseBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Agent 只读浏览（≤6）；空 query 拒绝全量枚举。"""
    svc = OntologyAgentService(db, _require_tenant_id(current_user))
    return svc.browse(ontology_id, body.query)


@router.post("/ontologies/{ontology_id}/semantics/resolve")
def agent_resolve(
    ontology_id: int,
    body: ResolveBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """Agent 定点解析（≤5 code）；不可见 code 归 not_found。"""
    svc = OntologyAgentService(db, _require_tenant_id(current_user))
    return svc.resolve(ontology_id, body.codes)


# ==================================================== E21-E22 LLM 语义补全（P0-8）


class SuggestBody(BaseModel):
    element_kind: str = Field(default="object", pattern="^(object|relation)$")
    element_codes: Optional[List[str]] = Field(default=None, description="限定元素子集（空=全部 accepted）")
    model_id: Optional[int] = Field(default=None, description="指定模型（空=默认）")


@router.post("/ontologies/{ontology_id}/semantics/suggest")
def semantics_suggest(
    ontology_id: int,
    body: SuggestBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """LLM 语义补全：只为已存在元素产文本建议（D3：永不直写结构）；模型不可用则 503。"""
    svc = OntologySemanticService(db, _require_tenant_id(current_user))
    result = svc.suggest(
        ontology_id, element_kind=body.element_kind,
        element_codes=body.element_codes, model_id=body.model_id,
    )
    db.commit()
    return result


@router.post("/ontologies/{ontology_id}/semantics/{semantic_id}/adopt")
def semantics_adopt(
    ontology_id: int,
    semantic_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """采纳一条语义建议 → 回写已存在元素文本列 + source 改写 human（§5.1）。"""
    svc = OntologySemanticService(db, _require_tenant_id(current_user))
    result = svc.adopt(ontology_id, semantic_id, adopted_by=getattr(current_user, "user_id", None))
    db.commit()
    return result


# ==================================================== E33 作用域草稿送数（P0-9）


class DraftScopeBody(BaseModel):
    mode: str = Field(default="tables", description="tables|tags|catalog")
    source_id: Optional[int] = None
    db_name: Optional[str] = None
    database: Optional[str] = None
    tables: List[str] = Field(default_factory=list)
    tag_ids: List[int] = Field(default_factory=list)
    catalog_ids: List[int] = Field(default_factory=list)
    origin: Optional[str] = Field(default=None, description="asset_picker|assistant|manual|tag|catalog（仅溯源）")
    clear: bool = Field(default=False, description="显式清空（空清单时唯一合法写入方式）")


@router.get("/ontologies/{ontology_id}/draft-scope")
def get_draft_scope(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyAssetService(db, _require_tenant_id(current_user))
    return svc.get_draft_scope(ontology_id)


@router.put("/ontologies/{ontology_id}/draft-scope")
def put_draft_scope(
    ontology_id: int,
    body: DraftScopeBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """送数（AF-08）：全量覆盖 ``draft_scope_json``；**不写结构表**。"""
    svc = OntologyAssetService(db, _require_tenant_id(current_user))
    result = svc.put_draft_scope(ontology_id, body.model_dump(exclude_none=True))
    db.commit()
    return result


@router.delete("/ontologies/{ontology_id}/draft-scope")
def delete_draft_scope(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyAssetService(db, _require_tenant_id(current_user))
    result = svc.delete_draft_scope(ontology_id)
    db.commit()
    return result


# ==================================================== E29-E32 资产标签体系（P0-10）


class TagCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=64)
    color: Optional[str] = Field(default=None, max_length=16)
    tag_kind: str = Field(default="custom", description="biz|security|quality|custom")
    description: Optional[str] = None


class TagUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    color: Optional[str] = None
    tag_kind: Optional[str] = None
    description: Optional[str] = None


class BindBody(BaseModel):
    tag_id: int
    asset_kind: str = Field(..., description="table|column")
    asset_ids: List[int] = Field(default_factory=list)
    op: str = Field(default="bind", pattern="^(bind|unbind)$")


@router.get("/asset-tags")
def list_asset_tags(
    kind: Optional[str] = Query(default=None, description="按 tag_kind 过滤"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    svc = OntologyTagService(db, _require_tenant_id(current_user))
    return svc.list_tags(kind=kind)


@router.post("/asset-tags", status_code=201)
def create_asset_tag(
    body: TagCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyTagService(db, _require_tenant_id(current_user))
    result = svc.create_tag(
        code=body.code, name=body.name, color=body.color, tag_kind=body.tag_kind,
        description=body.description, creator_id=getattr(current_user, "user_id", None),
    )
    db.commit()
    return result


@router.put("/asset-tags/{tag_id}")
def update_asset_tag(
    tag_id: int,
    body: TagUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    svc = OntologyTagService(db, _require_tenant_id(current_user))
    result = svc.update_tag(tag_id, **body.model_dump(exclude_unset=True))
    db.commit()
    return result


@router.delete("/asset-tags/{tag_id}", status_code=204, response_class=Response)
def delete_asset_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> Response:
    svc = OntologyTagService(db, _require_tenant_id(current_user))
    svc.delete_tag(tag_id)
    db.commit()
    return Response(status_code=204)


@router.post("/asset-tags/bind")
def bind_asset_tag(
    body: BindBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """批量打标/摘标（幂等）：同一 ``tag_id`` 对多个资产 ``bind``/``unbind``。"""
    svc = OntologyTagService(db, _require_tenant_id(current_user))
    result = svc.bind(
        tag_id=body.tag_id, asset_kind=body.asset_kind, asset_ids=body.asset_ids,
        op=body.op, created_by=getattr(current_user, "user_id", None),
    )
    db.commit()
    return result


# ================================================ E34-E36 应用发布登记（P0-11）


class AppPublishCreate(BaseModel):
    target_type: str = Field(..., description="skill|http|mcp")
    code: str = Field(..., min_length=1, max_length=64, description="目标侧唯一标识")
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    payload: Optional[dict] = Field(default=None, description="{tools[],input_schema,endpoint,...}")


class AppPublishToggle(BaseModel):
    status: str = Field(..., pattern="^(enabled|disabled)$")


@router.get("/ontologies/{ontology_id}/publishes")
def list_app_publishes(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> list:
    """应用发布登记列表（含 ``stale`` 标记：登记版本落后于 current_version）。"""
    svc = OntologyAppPublishService(db, _require_tenant_id(current_user))
    return svc.list_publishes(ontology_id)


@router.post("/ontologies/{ontology_id}/publishes", status_code=201)
def create_app_publish(
    ontology_id: int,
    body: AppPublishCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """登记一个发布目标：仅钉 ``version=current_version``；草稿态强制 ``disabled``。"""
    svc = OntologyAppPublishService(db, _require_tenant_id(current_user))
    result = svc.register(
        ontology_id, target_type=body.target_type, code=body.code, name=body.name,
        description=body.description, payload=body.payload,
        creator_id=getattr(current_user, "user_id", None),
    )
    db.commit()
    return result


@router.put("/ontologies/{ontology_id}/publishes/{publish_id}/toggle")
def toggle_app_publish(
    ontology_id: int,
    publish_id: int,
    body: AppPublishToggle,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """启停一个发布登记（``enabled``/``disabled``）。"""
    svc = OntologyAppPublishService(db, _require_tenant_id(current_user))
    result = svc.toggle(ontology_id, publish_id, status=body.status)
    db.commit()
    return result


# ================================================ E37-E38 建模助手 + 链路拓扑（P0-12）


class AssistantBody(BaseModel):
    intent: str = Field(..., description="ask|explain|propose_scope|build（白名单硬校）")
    utterance: str = Field(default="", description="自然语言输入")
    context: Optional[dict] = Field(
        default=None, description="前端显式携带：当前页签/选中元素 code/当前 scope/candidates/fingerprint"
    )
    commit: bool = Field(default=False, description="仅 build 档生效：false 预览零写入，true 需回传指纹")


@router.post("/ontologies/{ontology_id}/assistant")
def ontology_assistant(
    ontology_id: int,
    body: AssistantBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """四档建模助手统一入口（§5.6）：``ask``/``explain``/``propose_scope``/``build``。

    助手**绝不建 build_job / 不调 review / 不调 publish**；``build`` 档两步提交，
    仅落 ``build_item(origin='llm', status='suggested')``（§5.7 三层防线）。未知 ``intent``
    直接 ``ASSISTANT_INTENT_UNSUPPORTED``。LLM 不可用一律降级，不阻断主链路。
    """
    svc = OntologyAssistantService(db, _require_tenant_id(current_user))
    result = svc.handle(
        ontology_id, intent=body.intent, utterance=body.utterance, context=body.context,
        commit=body.commit, user_id=getattr(current_user, "user_id", None),
    )
    db.commit()
    return result


@router.get("/ontologies/{ontology_id}/pipeline")
def ontology_pipeline(
    ontology_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
) -> dict:
    """五步链路拓扑各环节计数与状态（§6.6），供前端 PipelineBar 渲染（只读）。"""
    svc = OntologyAssistantService(db, _require_tenant_id(current_user))
    return svc.pipeline(ontology_id)
