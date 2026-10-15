"""临时：探测 lm-studio 嵌入端点实际返回维度。"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:1234/v1/embeddings"


def post(payload: dict) -> dict:
    req = urllib.request.Request(
        BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"  HTTP {exc.code} body={body[:400]}")
        raise


for model in ("text-embedding-embeddinggemma-2", "text-embedding-nomic-embed-text-v1.5"):
    print("model =", model)
    for extra in ({}, {"dimensions": 768}, {"dimensions": 2048}):
        try:
            payload = {"model": model, "input": "维度探测"}
            payload.update(extra)
            data = post(payload)["data"]
            print(f"  req={extra} -> dims={[len(d['embedding']) for d in data]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  req={extra} -> ERR {type(exc).__name__}: {exc}")

# 列出服务端可用的嵌入模型
try:
    with urllib.request.urlopen("http://127.0.0.1:1234/v1/models", timeout=30) as resp:
        models = json.loads(resp.read().decode("utf-8")).get("data", [])
    print("models =", [m.get("id") for m in models])
except Exception as exc:  # noqa: BLE001
    print("models ERR", exc)
