"""菜单 SQL 的两处一致性与可执行性（spec §2.3 菜单行 / §3.9）。

不用 `db` 夹具里的表列表建 `sys_menu`：`tests/twin/conftest.py::_tables()` 沿用本体版，
没 import `app.models.sys.sys_user`，所以这里自己 `create(checkfirst=True)`。

**行号说明（执行时实测，2026-11-01）**：本任务原定 `id=2406`，但工作区里 `2406` 已被
「数据资产目录」（`/admin/data-asset`，`kg:asset:read`）占走——那是并行在飞的另一条特性，
`docs/sql/menu_knowledge_governance.sql` 与 `frontend/src/views/admin/componentMap.ts:70`
都写着 `sys_menu 2406`。同一 `VALUES` 块里出现两行 2406 = 一条重复主键的 SQL，
所以孪生应用改用下一个空号 **2407**（`sort` 也顺延为 5）。
"""
import re
from pathlib import Path

from sqlalchemy import text

from app.models.sys.sys_user import SysMenu

REPO = Path(__file__).resolve().parents[3]      # backend/tests/twin/本文件 → 仓库根
GOV = REPO / "docs" / "sql" / "menu_knowledge_governance.sql"
INIT = REPO / "docs" / "sql" / "init.sql"

TWIN_ID = "2407"      # 原定 2406，被「数据资产」先行占用（见模块 docstring）

# spec §2.3 定死的 15 个字段（顺序即 VALUES 列顺序）
FIELDS = ["id", "name", "i18n_key", "path", "parent_id", "sort", "status", "permission",
          "type", "icon", "component", "is_deleted", "visible", "keep_alive", "always_show"]
EXPECTED = {
    "id": TWIN_ID, "name": "'孪生应用'", "i18n_key": "'knowledge.menu.twin'",
    "path": "'/admin/kg-twin'", "parent_id": "2401", "sort": "5", "status": "0",
    "permission": "'kg:twin:read'", "type": "2", "icon": "'DeploymentUnitOutlined'",
    "component": "NULL", "is_deleted": "false", "visible": "0",
    "keep_alive": "0", "always_show": "0",
}


def twin_row(path: Path) -> str:
    """取出孪生应用那一行（去首尾空白与行尾逗号），多于/少于一条都是失败。"""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    hits = [ln for ln in lines if ln.startswith(f"({TWIN_ID},")]
    assert len(hits) == 1, f"{path.name} 应恰好有一行 {TWIN_ID}，实得 {len(hits)} 行"
    return hits[0].rstrip(",")


def values_columns(path: Path) -> list:
    """从文件里抽 `INSERT INTO "public"."sys_menu"` 后的列名清单（不自己另写一列）。

    只取**包含孪生应用那一行**的那个 INSERT 块：`init.sql` 里有十几个菜单 INSERT，
    拿错块会让测试假绿。
    """
    raw = path.read_text(encoding="utf-8")
    blocks = re.findall(r'INSERT INTO "public"\."sys_menu"\s*\n\s*\(([^)]*)\)(.*?);',
                        raw, flags=re.S)
    hit = [b for b in blocks if f"({TWIN_ID}," in b[1]]
    assert len(hit) == 1, f"{path.name} 里包含 {TWIN_ID} 的 INSERT 块应唯一，实得 {len(hit)}"
    return [c.strip() for c in hit[0][0].split(",")]


def row_parts(row: str) -> list:
    """拆 VALUES 元组。本行的 15 个值**均不含逗号**（名字/路径/角色码都无逗号），
    所以直接 split 就够；若将来加了带逗号的值，这里必须换真解析器而不是改测试。"""
    return [p.strip() for p in row.strip()[1:-1].split(",")]


def twin_block_rows(path: Path) -> list:
    """孪生应用所在 INSERT 块里的全部元组行（含尾逗号原样），用于逗号终止性检查。"""
    raw = path.read_text(encoding="utf-8")
    blocks = re.findall(r'INSERT INTO "public"\."sys_menu"\s*\n\s*\(([^)]*)\)(.*?);',
                        raw, flags=re.S)
    hit = [b for b in blocks if f"({TWIN_ID}," in b[1]]
    assert len(hit) == 1
    return [ln.strip() for ln in hit[0][1].splitlines() if ln.strip().startswith("(")]


