"""KB 文档实体（spec §10.2）：文档列表页与处理状态机的承载表。

``kb_segment.document_id`` 的字符串值即本表 ``uuid_code``；文档状态机：
pending → processing → completed | failed（后台摄取管线回写）。
"""
import uuid

from sqlalchemy import BigInteger, Column, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


def new_document_uuid() -> str:
    """生成 kb_segment.document_id 使用的 UUID（独立函数便于测试）。"""
    return uuid.uuid4().hex


class KbDocument(Base, TenantMixin):
    __tablename__ = "kb_document"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    uuid_code = Column(String(64), nullable=False, unique=True,
                       default=new_document_uuid, comment="对外文档 ID（=kb_segment.document_id）")
    knowledge_id = Column(BigInteger, nullable=False, index=True, comment="所属统一容器")
    collection = Column(String(128), nullable=False, comment="落库集合名 → kb_collection.name")
    name = Column(String(500), nullable=False, comment="文档显示名/来源名")
    source_type = Column(String(16), nullable=False, server_default="upload",
                         comment="来源: upload|db_table|api|qa_import|connector")
    file_type = Column(String(32), nullable=True, comment="文件类型（pdf/docx/md/…）")
    file_size = Column(BigInteger, nullable=True, comment="字节数")
    status = Column(String(16), nullable=False, server_default="pending",
                    comment="状态: pending|processing|completed|failed")
    segment_count = Column(Integer, nullable=False, server_default="0", comment="切片数")
    error_detail = Column(Text, nullable=True, comment="失败详情（含步骤名）")
    meta = Column(JSONB, nullable=True, comment="附加元数据")
    creator_id = Column(BigInteger, nullable=True, comment="创建人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(),
                        onupdate=func.now(), comment="更新时间")
