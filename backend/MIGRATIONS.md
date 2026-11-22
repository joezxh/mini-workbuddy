# 数据库迁移（Alembic）使用说明

知识库 `kb_*` 三表（及 HNSW/trgm 索引、`pg_trgm`/`vector` 扩展）由 alembic 迁移
**006 独占建表**。基础表由 `create_all`（开发）或 alembic 001–005 创建，**二者不要混用**。

## 两种运行模式

### 开发 / 小环境（`AUTO_CREATE_TABLES=true`，默认）
- `app.main` 启动时：`Base.metadata.create_all`（排除 `kb_*`）+ `ensure_kb_schema` 跑 alembic 006。
- 无需手动执行 alembic。

### 生产部署（`AUTO_CREATE_TABLES=false`）
- **唯一建表/迁移来源 = `alembic upgrade head`**（001–006 全量）。
- `Dockerfile.prod` 的启动命令已包含 `sh /app/scripts/db-migrate.sh`，会在 gunicorn
  启动前自动执行（带数据库连接重试，最多 60 次）。
- 也可手动执行：
  ```bash
  cd backend && alembic upgrade head
  ```
- 生产 `.env` / 部署环境变量务必设置 `AUTO_CREATE_TABLES=false`，否则会回落到
  `create_all` 路径，与 alembic 重复建表。

## 从旧库（曾用 create_all）切换到 alembic 管理
若数据库已由 `create_all` 建好、但无 `alembic_version` 记录，直接 `alembic upgrade head`
会因表已存在而报错。一次性把基线钉到当前状态再升级：
```bash
alembic stamp head      # 仅写版本号，不执行建表 SQL
# 之后正常：
alembic upgrade head
```

## 新增迁移
```bash
alembic revision -m "描述" --autogenerate
```
`alembic/env.py` 已显式 `import app.db.init_models` 以注册全部 ORM 模型，
autogenerate 不会漏表。

## 与 create_all 混合库的注意事项
- 开发库由 `create_all` 建表时，`alembic_version` 往往停在中途，而新表/新列已由 ORM 补
  不到（`create_all` 只建缺失的表，**不会 ALTER 已存在的表**），于是出现
  `column xxx does not exist`。遇到时把相关迁移写成幂等（`has_table` / `information_schema` 守卫
  + `CREATE INDEX IF NOT EXISTS`），再 `alembic upgrade head`，既修正 schema 又不破坏纯 alembic 部署。
- 历史表（如 `sys_menu`、`sys_infra_file*`）属主可能是 `postgres`，而应用连的是其他账号；
  `CREATE SEQUENCE ... OWNED BY <table>.id` 会报「sequence must have same owner as table」，
  需先 `ALTER SEQUENCE ... OWNER TO <表属主>` 再建立归属。
