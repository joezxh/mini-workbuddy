/*
 * 10 种主流 Agent 设计模式 —— AgentScope Java 版共享脚手架。
 * 供 Pattern01ReAct ~ Pattern10Hierarchical 复用，统一模型、
 * Agent 构建与事件流打印方式，保证各范例代码只展示模式本身。
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.event.AgentEvent;
import io.agentscope.core.event.AgentResultEvent;
import io.agentscope.core.event.TextBlockDeltaEvent;
import io.agentscope.core.event.ToolCallStartEvent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.tool.Toolkit;
import java.util.concurrent.atomic.AtomicReference;
import reactor.core.publisher.Flux;

/**
 * 共享脚手架：模型工厂、Agent 工厂与事件流打印。
 *
 * <p>模型默认走 DashScope（读取环境变量 {@code DASHSCOPE_API_KEY}）。若要切换到
 * OpenAI 兼容端点（自建网关 / vLLM / GPUStack 等），有两种等价写法：
 *
 * <pre>{@code
 * // 1) 字符串形式：自动读取 OPENAI_API_KEY / OPENAI_BASE_URL 环境变量
 * .model("openai:qwen3-32b")
 *
 * // 2) 显式指定 base_url（例如 DashScope 兼容模式）
 * ModelCreationContext ctx = ModelCreationContext.builder()
 *         .apiKey(System.getenv("DASHSCOPE_API_KEY"))
 *         .baseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1")
 *         .build();
 * Model model = ModelRegistry.resolve("openai:qwen3.8-max", ctx);
 * }</pre>
 */
public final class PatternSupport {

    /** 默认模型 ID，格式为 "provider:model"，由 ModelRegistry 解析。 */
    public static final String MODEL_ID = "dashscope:qwen-plus";

    /** 默认推理-行动迭代上限，示例刻意调小以便快速跑完。 */
    public static final int DEFAULT_MAX_ITERS = 10;

    private PatternSupport() {
        // 工具类，禁止实例化
    }

    /** 运行前校验模型密钥环境变量，缺失时直接退出。 */
    public static void checkApiKey() {
        String dashscope = System.getenv("DASHSCOPE_API_KEY");
        String openai = System.getenv("OPENAI_API_KEY");
        if ((dashscope == null || dashscope.isBlank())
                && (openai == null || openai.isBlank())) {
            System.err.println("请先设置 DASHSCOPE_API_KEY（或 OPENAI_API_KEY + OPENAI_BASE_URL）");
            System.exit(1);
        }
    }

    /**
     * 构建一个最简 Agent。
     *
     * @param name 智能体名称（也是其他智能体引用它的名字）
     * @param sysPrompt 系统提示词，说明该智能体的职责
     * @return 已构建的 ReActAgent
     */
    public static ReActAgent agent(String name, String sysPrompt) {
        return agent(name, sysPrompt, new Toolkit(), DEFAULT_MAX_ITERS);
    }

    /**
     * 构建一个带工具集的 Agent。
     *
     * @param name 智能体名称
     * @param sysPrompt 系统提示词
     * @param toolkit 工具集；工具通过 {@code toolkit.registerTool(...)} 注册
     * @param maxIters 单次回复的推理-行动迭代上限
     * @return 已构建的 ReActAgent
     */
    public static ReActAgent agent(String name, String sysPrompt, Toolkit toolkit, int maxIters) {
        return ReActAgent.builder()
                .name(name)
                .sysPrompt(sysPrompt)
                .model(MODEL_ID)
                .toolkit(toolkit)
                .maxIters(maxIters)
                .build();
    }

    /**
     * 消费事件流并实时打印文本增量与工具调用，返回最终回复消息。
     *
     * <p>AgentScope Java 的事件流是 Project Reactor 的 {@code Flux<AgentEvent>}，
     * 同一套事件既能驱动终端打印，也能推给前端渲染。
     *
     * @param stream 由 {@code agent.streamEvents(...)} 得到的事件流
     * @return 最终回复消息（来自 AgentResultEvent）
     */
    public static Msg printStreamed(Flux<AgentEvent> stream) {
        AtomicReference<Msg> result = new AtomicReference<>();
        stream.doOnNext(
                        event -> {
                            if (event instanceof TextBlockDeltaEvent delta) {
                                System.out.print(delta.getDelta());
                            } else if (event instanceof ToolCallStartEvent call) {
                                System.out.printf("%n  [tool] %s%n", call.getToolCallName());
                            } else if (event instanceof AgentResultEvent finished) {
                                result.set(finished.getResult());
                            }
                        })
                .blockLast();
        System.out.println();
        return result.get();
    }

    /** 打印章节横幅，便于终端阅读。 */
    public static void banner(String title) {
        System.out.println();
        System.out.println("=".repeat(60));
        System.out.println(title);
        System.out.println("=".repeat(60));
    }
}
