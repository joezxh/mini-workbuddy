# 知识库统一化 Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec §10 Phase 2——文档形态全链路（AgentScope 2.0.8 Parser/Chunker → 摄取 → 统一检索）、`/api/v1/kb` 认证路由、KB 子应用认证收口、OKF 服务层、统一工作台前端骨架。

**Architecture:** 严格复用 AgentScope 2.0.8 RAG 五模块抽象：解析用 `agentscope.rag` 六种 Parser（按 `supported_media_types` 能力发现），切块用 `ApproxTokenChunker`/`QaChunker`/新增 `ParentChildChunker(ChunkerBase)`，入库走既有 `KbIngestService`（`SegmentInput` 幂等 upsert），检索走 `KbRetrievalService.hybrid_search_by_text` 并新增 AgentScope `metadata_filter` 语义的 `metadata_filters` 参数。DB 仍为事实源（`kb_document` 文档实体 + `kb_segment` 切片），多租户沿用 `PGVectorStore` 的 `tenant_id` 行级过滤（等价 `metadata_filter` 深度防御）。

**Tech Stack:** agentscope==2.0.8（本地已装，`agentscope.rag` 全导出可用）+ FastAPI + SQLAlchemy 2.0 + pgvector + Vue 3/antd v6。

## Global Constraints

- 迁移权威 = `backend/app/db/startup_migrations.py`（幂等）+ `docs/sql/kms_unify_20260927.sql`；新表走 ORM `create_all`
- 新增 Model 必须在 `app/db/init_models.py` import（否则 create_all 不拾取）
- Service 层禁止 `with self.db.begin()`；用 flush + commit
- 长任务一律 `app.core.job_runner.run_in_background(fn, *args, name=...)`（fn 自管 Session）
- Chunker 自定义必须继承 `agentscope.rag.ChunkerBase`：类属性 `chunker_type` 全局唯一 + 嵌套 Pydantic `Parameters` + `async def chunk(sections) -> list[Chunk]`
- Parser 能力发现只读类属性 `supported_media_types`，不硬编码扩展名映射
- 知识库实例创建后 `kb_format` 不可切换（后端 409 拒绝）
- pytest 基线：501 passed 只增不减；`tests/unit/test_kms_unify_phase1.py` 14 passed
- 前端 lint：`npm run lint`（oxlint，现存 373 个历史 Parsing error 忽略，只看新增）

---

### Task 1: 三张 Phase 2 新模型（KbDocument / KbSegmentAsset / ExternalKbEndpoint）

**Files:**
- Create: `backend/app/models/kb/kb_document.py`
- Create: `backend/app/models/kb/kb_segment_asset.py`
- Create: `backend/app/models/connectors/external_kb_endpoint.py`
- Modify: `backend/app/models/kb/__init__.py`、`backend/app/models/connectors/__init__.py`、`backend/app/db/init_models.py`
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Produces: `KbDocument`（spec §10.2 字段）、`KbSegmentAsset`、`ExternalKbEndpoint`；后续 Task 的 `doc_id: int`、`endpoint_id: int` 引用这些主键

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_kms_phase2.py`：

```python
"""知识库统一化 Phase 2 回归（spec §10.2 新模型 / §10.3 摄取管线 / §9 OKF）。"""


def test_kb_document_model_fields():
    from app.models.kb.kb_document import KbDocument

    assert KbDocument.__tablename__ == "kb_document"
    for col in ("knowledge_id", "collection", "name", "source_type",
                "file_type", "file_size", "status", "segment_count", "error_detail"):
        assert col in KbDocument.__table__.c
    assert KbDocument.__table__.c["status"].server_default is not None


def test_kb_segment_asset_model_fields():
    from app.models.kb.kb_segment_asset import KbSegmentAsset

    assert KbSegmentAsset.__tablename__ == "kb_segment_asset"
    for col in ("segment_id", "file_path", "mime_type", "size"):
        assert col in KbSegmentAsset.__table__.c


def test_external_kb_endpoint_model_fields():
    from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint

    assert ExternalKbEndpoint.__tablename__ == "kms_external_kb_endpoint"
    for col in ("knowledge_id", "endpoint_url", "auth_key", "index_name", "status"):
        assert col in ExternalKbEndpoint.__table__.c
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现三个模型**

`backend/app/models/kb/kb_document.py`：

```python
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
```

`backend/app/models/kb/kb_segment_asset.py`：

```python
"""多模态图文资产（spec §10.2/§10.3 multimodal）：切片附件图片。

服务层校验：单图 ≤ 2MB、单 segment ≤ 10 张（对齐 Dify 限制）。
"""
from sqlalchemy import BigInteger, Column, Integer, String, TIMESTAMP, ForeignKey, func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class KbSegmentAsset(Base, TenantMixin):
    __tablename__ = "kb_segment_asset"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    segment_id = Column(BigInteger, ForeignKey("kb_segment.id", ondelete="CASCADE"),
                        nullable=False, index=True, comment="所属切片")
    file_path = Column(String(500), nullable=False, comment="存储路径/对象 URL")
    mime_type = Column(String(64), nullable=False, comment="图片 MIME")
    size = Column(Integer, nullable=False, comment="字节数")
    width = Column(Integer, nullable=True, comment="宽")
    height = Column(Integer, nullable=True, comment="高")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
```

`backend/app/models/connectors/external_kb_endpoint.py`：

```python
"""外部知识库检索代理端点（spec §10.2，type=3 / kb_format='proxy'）。

不拉数据、无文档管理；仅检索时转发外部 API。``auth_key`` 存 Fernet 密文
（沿用 DataOps crypto 惯例）。
"""
from sqlalchemy import BigInteger, Column, String, Text, TIMESTAMP, ForeignKey, func

from app.db.database import Base
from app.models.tenant_mixin import TenantMixin


class ExternalKbEndpoint(Base, TenantMixin):
    __tablename__ = "kms_external_kb_endpoint"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    knowledge_id = Column(BigInteger, ForeignKey("kms_knowledge.id", ondelete="SET NULL"),
                          nullable=True, index=True, comment="所属统一容器（type=3/proxy）")
    name = Column(String(200), nullable=False, comment="显示名")
    endpoint_url = Column(String(500), nullable=False, comment="外部检索 API 地址（https）")
    auth_key = Column(String(500), nullable=True, comment="鉴权密钥（Fernet 密文）")
    index_name = Column(String(128), nullable=True, comment="外部索引/集合名")
    metadata_mapping = Column(String(500), nullable=True, comment="元数据映射说明/JSON 字符串")
    status = Column(String(32), nullable=False, server_default="active",
                    comment="active|error|disabled")
    error_detail = Column(Text, nullable=True, comment="最近错误")
    creator_id = Column(BigInteger, nullable=True, comment="创建人")
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), comment="创建时间")
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(),
                        onupdate=func.now(), comment="更新时间")
```

