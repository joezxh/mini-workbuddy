/*
 * 模式 5 —— Routing（智能分流）。
 * 对应 Python 版：examples/architecture_patterns/05_routing.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.UserMessage;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 模式 5 —— Routing（智能分流：先分类，再派对应流程）。
 *
 * <p><b>适用场景</b>：客服分流、按难度选模型——不同请求应走不同流程或不同模型。
 *
 * <p><b>AgentScope Java 中的实现</b>：路由 Agent 通过<b>结构化输出</b>选出目标专家
 * （{@code expert} 取值受 Schema 字段说明约束），驱动代码再把请求交给对应专家。
 * 这是"路由工作"的轴。
 *
 * <p>另有一条正交的"路由模型"轴：AgentScope Java 提供
 * {@code JevModelRouterMiddleware}（agentscope-extensions-jev，需 TYPESAFE_API_KEY）
 * 与 {@code OpenAIDecisionsModelRouterMiddleware}（agentscope-extensions-openai-decisions），
 * 在 {@code onAgent} 钩子里按输入分类并临时替换 {@code agent.model}。因需要额外的
 * 分类服务 API Key，本示例不演示，仅在此备注。
 */
public class Pattern05Routing {

    /** 路由决策 Schema：expert 的合法取值靠字段注释与提示词约束。 */
    public static class Route {
        /** 目标专家：billing / tech / general 三选一。 */
        public String expert;

        /** 一句话说明为什么选它。 */
        public String reason;

        /** 默认构造器（结构化输出反序列化必需）。 */
        public Route() {}
    }

    /**
     * 运行 Routing 演示：三条请求 → 路由 → 对应专家回答。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 05 - Routing（智能分流）");

        try (ReActAgent router =
                        PatternSupport.agent(
                                "Router",
                                "你是客服分流员。把请求归类到唯一的专家并一句话说明理由。"
                                        + "expert 只能取：billing（退款/发票/价格）、"
                                        + "tech（报错/接入/配置）、general（其他）。");
                ReActAgent billing =
                        PatternSupport.agent(
                                "Billing", "你是账务专家，只回答退款、发票与价格问题。");
                ReActAgent tech =
                        PatternSupport.agent(
                                "Tech", "你是技术支持工程师，给出能直接执行的命令或配置。");
                ReActAgent general =
                        PatternSupport.agent("General", "你是友好的通用客服。")) {

            Map<String, ReActAgent> experts = new LinkedHashMap<>();
            experts.put("billing", billing);
            experts.put("tech", tech);
            experts.put("general", general);

            String[] requests = {
                "我上个月重复扣费了，怎么退款？",
                "TeamPipeline 里成员之间为什么看不到彼此的对话？",
                "你们的服务覆盖哪些地区？",
            };

            for (String request : requests) {
                System.out.println();
                System.out.println("===== 请求：" + request + " =====");

                // 1) 路由：结构化输出选出专家
                Msg routeMsg =
                        router.call(
                                        new UserMessage(request),
                                        Route.class)
                                .block();
                if (routeMsg == null || !routeMsg.hasStructuredData()) {
                    System.out.println("路由失败，跳过该请求。");
                    continue;
                }
                Route route = routeMsg.getStructuredData(Route.class);
                System.out.println("→ expert=" + route.expert + " (" + route.reason + ")");

                // 2) 派发：交给对应专家
                ReActAgent expert = experts.get(route.expert);
                if (expert == null) {
                    System.out.println("未知专家：" + route.expert);
                    continue;
                }
                Msg reply = expert.call(new UserMessage(request)).block();
                System.out.println("[" + route.expert + "] "
                        + (reply == null ? "（无回复）" : reply.getTextContent()));
            }
        }
    }
}
