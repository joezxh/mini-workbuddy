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
from sqlalchemy import select
from sqlalchemy.orm import Session

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