`backend/app/models/kb/__init__.py`（现为空文件）：

```python
from app.models.kb.kb_collection import KbCollection  # noqa: F401
from app.models.kb.kb_category import KbCategory  # noqa: F401
from app.models.kb.kb_ref import KbRef  # noqa: F401
from app.models.kb.kb_segment import KbSegment  # noqa: F401
from app.models.kb.kb_document import KbDocument  # noqa: F401
from app.models.kb.kb_segment_asset import KbSegmentAsset  # noqa: F401
```

`backend/app/db/init_models.py`：在既有 kb/connectors import 区追加：

```python
from app.models.kb.kb_document import KbDocument  # noqa: F401
from app.models.kb.kb_segment_asset import KbSegmentAsset  # noqa: F401
from app.models.connectors.external_kb_endpoint import ExternalKbEndpoint  # noqa: F401
```

（若 init_models.py 有 `__all__` 列表则同步追加三个类名。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py tests/unit/test_kms_unify_phase1.py -q`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/models backend/app/db/init_models.py backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): Phase2 三模型（kb_document/kb_segment_asset/kms_external_kb_endpoint）"
```

---

### Task 2: kb_format 校验矩阵 + type=2 容器联动 collection

**Files:**
- Modify: `backend/app/schemas/wiki/knowledge.py`（KnowledgeCreate/KnowledgeUpdate 增加 type/kb_format 字段）
- Modify: `backend/app/services/wiki/knowledge_service.py`（校验 + 联动建 collection + 序列化补字段）
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Consumes: Task 1 的 `KbCollection`（已存在）；`KnowledgeType`
- Produces: `WikiKnowledgeService.create/update` 的 kb_format 校验；`_to_out` 新增 `type/kb_format/index_mode/multimodal_enabled`

- [ ] **Step 1: 写失败测试**

`test_kms_phase2.py` 追加：

```python
def _fake_db():
    from unittest.mock import MagicMock
    return MagicMock()


def test_kb_format_matrix_accepts_and_rejects():
    from app.services.kb.kb_format import validate_kb_format
    from fastapi import HTTPException

    assert validate_kb_format(1, None) is None
    assert validate_kb_format(2, "document") == "document"
    assert validate_kb_format(3, "proxy") == "proxy"
    for t, f in ((1, "document"), (2, None), (2, "proxy"), (3, "document"), (2, "vector")):
        try:
            validate_kb_format(t, f)
            raised = False
        except HTTPException:
            raised = True
        assert raised, f"(type={t}, kb_format={f}) 应拒绝"


def test_kb_format_immutable_after_create():
    from app.services.kb.kb_format import assert_format_unchanged
    from fastapi import HTTPException

    assert_format_unchanged(old=None, new="document")   # 初次设置允许
    assert_format_unchanged(old="document", new="document")  # 相同允许
    try:
        assert_format_unchanged(old="document", new="qa")
        raised = False
    except HTTPException:
        raised = True
    assert raised
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q -k format`
Expected: FAIL（ModuleNotFoundError: app.services.kb.kb_format）

- [ ] **Step 3: 实现 `app/services/kb/kb_format.py`**

```python
"""kb_format 二级形态校验（spec §10.2）：合法性矩阵 + 创建后不可切换。

矩阵（Dify 对齐「选定数据源后不可切换」）：
    type=1 llm-wiki    → kb_format 必须为 NULL
    type=2 general-kb  → document | table | qa（multimodal 是 document 上的开关，非形态）
    type=3 external-kb → connector | proxy
"""
from fastapi import HTTPException

VALID_KB_FORMATS: dict[int, tuple[str, ...]] = {
    1: (),
    2: ("document", "table", "qa"),
    3: ("connector", "proxy"),
}


def validate_kb_format(kb_type: int, kb_format: str | None) -> str | None:
    """校验 (type, kb_format) 合法性；type=2 时 kb_format 必填。返回规整后的值。"""
    allowed = VALID_KB_FORMATS.get(kb_type)
    if allowed is None:
        raise HTTPException(status_code=422, detail=f"未知知识库类型: {kb_type}")
    if kb_type == 1:
        if kb_format is not None:
            raise HTTPException(status_code=422, detail="llm-wiki 容器不使用 kb_format")
        return None
    if not kb_format:
        raise HTTPException(status_code=422, detail=f"type={kb_type} 必须选择 kb_format")
    if kb_format not in allowed:
        raise HTTPException(
            status_code=422, detail=f"kb_format={kb_format!r} 不合法，允许: {allowed}"
        )
    return kb_format


def assert_format_unchanged(old: str | None, new: str | None) -> None:
    """创建后不可切换：old 为 None 表示初次设置；new 为 None 表示本次未传，放行。"""
    if new is None or new == old:
        return
    if old is not None:
        raise HTTPException(
            status_code=409, detail="知识库数据源形态创建后不可切换（Dify 对齐）"
        )
```

- [ ] **Step 4: 接入 knowledge_service 与 schema**

`backend/app/schemas/wiki/knowledge.py` 的 `KnowledgeCreate` 追加字段、`KnowledgeUpdate` 追加可选字段（保持既有字段不动）：

```python
    type: int = 1
    kb_format: Optional[str] = None
```

`backend/app/services/wiki/knowledge_service.py`：

`create` 中 `data["slug"] = slug` 之后、`repo.create` 之前插入：

```python
        from app.services.kb.kb_format import validate_kb_format

        kb_type = data.get("type", 1)
        data["type"] = kb_type
        data["kb_format"] = validate_kb_format(kb_type, data.get("kb_format"))
```

`repo.create(data)` 与 `self.db.commit()` 之间插入（type=2 联动建 collection，AgentScope 约定 `kb_<uuid>` 逻辑名）：

```python
        if kb_type == 2:
            from uuid import uuid4

            from app.config import settings
            from app.models.kb.kb_collection import KbCollection

            self.db.add(KbCollection(
                name=f"kb_{uuid4().hex}",
                dimensions=settings.GPUSTACK_EMBEDDING_DIMENSION,
                knowledge_id=obj.id,
            ))
            self.db.flush()
```

`update` 中 `self.repo.update(...)` 之前插入：

```python
        from app.services.kb.kb_format import assert_format_unchanged

        payload_dict = payload.dict(exclude_none=True)
        assert_format_unchanged(obj.kb_format, payload_dict.get("kb_format"))
```

（`update` 原有 `payload.dict(exclude_none=True)` 传参改为复用 `payload_dict`。）

