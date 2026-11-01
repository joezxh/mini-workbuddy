"""文档摄取管线（对齐文档 §8.1 / D4）：原生三步，无自研中间格式。

    select_parser(mime) → parser.parse(bytes) → build_chunker(...).chunk(sections)
    → await kb.insert_document(chunks, document_id=..., document_metadata=...)

嵌入由 ``KnowledgeBase`` 内部完成（原生强制），维度与 ``kb_collection.dimensions``
强校验（D19）。父子段落由 ``Chunk.metadata['parent_content']`` 随检索返回，
不依赖 join（D13）。后台任务由调用方（``job_runner``）托管 Session。

``knowledge_factory`` 可注入（测试替换真实嵌入模型）。
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument
from app.services.kb.pipeline_runner import (
    PipelineStepError,
    run_pipeline_from_config,
)


def _fail(db: Session, doc_id: int, step: str, exc: Exception) -> None:
    doc = db.get(KbDocument, doc_id)
    if doc is not None:
        doc.status = "failed"
        doc.error_detail = f"[{step}] {type(exc).__name__}: {exc}"
        # 记录失败步骤：文档列表「流程」视图据此高亮失败节点
        doc.meta = {**(doc.meta or {}), "failed_step": step, "pipeline_steps": None}
        db.commit()
    logger.error(f"[KB 管线] 文档 {doc_id} 在 {step} 步失败: {exc}")


def _maybe_submit_graph_build(db: Session, tenant_id: int, doc_id: int) -> None:
    """图谱库（type=4）在切片就绪后提交后台图谱构建。

    这里只做**提交**，不等结果：LLM 抽取耗时长，不能阻塞摄取返回。
    任何异常都只记日志——图谱构建是增强能力，失败不得让文档摄取看起来失败。
    """
    try:
        doc = db.get(KbDocument, doc_id)
        if doc is None or doc.knowledge_id is None:
            return
        from app.models.wiki.wiki_knowledge import KnowledgeType, WikiKnowledge

        kb = db.get(WikiKnowledge, doc.knowledge_id)
        if kb is None or kb.type != KnowledgeType.GRAPH_KB:
            return
        from app.services.kb.kg.kg_build_service import submit_build

        submit_build(
            tenant_id=tenant_id,
            knowledge_id=doc.knowledge_id,
            action="build",
            document_uuid=doc.uuid_code,
        )
    except Exception as exc:  # noqa: BLE001 - 图谱构建失败不影响文档可用
        logger.warning(f"[KB 管线] 文档 {doc_id} 图谱构建提交失败: {exc}")


def _resolve_index_mode(db: Session, collection: str) -> str:
    """由 collection 名反查知识库索引模式（spec §10.2）；复用共享实现。"""
    from app.services.kb.index_mode import resolve_index_mode

    return resolve_index_mode(db, collection)


# 嵌入失败的典型信号：只有命中这些线索才值得补上端点上下文
_EMBED_ERROR_HINTS = (
    "connection", "connect", "timeout", "timed out", "status code",
    "embedding", "dimension", "api key", "rate limit", "unauthorized",
)


def _embed_failure(exc: Exception) -> Exception:
    """给**嵌入相关**失败补上嵌入端点上下文，让失败节点可自解释。

    嵌入依赖外部 HTTP 服务（GPUStack / NIM / 百炼），裸 ``APIConnectionError``
    无法看出是哪个节点、哪个端点不可达；此处补齐 provider/base_url/model/维度。

    非嵌入类失败（如落库时 PG 报 ``A string literal cannot contain NUL``）原样
    返回：硬贴「嵌入服务不可达」会把排查方向带偏，本轮就因此误判过一次。
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    if not any(hint in text for hint in _EMBED_ERROR_HINTS):
        return exc
    try:
        from app.services.kb.embedding_config import (
            describe_embedding_config,
            resolve_embedding_config_with_fallback,
        )

        # 用与构建链路相同的解析（模型管理默认优先、env 兜底），
        # 日志展示的才是真实生效端点，provider=model_mgmt:* 即来自模型管理
        info = describe_embedding_config(resolve_embedding_config_with_fallback(None))
        return RuntimeError(
            f"{type(exc).__name__}: {exc}"
            f"（向量化步：嵌入服务不可达或不可用"
            f" provider={info['provider']} base_url={info['base_url']}"
            f" model={info['model']} dimension={info['dimension']}"
            f" api_key_configured={info['api_key_configured']}）"
        )
    except Exception:  # noqa: BLE001 - 附加上下文失败时不影响原始异常
        return exc


