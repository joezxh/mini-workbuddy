"""Skill Hub 适配器抽象基类与数据结构。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SkillHubEntry:
    """Hub 中一个可拉取的 skill 条目。"""

    id: str
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    meta: dict[str, Any] = None  # 来源相关的附加元数据

    def __post_init__(self) -> None:
        if self.meta is None:
            self.meta = {}


class SkillHubAdapter(ABC):
    """第三方 Skill Hub 适配器接口。

    实现方只需负责「列举远程条目」与「按条目拉取 zip 字节流」，
    导入与落盘逻辑统一复用 AiSkillAdminService.import_zip。
    """

    #: 适配器标识，用于注册与配置选择
    name: str = "base"

    @abstractmethod
    def list_remote(self) -> list[SkillHubEntry]:
        """列出远程 Hub 上可拉取的 skill。"""

    @abstractmethod
    def fetch(self, entry: SkillHubEntry) -> bytes:
        """按条目拉取 skill 包，返回 zip 字节流。"""