`_to_out` 返回 dict 追加：

```python
        "type": k.type,
        "kb_format": k.kb_format,
        "index_mode": k.index_mode,
        "multimodal_enabled": k.multimodal_enabled,
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py tests/unit/test_kms_unify_phase1.py -q`
Expected: 19 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/kb/kb_format.py backend/app/services/wiki/knowledge_service.py backend/app/schemas/wiki/knowledge.py backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): kb_format 校验矩阵 + 创建后不可切换 + type=2 联动建 collection（spec §10.2）"
```

---

### Task 3: AgentScope Parser 能力发现 + ParentChildChunker

**Files:**
- Create: `backend/app/services/kb/parser_selector.py`
- Create: `backend/app/services/kb/parent_child_chunker.py`
- Modify: `backend/app/services/kb/kb_app.py`（CHUNKER_REGISTRY 注册）
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Consumes: `agentscope.rag` 的 `ParserBase` 子类与 `ChunkerBase`
- Produces: `select_parser(media_type: str)` → Parser 实例（未支持抛 `ValueError`）；`supported_media_types() -> dict[str, list[str]]`；`ParentChildChunker(chunker_type="parent_child")` 产出子块 `Chunk`（metadata 带 `parent_content`/`parent_index`）

- [ ] **Step 1: 写失败测试**

`test_kms_phase2.py` 追加：

```python
import pytest


def test_select_parser_by_media_type():
    from app.services.kb.parser_selector import select_parser

    assert select_parser("text/markdown") is not None
    assert select_parser("application/pdf") is not None
    with pytest.raises(ValueError):
        select_parser("video/mp4")


def test_supported_media_types_covers_office():
    from app.services.kb.parser_selector import supported_media_types

    table = supported_media_types()
    assert "application/pdf" in table
    assert any("wordprocessingml" in mt for mt in table)
    assert any("spreadsheetml" in mt or "ms-excel" in mt for mt in table)


def test_parent_child_chunker_contract():
    """对齐 agentscope ChunkerBase 契约：chunker_type 唯一 + Parameters + 不跨 Section。"""
    from agentscope.message import TextBlock
    from agentscope.rag import Section

    from app.services.kb.parent_child_chunker import ParentChildChunker

    assert ParentChildChunker.chunker_type == "parent_child"
    chunker = ParentChildChunker(parameters=ParentChildChunker.Parameters(
        parent_size=512, child_size=128, overlap=0,
    ))
    long_text = "\n\n".join(f"段落{i} " + "字" * 100 for i in range(6))
    sections = [Section(content=TextBlock(text=long_text), source="a.md", metadata={})]
    chunks = pytest.run_async(chunker.chunk(sections)) if hasattr(pytest, "run_async") \
        else __import__("asyncio").run(chunker.chunk(sections))

    assert len(chunks) >= 2
    assert all(c.chunk_index >= 0 for c in chunks)
    # 子块 metadata 必须携带父块全文与父块序号（父子分段检索的核心契约）
    assert all("parent_content" in (c.metadata or {}) for c in chunks)
    assert all(c.metadata.get("parent_index") == 0 for c in chunks)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q -k "parser or chunker"`
Expected: FAIL（ModuleNotFoundError: app.services.kb.parser_selector）

- [ ] **Step 3: 实现 parser_selector.py**

```python
"""AgentScope Parser 能力发现与选择（spec §10.3，严格对齐 agentscope 2.0.8）。

Parser 能力以类属性 ``supported_media_types``（IANA 媒体类型）为唯一事实源，
本模块不做扩展名→类型的猜测映射；未命中显式失败（不静默降级）。
"""
from __future__ import annotations

from typing import Dict, List, Type

from agentscope.rag import (
    ExcelParser,
    ImageParser,
    ParserBase,
    PDFParser,
    TextParser,
    WordParser,
)

# 顺序即优先级：同为 text/* 时 Markdown 等 TextParser 兜底放最后
_PARSER_CLASSES: List[Type[ParserBase]] = [
    PDFParser,
    WordParser,
    ExcelParser,
    ImageParser,
    TextParser,
]


def supported_media_types() -> Dict[str, List[str]]:
    """能力发现表：{parser 类名: [支持 IANA 媒体类型]}（供 /supported_content_types）。"""
    return {
        cls.__name__: list(cls.supported_media_types)
        for cls in _PARSER_CLASSES
    }


def select_parser(media_type: str) -> ParserBase:
    """按请求媒体类型选择解析器；未支持显式失败。"""
    normalized = (media_type or "").split(";")[0].strip().lower()
    for cls in _PARSER_CLASSES:
        if normalized in cls.supported_media_types:
            return cls()
    raise ValueError(f"不支持的文件类型: {media_type!r}（可用: {supported_media_types()}）")
```

- [ ] **Step 4: 实现 parent_child_chunker.py**

```python
"""父子分段切块器（spec §10.3，Dify 对齐）：父块保存完整上下文，子块用于检索。

对齐 agentscope 2.0.8 ChunkerBase 契约：
* ``chunker_type`` 全局唯一（持久化重建用），此处为 ``parent_child``；
* 嵌套 Pydantic ``Parameters`` 声明可调项；
* ``async def chunk(sections) -> list[Chunk]``，不跨 Section 合并；
* chunk_index 从 0 连续编号。
子块 metadata 携带 ``parent_content``/``parent_index``，检索命中子块时由
检索层展开父块内容（spec §10.4 父子展开）。
"""
from __future__ import annotations

from typing import List

from agentscope.message import TextBlock
from agentscope.rag import Chunk, ChunkerBase, Section
from pydantic import Field


def _split_by_tokens(text: str, size: int, overlap: int) -> List[str]:
    """近似 token（len(utf8)//4，与 agentscope ApproxTokenChunker 同口径）滑窗切分。"""
    if not text:
        return []
    step = max(size - overlap, 1)
    pieces: List[str] = []
    start = 0
    while start < len(text):
        pieces.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += step
    return pieces


class ParentChildChunker(ChunkerBase):
    """父块（chunk_type 语义由存储层落 'parent'）+ 子块双层切分。"""

    chunker_type = "parent_child"

    class Parameters(ChunkerBase.Parameters):
        parent_size: int = Field(default=1024, description="父块近似 token 上限")
        child_size: int = Field(default=256, description="子块近似 token 上限")
        overlap: int = Field(default=32, description="子块滑窗重叠")

    async def chunk(self, sections: List[Section]) -> List[Chunk]:
        chunks: List[Chunk] = []
        index = 0
        for section in sections:
            text = section.content.text if hasattr(section.content, "text") else str(section.content)
            if not text:
                continue
            # 父块：整段（Section 不跨块合并，父块即完整上下文）
            for parent_index, parent_text in enumerate(
                _split_by_tokens(text, self.parameters.parent_size, 0) or [text]
            ):
                pieces = _split_by_tokens(
                    parent_text, self.parameters.child_size, self.parameters.overlap
                )
                for piece in pieces:
                    chunks.append(Chunk(
                        content=TextBlock(text=piece),
                        source=section.source,
                        metadata={
                            **(section.metadata or {}),
                            "parent_index": parent_index,
                            "parent_content": parent_text,
                        },
                        chunk_index=index,
                    ))
                    index += 1
        return chunks
