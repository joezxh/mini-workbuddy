"""表格知识库集合（``kms_collection``）服务：多集合创建 / 列表 / 归属校验。

背景
----
表格知识库支持「一个知识库配置多个集合」（``kms_collection`` 多对一
``kms_knowledge``）。集合名沿用 ``kb_{knowledge_id}`` 前缀并追加 slug
（``kb_{kid}_{slug}``），因此 :func:`~app.services.kb.index_mode.resolve_knowledge_id`
正则放宽后，既有「按集合名反查知识库 / 维度 / 索引模式」的链路零改动继续可用；
普通文档知识库仍维持 ``kb_{kid}`` 1:1，行为不变。

职责
----
* :func:`create_knowledge_collection` —— 在指定知识库下新建集合（slug 去重）；
* :func:`list_knowledge_collections` —— 列出某知识库下的全部集合；
* :func:`resolve_or_create_collection` —— 导入时解析目标集合：指定了则用之
  （并校验归属），未指定则自动新建（承载按文件表头推断出的字段定义）；
* :func:`validate_collection_ownership` —— 校验集合属于指定知识库。
"""
from __future__ import annotations

import re
from typing import Optional

from loguru import logger
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb.kb_collection import KbCollection

# slug 仅保留小写字母、数字与短横线
_INVALID_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str, fallback: str = "c") -> str:
    """把任意文本（文件名/集合名）收敛为集合名可用的 slug。"""
    slug = _INVALID_SLUG_CHARS.sub("-", (text or "").strip().lower()).strip("-")
    return slug or fallback


def build_collection_name(knowledge_id: int, slug: str) -> str:
    """集合名 ``kb_{knowledge_id}_{slug}``（保留 ``kb_`` 前缀以兼容按名反查）。"""
    return f"kb_{knowledge_id}_{slug}"


def unique_collection_name(db: Session, knowledge_id: int, slug: str) -> str:
    """``kb_{kid}_{slug}`` 去重：冲突时追加 ``-2``/``-3``…"""
    base = build_collection_name(knowledge_id, slug)
    taken = {
        name
        for (name,) in db.execute(
            select(KbCollection.name).where(KbCollection.name.like(f"{base}%"))
        )
    }
    if base not in taken:
        return base
    idx = 2
    while f"{base}-{idx}" in taken:
        idx += 1
    return f"{base}-{idx}"


def get_collection_by_name(db: Session, name: str) -> Optional[KbCollection]:
    """按集合名取集合行。"""
    if not name:
        return None
    return db.execute(
        select(KbCollection).where(KbCollection.name == name)
    ).scalar_one_or_none()


def get_collection_by_id(db: Session, collection_id: int) -> Optional[KbCollection]:
    """按主键取集合行。"""
    if not collection_id:
        return None
    return db.get(KbCollection, collection_id)


def list_knowledge_collections(
    db: Session, tenant_id: Optional[int], knowledge_id: int
) -> list[KbCollection]:
    """列出某知识库下的全部集合（按 id 升序）。"""
    stmt = select(KbCollection).where(KbCollection.knowledge_id == knowledge_id)
    if tenant_id is not None:
        stmt = stmt.where(KbCollection.tenant_id == tenant_id)
    return list(db.execute(stmt.order_by(KbCollection.id)).scalars().all())


def create_knowledge_collection(
    db: Session,
    tenant_id: Optional[int],
    knowledge_id: int,
    *,
    slug: Optional[str] = None,
    schema_config: Optional[list] = None,
    dimensions: Optional[int] = None,
) -> KbCollection:
    """在指定知识库下新建集合；``slug`` 缺省取 ``c``，重名自动加序号。"""
    from app.config import settings

    name = unique_collection_name(db, knowledge_id, slugify(slug or "", fallback="c"))
    coll = KbCollection(
        name=name,
        dimensions=dimensions or settings.GPUSTACK_EMBEDDING_DIMENSION,
        knowledge_id=knowledge_id,
        tenant_id=tenant_id,
        schema_config=schema_config,
    )
    db.add(coll)
    db.flush()
    logger.info(
        f"[KB][Collection] 新建集合 {name}（knowledge_id={knowledge_id}, "
        f"字段数={len(schema_config) if schema_config else 0}）"
    )
    return coll


def validate_collection_ownership(
    db: Session, collection: KbCollection, knowledge_id: Optional[int]
) -> None:
    """校验集合属于指定知识库；跨知识库使用直接拒绝。

    空集合或集合/知识库缺一时不校验（历史数据兼容）。
    """
    if collection is None or knowledge_id is None:
        return
    if collection.knowledge_id is not None and collection.knowledge_id != knowledge_id:
        raise ValueError(
            f"集合 {collection.name!r} 不属于知识库 {knowledge_id}"
            f"（实际属于 {collection.knowledge_id}）"
        )


