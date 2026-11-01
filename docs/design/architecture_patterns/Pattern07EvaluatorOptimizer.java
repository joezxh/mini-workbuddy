/*
 * 模式 7 —— Evaluator-Optimizer（生成 + 评审）。
 * 对应 Python 版：examples/architecture_patterns/07_evaluator_optimizer.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.tool.Tool;
import io.agentscope.core.tool.ToolParam;
import io.agentscope.core.tool.Toolkit;

/**
 * 模式 7 —— Evaluator-Optimizer（一个生成，一个评审）。
 *
 * <p><b>适用场景</b>：翻译提质、代码必须跑通、文案达标——需要客观判据来保证质量。
 *
 * <p><b>AgentScope Java 中的实现</b>：Java 版 2.x 尚无 Python 版的
 * {@code GoalPipeline} 内置实现，因此用最小驱动循环：
 *
 * <ol>
 *   <li>executor 朝目标工作并产出成果报告；</li>
 *   <li>verifier 用<b>结构化输出</b>判定 pass / fail / impossible；</li>
 *   <li>fail 时把评审意见回喂 executor 重试，最多 {@code MAX_ITERS} 轮。</li>
 * </ol>
 *
 * <p>与模式 3（Reflection）的区别：评审是<b>独立 Agent</b>，看不到 executor 的
 * 推理过程，只评审成果；且本例给 verifier 配了同样的计算器工具，让它能
 * <b>自己验算</b>，而不是凭报告想象——评审者能拿到真实判据，是这个模式可靠的关键。
 */
public class Pattern07EvaluatorOptimizer {

    /** 最多重试轮数。 */
    private static final int MAX_ITERS = 3;

    /** 目标：executor 必须给出可被独立验算的准确计算结果。 */
    private static final String GOAL =
            "用工具准确计算 (2 的 30 次方) × 3 + 17，并在最终回答里给出完整计算过程与准确数值。";

    /** 评审结论 Schema。 */
    public static class Verdict {
        /** 判定结果：pass / fail / impossible。 */
        public String result;

        /** fail 时说明哪里错、怎么改；pass 时为空。 */
        public String message;

        /** 默认构造器（结构化输出反序列化必需）。 */
        public Verdict() {}
    }

    /** 计算器工具集：executor 与 verifier 共用，保证判据一致。 */
    public static class CalculatorTools {

        /**
         * 计算整数幂。
         *
         * @param base 底数
         * @param exponent 指数
         * @return base^exponent
         */
        @Tool(name = "power", description = "计算 base 的 exponent 次幂")
        public long power(
                @ToolParam(name = "base", description = "底数") long base,
                @ToolParam(name = "exponent", description = "指数") long exponent) {
            return (long) Math.pow(base, exponent);
        }

        /**
         * 计算两数之和。
         *
         * @param a 加数
         * @param b 被加数
         * @return a + b
         */
        @Tool(name = "add", description = "计算两个整数之和")
        public long add(
                @ToolParam(name = "a", description = "加数") long a,
                @ToolParam(name = "b", description = "被加数") long b) {
            return a + b;
        }

        /**
         * 计算两数之积。
         *
         * @param a 乘数
         * @param b 被乘数
         * @return a * b
         */
        @Tool(name = "multiply", description = "计算两个整数之积")
        public long multiply(
                @ToolParam(name = "a", description = "乘数") long a,
                @ToolParam(name = "b", description = "被乘数") long b) {
            return a * b;
        }
    }

    /**
     * 运行 Evaluator-Optimizer 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 07 - Evaluator-Optimizer（生成 + 评审）");

        Toolkit sharedTools = new Toolkit();
        sharedTools.registerTool(new CalculatorTools());

        try (ReActAgent executor =
                        PatternSupport.agent(
                                "Executor",
                                "你是程序员。用工具完成目标，"
                                        + "在最终回答里给出完整计算过程与成果报告。",
                                sharedTools.copy(),
                                20);
                ReActAgent verifier =
                        PatternSupport.agent(
                                "Verifier",
                                "你是严格的评审。不要轻信报告，先自己用工具验算，"
                                        + "只有完全达标才给 pass，否则说清哪里错、该怎么改。",
                                sharedTools.copy(),
                                20)) {

            // 第一轮：executor 先做
            System.out.println("----- Executor 工作 -----");
            Msg reportMsg = executor.call(GOAL).block();
            String report = reportMsg == null ? "" : reportMsg.getTextContent();
            System.out.println(report);

            // 评审-修订循环
            for (int round = 1; round <= MAX_ITERS; round++) {
                System.out.println();
                System.out.println("----- Verifier 第 " + round + " 轮判定 -----");

                String prompt =
                        "目标：" + GOAL + "\n\nExecutor 的成果报告如下：\n" + report
                                + "\n\n请判定：pass / fail / impossible。";
                Msg verdictMsg = verifier.call(prompt, Verdict.class).block();

                if (verdictMsg == null || !verdictMsg.hasStructuredData()) {
                    System.out.println("未得到有效判定，提前结束。");
                    break;
                }
                Verdict verdict = verdictMsg.getStructuredData(Verdict.class);
                System.out.println("result=" + verdict.result);
                if (verdict.message != null && !verdict.message.isBlank()) {
                    System.out.println("message=" + verdict.message);
                }

                if ("pass".equals(verdict.result) || "impossible".equals(verdict.result)) {
                    System.out.println();
                    System.out.println("===== 最终报告（已通过评审） =====");
                    System.out.println(report);
                    return;
                }

                System.out.println();
                System.out.println("----- Executor 按意见修订 -----");
                Msg revised =
                        executor
                                .call(
                                        "你没有通过评审，原因是：" + verdict.message
                                                + "\n请修正后重新给出成果报告。")
                                .block();
                report = revised == null ? report : revised.getTextContent();
                System.out.println(report);
            }

            System.out.println();
            System.out.println("===== 达到重试上限，未通过评审，如实上报 =====");
            System.out.println(report);
        }
    }
}