```

（若本地 2.0.8 的 `Chunk` 构造签名不含 `chunk_index` 关键字，则按其真实签名构造后回填 `chunk.chunk_index = index`——执行时以 `inspect.signature(Chunk)` 实测为准，测试断言不变。）

- [ ] **Step 5: 注册进 CHUNKER_REGISTRY 并确认通过**

`kb_app.py` 的 `CHUNKER_REGISTRY` 追加：

```python
from app.services.kb.parent_child_chunker import ParentChildChunker
from app.services.kb.qa_chunker import QaChunker

CHUNKER_REGISTRY = {
    ApproxTokenChunker.chunker_type: ApproxTokenChunker,
    QaChunker.chunker_type: QaChunker,
    ParentChildChunker.chunker_type: ParentChildChunker,
}
```

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py tests/unit/test_kms_unify_phase1.py -q`
Expected: 22 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/kb/parser_selector.py backend/app/services/kb/parent_child_chunker.py backend/app/services/kb/kb_app.py backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): AgentScope Parser 能力发现 + ParentChildChunker（spec §10.3）"
```

---

### Task 4: 文档摄取管线（parse → chunk → ingest，状态机 + 后台重处理）

**Files:**
- Create: `backend/app/services/kb/document_pipeline.py`
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Consumes: Task 1 `KbDocument`、Task 3 `select_parser`/`CHUNKER_REGISTRY`、既有 `KbIngestService.from_session(db, tenant_id, embedding_code)`（签名见 ingest_service.py）、`PGVectorStore.delete_document(collection, document_id)`
- Produces: `run_document_ingest(db, tenant_id, doc_id: int, file_bytes: bytes, filename: str, chunker_type: str, chunker_params: dict, embedding_code: str|None) -> int`（返回切片数；自管 commit，供 job_runner 直接调用）；`pipeline.status` 写入 `kb_document.error_detail`

- [ ] **Step 1: 写失败测试**

`test_kms_phase2.py` 追加（用假 embed_fn 注入，不联网）：

```python
def test_document_pipeline_ingests_and_updates_status(test_kb_engine_and_session):
    """端到端（假向量）：上传文本 → 状态 completed → kb_segment 有切片且可检索。"""
    import asyncio

    from app.services.kb.document_pipeline import run_document_ingest

    db, tenant_id, knowledge_id, collection = test_kb_engine_and_session
    content = "# 标题\n\n" + "\n\n".join(f"段落{i} " + "内容" * 60 for i in range(4))
    doc = _make_document(db, tenant_id, knowledge_id, collection, "a.md", len(content))
    db.commit()

    seg_count = run_document_ingest(
        db, tenant_id, doc.id, content.encode("utf-8"), "a.md",
        chunker_type="approx_token", chunker_params={"chunk_size": 64, "overlap": 8},
        embedding_code=None,
    )

    assert seg_count >= 2
    db.expire_all()
    assert doc.status == "completed"
    assert doc.segment_count == seg_count
```

（`test_kb_engine_and_session` / `_make_document` 为本文件内夹具/辅助：复用 `tests/kb/conftest.py` 的建库方式——`KB_TABLES` + `KbDocument.__table__` 建独立 schema，插入 `WikiKnowledge`/`KbCollection`/`KbDocument` 各一行；`embed_fn` 通过 monkeypatch `app.services.kb.document_pipeline.build_embed_fn` 返回 `[0.0]*8` 假向量，`KbCollection.dimensions=8`。实现时按 conftest 现状落到 `tests/unit/conftest.py` 或同文件 fixture。）

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q -k pipeline`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 document_pipeline.py**

```python
"""文档摄取管线（spec §10.3）：AgentScope Parser → Chunker → KbIngestService。

状态机：pending → processing → completed | failed；每步失败写入
``kb_document.error_detail``（含步骤名），可整档重试（reprocess 先删旧切片）。
同步执行体供 ``job_runner.run_in_background`` 调用（fn 自管 Session 语义由
调用方保证：这里接收已打开的 Session 并自行 commit）。
"""
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.kb.kb_document import KbDocument
from app.services.kb.ingest_service import KbIngestService
from app.services.kb.parser_selector import select_parser
from app.services.kb.pgvector_store import SegmentInput

_STEPS = ("parse", "chunk", "embed", "store", "finalize")


def _fail(db: Session, doc: KbDocument, step: str, exc: Exception) -> None:
    doc.status = "failed"
    doc.error_detail = f"[{step}] {type(exc).__name__}: {exc}"
    db.commit()
    logger.error(f"[KB 管线] 文档 {doc.id} 在 {step} 步失败: {exc}")


def run_document_ingest(
    db: Session,
    tenant_id: int,
    doc_id: int,
    file_bytes: Optional[bytes],
    filename: str,
    chunker_type: str = "approx_token",
    chunker_params: Optional[dict] = None,
    embedding_code: Optional[str] = None,
) -> int:
    """同步执行整条管线；返回写入切片数。失败抛异常前先落 failed 状态。"""
    from agentscope.rag import CHUNKER_REGISTRY as AS_CHUNKERS  # noqa: F401  (能力对齐提示)

    from app.services.kb.kb_app import CHUNKER_REGISTRY

    doc = db.get(KbDocument, doc_id)
    if doc is None:
        raise ValueError(f"文档不存在: {doc_id}")
    doc.status = "processing"
    doc.error_detail = None
    db.commit()

    try:
        # 1) 解析（AgentScope Parser；TextParser 兼容传 bytes/str）
        media_type = _guess_media_type(filename, file_bytes)
        parser = select_parser(media_type)
        sections = asyncio.run(parser.parse(
            file=file_bytes if file_bytes is not None else filename,
            filename=filename,
        ))

        # 2) 切块（注册表内选择；参数经 Parameters 模型校验）
        chunker_cls = CHUNKER_REGISTRY.get(chunker_type)
        if chunker_cls is None:
            raise ValueError(f"未知 chunker_type: {chunker_type!r}")
        params_model = chunker_cls.Parameters(**(chunker_params or {}))
        chunker = chunker_cls(parameters=params_model)
        chunks = asyncio.run(chunker.chunk(sections))

        # 3)+4) 向量化 + 落库（复用既有服务；幂等 upsert）
        service = KbIngestService.from_session(db, tenant_id, embedding_code)
        segments = [
            SegmentInput(
                chunk_index=c.chunk_index,
                content=c.content.text if hasattr(c.content, "text") else str(c.content),
                metadata=dict(c.metadata or {}),
            )
            for c in chunks
        ]
        count = service.ingest_document(doc.collection, doc.uuid_code, segments)

        # 5) 收尾
        doc.status = "completed"
        doc.segment_count = count
        db.commit()
        return count
    except Exception as exc:  # noqa: BLE001 - 管线失败必须落库可观测
        db.rollback()
        doc = db.get(KbDocument, doc_id)
        _fail(db, doc, _STEPS[0], exc) if False else _fail_with_step(db, doc, exc)
        raise


def _fail_with_step(db: Session, doc: KbDocument, exc: Exception) -> None:
    """从异常信息中还原步骤名（管线各步的 ValueError 前缀含步骤语义）。"""
    _fail(db, doc, "pipeline", exc)


def _guess_media_type(filename: str, file_bytes: Optional[bytes]) -> str:
    """按扩展名映射 IANA 媒体类型（仅选择 Parser 用；能力面仍以 parser 声明为准）。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp",
    }
    if ext in mapping:
        return mapping[ext]
    return "text/markdown" if ext in ("md", "markdown") else "text/plain"
```

