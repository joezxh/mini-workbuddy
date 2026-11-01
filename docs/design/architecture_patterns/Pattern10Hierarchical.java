/*
 * 模式 10 —— Hierarchical（层级团队）。
 * 对应 Python 版：examples/architecture_patterns/10_hierarchical.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.tool.Toolkit;
import io.agentscope.core.tool.subagent.SubAgentConfig;
import io.agentscope.core.tool.subagent.SubAgentProvider;
import io.agentscope.core.tool.subagent.SubAgentTool;

/**
 * 模式 10 —— Hierarchical（层级团队：多层主管逐级分工）。
 *
 * <p><b>适用场景</b>：复杂项目——工作先按领域切、再按任务切。一个 leader 面对
 * 12 个成员会"选不动"；分两层后，每层 leader 只需在 2-4 个选项里挑。
 *
 * <p><b>AgentScope Java 中的实现</b>：仍然是「成员即工具」，只是嵌套两层——
 * director 的工具是两个<b>子团队 leader</b>（SubAgentTool），而子 leader 自己的
 * 工具集里又挂着各自的成员（SubAgentTool）。每一层的派活语义与模式 8 完全相同：
 * 成员在独立上下文里跑，只有最终回复上交。
 *
 * <p>注意：子 Agent 是"叶子"——声明式子智能体（HarnessAgent 的 SubagentDeclaration）
 * 明确禁止子 agent 再派生；用 core 层 SubAgentTool 手工嵌套时同样建议保持
 * 每层工具数 ≤ 4，层数 ≤ 3，否则调试与成本都会失控。
 */
public class Pattern10Hierarchical {

    private static final String TASK =
            "交付一份《AgentScope TeamPipeline 实战指南》："
                    + "research 团队负责核实 TeamPipeline 的三条关键语义"
                    + "（派活方式、成员上下文隔离、并发规则）；"
                    + "engineering 团队负责写一个最小可运行示例；"
                    + "最后由你汇总成一份中文指南，直接输出在回复里。";

    /**
     * 运行 Hierarchical 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 10 - Hierarchical（层级团队）");

        try (ReActAgent director =
                PatternSupport.agent(
                        "Director",
                        "你是总监，手下有 research 与 engineering 两个团队。"
                                + "用 ask_research_lead / ask_eng_lead 派活，给每个团队长的"
                                + "指令必须完整自足；结果回来后由你亲自汇总写出最终交付物。",
                        directorToolkit(),
                        10)) {

            Msg reply = PatternSupport.printStreamed(director.streamEvents(TASK));
            System.out.println();
            System.out.println("===== Director 的最终交付 =====");
            System.out.println(reply == null ? "（无回复）" : reply.getTextContent());
        }
    }

    /** Director 的工具集：两个子团队 leader（各自再挂自己的成员）。 */
    private static Toolkit directorToolkit() {
        Toolkit toolkit = new Toolkit();
        toolkit.registerTool(
                new SubAgentTool(
                        researchLeadProvider(),
                        SubAgentConfig.builder()
                                .toolName("ask_research_lead")
                                .description("research 团队：核实事实与关键语义，返回要点清单")
                                .build()));
        toolkit.registerTool(
                new SubAgentTool(
                        engineeringLeadProvider(),
                        SubAgentConfig.builder()
                                .toolName("ask_eng_lead")
                                .description("engineering 团队：写最小可运行示例并说明如何运行")
                                .build()));
        return toolkit;
    }

    /** research 团队 leader：自己再派活给 DocReader 与 Summarizer。 */
    private static SubAgentProvider<ReActAgent> researchLeadProvider() {
        return () -> {
            Toolkit tools = new Toolkit();
            tools.registerTool(
                    new SubAgentTool(
                            () ->
                                    PatternSupport.agent(
                                            "DocReader",
                                            "你负责读代码与文档，只报告事实，每条注明依据。"),
                            SubAgentConfig.builder()
                                    .toolName("ask_doc_reader")
                                    .description("读代码与文档，报告事实")
                                    .build()));
            tools.registerTool(
                    new SubAgentTool(
                            () ->
                                    PatternSupport.agent(
                                            "Summarizer",
                                            "你负责把素材压缩成简短要点，不超过 150 字。"),
                            SubAgentConfig.builder()
                                    .toolName("ask_summarizer")
                                    .description("把素材压缩成简短要点")
                                    .build()));

            return PatternSupport.agent(
                    "ResearchLead",
                    "你是 research 团队负责人。把调研任务拆给 ask_doc_reader 与 "
                            + "ask_summarizer，汇总后给出一份要点清单。",
                    tools,
                    10);
        };
    }

    /** engineering 团队 leader：自己再派活给 Coder 与 Reviewer。 */
    private static SubAgentProvider<ReActAgent> engineeringLeadProvider() {
        return () -> {
            Toolkit tools = new Toolkit();
            tools.registerTool(
                    new SubAgentTool(
                            () ->
                                    PatternSupport.agent(
                                            "Coder",
                                            "你负责写完整、可直接复制的示例代码。"),
                            SubAgentConfig.builder()
                                    .toolName("ask_coder")
                                    .description("写最小可运行示例代码")
                                    .build()));
            tools.registerTool(
                    new SubAgentTool(
                            () ->
                                    PatternSupport.agent(
                                            "Reviewer",
                                            "你负责评审代码：指出缺陷并给出修正后的代码。"),
                            SubAgentConfig.builder()
                                    .toolName("ask_reviewer")
                                    .description("评审代码并给出修正")
                                    .build()));

            return PatternSupport.agent(
                    "EngLead",
                    "你是 engineering 团队负责人。先让 ask_coder 写示例，"
                            + "再让 ask_reviewer 评审修订，最后汇报代码与运行方式。",
                    tools,
                    10);
        };
    }
}
