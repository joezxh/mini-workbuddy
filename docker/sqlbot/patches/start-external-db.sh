#!/bin/sh
# ============================================================
# SQLBot 启动脚本 —— 外部数据库版
# 与镜像内置 start.sh 的区别:
#   1. 不启动容器内置 PostgreSQL（使用外部 PG，地址由环境变量注入）
#   2. 不执行 wait-for-it（无需等待内置 DB）
#   3. 入口用 serve_ui: 在 main:app 之上挂载前端 SPA，使 UI 与 API 同源共用 8000
# 通过 docker-compose volume 挂载覆盖镜像内的同名文件。
# ============================================================
set -e

SSR_PATH=/opt/sqlbot/g2-ssr
APP_PATH=/opt/sqlbot/app
PM2_CMD_PATH=$SSR_PATH/node_modules/pm2/bin/pm2

echo "[start] SQLBot 使用外部数据库: ${POSTGRES_SERVER}:${POSTGRES_PORT}/${POSTGRES_DB}"

# 启动 g2-ssr 图表渲染服务
nohup "$PM2_CMD_PATH" start "$SSR_PATH/app.js" >/dev/null 2>&1 &

# 启动 MCP 服务 (8001)
nohup uvicorn serve_ui:mcp_app --host 0.0.0.0 --port 8001 --proxy-headers --forwarded-allow-ips='*' &

# 启动主服务 (8000, 前台常驻) —— 同时提供前端页面与 API
cd "$APP_PATH"
exec uvicorn serve_ui:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'