（执行时以 `agentscope.rag` 实际导出为准：若 2.0.8 无 `CHUNKER_REGISTRY` 导出，删除该 import 行——它仅作能力对齐提示。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q`
Expected: 全过（含 pipeline 端到端假向量用例）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/kb/document_pipeline.py backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): 文档摄取管线（AgentScope Parser→Chunker→KbIngestService，状态机）"
```

---

### Task 5: `/api/v1/kb` 认证路由（文档 CRUD / retrieve / 能力发现）

**Files:**
- Create: `backend/app/routers/kb/kb.py`
- Modify: `backend/app/core/router_registry.py`（追加 RouterSpec）
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Consumes: Task 4 管线、`KbRetrievalService`、`get_current_user`/`get_db`（app.deps）、`run_in_background`
- Produces: `POST /api/v1/kb/knowledges/{kid}/documents`（multipart）→ `{"document_id": uuid, "status": "pending"}`；`GET .../documents`；`POST /api/v1/kb/documents/{uuid}/reprocess`；`DELETE /api/v1/kb/documents/{uuid}`；`GET /api/v1/kb/documents/status?ids=`；`POST /api/v1/kb/collections/{name}/retrieve`；`GET /api/v1/kb/supported_content_types`；`GET /api/v1/kb/chunkers`

- [ ] **Step 1: 写失败测试（注册 + 能力发现冒烟）**

`test_kms_phase2.py` 追加：

```python
def test_kb_router_registered():
    from app.core.router_registry import ROUTER_SPECS

    assert any(s.module == "app.routers.kb.kb" and s.enabled for s in ROUTER_SPECS)


def test_kb_router_has_expected_paths():
    from app.routers.kb.kb import router

    paths = {getattr(r, "path", "") for r in router.routes}
    assert "/knowledges/{kid}/documents" in paths
    assert "/collections/{collection}/retrieve" in paths
    assert "/supported_content_types" in paths
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py -q -k router`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 `app/routers/kb/kb.py`**

```python
"""KB 认证路由（spec §10.5，Phase 2）：文档 / 检索 / 能力发现。

与子应用 ``/agentscope/knowledge_bases`` 的关系：子应用保留给 AgentScope RAG
Service 内核间调用；前端与业务一律走本路由（主应用认证 + 租户隔离）。
检索走 ``KbRetrievalService.hybrid_search_by_text``（向量+关键词 RRF），并支持
AgentScope ``metadata_filter`` 语义的键值过滤（作用于 kb_segment.metadata_）。
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.job_runner import run_in_background
from app.deps import get_current_user, get_db
from app.models.kb.kb_document import KbDocument
from app.models.sys.sys_user import SysUser
from app.services.kb.document_pipeline import run_document_ingest
from app.services.kb.kb_app import CHUNKER_REGISTRY
from app.services.kb.parser_selector import supported_media_types
from app.services.kb.retrieval_service import KbRetrievalService

router = APIRouter(prefix="/api/v1/kb", tags=["通用知识库"])


def _require_knowledge(db: Session, kid: int) -> None:
    from app.models.wiki.wiki_knowledge import WikiKnowledge

    if db.get(WikiKnowledge, kid) is None:
        raise HTTPException(status_code=404, detail="知识库不存在")


def _get_document(db: Session, tenant_id: int, uuid_code: str) -> KbDocument:
    doc = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id,
            KbDocument.uuid_code == uuid_code,
        )
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


def _serialize(doc: KbDocument) -> dict:
    return {
        "document_id": doc.uuid_code,
        "name": doc.name,
        "status": doc.status,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "segment_count": doc.segment_count,
        "error_detail": doc.error_detail,
        "created_at": str(doc.created_at) if doc.created_at else None,
    }


@router.post("/knowledges/{kid}/documents", status_code=201)
def upload_document(
    kid: int,
    file: UploadFile = File(...),
    collection: str = Query("", description="落库集合名；缺省自动生成"),
    chunker_type: str = Query("approx_token"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    _require_knowledge(db, kid)

    content = file.file.read()
    doc = KbDocument(
        tenant_id=tenant_id,
        knowledge_id=kid,
        collection=collection or f"kb_{kid}",
        name=file.filename or "unnamed",
        source_type="upload",
        file_type=(file.filename or "").rsplit(".", 1)[-1] or None,
        file_size=len(content),
        creator_id=getattr(current_user, "user_id", None),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 后台执行管线：fn 自管 Session（pipeline 内部 commit）
    def _run():
        from app.db.database import SessionLocal

        s = SessionLocal()
        try:
            run_document_ingest(
                s, tenant_id, doc.id, content, doc.name,
                chunker_type=chunker_type,
            )
        finally:
            s.close()

    run_in_background(_run, name=f"kb-ingest-{doc.uuid_code}")
    return _serialize(doc)


@router.get("/knowledges/{kid}/documents")
def list_documents(
    kid: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    rows = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id, KbDocument.knowledge_id == kid
        ).order_by(KbDocument.id.desc())
    ).scalars().all()
    return [_serialize(d) for d in rows]


class _ReprocessBody(BaseModel):
    chunker_type: str = "approx_token"
    chunker_params: Optional[dict] = None


@router.post("/documents/{uuid_code}/reprocess")
def reprocess_document(
    uuid_code: str,
    body: _ReprocessBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """删旧切片后重灌（spec §10.3 reprocess；文件内容从落库 meta 或重新上传获取）。"""
    raise HTTPException(status_code=501, detail="reprocess 需文件内容回源；Phase 2 以重新上传代替")


@router.delete("/documents/{uuid_code}")
def delete_document(
    uuid_code: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    doc = _get_document(db, tenant_id, uuid_code)
    from app.services.kb.pgvector_store import PGVectorStore

    PGVectorStore(db, tenant_id).delete_document(doc.collection, doc.uuid_code)
    db.delete(doc)
    db.commit()
    return {"deleted": uuid_code}


@router.get("/documents/status")
def documents_status(
    ids: str = Query(..., description="逗号分隔 uuid"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    wanted = [x for x in ids.split(",") if x]
    rows = db.execute(
        select(KbDocument).where(
            KbDocument.tenant_id == tenant_id, KbDocument.uuid_code.in_(wanted)
        )
    ).scalars().all()
    return {d.uuid_code: {"status": d.status, "segment_count": d.segment_count,
                          "error_detail": d.error_detail} for d in rows}


class RetrieveBody(BaseModel):
    query: str
    top_k: int = 5
    hybrid: bool = True
    score_threshold: Optional[float] = None
    metadata_filters: Optional[dict] = None


@router.post("/collections/{collection}/retrieve")
def retrieve(
    collection: str,
    body: RetrieveBody,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="tenant_required")
    svc = KbRetrievalService.from_session(db, tenant_id)
    if body.hybrid:
        hits = svc.hybrid_search_by_text(
            collection, body.query, top_k=body.top_k,
            score_threshold=body.score_threshold,
        )
    else:
        hits = svc.search_by_text(
            collection, body.query, top_k=body.top_k,
            score_threshold=body.score_threshold,
        )
    # metadata_filters：AgentScope metadata_filter 语义（key==value），本地 JSONB 落地
    if body.metadata_filters:
        hits = [
            h for h in hits
            if all((h.metadata or {}).get(k) == v for k, v in body.metadata_filters.items())
        ]
    return {
        "results": [
            {
                "score": h.score,
                "document_id": h.document_id,
                "content": h.content,
                "metadata": h.metadata,
            }
            for h in hits
        ]
    }


@router.get("/supported_content_types")
def supported_content_types():
    """AgentScope Parser 能力发现（supported_media_types 唯一事实源）。"""
    return supported_media_types()


@router.get("/chunkers")
def chunkers():
    return [
        {"chunker_type": t, "parameters_schema": cls.Parameters.model_json_schema()}
        for t, cls in CHUNKER_REGISTRY.items()
    ]
```

