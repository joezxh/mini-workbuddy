"""统一文件管理 Pydantic 模型（对齐 Java File*VO）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FileCreateReq(BaseModel):
    configId: Optional[int] = None
    path: str
    name: str
    url: Optional[str] = None
    type: Optional[str] = None
    code: Optional[str] = None
    size: int = 0


class FileResp(BaseModel):
    id: int
    configId: Optional[int] = None
    path: str
    name: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None
    size: int = 0
    createTime: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FilePresignedUrlResp(BaseModel):
    configId: int
    uploadUrl: str
    url: str
    path: str


class DirectoryItemResp(BaseModel):
    name: str
    path: str
    hasChildren: bool = False
    children: list["DirectoryItemResp"] = Field(default_factory=list)


DirectoryItemResp.model_rebuild()


class FileConfigSaveReq(BaseModel):
    id: Optional[int] = None
    name: str
    code: str
    storage: int
    config: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None


class FileConfigResp(BaseModel):
    id: int
    name: str
    code: str
    storage: int
    master: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    remark: Optional[str] = None
    createTime: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FileStatisticsResp(BaseModel):
    configId: int
    configName: str
    storageType: int
    fileCount: int = 0
    totalSize: int = 0
    storage: int = 0


class ArchiveUploadResp(BaseModel):
    taskId: str
    archiveName: str
    total: int = 0


class ArchiveExtractFileResp(BaseModel):
    name: str
    url: str
    size: int = 0


class ArchiveExtractFailedResp(BaseModel):
    name: str
    reason: str


class ArchiveExtractProgressResp(BaseModel):
    taskId: str
    archiveName: str
    status: int = 0
    total: int = 0
    done: int = 0
    list: list[ArchiveExtractFileResp] = Field(default_factory=list)
    failed: list[ArchiveExtractFailedResp] = Field(default_factory=list)
    message: str = ""
