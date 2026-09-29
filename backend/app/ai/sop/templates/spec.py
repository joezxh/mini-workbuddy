"""SOP 模板的载体结构。

模板 = 元数据（id/名称/标签）+ 一份可直接执行的 ``SOPDefinition``。
元数据用于前端模板选择器与关键词匹配；definition 用于驱动 SOPEngine。
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..schemas import SOPDefinition


class SOPTemplateSpec(BaseModel):
    """一个可播种、可检索的 SOP 模板。"""

    id: str
    """稳定标识（slug），种子与引用均以此为准，禁止随意改名。"""

    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    builtin: bool = True
    """系统内置模板为 True；用户自建模板为 False（不可被种子覆盖）。"""

    definition: SOPDefinition

    @property
    def keywords(self) -> str:
        """供关键词匹配检索的合并文本。"""
        return " ".join([self.id, self.name, self.description, *self.tags])
