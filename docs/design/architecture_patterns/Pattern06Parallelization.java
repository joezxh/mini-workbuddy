/*
 * 模式 6 —— Parallelization（并行分身）。
 * 对应 Python 版：examples/architecture_patterns/06_parallelization.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.UserMessage;
import io.agentscope.core.tool.Toolkit;
import io.agentscope.core.tool.ToolkitConfig;
import io.agentscope.core.tool.Tool;
import io.agentscope.core.tool.ToolParam;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

/**
 * 模式 6 —— Parallelization（并行分身：拆分并行或多次投票）。
 *
 * <p><b>适用场景</b>：批量处理、多方评审、用多次采样对抗单次抽风。
 *
 * <p><b>AgentScope Java 中的实现</b>：框架基于 Project Reactor（Mono/Flux），
 * 并行就是自然的响应式组合：
 *
 * <ul>
 *   <li><b>扇出 + 聚合</b>：{@code Flux.fromIterable(agents).flatMap(a -> a.call(...))}
 *       ——flatMap 对每个内部 Mono 立即订阅，天然并发；</li>
 *   <li><b>多次采样投票</b>：同一问题让 N 个独立实例各答一次，取多数；</li>
 *   <li><b>同一 Agent 内并发工具调用</b>：{@code ToolkitConfig.builder().parallel(true)}
 *       （默认开启）让模型一轮发出的多个工具调用并行执行。</li>
 * </ul>
 *
 * <p>⚠️ 硬性约束：一个 {@link ReActAgent} 实例就是一段对话（状态里存着上下文），
 * 并行分支必须各自持有独立实例，绝不能对同一个实例并发调用。
 */
public class Pattern06Parallelization {

    private static final String REVIEW_TARGET =
            "AgentScope 的 TeamPipeline 让 leader 通过 TeamAssign 工具给成员派活，"
                    + "成员在各自上下文里执行，结果只回给 leader。";

    private static final String QUESTION =
            "一段文本有 3 个段落，每段 120 字，用中文写。总分多少字？"
                    + "选项：A. 240  B. 360  C. 480";

    /** 投票结果 Schema。 */
    public static class Vote {
        /** 选中的选项：A / B / C。 */
        public String answer;

        /** 一句话理由。 */
        public String reason;

        /** 默认构造器（结构化输出反序列化必需）。 */
        public Vote() {}
    }

    /** 演示并发工具调用的工具集（两个 @Tool 默认 concurrencySafe=true）。 */
    public static class CityTools {

        /**
         * 查询城市天气。
         *
         * @param city 城市名
         * @return 天气描述
         */
        @Tool(name = "get_weather", description = "查询指定城市当前天气")
        public String getWeather(
                @ToolParam(name = "city", description = "城市名") String city) {
            return switch (city) {
                case "杭州" -> "晴，28°C";
                case "北京" -> "多云，22°C";
                default -> city + "：晴，26°C";
            };
        }

        /**
         * 查询城市人口。
         *
         * @param city 城市名
         * @return 人口描述
         */
        @Tool(name = "get_population", description = "查询指定城市常住人口")
        public String getPopulation(
                @ToolParam(name = "city", description = "城市名") String city) {
            return switch (city) {
                case "杭州" -> "约 1250 万";
                case "北京" -> "约 2180 万";
                default -> "未知";
            };
        }
    }