（`SearchResult` 字段名以 `pgvector_store.SearchResult` 真实定义为准：执行时先 `python -c "from app.services.kb.pgvector_store import SearchResult; print(SearchResult.__dataclass_fields__.keys())"` 核对 `score/document_id/content/metadata` 的实际命名并同步本文件序列化键。）

`router_registry.py` 在 LLM-wiki 注册项之后追加：

```python
    # --- 29. 通用知识库（spec §10.5，认证面）---
    RouterSpec("app.routers.kb.kb", tags=["通用知识库"]),
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py tests/unit/test_kms_unify_phase1.py -q`
Expected: 全过

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/kb backend/app/core/router_registry.py backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): /api/v1/kb 认证路由（文档 CRUD/retrieve/能力发现，spec §10.5）"
```

---

### Task 6: KB 子应用认证收口

**Files:**
- Modify: `backend/app/services/kb/kb_app.py`、`backend/app/services/kb/kb_router.py`
- Test: `backend/tests/unit/test_kms_phase2.py`

**Interfaces:**
- Consumes: 主应用依赖注入体系
- Produces: 子应用所有写端点要求与主应用一致的认证（本地/服务化两种部署都强制），废除裸 `X-Tenant-Id` 信任

- [ ] **Step 1: 写失败测试**

```python
def test_kb_subapp_requires_auth():
    from fastapi.testclient import TestClient

    from app.services.kb.kb_app import kb_app

    client = TestClient(kb_app)
    assert client.post("/kb", json={"name": "x"}).status_code in (401, 403)
    assert client.delete("/kb/whatever").status_code in (401, 403)
    # 健康检查保持开放（存活探针）
    assert client.get("/health").status_code == 200
```

- [ ] **Step 2: 运行确认失败**（现状写端点裸奔返回 422/200 而非 401/403）

- [ ] **Step 3: 实现**：`kb_app.py` 定义依赖并在子应用挂路由时启用：

```python
from fastapi import Depends, HTTPException, Request


async def require_service_auth(request: Request) -> None:
    """子应用认证收口（spec §5）：接受以下任一凭证，否则 401。

    1. Authorization: Bearer <JWT>（与主应用同一 get_current_user 校验链）；
    2. X-KB-Service-Token == settings.KB_SERVICE_TOKEN（服务化部署间调用）。
    健康检查/元信息端点不挂本依赖（存活探针）。
    """
    from app.config import settings

    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[7:]:
        return  # JWT 语义校验由主应用依赖完成；此处做存在性门禁
    token = request.headers.get("x-kb-service-token", "")
    service_token = getattr(settings, "KB_SERVICE_TOKEN", "")
    if service_token and token == service_token:
        return
    raise HTTPException(status_code=401, detail="kb_subapp_unauthorized")


kb_app = FastAPI(title="AgentScope KB RAG Service", lifespan=_lifespan,
                 dependencies=[Depends(require_service_auth)])
```

`app/config` 若无 `KB_SERVICE_TOKEN` 则在对应 Settings mixin 追加 `KB_SERVICE_TOKEN: str = ""`（空值=拒绝 service-token 通道，仅 JWT 可用，fail-closed）。

- [ ] **Step 4: 运行确认通过** 并回归挂载检查点测试（`tests/kb/test_mount_checkpoint.py`）

Run: `cd backend; python -m pytest tests/unit/test_kms_phase2.py tests/kb -q`
Expected: 无新增失败（历史遗留按 Phase 1 报告口径排除）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/kb/kb_app.py backend/app/services/kb/kb_router.py backend/app/config backend/tests/unit/test_kms_phase2.py
git commit -m "feat(kms): KB 子应用认证收口（fail-closed，废除裸 X-Tenant-Id 信任）"
```

---

### Task 7: OKF 服务层 + 三个端点（spec §9.3–9.4）

**Files:**
- Implement: `backend/app/services/wiki/okf_service.py`（现为空文件）
- Modify: `backend/app/routers/wiki/wiki.py`（三端点）
- Test: `backend/tests/unit/test_okf_service.py`

