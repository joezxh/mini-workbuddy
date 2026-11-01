"""Task 8：静态隔离断言（验收 A7——沙箱代码绝不写生产本体/数据域）。

纯源码文本扫描，不连库。红线（D2/V1）：沙箱域例外物化只落 ``onto_sandbox_*``，任何服务/路由
不得对 ``meta_*`` / ``onto_ontology*`` 生产表发起 DML。克隆链路取数 SQL 只允许 SELECT（源库只读）。
"""
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
SERVICE_DIR = BACKEND / "app" / "services" / "sandbox"
ROUTER_DIR = BACKEND / "app" / "routers" / "sandbox"

# 生产域写迹象：裸 SQL DML（服务层应统一走 ORM + 只读 SELECT）
_DML_SQL = ("INSERT ", "UPDATE ", "DELETE FROM ", "TRUNCATE ")
# 生产本体/元数据 ORM 模型（读取允许，写语义禁止）
_PROD_MODELS = ("MetaOntology", "MetaTable", "MetaColumn", "MetaStandard",
                "MetaRelation", "MetaOntologyVersion", "DataSource")
_WRITE_TOKENS = ("db.add", "db.delete", ".update(", ".delete(", "insert", "truncate")


def _sandbox_sources():
    files = sorted(SERVICE_DIR.glob("*.py")) + sorted(ROUTER_DIR.glob("*.py"))
    assert files, "未找到沙箱服务/路由源码"
    return files


@pytest.mark.parametrize("path", _sandbox_sources(), ids=lambda p: p.name)
def test_acceptance_a7_static_scan(path):
    src = path.read_text(encoding="utf-8")
    up = src.upper()
    # 无任何裸 SQL DML 语句（服务层统一走 ORM，取数走只读 SELECT）
    for kw in _DML_SQL:
        assert kw not in up, f"{path.name} 含裸 SQL DML: {kw!r}"
    # 生产本体/元数据模型不得出现在同一行的写语义调用中（读取 select 允许）
    for line in src.splitlines():
        if any(m in line for m in _PROD_MODELS):
            assert not any(w in line for w in _WRITE_TOKENS), \
                f"{path.name} 对生产模型发起写: {line.strip()}"
