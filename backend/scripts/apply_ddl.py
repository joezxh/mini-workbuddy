"""应用指定 DDL 脚本到当前配置的数据库（spec 2026-09-21 §6.1）。

用法:
    python scripts/apply_ddl.py docs/sql/47_agent_event_enhance.sql

脚本中的语句以 `;` 切分（DDL 内无字符串字面量分号），逐条在事务中执行。
所有语句均使用 `IF NOT EXISTS`，可重复、安全执行。
目标库来自 app.config.settings.DATABASE_URL（即应用运行时所用的同一数据库）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
PROJECT_ROOT = ROOT.parent  # 仓库根（docs/ 所在目录）
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402


def apply(sql_path: Path) -> int:
    raw = sql_path.read_text(encoding="utf-8")
    # 去掉注释行，避免 `--` 出现在切分后语句里造成误判（不影响执行）
    statements = [
        s.strip()
        for s in raw.replace("\n", " ").split(";")
        if s.strip() and not s.strip().startswith("--")
    ]
    engine = create_engine(settings.DATABASE_URL, future=True)
    n = 0
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
            n += 1
    engine.dispose()
    return n


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/apply_ddl.py <ddl.sql>", file=sys.stderr)
        raise SystemExit(2)
    sql_path = PROJECT_ROOT / sys.argv[1]
    if not sql_path.exists():
        print(f"未找到 DDL 文件: {sql_path}", file=sys.stderr)
        raise SystemExit(2)
    n = apply(sql_path)
    print(f"✓ 已在 {settings.DATABASE_URL} 应用 {n} 条语句（来自 {sql_path.name}）")


if __name__ == "__main__":
    main()