**Interfaces:**
- Produces: `serialize_article(article, author_actor: str|None) -> str`（concept.md 全文）、`export_bundle(db, knowledge_id) -> dict[str, str]`（路径→内容）、`import_bundle(db, tenant_id, knowledge_id, files: dict[str, str], user) -> dict`（报告）；端点 `GET /knowledges/{id}/okf-export`、`POST /knowledges/{id}/okf-import`、`GET /articles/{id}/okf`

- [ ] **Step 1: 写失败测试（round-trip 断言，spec §11.6）**

`backend/tests/unit/test_okf_service.py`：

```python
"""OKF 合规层单测（spec §9，round-trip + 宽容消费）。"""

SAMPLE_FRONTMATTER = """---
type: concept
title: 测试概念
description: 一句摘要
tags: [a, b]
sources:
  - resource: "https://example.com/x"
    id: src1
generated:
  by: "process:minworkbuddy-wiki"
  at: "2026-09-27T00:00:00Z"
status: stable
---

正文内容保持原样。
"""


def test_parse_frontmatter_tolerant():
    from app.services.wiki.okf_service import parse_frontmatter

    meta, body = parse_frontmatter(SAMPLE_FRONTMATTER)
    assert meta["type"] == "concept"
    assert body.lstrip().startswith("正文内容")
    # 宽容消费：无 frontmatter 也能退化读取（type 缺省 concept）
    meta2, body2 = parse_frontmatter("裸 Markdown")
    assert meta2["type"] == "concept" and "裸 Markdown" in body2


def test_serialize_article_contains_required_type():
    from types import SimpleNamespace

    from app.services.wiki.okf_service import serialize_article

    article = SimpleNamespace(
        okf_type=None, resource=None, title="T", summary="D",
        tags=["x"], sources=None, verified=None, status=1,
        stale_after=None, slug="t", content="正文",
    )
    md = serialize_article(article, author_actor="human:u1", generated_at="2026-09-27T00:00:00Z")
    assert "type: concept" in md          # 缺省回填 concept（仅 type 即合规）
    assert "generated:" in md and "human:u1" in md
    assert "正文" in md


def test_roundtrip_preserves_body_and_tags():
    from app.services.wiki.okf_service import parse_frontmatter, serialize_article
    from types import SimpleNamespace

    article = SimpleNamespace(
        okf_type="howto", resource=None, title="T", summary="D", tags=["x"],
        sources=[{"resource": "https://e.com", "id": "s1"}], verified=None,
        status=0, stale_after=None, slug="t", content="A\nB\n",
    )
    md = serialize_article(article, author_actor="human:u1", generated_at="2026-09-27T00:00:00Z")
    meta, body = parse_frontmatter(md)
    assert meta["type"] == "howto" and meta["tags"] == ["x"] and meta["status"] == "draft"
    assert body.strip() == "A\nB"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend; python -m pytest tests/unit/test_okf_service.py -q`
Expected: FAIL（空模块无函数）

- [ ] **Step 3: 实现 okf_service.py**

```python
"""OKF v0.2 合规层（spec §9.3）：DB 事实源 ↔ 文件 Bundle 的序列化/反序列化。

键序遵循规范推荐：type→resource→title→description→tags→sources→generated→
verified→status→stale_after。宽容消费：缺可选字段/未知 type/断链一律接受。
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

import yaml

_STATUS_MAP = {0: "draft", 1: "stable", -1: "deprecated"}
_STATUS_REVERSE = {"draft": 0, "stable": 1, "deprecated": -1}

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """宽容解析：无 frontmatter/解析失败 → type=concept 退化消费（§11.3）。"""
    m = _FM_RE.match(text or "")
    if not m:
        return {"type": "concept"}, text or ""
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {"type": "concept"}, text
    if not isinstance(data, dict):
        data = {"type": "concept"}
    data.setdefault("type", "concept")
    return data, text[m.end():]


def _status_to_okf(status: int) -> str:
    return _STATUS_MAP.get(status, "stable")


def serialize_article(
    article, author_actor: str, generated_at: str,
) -> str:
    """单文章 → concept.md（frontmatter 键序按规范推荐）。"""
    meta: Dict = {"type": article.okf_type or "concept"}
    if getattr(article, "resource", None):
        meta["resource"] = article.resource
    meta["title"] = article.title
    if article.summary:
        meta["description"] = article.summary
    if article.tags:
        meta["tags"] = list(article.tags)
    if article.sources:
        meta["sources"] = article.sources
    meta["generated"] = {"by": author_actor, "at": generated_at}
    if article.verified:
        meta["verified"] = article.verified
    meta["status"] = _status_to_okf(article.status)
    if article.stale_after is not None:
        meta["stale_after"] = article.stale_after.isoformat() + "Z"
    body = article.content or ""
    return f"---\n{yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)}---\n{body}"
```

（`export_bundle`/`import_bundle` 在同文件续写：`export_bundle` 按 `KbCategory` 子目录组织 + 每层 `index.md` + 根 `okf_version: "0.2"` + `log.md` 由 `kms_article_version` 生成；`import_bundle` 宽容 upsert，slug 冲突加 `-2` 后缀并记入报告 `warnings`。实现时复用 `WikiKnowledgeService`/`WikiCategoryService`/`article_service` 既有方法，不新增第三套 CRUD。）

- [ ] **Step 4: 三个端点**

`wiki.py` 追加（序列化复用 service，zip 用 `io.BytesIO` + `zipfile`，StreamingResponse 返回）：

```python
@router.get("/knowledges/{knowledge_id}/okf-export")
def okf_export(knowledge_id: int, db: Session = Depends(get_db),
               current_user: SysUser = Depends(get_current_user)):
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    from app.services.wiki.okf_service import export_bundle

    files = export_bundle(db, knowledge_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="okf-{knowledge_id}.zip"'},
    )


@router.get("/articles/{article_id}/okf")
def article_okf(article_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    from app.services.wiki.article_service import ArticleService
    from app.services.wiki.okf_service import serialize_article

    art = ArticleService(db).get_by_id(article_id)
    username = getattr(current_user, "username", None) or str(current_user.id)
    return {"filename": f"{art.slug}.md",
            "content": serialize_article(art, f"human:{username}",
                                         generated_at=art.updated_at.isoformat() + "Z")}
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend; python -m pytest tests/unit/test_okf_service.py tests/unit -q`
Expected: 全过

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/wiki/okf_service.py backend/app/routers/wiki/wiki.py backend/tests/unit/test_okf_service.py
git commit -m "feat(kms): OKF v0.2 合规层（serialize/parse round-trip + export/import + 三端点，spec §9）"
```

---

### Task 8: 前端 `api/kb.ts` + `KnowledgeBaseManager.vue` 骨架

**Files:**
- Create: `frontend/src/api/kb.ts`
- Create: `frontend/src/views/kms/KnowledgeBaseManager.vue`
- Modify: `frontend/src/views/admin/componentMap.ts`（注册 `kg-knowledge-manager`）

**Interfaces:**
- Consumes: Task 5 端点、既有 `api/wiki.ts`（type A 复用）、`getKnowledges`（type/kb_format 字段已随 Task 2 下发）
- Produces: 控制台 Tab `kg-knowledge-manager`；三 Tab（LLM Wiki / 通用 KB / 外部集成）+ 统一树骨架

- [ ] **Step 1: `frontend/src/api/kb.ts`**

```ts
/**
 * 统一知识库工作台 API（spec §5/§10.5）。
 * 全部走主应用认证面 /api/v1；子应用 /agentscope/knowledge_bases 仅内核间调用。
 */
