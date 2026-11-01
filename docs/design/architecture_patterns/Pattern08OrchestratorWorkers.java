/*
 * 模式 8 —— Orchestrator-Workers（主管派活）。
 * 对应 Python 版：examples/architecture_patterns/08_orchestrator_workers.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.tool.Toolkit;
import io.agentscope.core.tool.subagent.SubAgentConfig;
import io.agentscope.core.tool.subagent.SubAgentProvider;
import io.agentscope.core.tool.subagent.SubAgentTool;

/**
 * 模式 8 —— Orchestrator-Workers（主管派活：主控动态拆分，再汇总）。
 *
 * <p><b>适用场景</b>：深度研究、大型编码——子任务取决于执行过程中发现的东西。
 *
 * <p><b>AgentScope Java 中的实现</b>：把「成员 Agent」注册为 leader 的工具。核心类是
 * {@code io.agentscope.core.tool.subagent.SubAgentTool}（配合 {@link SubAgentProvider}
 * 与 {@link SubAgentConfig}），语义与 Python 版的 {@code TeamPipeline} 一致：
 *
 * <ul>
 *   <li>每个成员在<b>自己的上下文</b>里跑（provider 每次会话都创建全新实例，
 *       保证线程安全），只有最终回复作为工具结果回到 leader；</li>
 *   <li>成员之间<b>不互通</b>，汇总永远由 leader 完成；</li>
 *   <li>拆什么、派给谁，由 leader 模型<b>运行时自行决定</b>，不是代码写死的。</li>
 * </ul>
 *
 * <p>另有 HarnessAgent 的声明式子智能体（{@code Builder#subagent(SubagentDeclaration)}
 * + {@code agent_spawn} 工具），面向生产、需要 workspace；本示例用 core 层的
 * SubAgentTool，轻量且依赖最少。
 */
public class Pattern08OrchestratorWorkers {

    private static final String TASK =
            "产出一份《AgentScope TeamPipeline 上手指南》："
                    + "先调研 TeamPipeline 的三条关键语义（派活方式、成员上下文隔离、并发规则），"
                    + "再写一个最小可运行示例，"
                    + "最后汇总成一份结构化中文指南，直接输出在回复里。";

    /**
     * 运行 Orchestrator-Workers 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 08 - Orchestrator-Workers（主管派活）");

        // 三个成员 Agent，以工具的形式暴露给 leader
        Toolkit leaderTools = new Toolkit();
        leaderTools.registerTool(
                new SubAgentTool(
                        researcherProvider(),
                        SubAgentConfig.builder()
                                .toolName("ask_researcher")
                                .description("调研事实与概念，返回带来源的要点清单")
                                .build()));
        leaderTools.registerTool(
                new SubAgentTool(
                        coderProvider(),
                        SubAgentConfig.builder()
                                .toolName("ask_coder")
                                .description("写一段可运行的示例代码并解释")
                                .build()));
        leaderTools.registerTool(
                new SubAgentTool(
                        writerProvider(),
                        SubAgentConfig.builder()
                                .toolName("ask_writer")
                                .description("把素材整理成结构化的中文文档")
                                .build()));

        try (ReActAgent leader =
                PatternSupport.agent(
                        "Leader",
                        "你是技术负责人。把需求拆成 2-4 个子任务，逐个用 ask_* 工具派给成员，"
                                + "给成员的指令必须完整自足（成员看不到你的对话）。"
                                + "所有结果回来后，由你亲自汇总写出最终交付物。",
                        leaderTools,
                        15)) {

            Msg reply = PatternSupport.printStreamed(leader.streamEvents(TASK));
            System.out.println();
            System.out.println("===== Leader 的最终交付 =====");
            System.out.println(reply == null ? "（无回复）" : reply.getTextContent());
        }
    }

    /** 研究员 provider：每次工具调用都会创建全新实例（ReActAgent 非线程安全）。 */
    private static SubAgentProvider<ReActAgent> researcherProvider() {
        return () ->
                PatternSupport.agent(
                        "Researcher",
                        "你是研究员。回答要给出事实与来源，控制在 200 字以内。");
    }

    /** 程序员 provider。 */
    private static SubAgentProvider<ReActAgent> coderProvider() {
        return () ->
                PatternSupport.agent(
                        "Coder", "你是程序员。给出完整、可直接复制的示例代码并逐行解释。");
    }

    /** 文档工程师 provider。 */
    private static SubAgentProvider<ReActAgent> writerProvider() {
        return () ->
                PatternSupport.agent(
                        "Writer", "你是技术文档工程师。把素材整理成结构清晰的中文文档。");
    }
}
