"""AI System Module - AgentScope 2.0.4 原生化架构。

核心子系统:
- agents: 业务 Agent 定义 + SubAgentTemplate
- middleware: GraphitiMiddleware / ConfigTraceMiddleware / SkillMetricsMiddleware
- platform: create_platform_app 工厂
- workspace: WorkspaceAdapter (LocalWorkspace 封装)
- skills: SkillManager (委托 WorkspaceAdapter)
- knowledge: 知识库服务
- simulation: 仿真引擎
"""
__version__ = "2.0.0"
__author__ = "AI Architect Team"
