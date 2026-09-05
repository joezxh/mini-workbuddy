"""ResearchOrchestrator - 深度研究四阶段流水线

阶段：拆解(decompose) → 并行检索(search, Semaphore(4) 限流) → 评估(evaluate) → 汇总(synthesize)
逐阶段 yield 进度事件 dict，末次 yield 为 research_report。

复用：
- WebSearchToolService（联网搜索统一服务，方案 1，见 ai/web_search/service）
- knowledge_search（已移除，知识库检索返回空）
- research.llm（AgentScope build_model + DB 模型配置）
- research.credibility（纯规则可信度评分）
不新建检索引擎 / 不额外调用 LLM 做评分。
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

from app.ai.web_search.service import WebSearchToolService
# knowledge_search 已移除，stub 为空列表
def _stub_search_knowledge_bases(*args, **kwargs):
    return []

from app.ai.research.llm import llm_json
from app.ai.research.credibility import score_sources


def _run_in_thread(func, *args):
    """在独立线程中执行同步 KB 检索，避免阻塞事件循环。

    使用 asyncio.to_thread（而非 asyncio.get_event_loop().run_in_executor），
    因为它会自动绑定到当前运行的事件循环，避免跨 loop 调度引发
    ``Event loop is closed`` 的未捕获异常（httpx aclose 在错误 loop 上触发）。
    """
    return asyncio.to_thread(func, *args)

_PROMPT_DECOMPOSE = """你是一个通用深度研究规划助手。

用户给定的研究主题如下：
<研究主题>
{topic}
</研究主题>

请基于上述主题，拆解为不超过 {max_n} 个相互独立、可并行检索的子问题，用于后续联网检索与知识库检索。

拆解要求：
1. 子问题必须紧密围绕给定主题的核心事实、关键概念、技术细节或实践应用，不得泛化为空泛的"学术开题"套路（严禁出现"技术现状与发展趋势""核心理论框架的文献综述""关键实验方法""跨学科融合路径""未来研究方向"等空泛表述）。
2. 优先从以下维度组织（按需取舍，不必全选）：
   - 核心概念与定义（关键术语、基本概念、范畴界定）
   - 现状与事实（当前状况、已知数据、已有成果）
   - 原因与分析（成因分析、影响因素、关联关系）
   - 对比与案例（相似案例、行业对标、最佳实践）
   - 方案与对策（解决方案、实施路径、建议措施）
3. 每个子问题应是可直接作为检索关键词短语的句子（例如"深度学习在自然语言处理中的最新应用"），而非问句。

只输出 JSON：{{"sub_questions": ["子问题1", "子问题2", ...]}}，不要任何解释。"""

_PROMPT_SYNTHESIZE = """你是一名资深研究分析师。基于下列子问题及其检索到的资料，撰写一份结构化研究报告。

研究主题：{topic}

子问题与资料：
{evidence}

请严格输出如下 JSON（不要任何额外文字）：
{{
  "summary": "研究摘要（2-4 句）",
  "key_findings": ["关键发现1", "关键发现2", ...],
  "analysis": "详细分析（多段落 Markdown）",
  "sources": [{{"title": "来源标题", "url": "来源URL", "credibility": 0.0-1.0}}, ...]
}}
"""

_PROMPT_ANALYZE_SQ = """你是一名研究分析师。请基于下列检索到的资料，针对该子问题给出精炼分析。

研究主题：{topic}
子问题：{question}

检索到的资料：
{evidence}

请严格输出如下 JSON（不要任何额外文字）：
{{
  "analysis": "针对该子问题的分析结论（2-4 段 Markdown，聚焦子问题本身，引用具体数据/来源/案例，避免泛泛而谈）",
  "key_points": ["要点1", "要点2", ...],
  "sources": [{{"title": "来源标题", "url": "来源URL"}}, ...]
}}"""

_PROMPT_VERIFY = """你是一名严谨的研究质量校验官。请判断下方「当前研究报告」是否已经充分、准确地回答了用户的原始研究问题。

用户原始问题：
{user_question}

当前研究报告（摘要 + 关键发现 + 详细分析）：
{report}

