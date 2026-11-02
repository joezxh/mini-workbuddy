# 一次性冒烟脚本：验证 LiveKit RTC 信令 WebSocket 可连通（用后删除）
import asyncio
import json

import websockets

URL = (
    "ws://localhost:7880/rtc?version=15&room=smoke-test-01&ufm=subscribe&access_token="
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoiXHU4ZDg1XHU3ZWE3XHU3YmExXHU3"
    "NDA2XHU1NDU4IiwidmlkZW8iOnsicm9vbUpvaW4iOnRydWUsInJvb20iOiJzbW9rZS10ZXN0LTAxI"
    "iwiY2FuUHVibGlzaCI6dHJ1ZSwiY2FuU3Vic2NyaWJlIjp0cnVlLCJjYW5QdWJsaXNoRGF0YSI6dH"
    "J1ZSwiY2FuVXBkYXRlT3duTWV0YWRhdGEiOnRydWV9LCJzdWIiOiI5OTk5IiwiaXNzIjoiZGV2a2V"
    "5IiwibmJmIjoxNzkzNTQxMTA2LCJleHAiOjE3OTM1NDE3MDZ9.QR0Rqt6bWaOshlFn_laPhRO5NGZ"
    "AwINDlkcHcDxObMU"
)


async def main():
    async with websockets.connect(URL, max_size=None) as ws:
        # 发送 JoinSession 请求（StartSession 之前的 handshake 首条消息可不发，
        # 先等 server 的 offer/answer 或任何响应，证明连接与鉴权被接受）
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            print("RECV bytes:", len(raw))
        except asyncio.TimeoutError:
            print("RECV timeout（连接已建立但 server 未主动推送，可接受）")
        print("WS_CONNECT_OK")


asyncio.run(main())
