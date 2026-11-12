"""迁移：SKILL 智能体类型并入 CHAT + agent_hitl_pause 多轮列（spec agent-mgmt §B1/B2）。

用法:
    python scripts/migrate_agent_type_skill_to_chat.py

幂等可重复执行：
1. agent_hitl_pause 增列（IF NOT EXISTS）：round_no / pause_type / pause_payload；
2. agent_config.agent_type='SKILL' → 'CHAT'（is_deleted=false）；
3. 打印数据字典维护提示（agent_impl_type 字典停用 SKILL 项）。
目标库来自 app.config.settings.DATABASE_URL。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

DDL_STATEMENTS = [
    "ALTER TABLE agent_hitl_pause ADD COLUMN IF NOT EXISTS round_no INTEGER DEFAULT 1",
    "ALTER TABLE agent_hitl_pause ADD COLUMN IF NOT EXISTS pause_type VARCHAR(30)",
    "ALTER TABLE agent_hitl_pause ADD COLUMN IF NOT EXISTS pause_payload JSONB",
]

UPDATE_SKILL_SQL = (
    "UPDATE agent_config SET agent_type='CHAT' "
    "WHERE agent_type='SKILL' AND is_deleted=false"
)


def main() -> None:
    engine = create_engine(settings.DATABASE_URL, future=True)
    with engine.begin() as conn:
        for stmt in DDL_STATEMENTS:
            conn.execute(text(stmt))
        result = conn.execute(text(UPDATE_SKILL_SQL))
        migrated = result.rowcount or 0

    engine.dispose()
    print(f"✓ agent_hitl_pause 多轮列已就绪（round_no/pause_type/pause_payload）")
    print(f"✓ 已将 {migrated} 条 SKILL 智能体并入 CHAT（技能绑定 skills 保留）")
    print(
        "\n[数据字典维护提示] 请在管理后台数据字典中：\n"
        "  1. agent_impl_type 字典停用 SKILL 项；\n"
        "  2. CHAT 项 remark 更新为「统一智能体（原会话/技能型合并）」。"
    )


if __name__ == "__main__":
    main()