    /**
     * 运行 Parallelization 演示：扇出评审 → 投票 → 并发工具调用。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 06 - Parallelization（并行分身）");

        fanOutAndAggregate();
        voting();
        concurrentToolCalls();
    }

    /** 玩法一：三个评审并行处理同一输入，聚合者合并结论。 */
    private static void fanOutAndAggregate() {
        System.out.println();
        System.out.println("----- 1. 扇出 / 聚合 -----");

        List<ReActAgent> reviewers =
                List.of(
                        PatternSupport.agent(
                                "ReviewerAccuracy", "你只从准确性角度评审，最多三条要点。"),
                        PatternSupport.agent(
                                "ReviewerClarity", "你只从表达清晰度角度评审，最多三条要点。"),
                        PatternSupport.agent(
                                "ReviewerConcise", "你只从简洁性角度评审，最多三条要点。"));

        // flatMap 对每个内部 Mono 立即订阅 → 三个评审并发执行
        List<Msg> results =
                Flux.fromIterable(reviewers)
                        .flatMap(agent -> agent.call(REVIEW_TARGET))
                        .collectList()
                        .block();

        StringBuilder merged = new StringBuilder();
        for (int i = 0; i < reviewers.size() && results != null; i++) {
            String text = results.get(i).getTextContent();
            System.out.println();
            System.out.println("[" + reviewers.get(i).getName() + "]");
            System.out.println(text);
            merged.append("[").append(reviewers.get(i).getName()).append("] ")
                    .append(text).append("\n\n");
        }

        try (ReActAgent aggregator =
                PatternSupport.agent(
                        "Aggregator", "把收到的多条评审合并成一段简短结论。")) {
            Msg verdict = aggregator.call("合并这些评审：\n" + merged).block();
            System.out.println();
            System.out.println("[合并结论]");
            System.out.println(verdict == null ? "（无回复）" : verdict.getTextContent());
        }
    }

    /** 玩法二：同一问题多次采样，取多数答案。 */
    private static void voting() {
        System.out.println();
        System.out.println("----- 2. 多次采样投票 -----");

        List<ReActAgent> voters =
                List.of(
                        PatternSupport.agent("Voter1", "直接回答选择题。"),
                        PatternSupport.agent("Voter2", "直接回答选择题。"),
                        PatternSupport.agent("Voter3", "直接回答选择题。"));

        List<Msg> voteMsgs =
                Flux.fromIterable(voters)
                        .flatMap(agent -> agent.call(QUESTION, Vote.class))
                        .collectList()
                        .block();

        Map<String, Integer> counter = new LinkedHashMap<>();
        if (voteMsgs != null) {
            for (int i = 0; i < voteMsgs.size(); i++) {
                Msg msg = voteMsgs.get(i);
                if (msg == null || !msg.hasStructuredData()) {
                    System.out.println(voters.get(i).getName() + ": （未给出有效投票）");
                    continue;
                }
                Vote vote = msg.getStructuredData(Vote.class);
                System.out.println(voters.get(i).getName() + ": " + vote.answer
                        + " (" + vote.reason + ")");
                counter.merge(vote.answer, 1, Integer::sum);
            }
        }
        String winner = null;
        int max = 0;
        for (Map.Entry<String, Integer> entry : counter.entrySet()) {
            if (entry.getValue() > max) {
                max = entry.getValue();
                winner = entry.getKey();
            }
        }
        System.out.println();
        System.out.println("多数答案：" + winner + "（" + max + "/" + counter.values().stream()
                .mapToInt(Integer::intValue).sum() + " 票）");
    }

    /** 玩法三：一个 Agent 一轮内并发调用多个工具（ToolkitConfig.parallel=true 默认开启）。 */
    private static void concurrentToolCalls() {
        System.out.println();
        System.out.println("----- 3. 同一 Agent 内并发工具调用 -----");

        // parallel(true) 为默认值，这里显式写出以便对照学习
        Toolkit toolkit =
                new Toolkit(ToolkitConfig.builder().parallel(true).build());
        toolkit.registerTool(new CityTools());

        try (ReActAgent researcher =
                PatternSupport.agent(
                        "Researcher",
                        "用工具回答。需要两条信息时，在同一轮把两个工具一起调用，"
                                + "不要一个接一个。",
                        toolkit,
                        8)) {

            Msg reply =
                    researcher
                            .call("杭州和北京今天的天气与常住人口分别是多少？")
                            .block();
            System.out.println(reply == null ? "（无回复）" : reply.getTextContent());
        }
    }
}
