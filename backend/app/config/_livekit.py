"""LiveKit 视频会议配置（自建 SFU，见 docs/LIVEKIT_SELF_HOSTED_DEPLOYMENT_GUIDE.md）"""
from pydantic import BaseModel


class LiveKitSettings(BaseModel):
    """LiveKit 自建服务接入参数

    API_KEY/API_SECRET 必须与 docker/livekit/livekit.yaml 的 keys 保持一致；
    WS_URL 下发给前端（livekit-client 连接地址），HTTP_URL 供服务端 API/webhook。
    """
    LIVEKIT_HTTP_URL: str = "http://localhost:7880"
    LIVEKIT_WS_URL: str = "ws://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"
    # 入会 token 有效期（秒）。入会后连接不受影响，短 TTL 降低泄露风险
    LIVEKIT_TOKEN_TTL_SECONDS: int = 600