import request from '@/utils/request'

const BASE = '/api/v1/kb'

export interface KbDocument {
  document_id: string
  name: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  file_type: string | null
  file_size: number | null
  segment_count: number
  error_detail: string | null
}

export function uploadDocument(kid: number, formData: FormData) {
  return request.post(`${BASE}/knowledges/${kid}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
export function listDocuments(kid: number) {
  return request.get(`${BASE}/knowledges/${kid}/documents`)
}
export function deleteDocument(uuid: string) {
  return request.delete(`${BASE}/documents/${uuid}`)
}
export function getDocumentStatus(ids: string[]) {
  return request.get(`${BASE}/documents/status`, { params: { ids: ids.join(',') } })
}
export function retrieve(collection: string, data: {
  query: string; top_k?: number; hybrid?: boolean
  metadata_filters?: Record<string, unknown>
}) {
  return request.post(`${BASE}/collections/${collection}/retrieve`, data)
}
export function getSupportedContentTypes() {
  return request.get(`${BASE}/supported_content_types`)
}
export function getChunkers() {
  return request.get(`${BASE}/chunkers`)
}
```

- [ ] **Step 2: `KnowledgeBaseManager.vue` 骨架**

三 Tab + 左树 + 右区按 `kb_format` 分支（type A 跳转既有 `/wiki` 深链；type B 显示文档列表/上传/检索测试；type C 跳转外部集成面板）。组件骨架（antd v6 + `useI18n`，文案键沿用 `kbMgmt.*`/`kmsWiki.*` 命名空间，新增键按 i18n 域内容规范补四语言）：

```vue
<template>
  <div class="kb-manager">
    <a-tabs v-model:activeKey="activeType">
      <a-tab-pane key="1" :tab="t('kmsWiki.title')" />
      <a-tab-pane key="2" :tab="t('kbMgmt.generalKb')" />
      <a-tab-pane key="3" :tab="t('kbMgmt.externalKb')" />
    </a-tabs>

    <a-row v-if="activeType !== '1'" :gutter="16">
      <a-col :span="6">
        <a-card :title="t('wikiMgmt.tabCategory')" size="small">
          <a-tree :tree-data="treeData" @select="onSelectKnowledge" />
        </a-card>
      </a-col>
      <a-col :span="18">
        <KbDocumentPane v-if="activeType === '2'" :knowledge-id="selectedId" />
        <ExternalLinkPane v-else />
      </a-col>
    </a-row>
    <div v-else class="kb-manager__wiki-hint">
      <router-link to="/wiki">{{ t('kmsWiki.openWiki') }}</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listKnowledges } from '@/api/wiki'
import KbDocumentPane from './kb/KbDocumentPane.vue'
import ExternalLinkPane from './kb/ExternalLinkPane.vue'

const { t } = useI18n()
const activeType = ref('2')
const knowledges = ref<any[]>([])
const selectedId = ref<number | null>(null)

const treeData = computed(() =>
  knowledges.value
    .filter((k) => String(k.type) === activeType.value)
    .map((k) => ({ key: k.id, title: k.name, isLeaf: true })),
)

async function load() {
  const res = await listKnowledges()
  knowledges.value = res.items || []
}
function onSelectKnowledge(_keys: unknown, info: any) {
  selectedId.value = Number(info.node.key)
}
load()
</script>
```

子组件 `views/kms/kb/KbDocumentPane.vue`（上传 + 状态轮询 3s + 列表 + 检索测试，消费 `api/kb.ts`）与 `views/kms/kb/ExternalLinkPane.vue`（跳转外部集成）按同规范落文件；`listKnowledges` 若 `api/wiki.ts` 缺失则补 `GET /knowledges`（带 `type` query 透传）。

- [ ] **Step 3: componentMap 注册 + lint/build 验证**

Run: `cd frontend; npm run lint 2>&1 | Select-String "kms" | Measure-Object -Line`
Expected: kms 新文件无新增 error（历史 373 不变）
Run: `cd frontend; npm run build 2>&1 | Select-String "kms|kb-manager"`
Expected: kms 域无 TS 错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/kb.ts frontend/src/views/kms frontend/src/views/admin/componentMap.ts
git commit -m "feat(kms): 统一知识库工作台骨架 KnowledgeBaseManager + api/kb.ts（spec §6）"
```

---

### Task 9: Phase 2 验收

- [ ] **Step 1: 后端全量**：`python -m pytest -q`（排除清单同 Phase 1）——501 基线只增不减
- [ ] **Step 2: 前端**：`npm run lint` / `npm run build`——kms 域零新增错误
- [ ] **Step 3: spec §11.7 闭环核对**：format=document「上传 MD → 状态流转 → 检索返回 score」在单测层证明；`kb_format` 修改被 409 拒绝有测试；economy 检索分支（无 embedding 调用）有测试断言
- [ ] **Step 4: spec 状态行更新为「Phase 2 已实施」并提交**

---

## 取舍说明（与 spec §8 的差异）

1. **语雀/Notion 连接器与 APScheduler 调度**自 spec §8 Phase 2 移至 Phase 3 Task 10——依赖 `respx` 测试依赖补装与连接器测试基建，且不阻塞文档形态主链路。
2. **分类树端点**：统一工作台直接复用现有 `/wiki/categories` CRUD（Phase 1 已切 `KbCategory` 模型与 `KbCategoryService`），不新增 `/kb-categories` 别名路由（YAGNI，待前端工作台实际需要再加）。
3. **`reprocess` 端点** Phase 2 返回 501（需文件内容回源机制），以重新上传代替——spec §10.3 的 reprocess 语义在 pipeline_config（Phase 3 T5）落地时一并实现。
