/*
 * 模式 1 —— ReAct（边想边做）。
 * 对应 Python 版：examples/architecture_patterns/01_react.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.UserMessage;
import io.agentscope.core.tool.Tool;
import io.agentscope.core.tool.ToolParam;
import io.agentscope.core.tool.Toolkit;

/**
 * 模式 1 —— ReAct（Reasoning + Acting，边想边做）。
 *
 * <p><b>适用场景</b>：搜索问答、通用助手——需要多少步事先不知道，每一步取决于
 * 上一步的结果。
 *
 * <p><b>AgentScope Java 中的实现</b>：{@link ReActAgent} 自带推理-行动循环，
 * 不需要手写"思考 → 调工具 → 看结果"的循环代码。开发者只需要：
 *
 * <ol>
 *   <li>用 {@code @Tool} 注解把普通 Java 方法声明为工具；</li>
 *   <li>通过 {@code Toolkit.registerTool(...)} 注册到工具集；</li>
 *   <li>交给 Agent，模型会自行决定何时调用哪个工具。</li>
 * </ol>
 *
 * <p>本例演示：一个 Agent 同时使用天气与计算器两个工具回答问题，并用
 * {@code streamEvents} 实时打印流式回复与工具调用事件。
 */
public class Pattern01ReAct {

    /** 天气查询工具集（@Tool 注解声明，参数必须加 @ToolParam）。 */
    public static class WeatherTools {

        /**
         * 查询城市天气。
         *
         * @param city 城市名
         * @return 天气描述
         */
        @Tool(name = "get_weather", description = "查询指定城市当前天气")
        public String getWeather(
                @ToolParam(name = "city", description = "城市名，例如：杭州") String city) {
            return switch (city) {
                case "杭州" -> "晴，28°C";
                case "北京" -> "多云，22°C";
                default -> city + "：晴，26°C";
            };
        }
    }

    /** 计算器工具集。 */
    public static class CalculatorTools {

        /**
         * 计算四则运算表达式。
         *
         * @param expression 表达式
         * @return 计算结果
         */
        @Tool(name = "calculate", description = "计算简单四则运算表达式")
        public String calculate(
                @ToolParam(name = "expression", description = "例如：(12 + 8) * 3")
                        String expression) {
            try {
                long result = evaluate(expression);
                return expression + " = " + result;
            } catch (Exception e) {
                return "无法计算表达式：" + expression + "，原因：" + e.getMessage();
            }
        }

        /** 仅支持整数四则运算的最小实现，避免 eval 的安全隐患。 */
        private long evaluate(String expression) {
            String normalized = expression.replaceAll("\\s+", "");
            java.util.Deque<Long> numbers = new java.util.ArrayDeque<>();
            java.util.Deque<Character> ops = new java.util.ArrayDeque<>();
            int i = 0;
            while (i < normalized.length()) {
                char c = normalized.charAt(i);
                if (Character.isDigit(c)) {
                    int j = i;
                    while (j < normalized.length() && Character.isDigit(normalized.charAt(j))) {
                        j++;
                    }
                    numbers.push(Long.parseLong(normalized.substring(i, j)));
                    i = j;
                } else {
                    while (!ops.isEmpty() && precedence(ops.peek()) >= precedence(c)) {
                        apply(numbers, ops.pop());
                    }
                    ops.push(c);
                    i++;
                }
            }
            while (!ops.isEmpty()) {
                apply(numbers, ops.pop());
            }
            return numbers.pop();
        }

        private int precedence(char op) {
            return (op == '+' || op == '-') ? 1 : 2;
        }

        private void apply(java.util.Deque<Long> numbers, char op) {
            long right = numbers.pop();
            long left = numbers.pop();
            numbers.push(
                    switch (op) {
                        case '+' -> left + right;
                        case '-' -> left - right;
                        case '*' -> left * right;
                        case '/' -> left / right;
                        default -> throw new IllegalArgumentException("未知运算符: " + op);
                    });
        }
    }

    /**
     * 运行 ReAct 演示。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 01 - ReAct（边想边做）");

        Toolkit toolkit = new Toolkit();
        toolkit.registerTool(new WeatherTools());
        toolkit.registerTool(new CalculatorTools());

        try (ReActAgent agent =
                PatternSupport.agent(
                        "Friday",
                        "你是一个乐于助人的助手。能用工具查到的信息不要靠猜。",
                        toolkit,
                        10)) {

            Msg userMsg =
                    new UserMessage("杭州和北京今天谁更热？温差是多少摄氏度？顺便算一下 (12 + 8) * 3。");

            Msg reply = PatternSupport.printStreamed(agent.streamEvents(userMsg));
            System.out.println("\n===== 最终回答 =====");
            System.out.println(reply == null ? "（无回复）" : reply.getTextContent());
        }
    }
}
