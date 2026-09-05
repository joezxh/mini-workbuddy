"""Skill Evolution Engine - 评估 + 触发 + 记录 + Workspace 文件写回。

设计原则:
- 同步 SQLAlchemy (符合项目实际)
- 用 ai_skill_metrics / ai_skill_version / ai_skill_evolution_log 三张已有表
- 评估用权重公式 WEIGHTS = {success, latency, user_rating, resource}
- trigger_thresholds 控制是否触发进化
- 进化/回滚后写回 SKILL.md → mtime 变化 → SDK LocalWorkspace 自动热重载
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from app.ai.skills.evolution.optimizer import SkillOptimizer
from app.ai.skills.evolution.version_manager import SkillVersionManager
from app.models.ai.ai_skill_package import AiSkillPackage
from app.models.ai.ai_skill_metrics import AiSkillMetrics
from app.models.ai.ai_skill_version import AiSkillVersion
from app.models.ai.ai_skill_evolution_log import AiSkillEvolutionLog

logger = logging.getLogger(__name__)


WEIGHTS = {"success_rate": 0.4, "latency": 0.2, "user_rating": 0.3, "resource": 0.1}
DEFAULT_THRESHOLD = 0.7
DEFAULT_RESOURCE_SCORE = 0.8  # 缺省资源评估得分 (后续接入 APM)


class SkillEvolutionEngine:
    """Skill 自动进化引擎。

    用法:
        eng = SkillEvolutionEngine(db=session, workspace=workspace_adapter)
        score = eng.evaluate("case-retrieval")
        if score < THRESHOLD:
            eng.evolve_if_needed("case-retrieval")

    workspace 参数可选:
        - 提供时: 进化/回滚后自动写回 SKILL.md，触发 SDK 热重载
        - 不提供时: 仅更新 DB 记录（兼容旧行为）
    """

    def __init__(
        self,
        db,
        optimizer: Optional[SkillOptimizer] = None,
        version_manager: Optional[SkillVersionManager] = None,
        threshold: float = DEFAULT_THRESHOLD,
        workspace=None,
    ) -> None:
        self.db = db
        self.optimizer = optimizer or SkillOptimizer()
        self.version_manager = version_manager or (SkillVersionManager(db=db) if db is not None else None)
        self.threshold = threshold
        self.workspace = workspace  # WorkspaceAdapter 实例（可选）
        # 可注入的 metrics 提供器, 主要用于不依赖 DB 的纯函数评估 (测试用)
        self._metrics_provider: Optional[Callable[[str], AiSkillMetrics]] = None

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------
    def evaluate(self, skill_id: str) -> float:
        """返回 0-1 综合评分, 低于 threshold 触发进化。"""
        metrics = self._get_metrics(skill_id)
        if metrics is None:
            return 1.0  # 无数据时默认高分
        sr = float(metrics.success_rate or 0.0)
        ur = float(metrics.user_rating or 0.0)
        latency = float(metrics.avg_latency or 0.0)
        # 60s 满延时时延分为 0
        latency_score = max(0.0, 1.0 - latency / 60.0)
        return (
            WEIGHTS["success_rate"] * sr
            + WEIGHTS["user_rating"] * ur
            + WEIGHTS["latency"] * latency_score
            + WEIGHTS["resource"] * DEFAULT_RESOURCE_SCORE
        )

    def _build_reason(self, score: float, metrics: Optional[AiSkillMetrics]) -> str:
        """构造触发进化的「低分原因」文本（供 LLM 改写提示词）。"""
        if metrics is None:
            return f"综合评分 {score:.3f} 低于阈值，但缺少执行指标，建议优化提示词结构。"
        parts = [f"综合评分 {score:.3f} 低于阈值 {self.threshold}"]
        try:
            ec = int(metrics.execution_count or 0)
            sc = int(metrics.success_count or 0)
            sr = (sc / ec) if ec > 0 else 1.0
            if sr < 0.75:
                parts.append(f"成功率 {sr:.0%} 偏低（{sc}/{ec}）")
            if int(metrics.error_count or 0) > 0:
                parts.append(f"失败 {metrics.error_count} 次")
            if int(metrics.low_score_count or 0) > 0:
                parts.append(f"低分 {metrics.low_score_count} 次")
            if metrics.low_score_reason:
                parts.append(f"低分原因：{metrics.low_score_reason}")
        except Exception:
            pass
        return "；".join(parts)

    def _get_metrics(self, skill_id: str) -> Optional[AiSkillMetrics]:
        if self._metrics_provider is not None:
            return self._metrics_provider(skill_id)
        if self.db is None:
            return None
        return (
            self.db.query(AiSkillMetrics)
            .filter(AiSkillMetrics.skill_id == skill_id)
            .first()
        )

    # ------------------------------------------------------------------
    # 进化触发
    # ------------------------------------------------------------------
    def evolve_if_needed(
        self, skill_id: str, trigger: str = "performance", model_code: Optional[str] = None
    ) -> bool:
        """评估 + 触发进化 + 记录日志 + 创建新版本 + 写回文件。返回是否触发了进化。

        Args:
            model_code: 进化时使用的 LLM 文本模型编码（关联 ai_chat_model.code）。
                        None 表示使用默认模型（库内首个启用模型 / .env 兜底）。
        """
        score = self.evaluate(skill_id)
        if score >= self.threshold:
            logger.info("skill %s score=%.3f >= threshold, no evolution", skill_id, score)
            return False

        if self.db is None:
            logger.warning("no db, skip evolution for %s", skill_id)
            return False

        pkg = (
            self.db.query(AiSkillPackage)
            .filter(AiSkillPackage.package_id == skill_id)
            .first()
        )
        if pkg is None:
            logger.warning("package %s not found, skip", skill_id)
            return False

        # 准备指标与低分原因，供优化器（含 LLM 改写）使用
        metrics = self._get_metrics(skill_id)
        reason = self._build_reason(score, metrics)

        from_version = (
            self.db.query(AiSkillVersion.version_number)
            .filter(AiSkillVersion.skill_id == skill_id)
            .order_by(AiSkillVersion.version_number.desc())
            .first()
        )
        from_version_num = int(from_version[0]) if from_version else 0
        to_version_num = (self.version_manager.get_next_version(skill_id)
                          if self.version_manager is not None
                          else from_version_num + 1)

        try:
            optimized = self.optimizer.optimize_skill(
                pkg, metrics=metrics, reason=reason, trigger=trigger,
                model_code=model_code,
            )
            # 将完整 SKILL.md 内容写入版本记录，供回滚恢复 LLM 进化结果
            version_changes = dict(optimized["changes"])
            if optimized.get("new_skill_md"):
                version_changes["skill_md_content"] = optimized["new_skill_md"]
            else:
                # 回退场景：记录当前正文，保证回滚可用
                version_changes["skill_md_content"] = self._build_updated_skill_md(pkg, optimized)
            self.db.add(AiSkillVersion(
                skill_id=skill_id,
                version_number=to_version_num,
                changes=version_changes,
                is_stable=True,
            ))
            self.db.add(AiSkillEvolutionLog(
                skill_id=skill_id,
                from_version=from_version_num or None,
                to_version=to_version_num,
                trigger_type=trigger,
                result="success",
            ))
            self.db.commit()

            # 写回 SKILL.md → 触发 SDK LocalWorkspace 热重载
            self._write_skill_file(skill_id, pkg, optimized)

            logger.info(
                "evolved skill %s v%d -> v%d (score=%.3f)",
                skill_id, from_version_num, to_version_num, score,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("evolution failed for %s: %s", skill_id, exc)
            try:
                self.db.add(AiSkillEvolutionLog(
                    skill_id=skill_id,
                    from_version=from_version_num or None,
                    to_version=to_version_num,
                    trigger_type=trigger,
                    result="failed",
                ))
                self.db.commit()
            except Exception:  # noqa: BLE001
                self.db.rollback()
            return False

    # ------------------------------------------------------------------
    # 回滚便捷
    # ------------------------------------------------------------------
    def rollback(self, skill_id: str, target_version: int) -> None:
        if self.version_manager is None:
            raise RuntimeError("version_manager not configured")
        before_version = (
            self.db.query(AiSkillVersion.version_number)
            .filter(AiSkillVersion.skill_id == skill_id)
            .order_by(AiSkillVersion.version_number.desc())
            .first()
        )
        before_version_num = int(before_version[0]) if before_version else 0
        self.version_manager.rollback(skill_id, target_version)
        self.db.add(AiSkillEvolutionLog(
            skill_id=skill_id,
            from_version=before_version_num or None,
            to_version=target_version,
            trigger_type="rollback",
            result="rolled_back",
        ))
        self.db.commit()

        # 回滚后写回 SKILL.md（从目标版本的 changes 恢复）
        self._rollback_skill_file(skill_id, target_version)

    # ------------------------------------------------------------------
    # Workspace 文件写回
    # ------------------------------------------------------------------
    def _write_skill_file(self, skill_id: str, pkg: AiSkillPackage, optimized: dict) -> None:
        """将优化结果写回 SKILL.md，触发 SDK 热重载（同步更新数据库 skill_markdown）。"""
        skill_md_path = self._resolve_skill_md_path(skill_id, pkg)
        if skill_md_path is None:
            return

        try:
            content = self._build_updated_skill_md(pkg, optimized)
            os.makedirs(os.path.dirname(skill_md_path), exist_ok=True)
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 同步数据库（skill_markdown 优先来源）
            if self.db is not None:
                pkg.skill_markdown = content
                self.db.commit()
            logger.info("skill file updated: %s (mtime hot-reload triggered)", skill_md_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to write skill file %s: %s", skill_md_path, exc)

    def _rollback_skill_file(self, skill_id: str, target_version: int) -> None:
        """回滚时从版本记录恢复 SKILL.md 内容。"""
        if self.version_manager is None:
            return
        version = self.version_manager.get_version(skill_id, target_version)
        if version is None:
            return

        # 从 DB 查找 package 信息
        pkg = None
        if self.db is not None:
            pkg = (
                self.db.query(AiSkillPackage)
                .filter(AiSkillPackage.package_id == skill_id)
                .first()
            )
        if pkg is None:
            return

        skill_md_path = self._resolve_skill_md_path(skill_id, pkg)
        if skill_md_path is None:
            return

        try:
            # 用原始 frontmatter + 版本 changes 中的 content（如有）重建
            changes = version.changes or {}
            content = changes.get("skill_md_content")
            if content:
                with open(skill_md_path, "w", encoding="utf-8") as f:
                    f.write(content)
                # 同步数据库（skill_markdown 优先来源）
                if self.db is not None:
                    pkg.skill_markdown = content
                    self.db.commit()
                logger.info("skill file rolled back: %s -> v%d", skill_md_path, target_version)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to rollback skill file %s: %s", skill_md_path, exc)

    def _resolve_skill_md_path(self, skill_id: str, pkg: AiSkillPackage) -> Optional[str]:
        """解析 SKILL.md 的写入路径。

        优先使用 workspace 的 skills 目录，其次使用 pkg.file_path。
        """
        if self.workspace is not None:
            # WorkspaceAdapter: 写到 workspace/skills/{skill_id}/SKILL.md
            skills_dir = os.path.join(self.workspace.workdir, "skills")
            return os.path.join(skills_dir, skill_id, "SKILL.md")

        if pkg.file_path:
            # 兼容旧行为: 直接写到 file_path 指向的目录
            base = pkg.file_path
            if os.path.isdir(base):
                return os.path.join(base, "SKILL.md")
            return base

        return None

    def _build_updated_skill_md(self, pkg: AiSkillPackage, optimized: dict) -> str:
        """构建更新后的 SKILL.md 内容。

        重要：必须保留原有 SKILL.md 正文，否则进化会把技能指令清空，导致
        "进化未生效"（实为被空壳覆盖）。这里以原内容为基础追加进化记录。
        """
        # 优先使用 LLM 改写后的正文（optimize_skill 产出），其次回退原文
        llm_md = (optimized.get("new_skill_md") or "").strip()
        if llm_md:
            base = llm_md
            logger.info("using LLM-rewritten SKILL.md body for evolution")
        else:
            # 优先级：数据库最新内容 → 文件系统 → 空串
            base = pkg.skill_markdown
            if not base:
                try:
                    path = self._get_skill_file_path(pkg.package_id, pkg)
                    if path and os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as fh:
                            base = fh.read()
                except Exception:
                    base = None
            if not base:
                base = pkg.skill_markdown or ""

        name = pkg.name or pkg.package_id
        description = optimized.get("description", pkg.description or "")

        # 仅替换 frontmatter 中的 description，保留其余正文
        changes = optimized.get("changes", {})
        recommendations = optimized.get("recommendations", {}) or {}

        note_lines = [
            "",
            "## 进化记录",
            "",
            f"- 优化摘要: {changes.get('summary', 'auto-tuned')}",
            f"- 时间: {changes.get('applied_at', '')}",
            f"- 触发方式: {changes.get('trigger', 'manual')}",
        ]
        if recommendations:
            note_lines.append("- 推荐配置:")
            for k, v in recommendations.items():
                note_lines.append(f"  - {k}: {v}")
        note_lines.append("")

        note = "\n".join(note_lines)

        # 若原内容已含「进化记录」段，避免重复追加
        if "## 进化记录" in base:
            # 替换第一个「## 进化记录」之后的内容
            idx = base.index("## 进化记录")
            return base[:idx].rstrip() + "\n" + note.strip() + "\n"

        return base.rstrip() + "\n" + note
