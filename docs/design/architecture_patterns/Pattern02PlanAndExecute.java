/*
 * 模式 2 —— Plan-and-Execute（先谋后动）。
 * 对应 Python 版：examples/architecture_patterns/02_plan_and_execute.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;

/**
 * 模式 2 —— Plan-and-Execute（先谋后动）。
 *
 * <p><b>适用场景</b>：多步骤长任务——模型容易"干着干着忘了最初要做什么"。
 *
 * <p><b>AgentScope Java 中的实现</b>：把计划放进智能体的状态，而不是写死在提示词里。
 * 通过 {@code ReActAgent.Builder#enableTaskList(true)} 开启内置任务清单后，框架会：
 *
 * <ol>
 *   <li>注册内置工具 {@code todo_write}，让模型自己创建并维护任务列表；</li>
 *   <li>注册 {@code TaskReminderMiddleware}，在每一轮推理前把当前任务清单
 *       重新注入上下文——模型随时能看到自己承诺过什么。</li>
 * </ol>
 *
 * <p>本例演示：Agent 先列计划（创建任务），再逐节完成一份上手清单。
 */
public class Pattern02PlanAndExecute {

    private static final String GOAL =
            "交付一份《AgentScope Java 上手清单》，包含三个小节："
                    + "① 环境准备（JDK/Maven/依赖）；"
                    + "② 第一个 Agent（最小可运行代码）；"
                    + "③ 常见坑（至少 2 条）。"
                    + "先用任务清单列计划，再逐节完成，每完成一节更新任务状态。";

    /**
     * 运行 Plan-and-Execute 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 02 - Plan-and-Execute（先谋后动）");

        try (ReActAgent agent =
                ReActAgent.builder()
                        .name("Planner")
                        .sysPrompt(
                                "你是项目负责人，既做规划也亲自执行。"
                                        + "开工前先用 todo_write 把任务拆成清单，"
                                        + "然后一次处理一项，完成后立即更新状态，"
                                        + "需要回顾计划时再读清单。")
                        .model(PatternSupport.MODEL_ID)
                        .toolkit(new io.agentscope.core.tool.Toolkit())
                        // 关键开关：注册内置 todo_write 工具 + 每轮任务提醒中间件
                        .enableTaskList(true)
                        .maxIters(30)
                        .build()) {

            Msg reply = PatternSupport.printStreamed(agent.streamEvents(GOAL));
            System.out.println("\n===== 最终交付 =====");
            System.out.println(reply == null ? "（无回复）" : reply.getTextContent());
        }
    }
}
