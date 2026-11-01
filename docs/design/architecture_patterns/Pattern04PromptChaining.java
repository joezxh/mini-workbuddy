/*
 * 模式 4 —— Prompt Chaining（流水线）。
 * 对应 Python 版：examples/architecture_patterns/04_prompt_chaining.py
 */
package io.agentscope.examples.patterns;

import io.agentscope.core.ReActAgent;
import io.agentscope.core.message.Msg;

/**
 * 模式 4 —— Prompt Chaining（流水线，固定步骤逐个接力）。
 *
 * <p><b>适用场景</b>：写稿 → 翻译 → 审校——步骤固定且事先已知，每步只关心上一步的产物。
 *
 * <p><b>AgentScope Java 中的实现</b>：Java 版 2.x 尚无 Python 版的
 * {@code SOP / SOPStep / SOPEngine} 内置流水线，因此用最朴素也最清晰的写法——
 * 每步一个 Agent，前一步的回复文本作为下一步的输入，依次
 * {@code call(...).block()}。需要异步串联时，把顺序调用换成
 * {@code Mono.flatMap} 即可，语义不变。
 *
 * <p>与 Python 版的关键差异：Python 版每步只收到 {@code <handover>} 摘要块、
 * 天然限制上下文；Java 版此处直接传递全文，若要控制上下文可在中间做摘要。
 */
public class Pattern04PromptChaining {

    /** 用户原始需求（贯穿整条流水线）。 */
    private static final String BRIEF =
            "为「AgentScope 的 TeamPipeline」写一段产品简介，"
                    + "强调 leader 通过工具派活、成员并发执行、结果只回给 leader。";

    /**
     * 运行 Prompt Chaining 演示：写稿 → 翻译 → 审校。
     *
     * @param args 命令行参数（忽略）
     */
    public static void main(String[] args) {
        PatternSupport.checkApiKey();
        PatternSupport.banner("Pattern 04 - Prompt Chaining（流水线）");

        try (ReActAgent writer =
                        PatternSupport.agent(
                                "Writer", "你是中文产品文案作者，写简短有力的中文产品简介。");
                ReActAgent translator =
                        PatternSupport.agent(
                                "Translator",
                                "你是译者。把交给你的中文翻译成地道的英文，不增不减。");
                ReActAgent proofreader =
                        PatternSupport.agent(
                                "Proofreader",
                                "你是审校编辑。润色交给你的英文稿：修正语法与语感，不改变含义。")) {

            // Step 1：写中文初稿
            System.out.println("----- Step 1: 写中文初稿 -----");
            Msg draftMsg = writer.call(BRIEF).block();
            String draft = draftMsg == null ? "" : draftMsg.getTextContent();
            System.out.println(draft);

            // Step 2：译成英文（上一步的产物作为本步的输入）
            System.out.println();
            System.out.println("----- Step 2: 译成英文 -----");
            Msg englishMsg = translator.call("把下面的中文翻译成英文：\n" + draft).block();
            String english = englishMsg == null ? "" : englishMsg.getTextContent();
            System.out.println(english);

            // Step 3：英文审校
            System.out.println();
            System.out.println("----- Step 3: 英文审校 -----");
            Msg polishedMsg = proofreader.call("审校并润色下面的英文：\n" + english).block();
            String polished = polishedMsg == null ? "" : polishedMsg.getTextContent();
            System.out.println(polished);

            System.out.println();
            System.out.println("===== 最终交付（流水线末步输出） =====");
            System.out.println(polished);
        }
    }
}
