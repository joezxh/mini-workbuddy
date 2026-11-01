/*
 * 模式 3 —— Reflection（自我反思）。
 * 对应 Python 版：examples/architecture_patterns/03_reflection.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.UserMessage;
import java.util.List;

/**
 * 模式 3 —— Reflection（自我反思）。
 *
 * <p><b>适用场景</b>：写代码、改稿——一次成稿不够好，但多迭代几轮能明显变好。
 *
 * <p><b>AgentScope Java 中的实现</b>：同一个 {@link ReActAgent} 先产出草稿，再通过
 * <b>结构化输出</b>（{@code call(msg, Review.class)} → {@code msg.getStructuredData(...)}）
 * 让它给自己的草稿打分挑毛病，然后把意见回喂给它修订。因为评审与写作共享同一个
 * Agent 的会话上下文，这才是"自我反思"；若把评审换成另一个 Agent，就是模式 7。
 *
 * <p>结构化输出的 Schema 是普通 POJO：公开字段 + 默认构造器。
 */
public class Pattern03Reflection {

    /** 单轮反思的最大轮数，示例刻意调小。 */
    private static final int MAX_ROUNDS = 3;

    /** 结构化评审结果 Schema。 */
    public static class Review {
        /** 草稿是否足够好，可以直接交付。 */
        public boolean passed;

        /** 当前草稿得分（1-10）。 */
        public int score;

        /** 具体、可执行的修改意见；通过时应为空。 */
        public List<String> issues;

        /** 默认构造器（结构化输出反序列化必需）。 */
        public Review() {}
    }

    /**
     * 运行 Reflection 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 03 - Reflection（自我反思）");

        try (ReActAgent writer =
                PatternSupport.agent(
                        "Writer",
                        "你是一名技术作者。你写完后要诚实地审自己的稿："
                                + "说出问题在哪，不要自我吹捧。")) {

            String task =
                    "为 AgentScope 的 TeamPipeline 写一段 80 字以内的发布说明，"
                            + "面向开发者，突出「leader 通过工具派活、成员结果只回给 leader」。";

            // 第一步：初稿（普通对话式回复）
            System.out.println("===== 第 0 轮：初稿 =====");
            Msg draftMsg = writer.call(task).block();
            String draft = draftMsg == null ? "" : draftMsg.getTextContent();
            System.out.println(draft);

            // 第二步：自评 → 修订，直到通过或达到轮数上限
            for (int round = 1; round <= MAX_ROUNDS; round++) {
                System.out.println();
                System.out.println("===== 第 " + round + " 轮：自评 =====");

                Msg reviewMsg =
                        writer.call(
                                        new UserMessage("请严格评审你刚写的草稿，指出具体问题。"),
                                        Review.class)
                                .block();

                if (reviewMsg == null || !reviewMsg.hasStructuredData()) {
                    System.out.println("未得到有效评审，提前结束。");
                    break;
                }
                Review review = reviewMsg.getStructuredData(Review.class);
                System.out.println("passed=" + review.passed + " score=" + review.score);
                for (String issue : review.issues) {
                    System.out.println("  - " + issue);
                }

                if (review.passed || review.issues == null || review.issues.isEmpty()) {
                    break;
                }

                System.out.println();
                System.out.println("===== 第 " + round + " 轮：修订 =====");
                StringBuilder feedback = new StringBuilder("只针对以下问题修订你的草稿：\n");
                for (String issue : review.issues) {
                    feedback.append("- ").append(issue).append('\n');
                }
                Msg revised = writer.call(new UserMessage(feedback.toString())).block();
                draft = revised == null ? draft : revised.getTextContent();
                System.out.println(draft);
            }

            System.out.println();
            System.out.println("===== 最终定稿 =====");
            System.out.println(draft);
        }
    }
}