请严格输出如下 JSON（不要任何额外文字）：
{{
  "satisfied": true 或 false,
  "gaps": ["当前报告仍缺失或薄弱的要点1", "要点2", ...],
  "reason": "一句话说明判定理由"
}}

判定标准：
- 若报告已覆盖用户问题的主体事实、关键法律依据、核心风险与处置对策，且无明显事实缺失或关键矛盾，则 satisfied=true，gaps 可为空数组。
- 若存在重要事实空白、关键法条/类案缺失、结论无依据或前后矛盾，则 satisfied=false，并在 gaps 中列出需要补充的具体方向。"""

_PROMPT_REFINE = """你是一名深度研究规划助手。上一轮研究已产出初步报告，但经校验发现仍存在以下待补强的要点。

用户原始问题：
{user_question}

上一轮报告摘要：
{prev_summary}

上一轮已研究的子问题（避免重复）：
{prev_questions}

待补强的要点（gaps）：
{gaps}

请基于上述信息，补充拆解不超过 {max_n} 个新的、与已有子问题不重复的子问题，用于进一步检索与完善报告。
子问题必须紧扣 gaps 中列出的待补强方向，禁止泛化为通用学术表述。

只输出 JSON：{{"sub_questions": ["新子问题1", "新子问题2", ...]}}，不要任何解释。"""


class ResearchOrchestrator:
    def __init__(
        self,
        db: Any,
        model_id: Optional[int] = None,
        knowledge_bases: Optional[List[str]] = None,
        max_sub_questions: int = 8,
        max_concurrency: int = 4,
        per_question_timeout: int = 60,
        max_rounds: int = 5,
    ):
        self.db = db
        self.model_id = model_id
        self.knowledge_bases = knowledge_bases or ["general"]  # 默认通用知识库
        self.max_sub_questions = max_sub_questions
        self.max_concurrency = max_concurrency
        self.per_question_timeout = per_question_timeout
        self.max_rounds = max(1, min(max_rounds, 5))  # 最多 5 轮，下限 1
        self._web_search = WebSearchToolService(db)

    async def run(self, topic: str) -> AsyncGenerator[Dict[str, Any], None]:
        """迭代式深度研究：多轮「拆解→并行检索+LLM 分析→评估→汇总」。

        每轮汇总后校验是否已达到用户的原始研究目标；未达标且有可补充方向时，
        基于 gaps 分拆新一轮子问题继续研究，直至达标或达到 max_rounds（最多 5 轮）。
        """
        yield {"type": "research_start", "topic": topic}

        # emit 闭包：子方法无法直接使用 yield（yield 是语句关键字，不能作参数），
        # 故先缓冲到 pending_out，再由外层 async generator 冲刷出去。
        pending_out: List[Dict[str, Any]] = []

        def emit(ev: Dict[str, Any]) -> None:
            pending_out.append(ev)

        # 跨轮累积：所有子问题（含各轮）与交叉引用计数，最终报告综合全部证据
        all_sub_list: List[Dict[str, Any]] = []
        cross_counter: Dict[str, int] = {}
        prev_questions: List[str] = []
        gaps: List[str] = []
        final_report: Dict[str, Any] = {}
        did_multiple_rounds = False

        for round_idx in range(1, self.max_rounds + 1):
            is_first = (round_idx == 1)
            round_tag = f"r{round_idx}"
            yield {"type": "research_progress", "stage": "round_start", "progress": 5,
                   "message": f"第 {round_idx}/{self.max_rounds} 轮研究启动"
                              + ("（首次拆解）" if is_first else "（针对未达标要点的补充研究）"),
                   "round": round_idx}

            # ---- 本轮子问题 ----
            if is_first:
                sub_questions = await self._decompose(topic, round_tag, emit)
            else:
                did_multiple_rounds = True
                sub_questions = await self._refine(topic, final_report, prev_questions,
                                                   gaps, round_tag, emit)
            while pending_out:
                yield pending_out.pop(0)
            if not sub_questions:
                # 无新子问题可研究，提前结束迭代
                yield {"type": "research_progress", "stage": "round_end", "progress": 95,
                       "message": f"第 {round_idx} 轮无新增子问题，结束迭代",
                       "round": round_idx}
                break

            # ---- 本轮并行检索 + 子问题 LLM 分析 + 评估 ----
            sub_list = await self._research_round(
                topic, sub_questions, round_idx, round_tag, cross_counter, emit
            )
            while pending_out:
                yield pending_out.pop(0)
            all_sub_list.extend(sub_list)
            prev_questions.extend([s["question"] for s in sub_list])

            # ---- 本轮汇总 ----
            evidence = self._build_evidence(sub_list)
            report = await self._synthesize(topic, evidence, round_tag, cross_counter, emit)
            while pending_out:
                yield pending_out.pop(0)
            # 第一轮直接采用；后续轮将其作为「当前最佳」用于校验（最终报告在退出时综合）
            final_report = report

            yield {"type": "research_report", **report, "round": round_idx}
            yield {"type": "research_progress", "stage": "round_done", "progress": 90,
                   "message": f"第 {round_idx} 轮报告生成完成", "round": round_idx,
                   "sub_questions": sub_list}

            # ---- 目标校验：是否已达到用户原始问题 ----
            if round_idx >= self.max_rounds:
                yield {"type": "research_progress", "stage": "verify", "progress": 95,
                       "message": f"已达最大轮次（{self.max_rounds}），结束迭代",
                       "round": round_idx}
                break
            verify = await self._verify(topic, report, round_tag, emit)
            while pending_out:
                yield pending_out.pop(0)
            if verify.get("satisfied"):
                yield {"type": "research_progress", "stage": "verify", "progress": 95,
                       "message": f"第 {round_idx} 轮校验通过：已满足用户研究目标，结束迭代",
                       "round": round_idx}
                break
            gaps = verify.get("gaps") or []
            yield {"type": "research_progress", "stage": "verify", "progress": 95,
                   "message": f"第 {round_idx} 轮校验未达标，待补充：{'; '.join(gaps[:3]) or '（无明确缺口，继续深化）'}",
                   "round": round_idx}

        # ---- 收尾：仅当经历多轮时，用全量证据综合一次最终报告 ----
        # （单轮时 final_report 已是本轮完整报告，无需重复汇总）
        if did_multiple_rounds and all_sub_list:
            yield {"type": "research_progress", "stage": "finalize", "progress": 98,
                   "message": "正在综合各轮研究结果生成最终报告..."}
            full_evidence = self._build_evidence(all_sub_list)
            try:
                yield {"type": "model_call", "title": "调用大模型生成最终综合报告",
                       "status": "running"}
                final_report = await llm_json(
                    _PROMPT_SYNTHESIZE.format(topic=topic, evidence=full_evidence),
                    self.model_id,
                )
                yield {"type": "model_call", "title": "调用大模型生成最终综合报告",
                       "status": "done"}
            except Exception as e:
                logger.error(f"[orchestrator] 最终综合报告生成失败，沿用末轮报告: {e}")
            final_report = {
                "summary": final_report.get("summary", ""),
                "key_findings": final_report.get("key_findings", []),
                "analysis": final_report.get("analysis", ""),
                "sources": self._merge_report_sources(
                    final_report.get("sources", []), cross_counter
                ),
            }
        yield {"type": "research_report", **final_report, "round": 0,
               "final": True}
        yield {"type": "research_progress", "stage": "done", "progress": 100,
               "message": "研究完成", "sub_questions": all_sub_list}

    async def _decompose(self, topic, round_tag, yield_fn) -> List[str]:
        """阶段1：首次拆解用户主题。"""
        yield_fn({"type": "research_progress", "stage": "decompose", "progress": 8,
                  "message": "正在拆解研究主题...", "round": 1})
        try:
            yield_fn({"type": "model_call", "title": "调用大模型拆解研究主题",
                      "status": "running", "round": 1})
            plan = await llm_json(
                _PROMPT_DECOMPOSE.format(max_n=self.max_sub_questions, topic=topic),
                self.model_id,
            )
            yield_fn({"type": "model_call", "title": "调用大模型拆解研究主题",
                      "status": "done", "round": 1})
            sub_questions = plan.get("sub_questions", [])[: self.max_sub_questions] or [topic]
            logger.info(f"[orchestrator] 主题拆解得到 {len(sub_questions)} 个子问题")
        except Exception as e:
            yield_fn({"type": "model_call", "title": "调用大模型拆解研究主题",
                      "status": "failed", "detail": str(e)[:200], "round": 1})
            logger.error(f"[orchestrator] 主题拆解失败（LLM 调用异常），退化为单问题: {e}")
            sub_questions = [topic]
        sub_list = [
            {"id": f"{round_tag}_sq_{i+1}", "question": q, "status": "queued", "sources": []}
            for i, q in enumerate(sub_questions)
        ]
        yield_fn({"type": "research_plan", "sub_questions": sub_list, "round": 1})
        return sub_questions

    async def _refine(self, topic, prev_report, prev_questions, gaps, round_tag, yield_fn) -> List[str]:
        """后续轮：基于上轮校验的 gaps 补充拆解新子问题。"""
        try:
            yield_fn({"type": "model_call", "title": f"调用大模型拆解补充子问题（{round_tag}）",
                      "status": "running", "round": int(round_tag[1:])})
            plan = await llm_json(
                _PROMPT_REFINE.format(
                    user_question=topic,
                    prev_summary=prev_report.get("summary", ""),
                    prev_questions="\n".join(f"- {q}" for q in prev_questions),
                    gaps="\n".join(f"- {g}" for g in gaps),
                    max_n=self.max_sub_questions,
                ),
                self.model_id,
            )
            yield_fn({"type": "model_call", "title": f"调用大模型拆解补充子问题（{round_tag}）",
                      "status": "done", "round": int(round_tag[1:])})
            new_qs = plan.get("sub_questions", []) or []
            # 去重：剔除与已研究子问题高度相似的补充项
            seen = {q.strip().lower() for q in prev_questions}
            new_qs = [q for q in new_qs if q.strip().lower() not in seen][: self.max_sub_questions]
            logger.info(f"[orchestrator] 第 {round_tag} 轮补充拆解得到 {len(new_qs)} 个新子问题")
        except Exception as e:
            yield_fn({"type": "model_call", "title": f"调用大模型拆解补充子问题（{round_tag}）",
                      "status": "failed", "detail": str(e)[:200]})
            logger.error(f"[orchestrator] 补充拆解失败: {e}")
            new_qs = []
        sub_list = [
            {"id": f"{round_tag}_sq_{i+1}", "question": q, "status": "queued", "sources": []}
            for i, q in enumerate(new_qs)
        ]
        if sub_list:
            yield_fn({"type": "research_plan", "sub_questions": sub_list, "round": int(round_tag[1:])})
        return new_qs

    async def _verify(self, topic, report, round_tag, yield_fn) -> Dict[str, Any]:
        """校验当前报告是否满足用户原始研究目标。"""
        try:
            yield_fn({"type": "model_call", "title": f"调用大模型校验研究目标达成度（{round_tag}）",
                      "status": "running", "round": int(round_tag[1:])})
            report_text = json.dumps(
                {
                    "summary": report.get("summary", ""),
                    "key_findings": report.get("key_findings", []),
                    "analysis": report.get("analysis", ""),
                },
                ensure_ascii=False,
            )
            verify = await llm_json(
                _PROMPT_VERIFY.format(user_question=topic, report=report_text),
                self.model_id,
            )
            yield_fn({"type": "model_call", "title": f"调用大模型校验研究目标达成度（{round_tag}）",
                      "status": "done", "round": int(round_tag[1:])})
            return verify
        except Exception as e:
            logger.error(f"[orchestrator] 目标校验失败，默认继续: {e}")
            yield_fn({"type": "model_call", "title": f"调用大模型校验研究目标达成度（{round_tag}）",
                      "status": "failed", "detail": str(e)[:200]})
            # 校验异常时保守地继续一轮（最多轮次会兜底）
            return {"satisfied": False, "gaps": [], "reason": "校验失败"}

    async def _research_round(self, topic, sub_questions, round_idx, round_tag,
                             cross_counter, yield_fn):
        """单轮：并行检索 + 子问题 LLM 分析 + 评估来源，yield 进度事件。

        返回本轮 sub_list（含 sources / analysis / key_points）。
        """
        sub_list = [
            {"id": f"{round_tag}_sq_{i+1}", "question": q, "status": "queued",
             "sources": [], "analysis": "", "key_points": []}
            for i, q in enumerate(sub_questions)
        ]
        yield_fn({"type": "research_progress", "stage": "search", "progress": 20,
                  "message": f"正在并行检索 {len(sub_list)} 个子问题（第 {round_idx} 轮）",
                  "round": round_idx})
        sem = asyncio.Semaphore(self.max_concurrency)
        pending: List[Dict[str, Any]] = []

        def yield_progress(sq_id, status, sources=None):
            sq = next((s for s in sub_list if s["id"] == sq_id), None)
            q = sq["question"] if sq else sq_id
            verb = {"searching": "检索中", "done": "检索完成", "failed": "检索失败"}.get(status, status)
            pending.append({"type": "research_progress",
                            "stage": "search", "progress": None,
                            "message": f"子问题「{q}」{verb}",
                            "sub_question_id": sq_id, "status": status,
                            "round": round_idx, "sources": sources or []})

        async def _search_one(sq: Dict[str, Any]):
            async with sem:
                sq["status"] = "searching"
                yield_progress(sq["id"], "searching")
                try:
                    res = await asyncio.wait_for(
                        self._search_subquestion(sq["question"], topic),
                        timeout=self.per_question_timeout,
                    )
                    sq["status"] = "done"
                    sq["sources"] = res
                    for s in res:
                        cross_counter[s["url"]] = cross_counter.get(s["url"], 0) + 1
                    yield_progress(sq["id"], "done", sources=res)

                    # 子问题级 LLM 提炼：检索材料经 LLM 分析为针对该子问题的结论
                    if res:
                        yield_fn({"type": "model_call",
                                  "title": f"分析子问题：{sq['question']}",
                                  "status": "running", "sub_question_id": sq["id"],
                                  "round": round_idx})
                        try:
                            ev_text = "\n".join(
                                f"- [{s.get('title', '')}]({s.get('url', '')})" for s in res
                            )
                            sq_analysis = await llm_json(
                                _PROMPT_ANALYZE_SQ.format(
                                    topic=topic, question=sq["question"], evidence=ev_text
                                ),
                                self.model_id,
                            )
                            sq["analysis"] = sq_analysis.get("analysis", "")
                            sq["key_points"] = sq_analysis.get("key_points", [])
                            llm_src = sq_analysis.get("sources") or []
                            if llm_src:
                                sq["sources"] = [
                                    {"title": s.get("title", ""), "url": s.get("url", "")}
                                    for s in llm_src
                                ]
                            yield_fn({"type": "model_call",
                                      "title": f"分析子问题：{sq['question']}",
                                      "status": "done", "sub_question_id": sq["id"],
                                      "round": round_idx})
                        except Exception as e:
                            logger.warning(f"子问题 LLM 分析失败[{sq['question']}]: {e}")
                            sq["analysis"] = ""
                            sq["key_points"] = []
                            yield_fn({"type": "model_call",
                                      "title": f"分析子问题：{sq['question']}",
                                      "status": "failed", "sub_question_id": sq["id"],
                                      "detail": str(e)[:200], "round": round_idx})
                except Exception as e:
                    sq["status"] = "failed"
                    logger.warning(f"子问题检索失败[{sq['question']}]: {e}")
                    yield_progress(sq["id"], "failed")

        await asyncio.gather(*[_search_one(sq) for sq in sub_list])
        for ev in pending:
            yield_fn(ev)

        # 评估（可信度评分，纯规则）
        yield_fn({"type": "research_progress", "stage": "evaluate", "progress": 70,
                  "message": "正在评估来源可信度...", "round": round_idx})
        for sq in sub_list:
            scored = score_sources(sq["sources"], cross_counter)
            sq["sources"] = scored
            for s in scored:
                title = (s.get("title") or "").strip()
                url = (s.get("url") or "").strip()
                if not title and not url:
                    continue
                yield_fn({"type": "research_source", "sub_question_id": sq["id"],
                          "sub_question": sq["question"], "round": round_idx,
                          "title": title, "url": url, "credibility": s["credibility"]})
        return sub_list

    async def _synthesize(self, topic, evidence, round_tag, cross_counter, yield_fn) -> Dict[str, Any]:
        """单轮汇总：基于本轮证据生成结构化报告。"""
        yield_fn({"type": "research_progress", "stage": "synthesize", "progress": 90,
                  "message": "正在生成研究报告...", "round": int(round_tag[1:])})
        try:
            yield_fn({"type": "model_call", "title": "调用大模型生成研究报告",
                      "status": "running", "round": int(round_tag[1:])})
            report = await llm_json(
                _PROMPT_SYNTHESIZE.format(topic=topic, evidence=evidence), self.model_id
            )
            yield_fn({"type": "model_call", "title": "调用大模型生成研究报告",
                      "status": "done", "round": int(round_tag[1:])})
            report_out = {
                "summary": report.get("summary", ""),
                "key_findings": report.get("key_findings", []),
                "analysis": report.get("analysis", ""),
                "sources": self._merge_report_sources(report.get("sources", []), cross_counter),
            }
        except Exception as e:
            logger.error(f"[orchestrator] LLM 汇总失败，降级为规则报告: {e}")
            report_out = {
                "summary": "（LLM 汇总失败，已降级）",
                "key_findings": [],
                "analysis": f"研究主题：{topic}\n\n本轮检索未能汇总为结构化报告，建议结合检索来源进一步分析。",
                "sources": [],
            }
        return report_out

    async def _search_subquestion(self, question: str, topic: str = "") -> List[Dict[str, str]]:
        """对单个子问题执行 web + 知识库联合检索，返回扁平来源列表。

        web 检索走方案 1（WebSearchToolService，统一读 AiWebSearch 配置 + factory）；
        知识库检索走 knowledge_search（向量联合检索），二者并联聚合。

        检索 query 会拼接 ``topic`` 作为上下文前缀，约束联网检索范围，
        避免子问题脱离原始主题导致检索结果泛化、跑偏。
        """
        # 以原始主题 + 子问题共同构成检索式，提升相关性
        combined_query = f"{topic} {question}".strip() if topic else question
        web_task = self._web_search.search(query=combined_query, max_results=5)

        def _kb_search_in_thread():
            # 每个子问题使用独立的 SessionLocal，禁止与共享的 self.db 并发使用：
            # 同一 Session 实例在多线程/异步并发下会触发 "provisioning a new
            # connection; concurrent operations are not permitted"。独立 session
            # 仅在本线程内使用，用完即关。
            from app.db.database import SessionLocal

            kb_db = SessionLocal()
            try:
                return _stub_search_knowledge_bases(
                    kb_db,
                    combined_query,
                    self.knowledge_bases,
                    5,
                )
            finally:
                kb_db.close()

        kb_task = _run_in_thread(_kb_search_in_thread)
        web_payload, kb_results = await asyncio.gather(web_task, kb_task)

        merged: List[Dict[str, Any]] = list(web_payload.get("results", []))
        merged.extend(kb_results or [])
        out: List[Dict[str, str]] = []
        for r in merged:
            out.append({
                "title": r.get("title") or r.get("content", "")[:50],
                "url": r.get("url") or f"kb:{r.get('kb_type','')}:{r.get('id','')}",
            })
        return out

    @staticmethod
    def _build_evidence(sub_list: List[Dict[str, Any]]) -> str:
        lines = []
        for sq in sub_list:
            lines.append(f"### 子问题：{sq['question']}（状态：{sq['status']}）")
            # 优先使用 LLM 对该子问题的分析结论作为证据（信息密度更高），
            # 无分析结论时退化为来源链接列表。
            analysis = (sq.get("analysis") or "").strip()
            if analysis:
                lines.append(analysis)
            else:
                for s in sq.get("sources", []):
                    lines.append(f"- [{s.get('title','')}]({s.get('url','')}) 可信度:{s.get('credibility','-')}")
        return "\n".join(lines)

    @staticmethod
    def _merge_report_sources(sources: List[Dict[str, Any]], cross_counter: Dict[str, int]) -> List[Dict[str, Any]]:
        seen = {}
        for s in sources:
            url = s.get("url", "")
            if url in seen:
                continue
            cred = s.get("credibility")
            if cred is None:
                # 复用交叉计数粗略估计
                cred = min(1.0, 0.6 + 0.05 * max(0, cross_counter.get(url, 1) - 1))
            seen[url] = {"title": s.get("title", ""), "url": url, "credibility": round(float(cred), 4)}
        return list(seen.values())
