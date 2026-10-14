"""外部文档导入服务（对齐 table_sync_service 的服务层范式）。

职责：把外部平台的文档正文落成本地 ``KbDocument`` 并触发摄取管线，
同时维护 ``kb_external_doc_map`` 映射以实现「覆盖 or 新建」的幂等语义：

- 映射不存在            → **新建** 文档（source_type='connector'）
- 映射存在且 content_hash 相同 → **跳过**（不重复调嵌入，最重要的成本优化）
- 映射存在但 hash 变化   → **覆盖**：复用同一 uuid_code，清旧切片后重新切片

单篇失败不影响其它文档：失败计入 ``failed`` 并写入文档 error_detail。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from app.ai.dataops.crypto import decrypt_secret, encrypt_secret
from app.connectors.doc_sources import (
    DocConnResult,
    DocSourceError,
    ExternalDocRef,
    FetchDocResult,
    get_doc_source,
)
from app.core.job_runner import run_in_background
from app.models.connectors.connector_record import ConnectorInstance
from app.models.connectors.external_doc_map import KbExternalDocMap
from app.models.kb.kb_document import KbDocument
from app.models.kb.kb_segment import KbSegment

# 拉取并发上限：防止打爆平台限流
FETCH_CONCURRENCY = 5


class ImportSummary(BaseModel):
    """一次导入的汇总结果。"""

    total: int = 0
    created: int = 0          # 新建
    updated: int = 0          # 覆盖
    unchanged: int = 0        # 内容哈希命中，跳过嵌入
    failed: int = 0
    items: List[Dict[str, Any]] = Field(default_factory=list)


def content_hash(markdown: str) -> str:
    """正文 sha256。先归一化（统一换行、去首尾空白）再算，避免无关差异导致重复嵌入。"""
    normalized = re.sub(r"\r\n|\r", "\n", markdown or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _collection_of(knowledge_id: int) -> str:
    return f"kb_{knowledge_id}"


# ── 凭据加密落库（Fernet） ────────────────────────────────────────
def save_credentials(
    db: Session,
    tenant_id: int,
    knowledge_id: int,
    source_type: str,
    credentials: Dict[str, Any],
) -> None:
    """把平台凭据加密后存到连接器实例，供「重新选择文档」时免重复填写。"""
    payload = encrypt_secret(json.dumps(credentials or {}, ensure_ascii=False))
    inst = (
        db.query(ConnectorInstance)
        .filter(
            ConnectorInstance.tenant_id == tenant_id,
            ConnectorInstance.knowledge_id == knowledge_id,
            ConnectorInstance.connector_type == source_type,
        )
        .one_or_none()
    )
    if inst is None:
        inst = ConnectorInstance(
            tenant_id=tenant_id,
            knowledge_id=knowledge_id,
            connector_type=source_type,
            name=f"{source_type} 文档导入",
            config={"credentials": payload},
            target_collection=_collection_of(knowledge_id),
        )
        db.add(inst)
    else:
        inst.config = {"credentials": payload}
    db.flush()


def load_credentials(
    db: Session, tenant_id: int, knowledge_id: int, source_type: str
) -> Optional[Dict[str, Any]]:
    """读取并解密已保存的凭据；不存在或解密失败返回 None（不抛给前端）。"""
    inst = (
        db.query(ConnectorInstance)
        .filter(
            ConnectorInstance.tenant_id == tenant_id,
            ConnectorInstance.knowledge_id == knowledge_id,
            ConnectorInstance.connector_type == source_type,
        )
        .one_or_none()
    )
    if inst is None:
        return None
    raw = (inst.config or {}).get("credentials")
    if not raw:
        return None
    try:
        return json.loads(decrypt_secret(raw))
    except Exception:  # noqa: BLE001 - 密钥轮换/数据损坏时退化为要求重填
        return None


# ── 文档源薄封装 ──────────────────────────────────────────────────
async def test_source(source_type: str, credentials: Dict[str, Any]) -> DocConnResult:
    src = get_doc_source(source_type, credentials)
    try:
        return await src.test_connection()
    except DocSourceError as exc:
        return DocConnResult(ok=False, message=str(exc))
    except Exception as exc:  # noqa: BLE001 - 兜底，保证接口不 500
        return DocConnResult(ok=False, message=f"连通性测试异常：{exc}")
    finally:
        await src.aclose()


async def list_nodes(
    source_type: str, credentials: Dict[str, Any], parent_id: Optional[str]
) -> List[ExternalDocRef]:
    src = get_doc_source(source_type, credentials)
    try:
        return await src.list_nodes(parent_id)
    except DocSourceError as exc:
        raise
    finally:
        await src.aclose()


# ── 导入主流程 ────────────────────────────────────────────────────
async def import_documents(
    db: Session,
    tenant_id: int,
    knowledge_id: int,
    source_type: str,
    credentials: Dict[str, Any],
    doc_refs: List[Dict[str, str]],
    *,
    chunker_type: str = "approx_token",
    chunker_params: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> ImportSummary:
    """导入/重新导入选中的外部文档。

    同一端点天然幂等：重复导入同一篇文档时按映射表判定覆盖或跳过。
    """
    summary = ImportSummary(total=len(doc_refs or []))
    if not doc_refs:
        return summary

    src = get_doc_source(source_type, credentials)
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def _one(ref: Dict[str, str]) -> tuple:
        doc_id = str(ref.get("doc_id") or "")
        title = ref.get("title") or doc_id
        async with sem:
            try:
                return doc_id, title, await src.fetch_doc(doc_id), None
            except Exception as exc:  # noqa: BLE001 - 单篇失败不影响其它
                return doc_id, title, None, str(exc)

    fetched = await asyncio.gather(*(_one(r) for r in doc_refs))
    await src.aclose()

    collection = _collection_of(knowledge_id)
    pending_ingest: List[tuple] = []   # (doc_id, markdown_bytes, filename)

    for doc_id, title, result, error in fetched:
        if error is not None or result is None:
            summary.failed += 1
            summary.items.append(
                {"external_doc_id": doc_id, "title": title,
                 "action": "failed", "detail": error or "拉取失败"}
            )
            continue

        assert isinstance(result, FetchDocResult)
        markdown = result.markdown or ""
        if not markdown.strip():
            summary.failed += 1
            summary.items.append(
                {"external_doc_id": doc_id, "title": title,
                 "action": "failed", "detail": "文档正文为空"}
            )
            continue

        c_hash = content_hash(markdown)
        mapping = (
            db.query(KbExternalDocMap)
            .filter(
                KbExternalDocMap.tenant_id == tenant_id,
                KbExternalDocMap.knowledge_id == knowledge_id,
                KbExternalDocMap.source_type == source_type,
                KbExternalDocMap.external_doc_id == doc_id,
            )
            .one_or_none()
        )

        if mapping is None:
            # ── 新建 ──
            doc = KbDocument(
                tenant_id=tenant_id,
                knowledge_id=knowledge_id,
                collection=collection,
                name=f"{title}.md",
                source_type="connector",
                file_type="md",
                # 显式给出状态而不依赖 server_default：后台任务派发前对象即可读
                status="pending",
                file_size=len(markdown.encode("utf-8")),
                creator_id=user_id,
                meta={
                    "external": {"source_type": source_type, "external_doc_id": doc_id},
                    "chunker_type": chunker_type,
                    **( {"chunker_params": chunker_params} if chunker_params else {} ),
                },
            )
            db.add(doc)
            db.flush()  # 生成 uuid_code
            db.add(
                KbExternalDocMap(
                    tenant_id=tenant_id,
                    knowledge_id=knowledge_id,
                    source_type=source_type,
                    external_doc_id=doc_id,
                    external_title=title,
                    node_type="doc",
                    external_updated_at=result.updated_at,
                    document_id=doc.id,
                    content_hash=c_hash,
                )
            )
            action, target = "created", doc
            summary.created += 1
        elif mapping.content_hash == c_hash:
            # ── 未变更：跳过嵌入 ──
            mapping.external_title = title
            mapping.external_updated_at = result.updated_at
            summary.unchanged += 1
            summary.items.append(
                {"external_doc_id": doc_id, "title": title,
                 "action": "unchanged", "detail": "内容未变化，跳过嵌入"}
            )
            continue
        else:
            # ── 覆盖：复用同一 uuid_code，清旧切片 ──
            doc = db.get(KbDocument, mapping.document_id)
            if doc is None:
                # 映射还在但文档已被删除：按新建处理
                doc = KbDocument(
                    tenant_id=tenant_id,
                    knowledge_id=knowledge_id,
                    collection=collection,
                    name=f"{title}.md",
                    source_type="connector",
                    file_type="md",
                    status="pending",
                    creator_id=user_id,
                )
                db.add(doc)
                db.flush()
                mapping.document_id = doc.id
            else:
                db.execute(
                    sa_delete(KbSegment).where(
                        KbSegment.tenant_id == tenant_id,
                        KbSegment.collection == collection,
                        KbSegment.document_id == doc.uuid_code,
                    )
                )
                doc.file_size = len(markdown.encode("utf-8"))
            doc.status = "pending"
            doc.segment_count = 0
            doc.error_detail = None
            doc.meta = {
                **(doc.meta or {}),
                "external": {"source_type": source_type, "external_doc_id": doc_id},
                "chunker_type": chunker_type,
                **( {"chunker_params": chunker_params} if chunker_params else {} ),
            }
            mapping.content_hash = c_hash
            mapping.external_title = title
            mapping.external_updated_at = result.updated_at
            action, target = "updated", doc
            summary.updated += 1

        pending_ingest.append((target.id, markdown.encode("utf-8"), f"{title}.md"))
        summary.items.append(
            {"external_doc_id": doc_id, "title": title, "action": action,
             "detail": "已加入摄取队列"}
        )

    db.commit()

    # 提交后再派发后台任务：避免「提交了但任务丢了」
    for doc_pk, payload, filename in pending_ingest:
        _dispatch_ingest(tenant_id, doc_pk, payload, filename,
                         chunker_type, chunker_params)

    return summary


def _dispatch_ingest(
    tenant_id: int,
    doc_pk: int,
    payload: bytes,
    filename: str,
    chunker_type: str,
    chunker_params: Optional[Dict[str, Any]],
) -> None:
    """后台执行摄取；独立 Session，不绑 FastAPI 请求生命周期。"""

    def _run() -> None:
        from app.db.database import SessionLocal
        from app.services.kb.document_pipeline import run_document_ingest

        s = SessionLocal()
        try:
            run_document_ingest(
                s, tenant_id, doc_pk, payload, filename,
                chunker_type=chunker_type,
                chunker_params=chunker_params,
            )
        except Exception as exc:  # noqa: BLE001 - 失败已由管线写入文档状态
            doc = s.get(KbDocument, doc_pk)
            if doc is not None:
                doc.status = "failed"
                doc.error_detail = str(exc)
                s.commit()
        finally:
            s.close()

    run_in_background(_run, name=f"kb-external-ingest-{doc_pk}")


def list_external_documents(
    db: Session, tenant_id: int, knowledge_id: int
) -> List[Dict[str, Any]]:
    """已导入文档列表（映射 join 文档，含状态与更新时间）。"""
    rows = (
        db.query(KbExternalDocMap, KbDocument)
        .outerjoin(KbDocument, KbExternalDocMap.document_id == KbDocument.id)
        .filter(
            KbExternalDocMap.tenant_id == tenant_id,
            KbExternalDocMap.knowledge_id == knowledge_id,
        )
        .order_by(KbExternalDocMap.id.desc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for mapping, doc in rows:
        out.append(
            {
                "external_doc_id": mapping.external_doc_id,
                "source_type": mapping.source_type,
                "title": mapping.external_title or (doc.name if doc else ""),
                "external_updated_at": mapping.external_updated_at,
                "document_id": mapping.document_id,
                "document_uuid": doc.uuid_code if doc else None,
                "status": doc.status if doc else None,
                "segment_count": doc.segment_count if doc else None,
                "error_detail": doc.error_detail if doc else None,
                "updated_at": str(doc.updated_at) if doc and doc.updated_at else None,
                "deleted": mapping.deleted,
            }
        )
    return out
