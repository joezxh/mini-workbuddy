/*
 * 模式 9 —— Handoff（专家交接）。
 * 对应 Python 版：examples/architecture_patterns/09_handoff.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.UserMessage;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 模式 9 —— Handoff（专家交接：按专长直接转交）。
 *
 * <p><b>适用场景</b>：智能客服转接——请求不在当前专家的职责范围，应当把会话交出去。
 *
 * <p><b>AgentScope Java 中的实现</b>：框架没有内置 Handoff 原语。本示例用
 * <b>结构化输出表达交接信号</b>（Python 版用 externalTool + 事件流，两者等价）：
 *
 * <ol>
 *   <li>每个专家的回复都收束成 {@link HandoffDecision}：{@code answer} 为空
 *       表示"这不是我的活"，同时给出 {@code target} 与自足的 {@code summary}；</li>
 *   <li>驱动循环读到交接信号后<b>切换专家</b>，用摘要作为新专家的第一条消息
 *       ——交接的是摘要，不是整段对话，新专家上下文小、成本可控；</li>
 *   <li>{@code MAX_HOPS} 限制交接次数，防止 A → B → A 死循环。</li>
 * </ol>
 *
 * <p>与模式 8 的关键区别：8 里 leader 始终在场、成员是无状态子调用；9 里控制权
 * <b>真的交出去了</b>，前一个 Agent 从此出局。若需把请求路由到另一个已注册的
 * 服务端 Agent，也可用 {@code GatewayBootstrap + SendOptions.withAgentId(...)}。
 */
public class Pattern09Handoff {

    /** 交接次数上限。 */
    private static final int MAX_HOPS = 4;

    /** 交接决策 Schema：answer 为空表示要转交。 */
    public static class HandoffDecision {
        /** 若这是你的职责，给出对用户的完整回答；否则留空。 */
        public String answer;

        /** 要转交的目标专家名；不转交时留空。 */
        public String target;

        /** 交接摘要：用户要什么 + 目前已知的一切。目标专家只看得到这一段。 */
        public String summary;

        /** 默认构造器（结构化输出反序列化必需）。 */
        public HandoffDecision() {}
    }

    /**
     * 运行 Handoff 演示：前台 → 工程师 → （如需）账务。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 09 - Handoff（专家交接）");

        Map<String, ReActAgent> experts = buildExperts();

        try {
            String answer =
                    runHandoff(
                            experts,
                            "Triage",
                            "我们的 TeamPipeline 里，leader 派活给成员之后一直卡住不动，"
                                    + "日志里也没有报错，这是什么原因？");
            System.out.println();
            System.out.println("===== 用户最终得到的回答 =====");
            System.out.println(answer);
        } finally {
            experts.values().forEach(ReActAgent::close);
        }
    }

    /** 构建专家组：前台、技术支持、账务，各自只管自己的领域。 */
    private static Map<String, ReActAgent> buildExperts() {
        Map<String, ReActAgent> experts = new LinkedHashMap<>();
        experts.put(
                "Triage",
                PatternSupport.agent(
                        "Triage",
                        "你是前台。只回答问候与公司介绍类问题；"
                                + "遇到技术问题或账务问题，一律转交（answer 留空）。"));
        experts.put(
                "TechSupport",
                PatternSupport.agent(
                        "TechSupport",
                        "你是技术支持工程师，负责回答产品使用与故障排查。"
                                + "若问题其实是账务问题，请转交给 Billing。"));
        experts.put(
                "Billing",
                PatternSupport.agent(
                        "Billing", "你是账务专家，只回答退款、发票与价格问题。"));
        return experts;
    }

    /**
     * 驱动循环：跑当前专家 → 读到交接信号则切换 → 直到有人直接回答。
     *
     * @param experts 专家表，键为专家名
     * @param entry 首个接待用户的专家名
     * @param userRequest 用户原始请求
     * @return 最终回答文本
     */
    private static String runHandoff(
            Map<String, ReActAgent> experts, String entry, String userRequest) {
        String current = entry;
        // 首条消息 = 用户原始请求；后续 = 交接摘要
        String input = userRequest;

        for (int hop = 0; hop < MAX_HOPS; hop++) {
            ReActAgent agent = experts.get(current);
            System.out.println();
            System.out.println("----- 第 " + hop + " 跳：" + current + " -----");

            Msg reply = agent.call(new UserMessage(input), HandoffDecision.class).block();
            if (reply == null || !reply.hasStructuredData()) {
                return "（" + current + " 未给出有效回复）";
            }
            HandoffDecision decision = reply.getStructuredData(HandoffDecision.class);

            // 有答案：交接结束
            if (decision.answer != null && !decision.answer.isBlank()) {
                System.out.println("[" + current + "] " + decision.answer);
                return decision.answer;
            }

            // 无答案：转交
            if (decision.target == null || !experts.containsKey(decision.target)) {
                return "（" + current + " 想转交给未知专家 " + decision.target + "）";
            }
            System.out.println(">>> " + current + " --转交--> " + decision.target);
            System.out.println("    摘要：" + decision.summary);

            // 新专家只拿到摘要 + 原始请求，上下文从小开始
            input =
                    "交接摘要（来自 " + current + "）：\n" + decision.summary
                            + "\n\n用户原始请求：" + userRequest
                            + "\n请直接处理该请求。";
            current = decision.target;
        }
        return "（交接次数达到上限，未得到回答）";
    }
}
