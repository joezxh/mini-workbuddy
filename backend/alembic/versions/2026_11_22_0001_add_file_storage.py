"""add_file_storage — 统一文件存储：新增配置表、修正内容列为 BYTEA、补主键序列与索引。

Revision ID: 2026_11_22_0001_filestorage
Revises: 2026_11_22_0000_menucolor
Create Date: 2026-11-22 01:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "2026_11_22_0001_filestorage"
down_revision = "2026_11_22_0000_menucolor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 历史表主键原为无默认值 INTEGER（模型曾引用不存在的 Sequence），补自增序列。
    # 注：旧表（sys_menu/sys_infra_file*）属主可能是 postgres 而迁移以应用账号执行，
    #     而 OWNED BY 要求序列与表同属主，故先同步属主再建立归属关系。
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('public.sys_infra_file') IS NOT NULL THEN
            IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'sys_infra_file_id_seq') THEN
                CREATE SEQUENCE sys_infra_file_id_seq;
            END IF;
            EXECUTE format(
                'ALTER SEQUENCE sys_infra_file_id_seq OWNER TO %I',
                (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'public.sys_infra_file'::regclass)
            );
            ALTER SEQUENCE sys_infra_file_id_seq OWNED BY sys_infra_file.id;
            ALTER TABLE sys_infra_file ALTER COLUMN id SET DEFAULT nextval('sys_infra_file_id_seq');
            PERFORM setval('sys_infra_file_id_seq', COALESCE((SELECT MAX(id) FROM sys_infra_file), 1), true);
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('public.sys_infra_file_content') IS NOT NULL THEN
            IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'sys_infra_file_content_id_seq') THEN
                CREATE SEQUENCE sys_infra_file_content_id_seq;
            END IF;
            EXECUTE format(
                'ALTER SEQUENCE sys_infra_file_content_id_seq OWNER TO %I',
                (SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid = 'public.sys_infra_file_content'::regclass)
            );
            ALTER SEQUENCE sys_infra_file_content_id_seq OWNED BY sys_infra_file_content.id;
            ALTER TABLE sys_infra_file_content ALTER COLUMN id SET DEFAULT nextval('sys_infra_file_content_id_seq');
            PERFORM setval('sys_infra_file_content_id_seq', COALESCE((SELECT MAX(id) FROM sys_infra_file_content), 1), true);
        END IF;
    END $$;
    """)

    # 内容列 TEXT -> BYTEA（convert_to 兼容存量 UTF-8 文本；空表无副作用）。已是 bytea 则跳过。
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'sys_infra_file_content'
                     AND column_name = 'content'
                     AND data_type <> 'bytea') THEN
            ALTER TABLE sys_infra_file_content
                ALTER COLUMN content TYPE BYTEA USING convert_to(content, 'UTF8');
        END IF;
    END $$;
    """)

    # 开发库可能已由 create_all 建表，故需幂等。
    if not sa.inspect(op.get_bind()).has_table("sys_infra_file_config"):
        op.create_table(
            "sys_infra_file_config",
            sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False, comment="配置编号"),
            sa.Column("name", sa.String(64), nullable=False, comment="配置名称"),
            sa.Column("code", sa.String(64), nullable=False, comment="配置编码"),
            sa.Column("storage", sa.Integer(), nullable=False, comment="存储类型：1=DB 10=LOCAL 20=S3"),
            sa.Column("config", JSONB(), nullable=True, comment="存储配置 JSON"),
            sa.Column("remark", sa.String(256), nullable=True, comment="备注"),
            sa.Column("is_master", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否主配置"),
            sa.Column("creator", sa.String(64), nullable=True),
            sa.Column("create_time", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
            sa.Column("updater", sa.String(64), nullable=True),
            sa.Column("update_time", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
            sa.Column("deleted", sa.String(1), server_default="0", nullable=False),
            sa.Column("tenant_id", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_infra_file_config_code ON sys_infra_file_config (code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_infra_file_config_is_master ON sys_infra_file_config (is_master)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sys_infra_file_config_tenant_id ON sys_infra_file_config (tenant_id)")

    # 图片资产关联统一存储记录（可空，历史数据 file_path 保持不变）
    # 该表由 create_all 创建（AUTO_CREATE_TABLES=True），故用 to_regclass 守卫兼容纯 alembic 部署。
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('public.kms_segment_asset') IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                           WHERE table_name = 'kms_segment_asset' AND column_name = 'file_id') THEN
            ALTER TABLE kms_segment_asset ADD COLUMN file_id BIGINT;
            COMMENT ON COLUMN kms_segment_asset.file_id IS '统一文件存储记录 ID';
            CREATE INDEX IF NOT EXISTS ix_kms_segment_asset_file_id ON kms_segment_asset (file_id);
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.drop_index("ix_kms_segment_asset_file_id", table_name="kms_segment_asset")
    op.drop_column("kms_segment_asset", "file_id")
    op.drop_index("ix_sys_infra_file_config_tenant_id", table_name="sys_infra_file_config")
    op.drop_index("ix_sys_infra_file_config_is_master", table_name="sys_infra_file_config")
    op.drop_index("ix_sys_infra_file_config_code", table_name="sys_infra_file_config")
    op.drop_table("sys_infra_file_config")
    op.execute("""
    ALTER TABLE sys_infra_file_content
        ALTER COLUMN content TYPE TEXT USING convert_from(content, 'UTF8');
    """)
