"""技能优化器 - 基于指标与低分原因，用 LLM 改写 SKILL.md 正文。

设计目标：
- 优先用 LLM 根据「低分原因」对 SKILL.md 提示词正文做有针对性的改写，使进化「有意义」。
- 当未配置大模型 / 调用失败 / 返回不合规时，自动回退到确定性 metadata（retry/cache/timeout
  建议 + 追加进化记录），保证进化流程永远可用、且不会破坏原文。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SkillOptimizer:
    """技能优化器：根据指标与低分原因产出优化结果。

    返回结构（供 engine 使用）：
        {
            "description": str,        # 可能微调的 description
            "recommendations": dict,   # retry/cache/timeout 等确定性建议
            "changes": {               # 写入 AiSkillVersion.changes 的元数据
                "summary": str,
                "applied_at": str,
                "trigger": str,
                "llm_rewritten": bool, # 是否经 LLM 实际改写正文
            },
            "new_skill_md": Optional[str],  # LLM 改写后的完整 SKILL.md；None 表示未改写
        }
    """

    def optimize_skill(
        self,
        pkg: Any,
        metrics: Any,
        reason: Optional[str] = None,
        trigger: str = "manual",
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """基于 pkg / metrics / 低分原因 产出优化结果。

        Args:
            pkg: AiSkillPackage ORM 实例，含 skill_markdown / name / description。
            metrics: AiSkillMetrics ORM 实例（可能为空）。
            reason: 触发进化的低分原因（如「成功率 60% 低于阈值 75%」）。
            trigger: 触发方式 auto / manual。
        """
        name = pkg.name or pkg.package_id
        description = pkg.description or ""

        # ── 1. 确定性部分：从不依赖 LLM 的建议 ──────────────────────────────
        recommendations = self._build_recommendations(metrics)
        summary = reason or "基于执行指标自动调优"

        # ── 2. 尝试 LLM 改写正文 ───────────────────────────────────────────
        new_skill_md: Optional[str] = None
        llm_rewritten = False
        try:
            new_skill_md = self._llm_rewrite(pkg, metrics, reason, model_code)
            if new_skill_md and new_skill_md.strip():
                llm_rewritten = True
                summary = f"基于低分原因经 LLM 改写提示词：{reason or '自动优化'}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill optimizer LLM rewrite failed, fallback: %s", exc)
            new_skill_md = None

        return {
            "description": description,
            "recommendations": recommendations,
            "changes": {
                "summary": summary,
                "applied_at": _now_iso(),
                "trigger": trigger,
                "llm_rewritten": llm_rewritten,
            },
            "new_skill_md": new_skill_md,
        }

    # ------------------------------------------------------------------ #
    # 确定性建议
    # ------------------------------------------------------------------ #
    def _build_recommendations(self, metrics: Any) -> Dict[str, Any]:
        rec: Dict[str, Any] = {}
        if not metrics:
            return rec
        try:
            ec = int(metrics.execution_count or 0)
            sc = int(metrics.success_count or 0)
            success_rate = (sc / ec) if ec > 0 else 1.0
            if success_rate < 0.75:
                rec["retry"] = 2
                rec["timeout"] = 120
            if int(metrics.error_count or 0) > 0:
                rec["cache"] = True
        except Exception:
            pass
        return rec

    # ------------------------------------------------------------------ #
    # LLM 改写
    # ------------------------------------------------------------------ #
    def _llm_rewrite(
        self,
        pkg: Any,
        metrics: Any,
        reason: Optional[str],
        model_code: Optional[str] = None,
    ) -> Optional[str]:
        """用 LLM 根据低分原因改写 SKILL.md 正文，返回完整改写后的 Markdown。

        失败时抛异常（由调用方回退），不在此吞掉错误。
        """
        model = self._resolve_model(pkg, model_code)
        if model is None:
            raise RuntimeError(
                f"no available chat model for skill optimization"
                + (f" (model_code={model_code})" if model_code else "")
            )

        base_md = pkg.skill_markdown
        if not base_md:
            # 回退读取文件系统
            path = _get_skill_file_path(pkg.package_id, pkg)
            if path and os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    base_md = fh.read()
        if not base_md:
            raise RuntimeError("skill has no SKILL.md content to rewrite")

        prompt = self._build_rewrite_prompt(base_md, metrics, reason)

        resp = model(prompt)
        text = getattr(resp, "text", None) or str(resp)
        text = _strip_code_fence(text)

        if not text or len(text.strip()) < 50:
            raise RuntimeError("LLM returned empty/short rewrite")

        # 安全检查：改写结果必须保留 frontmatter 与技能名称，避免 LLM 跑题
        if "name:" not in text and "---" not in text:
            # 至少保留原 frontmatter
            return _ensure_frontmatter(base_md, text)
        return text

    def _resolve_model(self, pkg: Any, model_code: Optional[str] = None):
        """解析用于进化的 LLM。优先级：用户指定模型 → DB 首个启用模型 → settings 兜底。"""
        try:
            from app.db.database import SessionLocal
            from app.ai.strategy.registry_bridge import build_model_from_db
            from app.tasks.person_event_context_tasks import (
                _build_first_active_chat_model,
                _build_model_from_settings,
            )
            # 1) 用户在前端选择的模型（关联 ai_chat_model.code）
            if model_code:
                db = SessionLocal()
                try:
                    model = build_model_from_db(db, model_code)
                    if model is not None:
                        return model
                    logger.warning("specified model_code=%s not found, fallback", model_code)
                finally:
                    db.close()
            # 2) DB 首个启用的对话模型
            db = SessionLocal()
            try:
                model = _build_first_active_chat_model(db)
                if model is not None:
                    return model
            finally:
                db.close()
            # 3) settings 兜底（gpustack 等 .env 全局模型）
            model = _build_model_from_settings()
            if model is not None:
                return model
        except Exception as exc:  # noqa: BLE001
            logger.warning("skill optimizer model resolve failed: %s", exc)
        return None

    def _build_rewrite_prompt(
        self,
        skill_md: str,
        metrics: Any,
        reason: Optional[str],
    ) -> str:
        metrics_text = "无"
        if metrics:
            metrics_text = (
                f"执行次数={metrics.execution_count}, "
                f"成功次数={metrics.success_count}, "
                f"失败次数={metrics.error_count}, "
                f"低分次数={metrics.low_score_count}, "
                f"低分原因={metrics.low_score_reason or '无'}"
            )
        reason_text = reason or "执行指标偏低，提示词需要优化"

        return (
            "你是一名资深的 AI 技能（Skill）提示词工程师。下面是一份 SKILL.md 的当前内容。\n"
            "请根据【低分原因】与【执行指标】，对提示词正文进行有针对性的改写，"
            "目标是提升该技能的执行成功率与输出质量。\n\n"
            "要求：\n"
            "1. 保留原有 YAML frontmatter（name/description）。\n"
            "2. 保留技能的核心指令与结构，只做「针对性增强」，不要无谓重写。\n"
            "3. 针对低分原因补充更明确的约束、步骤、示例或自检要求。\n"
            "4. 不要改变技能的用途与输入输出契约。\n"
            "5. 直接输出改写后的完整 SKILL.md（Markdown），不要额外解释。\n\n"
            f"【低分原因】\n{reason_text}\n\n"
            f"【执行指标】\n{metrics_text}\n\n"
            f"【当前 SKILL.md】\n{skill_md}\n"
        )


# ---------------------------------------------------------------------- #
# 辅助函数
# ---------------------------------------------------------------------- #
def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def _strip_code_fence(text: str) -> str:
    """去掉 LLM 可能包裹的 ```markdown ... ``` 代码块。"""
    if not text:
        return text
    text = text.strip()
    pattern = re.compile(r"^```(?:markdown)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
    m = pattern.match(text)
    if m:
        return m.group(1).strip()
    # 退一步：去掉首尾的行内 ``` 标记
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _ensure_frontmatter(original: str, rewritten: str) -> str:
    """若 LLM 输出丢失 frontmatter，从原文件补齐。"""
    if "---" in original and "---" not in rewritten:
        end = original.find("---", 3)
        if end != -1:
            fm = original[: end + 3]
            return fm + "\n\n" + rewritten
    return rewritten


def _get_skill_file_path(package_id: str, pkg: Any) -> Optional[str]:
    """定位文件系统 SKILL.md（与 engine 逻辑一致）。"""
    try:
        from app.config import settings
        import os
        base = os.path.join(settings.BASE_DIR, "data", "skills")
        # 优先使用 pkg 记录的路径
        rel = getattr(pkg, "file_path", None)
        if rel:
            cand = os.path.join(base, rel)
            if os.path.exists(cand):
                return cand
        # 退化：按 package_id 目录查找
        for sub in (package_id,):
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                for fn in ("SKILL.md", "skill.md"):
                    p = os.path.join(d, fn)
                    if os.path.exists(p):
                        return p
    except Exception:
        return None
    return None
