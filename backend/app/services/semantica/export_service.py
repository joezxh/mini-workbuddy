"""RDF / OWL / Cypher / Parquet 导出与 PROV-O 溯源封装（替代旧 owl_engine 导出职责）。

导出经 semantica.export 完成；PROV-O 溯源经 semantica.provenance 记录，任何失败
均降级（溯源失败不应阻塞导出）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .client import SemanticaClient
from .scope import TenantScope


class SemanticExporter:
    """导出本体/图谱数据到多种格式，并附带溯源记录。"""

    def __init__(self, scope: Optional[TenantScope] = None) -> None:
        self.scope = scope
        self.client = SemanticaClient(scope=scope)

    def export(self, data: Any, file_path: str, *, fmt: str = "turtle") -> str:
        """导出 ``data`` 到 ``file_path``。

        :param fmt: ``turtle``/``rdf``/``nt``/``xml`` → export_rdf；``owl`` → export_owl。
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "owl":
            self.client.export_owl(data, path)
        elif fmt in ("turtle", "rdf", "nt", "xml"):
            self.client.export_rdf(data, path, format="turtle" if fmt == "rdf" else fmt)
        else:
            raise ValueError(f"不支持的导出格式: {fmt}")

        self._record_provenance(path)
        return str(path)

    def _record_provenance(self, path: Path) -> None:
        try:
            pm = self.client.provenance_manager(
                storage_path=str(path.parent / ".provenance")
            )
            record = getattr(pm, "record", None) or getattr(pm, "add", None)
            if callable(record):
                record(activity="export", source=str(path))
        except Exception as exc:  # 溯源失败不影响导出结果
            logger.warning("语义导出溯源记录失败（已忽略）: {}", exc)
