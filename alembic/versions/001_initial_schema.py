"""Initial Schema for WorkerConfig and MasterProduct

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-05

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create worker_configs table
    op.create_table(
        "worker_configs",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("tenant_id", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="STOPPED"
        ),
        sa.Column("schedule_cron", sa.String(length=50), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("checkpoint_data", sa.JSON(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_worker_configs_id"), "worker_configs", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_worker_configs_tenant_id"),
        "worker_configs",
        ["tenant_id"],
        unique=False,
    )

    # 2. Create master_products table
    op.create_table(
        "master_products",
        sa.Column("barcode", sa.String(length=100), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("brand_name", sa.String(length=100), nullable=True),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("category_name", sa.String(length=100), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("barcode", "sku"),
    )
    op.create_index(
        op.f("ix_master_products_barcode"), "master_products", ["barcode"], unique=False
    )
    op.create_index(
        op.f("ix_master_products_sku"), "master_products", ["sku"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_master_products_sku"), table_name="master_products")
    op.drop_index(op.f("ix_master_products_barcode"), table_name="master_products")
    op.drop_table("master_products")
    op.drop_index(op.f("ix_worker_configs_tenant_id"), table_name="worker_configs")
    op.drop_index(op.f("ix_worker_configs_id"), table_name="worker_configs")
    op.drop_table("worker_configs")
