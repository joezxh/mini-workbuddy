"""Excel/CSV 上传解析并落本系统 PG 隔离 schema（类型体系扩展 P5）。

形态（P2 决策）：上传文件不落外部库，而是解析成 DataFrame 写入后台自身 PG 的
独立 schema ``excel_ds_<source_id>``（命名见 dialects/excel_pg.schema_name_for），
之后即可由 ExcelPgAdapter 走标准「扫描 / 选表 / 画像」链路，与其他类型同构。

约定：
- 支持 .csv（单表，表名 data）与 .xlsx/.xls（每个 sheet 一表，表名取 sheet 名清洗）；
- 每个表 ``if_exists="replace"``：重复上传同一数据源即整体覆盖；
- 原始文件按租户落盘（复用 UPLOAD_DIR 惯例），便于溯源/重导；
- 大文件与非法类型在解析前拒绝，避免 OOM/无意义建表。
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import Engine

#: 单次上传字节上限（防御性；超过即拒绝，避免解析/落库压垮后台）
MAX_BYTES = 50 * 1024 * 1024
_SAFE_TABLE = re.compile(r"[^0-9A-Za-z_\u4e00-\u9fa5]+")
_ALLOWED_SUFFIX = {".csv", ".xlsx", ".xls"}


def safe_table_name(raw: object, index: int) -> str:
    """sheet/文件标题 → 合法 PG 表名（非安全字符折叠下划线，数字前缀补 t_）。"""
    base = _SAFE_TABLE.sub("_", str(raw or "").strip()).strip("_") or f"sheet_{index}"
    if base[0].isdigit():
        base = f"t_{base}"
    return base[:60]


def load_frames(filename: str, content: bytes) -> Dict[str, pd.DataFrame]:
    """解析上传字节为 {表名: DataFrame}；非法后缀/空内容显式失败。"""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIX:
        raise ValueError(f"不支持的文件类型 {suffix or filename!r}，仅支持 .csv/.xlsx/.xls")
    if len(content) > MAX_BYTES:
        raise ValueError(f"文件过大（{len(content) // 1024 // 1024}MB），上限 {MAX_BYTES // 1024 // 1024}MB")
    buffer = io.BytesIO(content)
    frames: Dict[str, pd.DataFrame] = {}
    if suffix == ".csv":
        df = None
        # 国内导出 CSV 常见 UTF-8-BOM / GBK，按序尝试
        for encoding in ("utf-8-sig", "gbk", "utf-8"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            raise ValueError("CSV 编码无法识别（尝试了 UTF-8/GBK）")
        if df.empty:
            raise ValueError("CSV 内容为空")
        frames[safe_table_name(Path(filename).stem, 0)] = df
        return frames
    sheets = pd.read_excel(buffer, sheet_name=None)
    for idx, (name, df) in enumerate(sheets.items()):
        if df is None or df.empty:
            continue
        frames[safe_table_name(name, idx)] = df
    if not frames:
        raise ValueError("Excel 中没有可用数据（全部工作表为空）")
    return frames


def save_original(uploads_root: Path, tenant_id: int, source_id: int, filename: str,
                  content: bytes) -> str:
    """原始文件落盘（尽力而为）：失败仅告警，不阻断入库主流程。"""
    try:
        target_dir = Path(uploads_root) / "dataops" / "excel" / str(tenant_id) / str(source_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        safe = safe_table_name(Path(filename).name, 0) + Path(filename).suffix.lower()
        (target_dir / safe).write_bytes(content)
        return str(target_dir / safe)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[Excel 落库] 原始文件落盘失败（不影响入库）: {exc}")
        return ""


class ExcelIngestService:
    """把解析出的 DataFrame 写入系统 PG 的隔离 schema。"""

    def __init__(self, engine: Engine, schema: str) -> None:
        self.engine = engine
        self.schema = schema

    def _ensure_schema(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'))

    def ingest(self, frames: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """每表 replace 写入；返回 [{name, rows, columns}] 摘要。"""
        if not frames:
            return []
        self._ensure_schema()
        summary: List[Dict[str, Any]] = []
        for table, df in frames.items():
            # replace：同名表整体重建，保证重复上传幂等
            df.to_sql(table, con=self.engine, schema=self.schema,
                      if_exists="replace", index=False, method="multi", chunksize=1000)
            summary.append({"name": table, "rows": int(len(df)),
                            "columns": [str(c) for c in df.columns]})
        return summary

    def drop_schema(self) -> None:
        """删除数据源时清理其隔离 schema（含全部表）；不存在则忽略。"""
        with self.engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE'))
