"""WorkbenchService 单元测试 —— 重点回归：JSON 列变更检测。

SQLAlchemy JSON 列在 flush 时若 old == new（浅拷贝 + 原地改 dict 场景）
会跳过 UPDATE。WorkbenchService 必须对 steps/proposals/notes 做 deep-copy。
FakeDB 复刻该语义：get 时快照，commit 时相等则不落库。
"""
import copy
import pytest

from app.ai.superagent.workbench import WorkbenchService, _fingerprint


class FakeGoal:
    """模拟 SaGoal ORM 对象。"""

    def __init__(self, **kw):
        self.id = kw.get("id", "goal-1")
        self.workspace_id = kw.get("workspace_id", 1)
        self.title = kw.get("title", "测试目标")
        self.context = kw.get("context")
        self.status = kw.get("status", "active")
        self.progress = kw.get("progress", 0)
        self.cron = None
        self.next_checkin = None
        self.due = None
        self.source = "test"
        self.version = kw.get("version", 0)
        self.steps = kw.get("steps", [])
        self.proposals = kw.get("proposals", [])
        self.notes = kw.get("notes", [])
        self.created_at = kw.get("created_at", None)
        self.updated_at = kw.get("updated_at", None)


class FakeDB:
    """模拟 Session —— JSON 列「相等即跳过 UPDATE」语义。"""

    def __init__(self, store: dict):
        self._store = store
        self._snapshots = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def add(self, obj):  # publish_feed 时不落库，忽略
        pass

    def refresh(self, obj):
        pass

    def get(self, model, pk):
        goal = self._store.get(pk)
        if goal is not None:
            # 加载时快照（模拟 SQLAlchemy identity map 记录的加载值）
            self._snapshots[pk] = {
                "steps": copy.deepcopy(goal.steps),
                "proposals": copy.deepcopy(goal.proposals),
                "notes": copy.deepcopy(goal.notes),
                "status": goal.status,
                "progress": goal.progress,
                "version": goal.version,
            }
        return goal

    def commit(self):
        for pk, goal in self._store.items():
            snap = self._snapshots.get(pk)
            if snap is None:
                continue
            # 关键语义：JSON 值相等 → SQLAlchemy 跳过该列 UPDATE（不落库）
            for field in ("steps", "proposals", "notes"):
                current = getattr(goal, field)
                if current == snap[field]:
                    # 回滚到快照值 —— 模拟 UPDATE 被跳过
                    setattr(goal, field, copy.deepcopy(snap[field]))
                else:
                    snap[field] = copy.deepcopy(current)


class FakeSessionFactory:
    def __init__(self, store: dict):
        self._store = store

    def __call__(self):
        return FakeDB(self._store)

    def __enter__(self):
        return FakeDB(self._store)

    def __exit__(self, *a):
        return False


@pytest.fixture
def goal_store():
    """id → FakeGoal 的内存存储。"""
    store = {
        "goal-1": FakeGoal(
            id="goal-1",
            steps=[
                {"idx": 0, "text": "步骤A", "status": "pending"},
                {"idx": 1, "text": "步骤B", "status": "pending"},
            ],
        ),
    }
    return store


@pytest.fixture
def svc(goal_store):
    return WorkbenchService(db_factory=FakeSessionFactory(goal_store))


# ============ JSON 变更持久化回归（deep-copy 修复） ============

def test_toggle_step_persists(svc):
    """勾选 step 后必须真正落库（deep-copy 回归）。"""
    result = svc.toggle_step("goal-1", 1, 0)
    assert result is not None
    assert result["steps"][0]["status"] == "done"
    assert result["progress"] == 50


def test_toggle_step_uncheck(svc):
    """二次 toggle → pending。"""
    svc.toggle_step("goal-1", 1, 0)
    result = svc.toggle_step("goal-1", 1, 0)
    assert result["steps"][0]["status"] == "pending"


def test_skip_step_persists(svc):
    result = svc.skip_step("goal-1", 1, 1)
    assert result["steps"][1]["status"] == "skipped"
    assert result["progress"] == 50


def test_auto_complete_all_done(svc):
    """全部 done/skipped → 自动完案 + progress 100。"""
    svc.toggle_step("goal-1", 1, 0)  # step0 done
    result = svc.skip_step("goal-1", 1, 1)  # step1 skipped
    assert result["status"] == "done"
    assert result["progress"] == 100
    assert any("自动完结" in n["text"] for n in result["notes"])


def test_accept_proposal_persists_and_bumps_version(svc, goal_store):
    goal_store["goal-1"].proposals = [
        {"idx": 0, "kind": "suggestion", "message": "新步骤",
         "payload": {"step": "追加的步骤"}, "status": "pending"},
    ]
    result = svc.accept_proposal("goal-1", 1, 0)
    assert result["version"] == 1
    assert result["proposals"][0]["status"] == "accepted"
    assert len(result["steps"]) == 3
    assert result["steps"][2]["text"] == "追加的步骤"
    assert result["steps"][2]["status"] == "pending"


def test_accept_proposal_twice_rejected(svc, goal_store):
    goal_store["goal-1"].proposals = [
        {"idx": 0, "kind": "suggestion", "message": "x", "payload": {}, "status": "pending"},
    ]
    assert svc.accept_proposal("goal-1", 1, 0) is not None
    assert svc.accept_proposal("goal-1", 1, 0) is None  # 已 accepted，不可重复


def test_dismiss_proposal_persists(svc, goal_store):
    goal_store["goal-1"].proposals = [
        {"idx": 0, "kind": "suggestion", "message": "x", "payload": {}, "status": "pending"},
    ]
    result = svc.dismiss_proposal("goal-1", 1, 0)
    assert result["proposals"][0]["status"] == "dismissed"
    assert result["version"] == 0  # dismiss 不加版本


def test_add_note_persists(svc):
    result = svc.add_note("goal-1", 1, "进展一条")
    assert len(result["notes"]) == 1
    assert result["notes"][0]["text"] == "进展一条"


# ============ 纯逻辑 ============

def test_calc_progress_mixed():
    steps = [
        {"status": "done"}, {"status": "skipped"},
        {"status": "pending"}, {"status": "in_progress"},
    ]
    assert WorkbenchService._calc_progress(steps) == 50


def test_calc_progress_empty():
    assert WorkbenchService._calc_progress([]) == 0


def test_fingerprint_stable_and_distinct():
    a1 = _fingerprint(1, "chat", "同一个 pitch")
    a2 = _fingerprint(1, "chat", "同一个 pitch")
    b = _fingerprint(1, "goal", "同一个 pitch")
    c = _fingerprint(2, "chat", "同一个 pitch")
    assert a1 == a2
    assert a1 != b
    assert a1 != c