def resolve_or_create_collection(
    db: Session,
    tenant_id: Optional[int],
    knowledge_id: Optional[int],
    *,
    collection_name: Optional[str] = None,
    collection_id: Optional[int] = None,
    slug: Optional[str] = None,
    schema_config: Optional[list] = None,
    dimensions: Optional[int] = None,
    auto_create: bool = True,
) -> Optional[KbCollection]:
    """导入时解析目标集合。

    * 指定 ``collection_id`` / ``collection_name`` → 取该集合并校验归属；
    * 均未指定且 ``auto_create`` → 在该知识库下自动新建集合（承载字段定义）；
    * 无法解析且不自动创建 → 返回 ``None``（调用方沿用原有按名入库逻辑）。
    """
    coll: Optional[KbCollection] = None
    if collection_id:
        coll = get_collection_by_id(db, collection_id)
        if coll is None:
            raise ValueError(f"集合不存在: collection_id={collection_id}")
    elif collection_name:
        coll = get_collection_by_name(db, collection_name)
        if coll is None:
            raise ValueError(f"集合不存在: {collection_name!r}")
    if coll is not None:
        validate_collection_ownership(db, coll, knowledge_id)
        return coll
    if not auto_create or knowledge_id is None:
        return None
    return create_knowledge_collection(
        db, tenant_id, knowledge_id, slug=slug,
        schema_config=schema_config, dimensions=dimensions,
    )


def get_collection_name_by_id(db: Session, collection_id: int) -> str:
    """按主键取集合名（向量库命名空间）。不存在抛 ``ValueError``（路由层转 404）。

    文档↔集合关联一律走 ``collection_id``，调用方不再直接传集合名；此处是
    唯一由 id 反查 name 的单点，name 仅作为向量库存储标签。
    """
    coll = get_collection_by_id(db, collection_id)
    if coll is None:
        raise ValueError(f"集合不存在: collection_id={collection_id}")
    return coll.name


def ensure_default_collection(
    db: Session, tenant_id: Optional[int], knowledge_id: int
) -> KbCollection:
    """确保某知识库存在默认集合 ``kb_{knowledge_id}``（普通文档 / Q&A 库的 1:1 集合）。

    表格知识库上传未指定集合时会自动新建 ``kb_{kid}_{slug}``，但「按 id 反查」要求
    每个知识库（含历史库）都有这一默认行，否则文档 / Q&A 库的接口无法解析。
    """
    default_name = f"kb_{knowledge_id}"
    existing = db.execute(
        select(KbCollection).where(
            KbCollection.knowledge_id == knowledge_id,
            KbCollection.name == default_name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    coll = KbCollection(
        name=default_name,
        dimensions=settings.GPUSTACK_EMBEDDING_DIMENSION,
        knowledge_id=knowledge_id,
        tenant_id=tenant_id,
    )
    db.add(coll)
    db.flush()
    logger.info(f"[KB][Collection] 补齐默认集合 {default_name}（knowledge_id={knowledge_id}）")
    return coll


def rename_collection(
    db: Session, collection_id: int, new_slug: Optional[str]
) -> KbCollection:
    """重命名集合（改 slug/name）。

    向量库以 ``collection`` 名作命名空间，重命名 = 对 ``kms_collection`` /
    ``kms_document`` / ``kms_segment`` 三张表的 name 标签做一致 UPDATE（向量 embedding
    数据不动，无数据搬运，安全）。同名冲突拒绝。
    """
    coll = get_collection_by_id(db, collection_id)
    if coll is None:
        raise ValueError(f"集合不存在: collection_id={collection_id}")
    kid = coll.knowledge_id
    new_name = build_collection_name(kid, slugify(new_slug)) if new_slug else f"kb_{kid}"
    old_name = coll.name
    if new_name != old_name and get_collection_by_name(db, new_name) is not None:
        raise ValueError(f"集合名已存在: {new_name!r}")
    if new_name != old_name:
        from app.models.kb.kb_document import KbDocument
        from app.models.kb.kb_segment import KbSegment

        db.execute(
            update(KbDocument)
            .where(KbDocument.collection_id == coll.id)
            .values(collection=new_name)
        )
        db.execute(
            update(KbSegment)
            .where(KbSegment.collection == old_name)
            .values(collection=new_name)
        )
    coll.name = new_name
    db.flush()
    logger.info(
        f"[KB][Collection] 重命名集合 {old_name} → {new_name}（id={collection_id}）"
    )
    return coll


def delete_collection_cascade(
    db: Session, tenant_id: int, collection_id: int
) -> None:
    """级联删除集合：先删其下文档，再删集合（含全部切片 + 集合元数据行）。

    向量数据存于 ``kms_segment.embedding`` 列，随切片行删除一并清除；文档行因
    ``collection_id`` 外键为 ``SET NULL``，需显式删除以免残留孤儿文档。
    """
    from app.models.kb.kb_document import KbDocument
    from app.services.kb.pgvector_store import PGVectorStore

    coll = get_collection_by_id(db, collection_id)
    if coll is None:
        raise ValueError(f"集合不存在: collection_id={collection_id}")
    # 先删文档，再交由 PGVectorStore 删集合（清切片 + 集合行）
    db.execute(delete(KbDocument).where(KbDocument.collection_id == coll.id))
    PGVectorStore(db, tenant_id).delete_collection(coll.name)
    db.flush()
    logger.info(f"[KB][Collection] 级联删除集合 {coll.name}（id={collection_id}）")
