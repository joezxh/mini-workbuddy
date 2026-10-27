"""外部文档 ↔ 本地文档映射表（落地 spec §5 设计）。

作用：记录「外部平台的某篇文档」与「本知识库某条 kms_document」的对应关系，
是需求 3「已存在则覆盖，不存在则新建」的**唯一判定依据**：

- 映射不存在            → 新建 KbDocument
- 映射存在且 content_hash 相同 → 跳过（不重复嵌入）
- 映射存在但 hash 变化   → 覆盖同一文档（复用 uuid_code）并重新切片

唯一约束 ``uq_ext_doc(tenant_id, knowledge_id, source_type, external_doc_id)``
保证同一篇外部文档在同一知识库下只有一条映射，重复导入天然幂等。
"""
from sqlalchemy import (
    BigInteger, Column, ForeignKey, String, TIMESTAMP, UniqueConstraint, func,
)

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbExternalDocMap(Base, TenantMixin):
    __tablename__ = "kb_external_doc_map"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "knowledge_id", "source_type", "external_doc_id",
            name="uq_ext_doc",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_id = Column(BigInteger, nullable=False, index=True,
                          comment="所属知识库（type=3 容器）")
    source_type = Column(String(32), nullable=False,
                         comment="外部平台: feishu|lark|feishu_drive|lark_drive|yuque|dingtalk|wecom|notion|gitlab|ima|rss|confluence|seafile|github|google_drive|onedrive|web_crawler|slack|imap")
    external_doc_id = Column(String(500), nullable=False,
                             comment="平台内稳定唯一标识（覆盖判定的外部键）")
    external_title = Column(String(500), nullable=True, comment="外部文档标题快照")
    node_type = Column(String(16), nullable=True, comment="space|folder|doc")
    external_updated_at = Column(String(64), nullable=True,
                                 comment="外部平台记录的更新时间（原始字符串）")
    document_id = Column(BigInteger, ForeignKey("kms_document.id", ondelete="SET NULL"),
                         nullable=True, index=True, comment="落地的本地文档")
    content_hash = Column(String(64), nullable=True,
                          comment="正文 sha256；命中即跳过嵌入")
    deleted = Column(String(1), nullable=False, server_default="0",
                     comment="外部侧已删除: 0|1")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(),
                        onupdate=func.now(), comment="更新时间")