def test_both_files_have_identical_twin_row():
    # 两文件逐字一致：`init.sql` 是各菜单 SQL 的同源镜像（文件里就写着“来源：menu_knowledge_governance.sql”）
    assert twin_row(GOV) == twin_row(INIT)


def test_row_has_exactly_15_fields_in_declared_order():
    for path in (GOV, INIT):
        assert values_columns(path) == FIELDS, f"{path.name} 的列清单与 spec §2.3 不一致"
        assert len(row_parts(twin_row(path))) == 15, f"{path.name} 的 {TWIN_ID} 行字段个数不是 15"


def test_row_field_values_match_spec():
    for path in (GOV, INIT):
        got = dict(zip(FIELDS, row_parts(twin_row(path))))
        assert got == EXPECTED, f"{path.name} 的 {TWIN_ID} 行与 spec §2.3 不符：{got}"


def test_every_values_row_but_the_last_ends_with_comma():
    """经典坑：在 VALUES 块中间或末尾插行时，原来的末行必须接上逗号。

    写成「除末行外全部以 `),` 结尾」而不是钉死某一行号：本块的真实末行随并行特性漂移
    （`menu_knowledge_governance.sql` 的 2406「数据资产」仍在他人工作区里未提交），
    钉行号的断言会在别人追加菜单时假失败。
    """
    for path in (GOV, INIT):
        rows = twin_block_rows(path)
        assert len(rows) >= 5, f"{path.name} 的元组行数异常：{len(rows)}"
        for ln in rows[:-1]:
            assert ln.endswith("),"), f"{path.name} 有元组行漏了尾逗号：{ln[:40]}…"
        assert not rows[-1].endswith(","), f"{path.name} 的末行不该带逗号：{rows[-1][-20:]}…"


def test_role_grant_range_covers_twin_row():
    """角色授权范围不同步 → 菜单真打开那天所有角色都看不到它（比后端 403 更难查的幽灵 bug）。"""
    needle = f"BETWEEN 2401 AND {TWIN_ID} AND id <> 2404"
    for path in (GOV, INIT):
        raw = path.read_text(encoding="utf-8")
        assert needle in raw, f"{path.name} 的角色授权范围未覆盖 {TWIN_ID}"
        for stale in ("2405", "2406"):
            assert f"BETWEEN 2401 AND {stale} AND id <> 2404" not in raw, \
                f"{path.name} 还残留旧范围 AND {stale}"


def test_twin_row_inserts_and_is_idempotent(db):
    """拿**文件里**的行元组与列清单拼成 INSERT 真跑两遍：第二遍必须 0 行。

    列清单与元组都来自文件，所以这一条同时钉住了字段个数、字面量合法性与幂等写法。
    裸 NULL（`parent_id`/`component`）不需 CAST：2401 行已在生产上用同一形状跑过。"""
    SysMenu.__table__.create(bind=db.get_bind(), checkfirst=True)
    cols = ", ".join(values_columns(GOV))
    row = twin_row(GOV)
    sql = (f'INSERT INTO sys_menu ({cols}) SELECT v.* FROM (VALUES {row}) AS v({cols}) '
           f'WHERE NOT EXISTS (SELECT 1 FROM sys_menu s WHERE s.id = v.id)')

    first = db.execute(text(sql))
    db.commit()
    assert first.rowcount == 1
    second = db.execute(text(sql))
    db.commit()
    assert second.rowcount == 0, "WHERE NOT EXISTS 没生效 → 重跑会插重复菜单"

    got = db.execute(text(f"SELECT id, name, path, permission, type, parent_id, sort, visible "
                          f"FROM sys_menu WHERE id = {TWIN_ID}")).mappings().all()
    assert len(got) == 1
    assert dict(got[0]) == {"id": 2407, "name": "孪生应用", "path": "/admin/kg-twin",
                            "permission": "kg:twin:read", "type": 2, "parent_id": 2401,
                            "sort": 5, "visible": 0}
