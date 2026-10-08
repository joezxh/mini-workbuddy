"""表格 KB 的 db_table 定时增量同步（spec §10.8 / §3.4）。

同步配置存于 ``kb_document.meta['sync']``::

    {"enabled": true, "interval_min": 60, "source_id": 1,
     "sql": "select id, title, body from faq", "embed_field": "body"}

拉数走 DataOps ``ReadonlyQueryService``（只读 + SqlGuard + 租户隔离），落库走
``content_service.ingest_table_rows``，**覆盖同一 document_id 的切片**（先删后灌，
不是追加），因此同步是幂等的。

调度注册 ``register_table_sync_jobs`` 由主应用 lifespan 调用；作业体自带独立
Session，不复用请求会话。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy import delete as sa_delete, select

from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment

SYNC_META_KEY = "sync"
DEFAULT_INTERVAL_MIN = 60
MAX_ROWS = 5000


def get_sync_config(doc: KbDocument) -> dict:
    return dict((doc.meta or {}).get(SYNC_META_KEY) or {})


def set_sync_config(db, tenant_id: int, doc_uuid: str, config: Optional[dict]) -> KbDocument:
    """写入/清空同步配置；``config=None`` 表示停用并移除配置。"""
    doc = db.execute(
        select(KbDocument).where(
            KbDocument.uuid_code == doc_uuid,
            KbDocument.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError(f"文档不存在: {doc_uuid}")

    meta = dict(doc.meta or {})
    if config is None:
        meta.pop(SYNC_META_KEY, None)
    else:
        meta[SYNC_META_KEY] = config
    doc.meta = meta or None
    db.commit()
    return doc


def iter_sync_targets(db, tenant_id: Optional[int] = None) -> list[KbDocument]:
    """扫描需定时同步的文档：``source_type='db_table'`` 且 ``meta.sync.enabled``。"""
    stmt = select(KbDocument).where(KbDocument.source_type == "db_table")
    if tenant_id is not None:
        stmt = stmt.where(KbDocument.tenant_id == tenant_id)
    docs = db.execute(stmt).scalars().all()
    return [d for d in docs if get_sync_config(d).get("enabled") is True]


def _fetch_rows(db, tenant_id: int, cfg: dict) -> list[dict]:
    from app.services.dataops.query_service import ReadonlyQueryService

    result = ReadonlyQueryService(db, tenant_id).run(
        int(cfg["source_id"]), cfg["sql"], limit=MAX_ROWS,
    )
    columns = result.get("columns") or []
    return [dict(zip(columns, row)) for row in (result.get("rows") or [])]


def sync_table_document(db, tenant_id: int, doc_uuid: str) -> dict:
    """执行一次同步：拉数 → 覆盖切片 → 回写状态。失败写 ``error_detail`` 后原样抛出。"""
    doc = db.execute(
        select(KbDocument).where(
            KbDocument.uuid_code == doc_uuid,
            KbDocument.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise ValueError(f"文档不存在: {doc_uuid}")

    cfg = get_sync_config(doc)
    if not cfg.get("enabled"):
        raise ValueError(f"文档 {doc_uuid} 未启用定时同步")
    missing = [k for k in ("source_id", "sql", "embed_field") if not cfg.get(k)]
    if missing:
        raise ValueError(f"同步配置缺少字段: {missing}")

    try:
        rows = _fetch_rows(db, tenant_id, cfg)
        # 覆盖式同步：先清该 document_id 的旧切片，避免重复累积
        db.execute(
            sa_delete(KbSegment).where(
                KbSegment.collection == doc.collection,
                KbSegment.tenant_id == tenant_id,
                KbSegment.document_id == doc.uuid_code,
            )
        )
        db.flush()

        from app.services.kb.rag.content_service import ingest_table_rows

        count = ingest_table_rows(
            db, tenant_id, doc.collection, rows, cfg["embed_field"],
            document_id=doc.uuid_code,
        )
        meta = dict(doc.meta or {})
        meta[SYNC_META_KEY] = {**cfg, "last_sync_at": _now_iso()}
        doc.meta = meta
        doc.segment_count = count
        doc.status = "completed"
        doc.error_detail = None
        db.commit()
        return {"document_id": doc_uuid, "rows": len(rows), "ingested": count}
    except Exception as exc:  # noqa: BLE001 - 同步失败必须可观测
        db.rollback()
        failed = db.execute(
            select(KbDocument).where(
                KbDocument.uuid_code == doc_uuid,
                KbDocument.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if failed is not None:
            cfg = get_sync_config(failed)
            meta = dict(failed.meta or {})
            meta[SYNC_META_KEY] = {**cfg, "last_error": str(exc)}
            failed.meta = meta
            failed.error_detail = f"[sync] {type(exc).__name__}: {exc}"
            db.commit()
        logger.error(f"[KB 表格同步] 文档 {doc_uuid} 同步失败: {exc}")
        raise


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _job_body(doc_uuid: str, tenant_id: int) -> None:
    """APScheduler 作业体：自带独立 Session。"""
    from app.db.database import SessionLocal

    s = SessionLocal()
    try:
        sync_table_document(s, tenant_id, doc_uuid)
    except Exception as exc:  # noqa: BLE001 - 作业失败只记日志，不连带调度器
        logger.error(f"[KB 表格同步] 作业 {doc_uuid} 失败: {exc}")
    finally:
        s.close()


def register_table_sync_jobs(scheduler, session_factory) -> int:
    """按 ``meta.sync.interval_min`` 注册/刷新定时作业；返回注册数量。

    ``scheduler`` 为 ``app.state.scheduler_service.scheduler``（进程内 APScheduler）。
    幂等：同 job_id 直接 replace，重复调用不会叠加作业。
    """
    from apscheduler.triggers.interval import IntervalTrigger

    s = session_factory()
    try:
        targets = iter_sync_targets(s)
        for doc in targets:
            cfg = get_sync_config(doc)
            interval = int(cfg.get("interval_min") or DEFAULT_INTERVAL_MIN)
            if interval < 1:
                interval = DEFAULT_INTERVAL_MIN
            scheduler.add_job(
                _job_body,
                trigger=IntervalTrigger(minutes=interval),
                id=f"kb-table-sync-{doc.uuid_code}",
                args=[doc.uuid_code, doc.tenant_id],
                replace_existing=True,
            )
        return len(targets)
    finally:
        s.close()


def remove_table_sync_job(scheduler, doc_uuid: str) -> None:
    try:
        scheduler.remove_job(f"kb-table-sync-{doc_uuid}")
    except Exception:  # noqa: BLE001 - 作业不存在时静默
        pass


def run_sync_now(db, tenant_id: int, doc_uuid: str) -> dict:
    """同步阻塞执行入口（供端点手动触发；与调度作业共用同一实现）。"""
    return sync_table_document(db, tenant_id, doc_uuid)
