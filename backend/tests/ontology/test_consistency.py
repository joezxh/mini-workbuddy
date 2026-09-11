"""Task 3：类层级与基础一致性校验测试。

三类校验 × 两层数据（建模层 object_type / OWL 层 class）：
* 悬空父类 —— 建模层被 DB 外键阻止、无法在正常路径构造，
  用纯函数检测器直接喂伪造数据验证；OWL 层（parent_uris 无外键）可构造；
* 循环继承 —— 两层均可构造；
* URI 冲突 —— 可构造（大小写差异）。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.knowledge.owl_engine import WikiOwlEngine
from app.services.ontology.modeling_service import (
    ConsistencyReport,
    ModelingService,
)
from app.services.ontology.ontology_repository import OntologyRepository

from .conftest import TENANT_A, TENANT_B


def _owl_engine(db: Session, tenant_id: int) -> WikiOwlEngine:
    return WikiOwlEngine.from_store(OntologyRepository(db, tenant_id))


# ── 1. 干净本体 ───────────────────────────────────────────────────────────────

def test_clean_ontology_reports_no_issues(db: Session) -> None:
    """干净本体（含合法父子链）→ 空报告；且校验是纯读操作。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("customer", "客户")
    svc.add_object_type("vip_customer", "VIP客户", parent_code="customer")
    _owl_engine(db, TENANT_A).register_class(
        "http://example.org/ontology#Risk",
        label="风险",
        parent_uris=["http://example.org/ontology#Base"],
    )
    # Base 未注册 —— 这是合法的悬空？不：悬空要报。这里注册 Base 使其干净
    _owl_engine(db, TENANT_A).register_class("http://example.org/ontology#Base")
    db.commit()

    report = svc.check_consistency()
    assert report.is_clean, report.issues

    # 纯读：空租户/其它租户不因校验而创建本体行
    n = db.execute(
        __import__("sqlalchemy").text(
            "SELECT count(*) FROM ontology WHERE tenant_id = :t"
        ),
        {"t": TENANT_B},
    ).scalar()
    ModelingService(db, TENANT_B).check_consistency()
    n_after = db.execute(
        __import__("sqlalchemy").text(
            "SELECT count(*) FROM ontology WHERE tenant_id = :t"
        ),
        {"t": TENANT_B},
    ).scalar()
    assert n == 0 and n_after == 0, "校验是读路径，不得创建本体行"


# ── 2. 悬空父类 ───────────────────────────────────────────────────────────────

def test_owl_dangling_parent_reported(db: Session) -> None:
    """OWL 层悬空父类：parent_uris 引用未注册的类（register_class 允许）。"""
    svc = ModelingService(db, TENANT_A)
    engine = _owl_engine(db, TENANT_A)
    engine.register_class(
        "http://example.org/ontology#OperationalRisk",
        label="操作风险",
        parent_uris=["http://example.org/ontology#GhostParent"],
    )
    db.commit()

    issues = svc.check_consistency().by_kind("dangling_parent")
    assert len(issues) == 1, issues
    issue = issues[0]
    assert issue.layer == "owl"
    assert issue.severity == "error"
    assert issue.subject == "http://example.org/ontology#OperationalRisk"
    assert "GhostParent" in issue.detail


def test_modeling_dangling_parent_detector(db: Session) -> None:
    """建模层悬空父类：DB 外键使正常路径不可构造，用纯函数检测器验证。

    （parent_id 的 FK ondelete=SET NULL 会消除悬空；此检测面向
    手工 SQL / 数据迁移等绕过约束的场景。）
    """
    rows = [
        (1, None, "customer"),      # 根
        (2, 1, "vip_customer"),     # 正常
        (3, 999, "orphan"),         # 悬空：999 不存在
    ]
    dangling = ModelingService._find_dangling_parents(rows)
    assert dangling == [("orphan", "999")]


# ── 3. 循环继承 ───────────────────────────────────────────────────────────────