def _resolve_pipeline_config(db: Session, collection: str) -> Optional[dict]:
    """由 collection 名取知识库编排配置（spec §10.7）；驱动 parse/clean/chunk。"""
    from app.services.kb.pipeline_config import resolve_knowledge_pipeline_config

    return resolve_knowledge_pipeline_config(db, collection)


def run_document_ingest(
    db: Session,
    tenant_id: int,
    doc_id: int,
    file_bytes: Optional[bytes],
    filename: str,
    chunker_type: str = "approx_token",
    chunker_params: Optional[dict] = None,
    embedding_code: Optional[str] = None,  # noqa: ARG001 - 兼容旧签名，原生后由 provider 决定
    embed_fn: Optional[Callable] = None,   # noqa: ARG001 - 兼容旧签名；原生链路不再需要
    knowledge_factory: Optional[Callable] = None,
) -> int:
    """同步执行整条原生管线；返回写入切片数。失败落 failed 状态后原样抛出。"""
    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    doc.status = "processing"
    doc.error_detail = None
    db.commit()

    try:
        # 媒体文件（图片/音频/视频/DXF）不走 parser/chunker，直接媒体提取路径（spec §5）
        from app.services.kb.media.base import detect_media_kind

        if detect_media_kind(filename) is not None:
            from app.services.kb.media.ingest import run_media_ingest

            return run_media_ingest(
                db, tenant_id, doc_id, file_bytes or b"", filename,
                session_factory=None, kb_factory=knowledge_factory,
            )

        # 1)-3) 解析 → 清洗 → 切块：与 dry-run 共用的编排执行器（spec §10.7）
        #    知识库 pipeline_config 优先，扁平 chunker_* 参数作兜底
        result = run_pipeline_from_config(
            file_bytes,
            filename,
            pipeline_config=_resolve_pipeline_config(db, doc.collection),
            chunker_type=chunker_type,
            chunker_params=chunker_params,
        )
        chunks = result.chunks
        if not chunks:
            raise ValueError(f"文档 {filename} 未产出任何切片")

        # 3) 落库：KnowledgeBase.insert_document（嵌入在其内部完成）
        #    economy 模式写 NULL 向量（D11），检索走独立关键词服务
        index_mode = _resolve_index_mode(db, doc.collection)

        async def _insert() -> int:
            if knowledge_factory is not None:
                async with knowledge_factory(index_mode=index_mode) as kb:
                    await kb.ensure_collection()
                    await kb.insert_document(
                        chunks,
                        document_id=doc.uuid_code,
                        document_metadata={
                            "filename": filename,
                            "kb_document_id": doc.id,
                            "source": filename,
                        },
                    )
                return len(chunks)
            from app.db.database import SessionLocal
            from app.services.kb.rag.knowledge_factory import knowledge_base

            async with knowledge_base(
                SessionLocal,
                collection_name=doc.collection,
                tenant_id=tenant_id,
                name=doc.name,
                description=filename,
                index_mode=index_mode,
            ) as kb:
                await kb.ensure_collection()
                await kb.insert_document(
                    chunks,
                    document_id=doc.uuid_code,
                    document_metadata={
                        "filename": filename,
                        "kb_document_id": doc.id,
                        "source": filename,
                    },
                )
            return len(chunks)

        # 4) 向量化 + 落库：单独标注步名（§10.7 单步可观测），
        #    失败时 error_detail 形如 [vectorize] …，不再笼统落成 [pipeline]
        try:
            count = asyncio.run(_insert())
        except PipelineStepError:
            raise
        except Exception as exc:  # noqa: BLE001 - 标注步名后交由外层统一落库
            db.rollback()
            raise PipelineStepError("vectorize", _embed_failure(exc)) from exc

        doc.status = "completed"
        doc.segment_count = count
        # 记录本次执行的各步摘要（parser/chunker 与产出数量），供「流程」视图展示
        doc.meta = {
            **(doc.meta or {}),
            "pipeline_steps": result.steps + [
                {"step": "vectorize", "chunks": count},
            ],
            "failed_step": None,
        }
        db.commit()
        # 5) 图谱构建（仅 type=4）：切片已就绪 → 提交后台抽取。
        #    图谱失败**不回滚**文档摄取（切片仍可用），仅标记图谱未就绪（spec §5.6）。
        _maybe_submit_graph_build(db, tenant_id, doc_id)
        return count
    except PipelineStepError as exc:
        # §10.7 单步可观测：error_detail 带具体步名（parse/clean/chunk/vectorize）
        db.rollback()
        _fail(db, doc_id, exc.step, exc)
        raise
    except Exception as exc:  # noqa: BLE001 - 管线失败必须落库可观测后原样抛出
        db.rollback()
        _fail(db, doc_id, "pipeline", exc)
        raise
