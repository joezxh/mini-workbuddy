"""本体持久化仓储 —— `WikiOwlEngine` 的存储后端。

职责
----
* 以 `tenant_id` 为边界读写 `ontology` / `ontology_class` / `ontology_annotation`；
* 对外暴露一组与 rdflib 无关的「记录」对象，供 `WikiOwlEngine` 组装 OWL 语义；
* 写操作**默认**立即 `commit`：`app.db.database.get_db()` 在会话存在待写入对象时
  **不会**自动提交（见其 `if not db.new ...` 判断），故持久化由仓储显式保证；
  构造参数 `auto_commit=False` 时只 `flush()`，提交权交回调用方（评审 IM-05）。

真相源
------
`ontology.ttl_content` 存**全量 TTL 原文**（唯一真相源，评审 R2-01 / R2-02）；
`ontology_class` / `ontology_annotation` 是从原文派生的**查询索引**，
由 `WikiOwlEngine._reindex()` 以覆盖语义重建，随时可丢弃重算。

写操作语义（与改造前 rdflib 图操作对齐）
----------------------------------------
* `upsert_class(parent_uris=...)` 默认与已有父类**取并集**（旧实现是 graph.add）；
  `merge_parents=False` 时为**覆盖**（含清空），供「按原文重建索引」使用；
* `label` / `comment` 为空字符串时不覆盖已有值（旧实现是 `if label: graph.set(...)`）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ontology.ontology import Ontology, OntologyAnnotation, OntologyClass

logger = logging.getLogger(__name__)

DEFAULT_ONTOLOGY_CODE = "default"
"""默认本体编码：一个租户一份"默认本体"，与改造前「一份进程级本体」等价。"""

# 与模型列宽一致（`ontology_class.uri` String(500)、`ontology_annotation.target_id` String(500)）。
# 超长值必须在入库前拦掉：否则 PostgreSQL 抛 DataError，路由层会把一个
# 本应是 400 的客户端错误报成 500（评审 IM-05）。
# uri 取 500 而非 1000：多字节 URI 以 UTF-8 最长 3 字节/字符，1000 字符可能超
# PG btree 索引条目上限（约 2704 字节），导致 `uq_ontology_class` 写入失败
# （P4.2 迁移 005 已同步把列宽收敛到 500）。
MAX_URI_LENGTH = 500
MAX_TARGET_ID_LENGTH = 500


def validate_uri(uri: str) -> None:
    """校验 URI 长度（公开：`WikiOwlEngine` 写路径在落库前先校验，避免部分写入）。"""
    if len(uri) > MAX_URI_LENGTH:
        raise ValueError(f"URI 长度 {len(uri)} 超过上限 {MAX_URI_LENGTH}")


def validate_target_id(target_id: str) -> None:
    """校验标注目标 ID 长度（同上）。"""
    if len(target_id) > MAX_TARGET_ID_LENGTH:
        raise ValueError(
            f"标注目标 ID 长度 {len(target_id)} 超过上限 {MAX_TARGET_ID_LENGTH}"
        )


@dataclass
class ClassRecord:
    """本体类记录（持久化行 → 引擎可用的对象）。"""

    uri: str
    label: str = ""
    comment: str = ""
    parent_uris: List[str] = field(default_factory=list)
    status: str = "active"


@dataclass
class AnnotationRecord:
    """本体标注记录。"""

    target_type: str
    target_id: str
    class_uris: List[str] = field(default_factory=list)


class OntologyStoreProtocol(Protocol):
    """OWL 引擎对存储后端的**结构化**接口约定（评审 MI-08）。

    `OntologyRepository`（持久化）与 `InMemoryOntologyStore`（离线/单测）
    都按此协议实现——Python 的 Protocol 是结构化类型，两个后端**无需显式继承**，
    只要方法签名匹配即视为实现了协议。`WikiOwlEngine` 的类型注解应引用本协议
    而不是具体实现，后端可插拔才有类型层面的保证。
    """

    def get_class(self, uri: str) -> Optional[ClassRecord]: ...

    def list_classes(self) -> List[ClassRecord]: ...

    def upsert_class(
        self,
        uri: str,
        *,
        label: str = "",
        comment: str = "",
        parent_uris: Optional[List[str]] = None,
        merge_parents: bool = True,
    ) -> Optional[ClassRecord]: ...

    def unregister(self, uri: str) -> bool: ...

    def get_annotation(
        self, target_type: str, target_id: str
    ) -> Optional[AnnotationRecord]: ...

    def list_annotations(self) -> List[AnnotationRecord]: ...

    def upsert_annotation(
        self,
        target_id: str,
        class_uris: List[str],
        target_type: str = "article",
        *,
        merge: bool = True,
    ) -> Optional[AnnotationRecord]: ...

    def get_ttl_content(self) -> str: ...

    def set_ttl_content(self, ttl_content: str) -> None: ...


class OntologyRepository:
    """按租户隔离的本体仓储。

    用法:
        repo = OntologyRepository(db, tenant_id)
        engine = WikiOwlEngine.from_store(repo)
    """

    def __init__(
        self,
        db: Session,
        tenant_id: Optional[int],
        code: str = DEFAULT_ONTOLOGY_CODE,
        *,
        auto_commit: bool = True,
    ) -> None:
        if db is None:
            raise ValueError("OntologyRepository 需要数据库会话")
        if tenant_id is None:
            # 评审 IM-07：HTTP 入口（wiki_owl.get_owl_engine）已用 400 tenant_required
            # 拦掉无租户请求；走到这里说明是**内部调用方**，仍会落到 NULL 分区
            # （所有无租户用户共享，与改造前「全局共享」等价），不静默处理。
            logger.warning(
                "OntologyRepository 的 tenant_id 为 None：本次读写落在 NULL 租户分区，"
                "本体在**所有无租户用户之间共享**（与改造前的进程级单例缺陷等价）。"
            )
        self._db = db
        self._tenant_id = tenant_id
        self._code = code
        # auto_commit=False：由调用方（如 TTL 导入）在一个显式事务里收口，
        # 避免一次请求产生 N 次提交、中途失败留下部分导入（评审 IM-05）。
        self._auto_commit = auto_commit
        self._ontology_id: Optional[int] = None

    # ── 本体行 ───────────────────────────────────────────────────────────────
    @property
    def tenant_id(self) -> Optional[int]:
        return self._tenant_id

    @property
    def code(self) -> str:
        return self._code

    def get_or_create_ontology(self) -> Ontology:
        """获取当前租户的本体行，不存在则创建（幂等）。"""
        if self._ontology_id is not None:
            cached = self._db.get(Ontology, self._ontology_id)
            if cached is not None:
                return cached

        stmt = select(Ontology).where(
            Ontology.tenant_id == self._tenant_id,
            Ontology.code == self._code,
        )
        ontology = self._db.execute(stmt).scalar_one_or_none()
        if ontology is not None:
            self._ontology_id = ontology.id
            return ontology

        ontology = Ontology(
            tenant_id=self._tenant_id,
            code=self._code,
            name=self._code,
            status="draft",
            source="manual",
            version=1,
        )
        try:
            with self._db.begin_nested():  # savepoint：并发创建失败时回滚到此处
                self._db.add(ontology)
                self._db.flush()
        except IntegrityError:
            # 并发下已被其它请求创建，重新读取
            ontology = self._db.execute(stmt).scalar_one_or_none()
            if ontology is None:  # pragma: no cover - 理论上不可达
                raise
        self._ontology_id = ontology.id
        return ontology

    def get_ontology_id(self) -> int:
        return self.get_or_create_ontology().id

    # ── 类读写 ───────────────────────────────────────────────────────────────
    def list_classes(self) -> List[ClassRecord]:
        """列出当前租户本体的全部类（按 URI 排序，保证输出稳定）。"""
        stmt = (
            select(OntologyClass)
            .where(
                OntologyClass.tenant_id == self._tenant_id,
                OntologyClass.ontology_id == self.get_ontology_id(),
            )
            .order_by(OntologyClass.uri)
        )
        return [self._to_class_record(row) for row in self._db.execute(stmt).scalars()]

    def get_class(self, uri: str) -> Optional[ClassRecord]:
        """按 URI 取单个类，不存在返回 None。"""
        stmt = select(OntologyClass).where(
            OntologyClass.tenant_id == self._tenant_id,
            OntologyClass.ontology_id == self.get_ontology_id(),
            OntologyClass.uri == uri,
        )
        row = self._db.execute(stmt).scalar_one_or_none()
        return self._to_class_record(row) if row else None

    def upsert_class(
        self,
        uri: str,
        *,
        label: str = "",
        comment: str = "",
        parent_uris: Optional[List[str]] = None,
        merge_parents: bool = True,
    ) -> ClassRecord:
        """新增或更新类（幂等）。

        :param merge_parents: `True` 与已有父类取并集；`False` **覆盖**父类列表
            （空列表也会清空），供「按原文重建索引」使用。
        """
        validate_uri(uri)
        for parent in parent_uris or []:
            validate_uri(parent)
        ontology_id = self.get_ontology_id()
        stmt = select(OntologyClass).where(
            OntologyClass.tenant_id == self._tenant_id,
            OntologyClass.ontology_id == ontology_id,
            OntologyClass.uri == uri,
        )
        row = self._db.execute(stmt).scalar_one_or_none()

        parents = [p for p in (parent_uris or []) if p]
        if row is None:
            row = OntologyClass(
                tenant_id=self._tenant_id,
                ontology_id=ontology_id,
                uri=uri,
                label=label or "",
                comment=comment or "",
                parent_uris=list(parents),
                status="active",
                display_order=0,
            )
            self._db.add(row)
        else:
            if label:
                row.label = label
            if comment:
                row.comment = comment
            if merge_parents:
                merged = list(row.parent_uris or [])
                for p in parents:
                    if p not in merged:
                        merged.append(p)
                row.parent_uris = merged
            else:
                row.parent_uris = list(parents)
        self._commit()
        return self._to_class_record(row)

    def delete_class(self, uri: str) -> bool:
        """删除类，返回是否真实删除。

        Deprecated: 单一真相源改造后（R2-01/R2-02）注销类请走 `unregister()` ——
        它同时删除 `ttl_content` 里的原文三元组，只删索引行会让类继续出现在导出里。
        """
        if not self._delete_class_rows(uri, self.get_ontology_id()):
            return False
        self._commit()
        return True

    def remove_parent_reference(self, uri: str) -> int:
        """把 `uri` 从其它类的 `parent_uris` 中摘除（对齐旧实现的宾语侧清理）。

        Deprecated: 仅保留 API 兼容性，注销类请走 `unregister()`（单事务完成三处清理）。

        :return: 被修改的类数量
        """
        changed = self._remove_parent_reference_rows(uri, self.get_ontology_id())
        if changed:
            self._commit()
        return changed

    def remove_class_reference(self, uri: str) -> int:
        """把 `uri` 从 `ontology_annotation.class_uris` 中摘除。

        对齐改造前 `unregister_class` 的语义：旧实现会删除所有
        `<target> a <uri>` 三元组，类删除后不应残留指向它的标注（评审 IM-04）。

        Deprecated: 仅保留 API 兼容性，注销类请走 `unregister()`（单事务完成三处清理）。

        :return: 被修改的标注数量
        """
        changed = self._remove_class_reference_rows(uri, self.get_ontology_id())
        if changed:
            self._commit()
        return changed

    def unregister(self, uri: str) -> bool:
        """原子地注销一个类：删类 + 摘父类引用 + 摘标注引用，**只提交一次**。

        拆成三次独立提交时，中途失败会留下「类已删、标注还在」的中间态。
        """
        ontology_id = self.get_ontology_id()
        if not self._delete_class_rows(uri, ontology_id):
            return False
        self._remove_parent_reference_rows(uri, ontology_id)
        self._remove_class_reference_rows(uri, ontology_id)
        self._commit()
        return True

    def _delete_class_rows(self, uri: str, ontology_id: int) -> bool:
        stmt = select(OntologyClass).where(
            OntologyClass.tenant_id == self._tenant_id,
            OntologyClass.ontology_id == ontology_id,
            OntologyClass.uri == uri,
        )
        row = self._db.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        self._db.delete(row)
        return True

    def _remove_parent_reference_rows(self, uri: str, ontology_id: int) -> int:
        changed = 0
        stmt = select(OntologyClass).where(
            OntologyClass.tenant_id == self._tenant_id,
            OntologyClass.ontology_id == ontology_id,
        )
        for row in self._db.execute(stmt).scalars():
            parents = list(row.parent_uris or [])
            if uri not in parents:
                continue
            row.parent_uris = [p for p in parents if p != uri]
            changed += 1
        return changed

    def _remove_class_reference_rows(self, uri: str, ontology_id: int) -> int:
        changed = 0
        stmt = select(OntologyAnnotation).where(
            OntologyAnnotation.tenant_id == self._tenant_id,
            OntologyAnnotation.ontology_id == ontology_id,
        )
        for row in self._db.execute(stmt).scalars():
            uris = list(row.class_uris or [])
            if uri not in uris:
                continue
            row.class_uris = [u for u in uris if u != uri]
            changed += 1
        return changed

    # ── TTL 原始内容 ─────────────────────────────────────────────────────────
    def get_ttl_content(self) -> str:
        """取本体的 TTL **原文**（唯一真相源：类与标注索引均由它派生）。"""
        return self.get_or_create_ontology().ttl_content or ""

    def set_ttl_content(self, ttl_content: str) -> None:
        """整体覆盖 TTL 内容。"""
        ontology = self.get_or_create_ontology()
        ontology.ttl_content = ttl_content or ""
        self._commit()

    # ── 标注读写 ─────────────────────────────────────────────────────────────
    def list_annotations(self) -> List[AnnotationRecord]:
        """列出当前租户本体的全部标注。"""
        stmt = select(OntologyAnnotation).where(
            OntologyAnnotation.tenant_id == self._tenant_id,
            OntologyAnnotation.ontology_id == self.get_ontology_id(),
        )
        return [
            AnnotationRecord(
                target_type=row.target_type,
                target_id=row.target_id,
                class_uris=list(row.class_uris or []),
            )
            for row in self._db.execute(stmt).scalars()
        ]

    def get_annotation(
        self, target_id: str, target_type: str = "article"
    ) -> Optional[AnnotationRecord]:
        stmt = select(OntologyAnnotation).where(
            OntologyAnnotation.tenant_id == self._tenant_id,
            OntologyAnnotation.ontology_id == self.get_ontology_id(),
            OntologyAnnotation.target_type == target_type,
            OntologyAnnotation.target_id == target_id,
        )
        row = self._db.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return AnnotationRecord(
            target_type=row.target_type,
            target_id=row.target_id,
            class_uris=list(row.class_uris or []),
        )

    def upsert_annotation(
        self,
        target_id: str,
        class_uris: List[str],
        target_type: str = "article",
        *,
        merge: bool = True,
    ) -> AnnotationRecord:
        """新增或更新标注（幂等）。"""
        validate_target_id(target_id)
        for class_uri in class_uris or []:
            validate_uri(class_uri)
        ontology_id = self.get_ontology_id()
        stmt = select(OntologyAnnotation).where(
            OntologyAnnotation.tenant_id == self._tenant_id,
            OntologyAnnotation.ontology_id == ontology_id,
            OntologyAnnotation.target_type == target_type,
            OntologyAnnotation.target_id == target_id,
        )
        row = self._db.execute(stmt).scalar_one_or_none()
        uris = [u for u in (class_uris or []) if u]
        if row is None:
            row = OntologyAnnotation(
                tenant_id=self._tenant_id,
                ontology_id=ontology_id,
                target_type=target_type,
                target_id=target_id,
                class_uris=list(uris),
            )
            self._db.add(row)
        else:
            merged = list(row.class_uris or [])
            for u in uris:
                if u not in merged:
                    merged.append(u)
            row.class_uris = merged if merge else list(uris)
        self._commit()
        return AnnotationRecord(
            target_type=row.target_type,
            target_id=row.target_id,
            class_uris=list(row.class_uris or []),
        )

    # ── 内部 ─────────────────────────────────────────────────────────────────
    def _commit(self) -> None:
        """提交（或仅 flush）。

        `auto_commit=False` 时只 `flush()`：写操作进入当前事务但不落盘，
        由调用方统一 `commit()` / `rollback()`，保证一次导入的原子性。
        """
        if not self._auto_commit:
            self._db.flush()
            return
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.exception("本体写入失败，已回滚")
            raise

    @staticmethod
    def _to_class_record(row: OntologyClass) -> ClassRecord:
        return ClassRecord(
            uri=row.uri,
            label=row.label or "",
            comment=row.comment or "",
            parent_uris=list(row.parent_uris or []),
            status=row.status or "active",
        )


class InMemoryOntologyStore:
    """内存版仓储（与改造前 `rdflib.Graph` 等价的后端）。

    仅用于离线脚本/单测：写入不落库，进程重启即丢。
    `WikiOwlEngine` 未显式传入 store 时使用它，并打印 warning。
    """

    def __init__(self, tenant_id: Optional[int] = None, code: str = DEFAULT_ONTOLOGY_CODE) -> None:
        self.tenant_id = tenant_id
        self.code = code
        self._classes: Dict[str, ClassRecord] = {}
        self._annotations: Dict[str, AnnotationRecord] = {}
        self._ttl_content: str = ""

    def list_classes(self) -> List[ClassRecord]:
        return [self._clone_class(c) for c in sorted(self._classes.values(), key=lambda r: r.uri)]

    def get_class(self, uri: str) -> Optional[ClassRecord]:
        record = self._classes.get(uri)
        return self._clone_class(record) if record else None

    def upsert_class(
        self,
        uri: str,
        *,
        label: str = "",
        comment: str = "",
        parent_uris: Optional[List[str]] = None,
        merge_parents: bool = True,
    ) -> ClassRecord:
        parents = [p for p in (parent_uris or []) if p]
        record = self._classes.get(uri)
        if record is None:
            record = ClassRecord(uri=uri, label=label or "", comment=comment or "", parent_uris=list(parents))
            self._classes[uri] = record
            return self._clone_class(record)
        if label:
            record.label = label
        if comment:
            record.comment = comment
        if merge_parents:
            for p in parents:
                if p not in record.parent_uris:
                    record.parent_uris.append(p)
        else:
            record.parent_uris = list(parents)  # 覆盖语义（含清空）
        return self._clone_class(record)

    def delete_class(self, uri: str) -> bool:
        return self._classes.pop(uri, None) is not None

    def remove_parent_reference(self, uri: str) -> int:
        return self._remove_parent_reference_rows(uri)

    def remove_class_reference(self, uri: str) -> int:
        """把 `uri` 从所有标注的 `class_uris` 中摘除（与 `OntologyRepository` 对齐）。"""
        changed = 0
        for record in self._annotations.values():
            if uri in record.class_uris:
                record.class_uris = [u for u in record.class_uris if u != uri]
                changed += 1
        return changed

    def unregister(self, uri: str) -> bool:
        """原子地注销一个类：删类 + 摘父类引用 + 摘标注引用。"""
        if self._classes.pop(uri, None) is None:
            return False
        self._remove_parent_reference_rows(uri)
        self.remove_class_reference(uri)
        return True

    def _remove_parent_reference_rows(self, uri: str) -> int:
        changed = 0
        for record in self._classes.values():
            if uri in record.parent_uris:
                record.parent_uris = [p for p in record.parent_uris if p != uri]
                changed += 1
        return changed

    def get_ttl_content(self) -> str:
        return self._ttl_content

    def set_ttl_content(self, ttl_content: str) -> None:
        self._ttl_content = ttl_content or ""

    def list_annotations(self) -> List[AnnotationRecord]:
        return [
            AnnotationRecord(a.target_type, a.target_id, list(a.class_uris))
            for a in self._annotations.values()
        ]

    def get_annotation(
        self, target_id: str, target_type: str = "article"
    ) -> Optional[AnnotationRecord]:
        record = self._annotations.get(self._key(target_type, target_id))
        if record is None:
            return None
        return AnnotationRecord(record.target_type, record.target_id, list(record.class_uris))

    def upsert_annotation(
        self,
        target_id: str,
        class_uris: List[str],
        target_type: str = "article",
        *,
        merge: bool = True,
    ) -> AnnotationRecord:
        key = self._key(target_type, target_id)
        record = self._annotations.get(key)
        uris = [u for u in (class_uris or []) if u]
        if record is None:
            record = AnnotationRecord(target_type=target_type, target_id=target_id, class_uris=list(uris))
            self._annotations[key] = record
            return record
        if merge:
            for u in uris:
                if u not in record.class_uris:
                    record.class_uris.append(u)
        else:
            record.class_uris = list(uris)
        return record

    @staticmethod
    def _key(target_type: str, target_id: str) -> str:
        return f"{target_type}::{target_id}"

    @staticmethod
    def _clone_class(record: ClassRecord) -> ClassRecord:
        return ClassRecord(
            uri=record.uri,
            label=record.label,
            comment=record.comment,
            parent_uris=list(record.parent_uris),
            status=record.status,
        )
