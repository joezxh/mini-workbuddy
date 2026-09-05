"""PGVectorStore - 基于 pgvector 的向量检索实现。

支持通用 knowledge_document (本项目通用知识库, OKF 导入后转 embedding)。
也支持 Wiki 文章向量检索 (wiki collection)。

设计:
- 不新建一张统一的 collection 表; 而是用 VectorCollection 注册描述每个 collection 对应哪个表/字段
- search: 构造 SELECT + pgvector cosine_distance <=> ORDER BY distance LIMIT
- upsert: UPDATE 现有行 (按 collection_id + id_col)
- delete: DELETE WHERE pk = id
"""
from __future__ import annotations
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import Column, delete, select, update
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeDecorator

from app.ai.knowledge.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


@dataclass
class VectorCollection:
    """一个向量集合的元数据描述。"""
    collection: str
    model_id: str                       # 'app.models.kms_legal.LegalInfo'
    vector_col: str                     # 'full_text_vector'
    text_col: str                       # 'full_text'
    pk_col: str = "id"                  # 主键列名
    metadata_cols: Dict[str, str] = field(default_factory=dict)
    where_clauses: List[str] = field(default_factory=list)  # 例如 ['deleted = :deleted', 'status = 1']
    distance_op: str = "<=>"            # pgvector: <=> cosine_distance; <-> L2; <#> inner_product
    model_class: Optional[Type] = None  # 缓存: 由 model_id 解析后填充


def _resolve_model(model_id: str) -> Type:
    """从 'app.models.x.Y' 字符串导入类。"""
    if "." not in model_id:
        raise ValueError(
            f"invalid model_id {model_id!r}, expected 'package.module.Class'",
        )
    mod_path, cls_name = model_id.rsplit(".", 1)
    mod = importlib.import_module(mod_path)
    cls = getattr(mod, cls_name)
    return cls


class PGVectorStore(BaseVectorStore):
    """基于 pgvector 的 BaseVectorStore 实现。

    用法:
        store = PGVectorStore(db=session)
        store.register_collection(VectorCollection(
            collection="legal_law",
            model_id="app.models.kms_legal.LegalInfo",
            vector_col="full_text_vector",
            text_col="full_text",
            metadata_cols={"law_title": "law_title"},
        ))
        results = await store.search("legal_law", query_vector, top_k=5)
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self._collections: Dict[str, VectorCollection] = {}

    # ---- collection 注册 ----
    def register_collection(self, col: VectorCollection) -> None:
        col.model_class = _resolve_model(col.model_id)
        self._collections[col.collection] = col
        logger.info("registered vector collection: %s -> %s.%s",
                    col.collection, col.model_id, col.vector_col)

    def get_collection(self, name: str) -> VectorCollection:
        if name not in self._collections:
            raise KeyError(f"vector collection not registered: {name!r}")
        return self._collections[name]

    def list_collections(self) -> List[str]:
        return list(self._collections.keys())

    # ---- BaseVectorStore 接口 ----
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Dict[str, Any],
    ) -> None:
        col = self.get_collection(collection)
        model_cls = col.model_class
        text_col = getattr(model_cls, col.text_col)
        vec_col = getattr(model_cls, col.vector_col)
        pk_col = getattr(model_cls, col.pk_col)

        values: Dict[str, Any] = {text_col.key: (metadata.get(col.text_col) or id)}
        values[vec_col.key] = vector
        # metadata_cols -> 同步字段
        for meta_key, db_col_name in col.metadata_cols.items():
            if meta_key in metadata:
                values[db_col_name] = metadata[meta_key]

        stmt = update(model_cls).where(pk_col == int(id)).values(**values)
        result = self.db.execute(stmt)
        # 若不存在 -> INSERT
        if getattr(result, "rowcount", 0) == 0:
            values[pk_col.key] = int(id)
            from sqlalchemy import insert
            stmt2 = insert(model_cls).values(**values)
            self.db.execute(stmt2)
        self.db.commit()

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        col = self.get_collection(collection)
        model_cls = col.model_class
        vec_col = getattr(model_cls, col.vector_col)
        pk_col = getattr(model_cls, col.pk_col)

        distance = vec_col.op(col.distance_op)(query_vector).label("distance")
        meta_cols = [getattr(model_cls, c) for c in col.metadata_cols.values()]

        stmt = (
            select(pk_col, *meta_cols, distance)
            .where(vec_col.isnot(None))
            .order_by(distance.asc())
            .limit(max(1, top_k))
        )
        # 应用 collection 自带的 where (如 deleted='0')
        for clause in col.where_clauses:
            # 形如 "deleted = :deleted" -> 参数化由调用方传入, 这里仅占位 None
            from sqlalchemy import text as _text
            stmt = stmt.where(_text(clause))
        # metadata filter
        if filter:
            for k, v in filter.items():
                col_attr = getattr(model_cls, k, None)
                if col_attr is not None:
                    stmt = stmt.where(col_attr == v)

        rows = self.db.execute(stmt).all()
        out: List[Dict[str, Any]] = []
        meta_keys = list(col.metadata_cols.keys())
        meta_db_cols = list(col.metadata_cols.values())
        for row in rows:
            row_dict = dict(row._mapping) if hasattr(row, "_mapping") else None
            if row_dict is None:
                # fall back: pk_col 是首项, 后续是 metadata + distance
                row_dict = {pk_col.key: row[0]}
                for i, k in enumerate(meta_db_cols, start=1):
                    row_dict[k] = row[i]
                row_dict["distance"] = row[-1]
            row_id = row_dict[pk_col.key]
            dist = float(row_dict.pop("distance"))
            score = 1.0 - dist  # cosine_distance -> similarity
            metadata_out = {meta_keys[i]: row_dict[meta_db_cols[i]] for i in range(len(meta_keys))}
            out.append({
                "id": str(row_id),
                "score": score,
                "metadata": metadata_out,
                "distance": dist,
            })
        return out

    async def delete(self, collection: str, id: str) -> bool:
        col = self.get_collection(collection)
        model_cls = col.model_class
        pk_col = getattr(model_cls, col.pk_col)
        stmt = delete(model_cls).where(pk_col == int(id))
        result = self.db.execute(stmt)
        self.db.commit()
        return bool(getattr(result, "rowcount", 0) > 0)

    # ---- 便捷 ----
    async def count(self, collection: str) -> int:
        col = self.get_collection(collection)
        model_cls = col.model_class
        from sqlalchemy import func
        stmt = select(func.count()).select_from(model_cls)
        for clause in col.where_clauses:
            from sqlalchemy import text as _text
            stmt = stmt.where(_text(clause))
        return int(self.db.execute(stmt).scalar() or 0)