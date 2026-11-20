# -*- coding: utf-8 -*-
"""跨境电商 8 组织模式团队幂等种子脚本（方案 A 双轨制的 API 挂载轨）。

只走 HTTP API（POST /api/v1/agent-config、GET/POST /api/v1/ai-team），
不做 DB 迁移；范式照 seed_domain_content.py（按 code 查重跳过、缺成员跳过整团队）。
种子数据单一事实源：app/ai/team/org_patterns/seed_data.py（AGENTS/TEAMS）；
真实模式语义由 app/ai/team/org_patterns/ 各模式模块实现（--mock 离线可跑）。
挂载 mode 仅记录来源模板 + 前端展示（UI 会话运行时统一 Leader+ask_xxx 派活，不读 mode）。

用法（需先启动后端 uvicorn）：
  python scripts/seed_org_pattern_teams.py --dry-run
  python scripts/seed_org_pattern_teams.py [--base-url http://127.0.0.1:8000] [--username admin] [--password xxx]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # 沿用 scripts/apply_ddl.py 惯例：挂 backend 以 import app

from app.ai.team.org_patterns.seed_data import AGENTS, TEAMS  # noqa: E402

BASE = "http://127.0.0.1:8000"
TOKEN = ""
TIMEOUT = 120


def api(method: str, path: str, ok_codes=(200, 201), **kw):
    headers = kw.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = requests.request(method, BASE + path, headers=headers, timeout=TIMEOUT, **kw)
    if r.status_code not in ok_codes:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else None


def as_items(res):
    """兼容 list / {data:[]} / {items:[]} 多种返回。"""
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("data", "items", "list", "records"):
            v = res.get(k)
            if isinstance(v, list):
                return v
    return []


def build_payloads() -> tuple:
    """纯函数：AGENTS/TEAMS → (agent_payloads, team_payloads)，不触网。

    node_key 统一 code.replace('-', '_')（与 seed_domain_content 一致）；
    agent_config_id 由 main() 运行时解析填充。
    """
    agent_payloads = [dict(a, agent_type="CHAT") for a in AGENTS]
    team_payloads = []
    for t in TEAMS:
        members = [
            {"node_key": code.replace("-", "_"), "agent_code": code, "role_name": t["roles"][code]}
            for code in t["members"]
        ]
        edges = [
            {"from_node_key": e["from_node_key"].replace("-", "_"),
             "to_node_key": e["to_node_key"].replace("-", "_")}
            for e in t["edges"]
        ]
        team_payloads.append({
            "team_code": t["team_code"], "name": t["name"], "description": t["description"],
            "category": t["category"], "mode": t["mode"],
            "members": members, "edges": edges, "sample_input": t["sample_input"],
        })
    return agent_payloads, team_payloads


# ── 运行时步骤（幂等：按 code 查重跳过、缺成员跳过整团队）──────────────────
def login(username: str, password: str):
    global TOKEN
    data = api("POST", "/api/v1/auth/login", json={"username": username, "password": password},
               ok_codes=(200, 401, 422))
    if isinstance(data, dict):
        TOKEN = data.get("token") or data.get("access_token") or ""
        if TOKEN:
            print("✔ 登录成功")
            return
    raise SystemExit("登录失败：请用 --username/--password 提供管理员账号")


def step_create_agents(agent_payloads: list):
    created = skipped = 0
    for ap in agent_payloads:
        res = api("GET", f"/api/v1/agent-config?page=1&page_size=100&keyword={ap['agent_code']}")
        if any(it.get("agent_code") == ap["agent_code"] for it in as_items(res)):
            skipped += 1
            continue
        api("POST", "/api/v1/agent-config", json=ap)
        print(f"✔ 创建 Agent {ap['name']}（{ap['agent_code']}）")
        created += 1
    print(f"✔ Agent：新建 {created} / 已存在 {skipped}")


def step_create_teams(team_payloads: list):
    created = skipped = 0
    for tp in team_payloads:
        res = api("GET", "/api/v1/ai-team?page=1&page_size=100")
        if any(it.get("team_code") == tp["team_code"] for it in as_items(res)):
            skipped += 1
            continue
        members = []
        for m in tp["members"]:
            r = api("GET", f"/api/v1/agent-config?page=1&page_size=50&keyword={m['agent_code']}")
            found = next((it for it in as_items(r) if it.get("agent_code") == m["agent_code"]), None)
            if not found:
                print(f"  ✗ 团队 {tp['team_code']} 缺成员 {m['agent_code']}，跳过团队")
                members = []
                break
            members.append({"node_key": m["node_key"], "agent_config_id": found["id"],
                            "role_name": m["role_name"]})
        if not members:
            continue
        api("POST", "/api/v1/ai-team", json={
            "name": tp["name"], "team_code": tp["team_code"], "description": tp["description"],
            "category": tp["category"], "mode": tp["mode"],
            "members": members, "edges": tp["edges"],
        })
        print(f"✔ 创建团队 {tp['name']}（{tp['team_code']}，mode={tp['mode']}，"
              f"{len(members)} 成员 {len(tp['edges'])} 边）")
        created += 1
    print(f"✔ Team：新建 {created} / 已存在 {skipped}")


def main():
    global BASE
    ap = argparse.ArgumentParser(description="跨境电商 xborder-* 8 团队幂等种子")
    ap.add_argument("--dry-run", action="store_true", help="只打印预览，不触网")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    args = ap.parse_args()
    BASE = args.base_url.rstrip("/")

    agent_payloads, team_payloads = build_payloads()
    if args.dry_run:
        print(f"== dry-run 预览：{len(agent_payloads)} Agent / {len(team_payloads)} 团队（不触网）==")
        for tp in team_payloads:
            print(f"[dry] {tp['team_code']}  {tp['name']}  mode={tp['mode']}  "
                  f"成员={len(tp['members'])}  边={len(tp['edges'])}")
            print(f"      示例输入：{tp['sample_input']}")
        return

    print(f"== 跨境电商组织模式种子（base={BASE}）==")
    login(args.username, args.password)
    step_create_agents(agent_payloads)
    step_create_teams(team_payloads)
    print("== 完成 ==")


if __name__ == "__main__":
    main()