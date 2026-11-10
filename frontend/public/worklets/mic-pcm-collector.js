/**
 * 麦克风 PCM 采集 worklet（语音演示 S2S 上行通道）：
 * 每个渲染量子把单声道 Float32 块原样 postMessage 给主线程，
 * 由 useRealtimeS2s 做流式重采样（→16k）+ PCM16 编码 + base64 append。
 */
class MicPcmCollector extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0]
    if (input && input[0] && input[0].length) {
      this.port.postMessage(new Float32Array(input[0]))
    }
    return true
  }
}
registerProcessor('mic-pcm-collector', MicPcmCollector)
