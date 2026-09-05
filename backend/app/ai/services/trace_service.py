"""Agent 执行链路追踪服务"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.telemetry.tracer import (
    get_tracer,
    create_span,
    get_current_span,
    get_trace_id,
    Span,
)
from app.ai.telemetry.exporter import get_exporter


class AgentTraceRecord:
    """Agent 执行链路记录"""
    
    def __init__(
        self,
        trace_id: str,
        agent_id: str,
        agent_type: str,
        session_id: Optional[int] = None,
        user_id: Optional[int] = None,
        input_prompt: Optional[str] = None,
        output_result: Optional[str] = None,
        skills_used: Optional[List[str]] = None,
        tools_used: Optional[List[Dict]] = None,
        error: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace_id = trace_id
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.session_id = session_id
        self.user_id = user_id
        self.input_prompt = input_prompt
        self.output_result = output_result
        self.skills_used = skills_used or []
        self.tools_used = tools_used or []
        self.error = error
        self.start_time = start_time or datetime.utcnow()
        self.end_time = end_time
        self.metadata = metadata or {}
        self.spans: List[Span] = []
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "input_prompt": self.input_prompt,
            "output_result": self.output_result,
            "skills_used": self.skills_used,
            "tools_used": self.tools_used,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "spans": [s.to_dict() for s in self.spans],
        }


class TraceService:
    """Agent 链路追踪服务"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self._tracer = get_tracer()
        self._exporter = get_exporter()
        self._current_trace: Optional[AgentTraceRecord] = None
    
    def start_trace(
        self,
        agent_id: str,
        agent_type: str,
        session_id: Optional[int] = None,
        user_id: Optional[int] = None,
        input_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """开始一条链路追踪"""
        trace_id = get_trace_id() or self._tracer._all_spans[-1].trace_id if self._tracer._all_spans else None
        
        if not trace_id:
            with create_span("root") as root_span:
                trace_id = root_span.trace_id
        
        self._current_trace = AgentTraceRecord(
            trace_id=trace_id,
            agent_id=agent_id,
            agent_type=agent_type,
            session_id=session_id,
            user_id=user_id,
            input_prompt=input_prompt,
            metadata=metadata or {},
            start_time=datetime.utcnow(),
        )
        
        logger.debug(f"[TRACE] Started trace: trace_id={trace_id}, agent_id={agent_id}")
        return trace_id
    
    def end_trace(
        self,
        output_result: Optional[str] = None,
        skills_used: Optional[List[str]] = None,
        tools_used: Optional[List[Dict]] = None,
        error: Optional[str] = None,
    ) -> Optional[AgentTraceRecord]:
        """结束链路追踪"""
        if not self._current_trace:
            logger.warning("[TRACE] No active trace to end")
            return None
        
        self._current_trace.end_time = datetime.utcnow()
        self._current_trace.output_result = output_result
        self._current_trace.skills_used = skills_used or []
        self._current_trace.tools_used = tools_used or []
        self._current_trace.error = error
        
        current_span = get_current_span()
        if current_span:
            self._current_trace.spans = self._collect_spans()
        
        self._export_trace(self._current_trace)
        self._save_to_db(self._current_trace)
        
        trace_record = self._current_trace
        self._current_trace = None
        
        logger.debug(
            f"[TRACE] Ended trace: trace_id={trace_record.trace_id}, "
            f"duration={trace_record.duration_ms:.2f}ms"
        )
        
        return trace_record
    
    def add_span(
        self,
        name: str,
        span_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """添加一个自定义 Span"""
        span = self._tracer.start_span(name, attributes={
            "span_type": span_type,
            **(attributes or {}),
        })
        return span
    
    def record_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录一个事件"""
        span = get_current_span()
        if span:
            span.add_event(name, attributes)
        logger.debug(f"[TRACE] Event: {name} - {attributes}")
    
    def set_span_attribute(self, key: str, value: Any) -> None:
        """设置当前 Span 属性"""
        span = get_current_span()
        if span:
            span.set_attribute(key, value)
    
    def _collect_spans(self) -> List[Span]:
        """收集所有相关 Span"""
        root_span = self._tracer.get_root_span()
        if root_span:
            return self._flatten_spans(root_span)
        
        current = get_current_span()
        if current:
            return [current]
        
        return []
    
    def _flatten_spans(self, span: Span) -> List[Span]:
        """扁平化 Span 树"""
        result = [span]
        for child in span.children:
            result.extend(self._flatten_spans(child))
        return result
    
    def _export_trace(self, trace: AgentTraceRecord) -> None:
        """导出链路记录"""
        if not trace.spans:
            return
        
        try:
            self._exporter.export(trace)
            
            for span in trace.spans:
                self._exporter.export(span)
        except Exception as e:
            logger.error(f"[TRACE] Failed to export trace: {e}")
    
    def _save_to_db(self, trace: AgentTraceRecord) -> None:
        """保存链路记录到数据库"""
        if not self.db:
            return
        
        try:
            from app.models.agent.agent_trace import AgentTrace

            trace_record = AgentTrace(
                trace_id=trace.trace_id,
                session_id=trace.session_id,
                user_id=trace.user_id,
                agent_id=trace.agent_id,
                agent_type=trace.agent_type,
                input_prompt=trace.input_prompt,
                output_result=trace.output_result,
                skills_used=trace.skills_used,
                tools_used=trace.tools_used,
                error=trace.error,
                status="ERROR" if trace.error else "OK",
                start_time=trace.start_time,
                end_time=trace.end_time,
                duration_ms=int(trace.duration_ms) if trace.duration_ms else None,
                extra_metadata=trace.metadata,
            )
            self.db.add(trace_record)

            self.db.commit()
            logger.debug(f"[TRACE] Saved to DB: trace_id={trace.trace_id}")
        except Exception as e:
            logger.error(f"[TRACE] Failed to save to DB: {e}")
            self.db.rollback()
    
    def get_trace_summary(
        self,
        trace_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取链路摘要"""
        spans = self._tracer.get_trace(trace_id)
        if not spans:
            return None
        
        root = next((s for s in spans if not s.parent_span_id), spans[0])
        
        return {
            "trace_id": trace_id,
            "service_name": root.service_name,
            "total_spans": len(spans),
            "start_time": root.start_time.isoformat() if root.start_time else None,
            "end_time": root.end_time.isoformat() if root.end_time else None,
            "duration_ms": root.duration_ms,
            "status": root.status,
            "root_span": {
                "name": root.name,
                "span_id": root.span_id,
                "attributes": root.attributes,
            },
        }
    
    def get_trace_timeline(
        self,
        trace_id: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取链路时间线"""
        spans = self._tracer.get_trace(trace_id)
        if not spans:
            return None
        
        return [
            {
                "span_id": s.span_id,
                "parent_span_id": s.parent_span_id,
                "name": s.name,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "duration_ms": s.duration_ms,
                "status": s.status,
                "attributes": s.attributes,
                "events": s.events,
            }
            for s in sorted(spans, key=lambda x: x.start_time or datetime.min)
        ]


# ── Dify 专用链路追踪辅助类 ──────────────────────────────────────────────────


class DifyTraceRecorder:
    """Dify 调用链路追踪辅助器

    用于在 Dify ChatFlow / Workflow 调用前后记录 AgentTrace。
    支持两种场景：
    - 流式调用（stream）：start() → 流式累积 → finish()
    - 同步调用（invoke）：start() → finish(output=...)

    用法：
        recorder = DifyTraceRecorder(...)
        recorder.start()
        try:
            # ... Dify 调用 ...
            recorder.finish(output=answer, conversation_id=conv_id)
        except Exception as e:
            recorder.finish(error=str(e))
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        session_id: Optional[int] = None,
        user_id: Optional[int] = None,
        agent_id: str = "general",
        agent_type: str = "general",
        input_prompt: Optional[str] = None,
        flow_code: Optional[str] = None,
        engine_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self._db = db
        self._session_id = session_id
        self._user_id = user_id
        self._agent_id = agent_id
        self._agent_type = agent_type
        self._input_prompt = input_prompt
        self._flow_code = flow_code
        self._engine_code = engine_code
        self._extra_metadata = metadata or {}
        self._trace_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._owns_db = False  # 是否由本类创建的 DB session（需自行 close）

    def start(self) -> str:
        """记录开始，返回 trace_id"""
        import uuid
        self._trace_id = uuid.uuid4().hex
        self._start_time = datetime.utcnow()
        logger.debug(
            f"[DIFY_TRACE] start: trace_id={self._trace_id}, "
            f"agent_id={self._agent_id}, session_id={self._session_id}"
        )
        return self._trace_id

    def finish(
        self,
        output: Optional[str] = None,
        error: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tool_calls: Optional[list] = None,
        tool_results: Optional[dict] = None,
    ) -> None:
        """记录结束并持久化到数据库"""
        if not self._trace_id or not self._start_time:
            logger.warning("[DIFY_TRACE] finish() called without start()")
            return

        end_time = datetime.utcnow()
        duration_ms = int((end_time - self._start_time).total_seconds() * 1000)
        status = "ERROR" if error else "OK"

        # 构建扩展元数据
        meta = dict(self._extra_metadata)
        if self._flow_code:
            meta["flow_code"] = self._flow_code
        if self._engine_code:
            meta["engine_code"] = self._engine_code
        if conversation_id:
            meta["conversation_id"] = conversation_id
        if message_id:
            meta["message_id"] = message_id
        if tool_calls:
            meta["tool_calls"] = tool_calls
        if tool_results:
            meta["tool_results"] = tool_results

        self._save_to_db(
            output=output,
            error=error,
            status=status,
            start_time=self._start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            metadata=meta,
        )

        logger.debug(
            f"[DIFY_TRACE] finish: trace_id={self._trace_id}, "
            f"status={status}, duration={duration_ms}ms"
        )

    def _save_to_db(
        self,
        output: Optional[str],
        error: Optional[str],
        status: str,
        start_time: datetime,
        end_time: datetime,
        duration_ms: int,
        metadata: Dict[str, Any],
    ) -> None:
        """持久化 AgentTrace 记录到数据库"""
        db = self._db
        if db is None:
            # 无外部传入的 db，创建临时 session
            try:
                from app.db.database import SessionLocal
                db = SessionLocal()
                self._owns_db = True
            except Exception as e:
                logger.warning(f"[DIFY_TRACE] 无法创建 DB session: {e}")
                return

        try:
            from app.models.agent.agent_trace import AgentTrace

            trace_record = AgentTrace(
                trace_id=self._trace_id,
                session_id=self._session_id,
                user_id=self._user_id,
                agent_id=self._agent_id,
                agent_type=self._agent_type,
                input_prompt=self._input_prompt,
                output_result=output,
                error=error,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                extra_metadata=metadata,
            )
            db.add(trace_record)
            db.commit()
            logger.debug(f"[DIFY_TRACE] 已保存: trace_id={self._trace_id}")
        except Exception as e:
            logger.error(f"[DIFY_TRACE] 保存失败: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            if self._owns_db and db is not None:
                try:
                    db.close()
                except Exception:
                    pass


_trace_service_instance: Optional[TraceService] = None


def get_trace_service(db: Optional[Session] = None) -> TraceService:
    """获取 TraceService 单例"""
    global _trace_service_instance
    if _trace_service_instance is None:
        _trace_service_instance = TraceService(db)
    return _trace_service_instance
