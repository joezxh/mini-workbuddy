#!/bin/sh
# 部署期数据库迁移：将 alembic 推到 head。
#
# 生产环境（AUTO_CREATE_TABLES=False）下，这是唯一的建表/迁移来源（含 kb_* 三表、
# HNSW/trgm 索引、pg_trgm/vector 扩展，见迁移 006）。
#
# 当 AUTO_CREATE_TABLES=True（开发/小环境，由 app.main 的 create_all + ensure_kb_schema
# 负责建表）时，跳过本步，避免与 create_all 重复建表冲突。
#
# 用法：sh /app/scripts/db-migrate.sh   （容器内 cwd=/app，已含 alembic.ini 与 venv）

set -e

case "${AUTO_CREATE_TABLES:-false}" in
  1|true|True|TRUE|yes|Yes|YES)
    echo "ℹ️  [db-migrate] AUTO_CREATE_TABLES=${AUTO_CREATE_TABLES}，跳过 alembic（由 create_all 负责建表）"
    exit 0
    ;;
esac

echo "🗄️  [db-migrate] 运行 alembic upgrade head ..."

i=1
max=60
until alembic upgrade head; do
  if [ "$i" -ge "$max" ]; then
    echo "❌ [db-migrate] alembic upgrade head 在 ${max} 次重试后仍失败" >&2
    exit 1
  fi
  echo "⏳ [db-migrate] 数据库连接失败，${i}/${max}，5s 后重试..."
  i=$((i + 1))
  sleep 5
done

echo "✅ [db-migrate] alembic upgrade head 完成"
