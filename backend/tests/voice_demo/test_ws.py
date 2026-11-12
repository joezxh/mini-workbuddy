"""WS 桥接测试 — spec §3.3（query JWT 鉴权）。"""
import pytest

from tests.voice_demo.test_health import make_client


def test_ws_bad_token_closed_1008():
    with pytest.raises(Exception):  # TestClient 对 accept 前 close 抛 WebSocketDisconnect
        with make_client().websocket_connect("/api/v1/voice-demo/ws?token=bad") as ws:
            ws.receive_json()


# 真实桥接泵（run_bridge）需在线 s2s 上游，不在单测覆盖范围（联调验证）。
