"""本地私有化语音管线（M4）。

四 stage 编排：
    Silero VAD（语音端点检测）
      → Paraformer 2pass（流式 ASR）
      → AgentAdapter（生成回复）
      → CosyVoice2（流式 TTS）

设计原则：
- 各 stage **惰性加载**重型依赖（onnxruntime / funasr / cosyvoice），
  未安装时模块仍可 import，仅 `available()` 返回 False。
- `available()` 用于 `LocalProvider.is_configured()` 探测，
  未就绪时上层自动降级到云端 Provider。
"""