def test_owl_cycle_reported_with_path(db: Session) -> None:
    """OWL 层 A→B→A 成环：报告路径，且同一环只报一次。"""
    svc = ModelingService(db, TENANT_A)
    engine = _owl_engine(db, TENANT_A)
    base = "http://example.org/ontology#"
    engine.register_class(f"{base}A", parent_uris=[f"{base}B"])
    engine.register_class(f"{base}B", parent_uris=[f"{base}A"])
    db.commit()

    issues = svc.check_consistency().by_kind("cyclic_inheritance")
    assert len(issues) == 1, issues
    issue = issues[0]
    assert issue.layer == "owl"
    assert issue.severity == "error"
    # 路径含回边（A -> B -> A 或 B -> A -> B，取决于遍历起点）
    cycle_part = issue.detail.split(": ", 1)[1]
    assert cycle_part.count("->") == 2
    assert cycle_part.split(" -> ")[0] == cycle_part.split(" -> ")[-1]


def test_modeling_cycle_reported(db: Session) -> None:
    """建模层 A→B→A（经 service 的 parent_code 构造后互改）。"""
    svc = ModelingService(db, TENANT_A)
    svc.add_object_type("a", "A")
    svc.add_object_type("b", "B", parent_code="a")
    db.commit()
    # 直接改库把 a 的父指向 b（绕开单方法校验，模拟外部工具写入）
    row_a = svc.get_object_type("a")
    row_b = svc.get_object_type("b")
    row_a.parent_id = row_b.id  # ORM 直改：同一会话内绕过 add_object_type 的无环假设
    db.commit()

    issues = svc.check_consistency().by_kind("cyclic_inheritance")
    assert len(issues) == 1, issues
    assert issues[0].layer == "modeling"
    assert "a" in issues[0].detail and "b" in issues[0].detail


def test_modeling_cycle_detector_deduplicates(db: Session) -> None:
    """纯函数：A→B→C→A 从任意环节点出发，同一环只报告一次。"""
    rows = [(1, 2, "A"), (2, 3, "B"), (3, 1, "C"), (4, None, "root")]
    cycles = ModelingService._find_parent_cycles(rows)
    assert len(cycles) == 1
    assert cycles[0][0] == cycles[0][-1]
    assert set(cycles[0][:-1]) == {"A", "B", "C"}


# ── 4. URI 冲突 ───────────────────────────────────────────────────────────────

def test_uri_conflict_reported_as_warning(db: Session) -> None:
    """`#Risk` 与 `#risk` 规范化后冲突：warning 级，不判 error。"""
    svc = ModelingService(db, TENANT_A)
    engine = _owl_engine(db, TENANT_A)
    engine.register_class("http://example.org/ontology#Risk", label="风险")
    engine.register_class("http://example.org/ontology#risk", label="risk")
    engine.register_class("http://example.org/ontology#Control", label="控制")
    db.commit()

    issues = svc.check_consistency().by_kind("uri_conflict")
    assert len(issues) == 1, issues
    issue = issues[0]
    assert issue.severity == "warning"
    assert "Risk" in issue.detail and "risk" in issue.detail


def test_uri_conflict_ignores_distinct_uris(db: Session) -> None:
    """不相关的 uri 不产生误报。"""
    svc = ModelingService(db, TENANT_A)
    engine = _owl_engine(db, TENANT_A)
    engine.register_class("http://example.org/ontology#Risk")
    engine.register_class("http://example.org/ontology#Control")
    db.commit()

    assert svc.check_consistency().by_kind("uri_conflict") == []


# ── 5. 租户隔离 ───────────────────────────────────────────────────────────────

def test_consistency_is_tenant_scoped(db: Session) -> None:
    """A 的悬空父类不出现在 B 的报告里。"""
    ModelingService(db, TENANT_A).add_object_type("a", "A")
    ModelingService(db, TENANT_B).add_object_type("b", "B")
    # A 里造悬空（ORM 直改绕 FK 不可行——parent_id 为 None 即无悬空；
    # 这里用 OWL 层造悬空）
    _owl_engine(db, TENANT_A).register_class(
        "http://example.org/ontology#OnlyA",
        parent_uris=["http://example.org/ontology#MissingInA"],
    )
    db.commit()

    assert len(
        ModelingService(db, TENANT_A).check_consistency().by_kind("dangling_parent")
    ) == 1
    report_b: ConsistencyReport = ModelingService(db, TENANT_B).check_consistency()
    assert all("OnlyA" not in i.subject for i in report_b.issues)
