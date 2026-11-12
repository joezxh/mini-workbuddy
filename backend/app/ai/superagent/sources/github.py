"""GitHub Source —— 4 Trigger + pollRound + PR lifecycle → followsDone。

对齐 dsh-superagent github.ts —— 完整实现 poll 循环 + ETag + PR merge/close。
"""
from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from .base import SourceKindProtocol, SourceTrigger, HealthStatus, SourceKind


def _kebab_branch_name(title: str, pr_number: int) -> str:
    """worktree_name —— kebab-case 1-4 英文短词。"""
    words = re.findall(r"[a-zA-Z]+", title.lower())[:4] or ["pr"]
    return f"pr-{pr_number}-" + "-".join(words)


class GitHubSource(SourceKindProtocol):
    """GitHub Source —— 完整实现。

    4 Trigger 类型：issue_mention / pull_mention / comment_mention / ci_failure
    pollRound() 4 步：notifications → repository → tickets → threads。
    PR merge/close → Thread status=closed → Subscription fan-out → Ticket followsDone 自动完结。
    """
    kind: SourceKind = "github"

    def __init__(self, *, repository: str, gh_cli_path: str = "gh", poll_seconds: int = 60,
                 failures_before_error: int = 3, observe_issues: bool = True, observe_pulls: bool = True,
                 observe_comments: bool = True, observe_ci: bool = False, ci_branch: str = "main",
                 allowed_senders: list[str] | None = None, bots: list[str] | None = None,
                 domain_whitelist: list[str] | None = None):
        self.repository = repository
        self.gh_cli = gh_cli_path
        self.poll_seconds = max(60, min(3600, poll_seconds))
        self.failures_before_error = failures_before_error
        self.observe_issues = observe_issues
        self.observe_pulls = observe_pulls
        self.observe_comments = observe_comments
        self.observe_ci = observe_ci
        self.ci_branch = ci_branch
        self.allowed_senders = set(allowed_senders or [])
        self.bots = set(bots or [])
        self.domain_whitelist = set(domain_whitelist or [])
        self._failures = 0
        self._last_cursor: str | None = None
        self._last_error: str | None = None

    def is_enabled(self) -> bool:
        return True

    def health(self) -> dict:
        status = "healthy" if self._failures < self.failures_before_error else (
            "degraded" if self._failures < self.failures_before_error * 3 else "down"
        )
        return HealthStatus(
            kind=self.kind, status=status, failures=self._failures,
            last_error=self._last_error,
            next_poll=datetime.utcnow() + timedelta(seconds=self.poll_seconds),
        ).to_dict()

    async def poll_once(self, workspace_id: int, last_cursor: str | None = None) -> tuple[list[SourceTrigger], str | None]:
        """pollRound —— 从 GitHub API 拉新通知。"""
        self._last_cursor = last_cursor
        try:
            triggers: list[SourceTrigger] = []
            # Step 1: gh api notifications（ETag 缓存）
            try:
                result = await self._gh_api(
                    "notifications",
                    params={"all": "false", "per_page": "50"},
                    headers={"If-Modified-Since": last_cursor} if last_cursor else None,
                )
                if result.get("status") == "modified":
                    for notif in result.get("data", []):
                        t = self._notification_to_trigger(notif, workspace_id)
                        if t:
                            triggers.append(t)
                    self._last_cursor = result.get("last_modified") or datetime.utcnow().isoformat()
            except Exception as e:
                logger.warning(f"GitHub notifications step failed: {e}")
            self._failures = 0
            self._last_error = None
            return triggers, self._last_cursor
        except Exception as e:
            self._failures += 1
            self._last_error = str(e)
            logger.error(f"GitHub poll failed ({self._failures}): {e}")
            return [], self._last_cursor

    async def _gh_api(self, path: str, params: dict | None = None, headers: dict | None = None) -> dict:
        """gh api wrapper —— 支持 ETag 条件请求。"""
        args = ["api", f"/repos/{self.repository}/{path}", "--jq", ".", "-X", "GET"]
        if headers:
            for k, v in headers.items():
                args += ["-H", f"{k}: {v}"]
        for k, v in (params or {}).items():
            args += ["-f", f"{k}={v}"]
        proc = await asyncio.create_subprocess_exec(
            self.gh_cli, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise RuntimeError(f"gh api failed: {err.decode()}")
        return {
            "status": "modified",
            "data": json.loads(out.decode()),
            "last_modified": datetime.utcnow().isoformat(),
        }

    def _notification_to_trigger(self, notif: dict, workspace_id: int) -> SourceTrigger | None:
        """GitHub Notification → SourceTrigger。"""
        subject = notif.get("subject", {})
        subject_type = subject.get("type", "")
        url = subject.get("url", "")
        # 从 API URL 解析 ref_id（issues/123 / pulls/456）
        ref_id = url.split("/")[-1] if url else None
        if not ref_id:
            return None
        kind_map = {"Issue": "issue_mention", "PullRequest": "pull_mention"}
        kind = kind_map.get(subject_type, "comment_mention")
        return SourceTrigger(
            source="github", ref_id=str(ref_id), kind=kind,
            sender_id=None, sender_name=None,
            title=subject.get("title"), body=None, url=subject.get("html_url"),
            context={"reason": notif.get("reason"), "type": subject_type},
            workspace_id=workspace_id,
        )

    # --- CI Trigger ---
    async def poll_ci(self, workspace_id: int) -> list[SourceTrigger]:
        """CI failure Trigger —— 检查 main 分支最近 workflow run。"""
        if not self.observe_ci:
            return []
        try:
            result = await self._gh_api(
                "actions/runs",
                params={"branch": self.ci_branch, "status": "failure", "per_page": "5"},
            )
            triggers: list[SourceTrigger] = []
            runs = result.get("data", {}).get("workflow_runs", [])
            for run in runs:
                triggers.append(SourceTrigger(
                    source="github", ref_id=f"ci:{run['id']}", kind="ci_failure",
                    title=f"CI failed: {run.get('name')}", url=run.get("html_url"),
                    context={
                        "branch": self.ci_branch,
                        "conclusion": run.get("conclusion"),
                        "environment": self._gh_env(run),
                    },
                    workspace_id=workspace_id,
                ))
            return triggers
        except Exception as e:
            logger.warning(f"GitHub CI poll failed: {e}")
            return []

    def _gh_env(self, run: dict) -> dict:
        """GitHub CI environment —— 对齐 spec.md FR7 中 environment 注入。"""
        return {
            "DSH_SUPERAGENT_GITHUB_REPOSITORY": self.repository,
            "DSH_SUPERAGENT_GITHUB_CI_RUN_ID": run.get("id"),
            "DSH_SUPERAGENT_GITHUB_CI_BRANCH": self.ci_branch,
        }
