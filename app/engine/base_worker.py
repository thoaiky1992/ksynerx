import json
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select, update, Table
from app.core.database import AsyncSessionLocal
from app.models.product import MasterProduct, get_tenant_product_model
from app.models.worker import WorkerConfig
from app.engine.normalizer import UnifiedProduct
from app.core.logger import logger


class BaseWorker:
    """Abstract base class for all CDMS workers."""

    def __init__(
        self,
        worker_id: str,
        tenant_id: str,
        source_type: str,
        schedule_cron: str = None,
        checkpoint_data: dict = None,
    ):
        self.worker_id = worker_id
        self.tenant_id = tenant_id
        self.source_type = source_type
        self.schedule_cron = schedule_cron
        self.checkpoint_data = checkpoint_data or {}
        self.is_running = False

    async def upsert_unified_product(self, unified: UnifiedProduct):
        """
        Perform a PostgreSQL UPSERT (ON CONFLICT DO UPDATE) into both:
        1. The tenant-specific table: products_{tenant_id}
        2. The shared master table: master_products
        """
        async with AsyncSessionLocal() as session:
            try:
                # 1. UPSERT into the products_{tenant_id} table
                TenantModel = get_tenant_product_model(self.tenant_id)

                # Ensure the tenant table exists in PostgreSQL
                async with session.bind.begin() as conn:
                    await conn.run_sync(TenantModel.__table__.create, checkfirst=True)

                stmt_tenant = (
                    pg_insert(TenantModel)
                    .values(
                        sku=unified.sku,
                        barcode=unified.barcode,
                        product_name=unified.product_name,
                        inventory_qty=unified.inventory_qty,
                        price=unified.price,
                        raw_source=unified.raw_source,
                        extra_info=unified.extra_info,
                        updated_at=datetime.now(timezone.utc),
                    )
                    .on_conflict_do_update(
                        index_elements=["sku"],
                        set_={
                            "product_name": unified.product_name,
                            "inventory_qty": unified.inventory_qty,
                            "price": unified.price,
                            "extra_info": unified.extra_info,
                            "updated_at": datetime.now(timezone.utc),
                        },
                    )
                )
                await session.execute(stmt_tenant)

                # 2. UPSERT into the master_products table
                stmt_master = (
                    pg_insert(MasterProduct)
                    .values(
                        barcode=unified.barcode,
                        sku=unified.sku,
                        brand_name=unified.brand_name,
                        normalized_name=unified.product_name,
                        category_name=unified.category_name,
                        weight_kg=unified.weight_kg,
                        updated_at=datetime.now(timezone.utc),
                    )
                    .on_conflict_do_update(
                        index_elements=["barcode", "sku"],
                        set_={
                            "brand_name": unified.brand_name,
                            "normalized_name": unified.product_name,
                            "category_name": unified.category_name,
                            "weight_kg": unified.weight_kg,
                            "updated_at": datetime.now(timezone.utc),
                        },
                    )
                )
                await session.execute(stmt_master)
                await session.commit()

                logger.info(
                    f"UPSERT successful for SKU '{unified.sku}' into tenant_{self.tenant_id} & master_products"
                )
            except Exception as e:
                await session.rollback()
                logger.error(f"Error upserting product {unified.sku}: {e}")
                raise e

    async def save_checkpoint(self, new_checkpoint: dict):
        """Save the latest synchronization checkpoint to worker_configs."""
        checkpoint_data = {**self.checkpoint_data, **new_checkpoint}
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    update(WorkerConfig)
                    .where(WorkerConfig.id == self.worker_id)
                    .values(
                        checkpoint_data=checkpoint_data,
                        last_heartbeat=datetime.now(timezone.utc),
                    )
                )
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error saving checkpoint for worker {self.worker_id}: {e}"
                )
                raise
        self.checkpoint_data = checkpoint_data

    async def update_status_in_db(self, status: str):
        """Update the worker status in the database ('RUNNING', 'STOPPED', 'FAILED')."""
        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    update(WorkerConfig)
                    .where(WorkerConfig.id == self.worker_id)
                    .values(status=status, last_heartbeat=datetime.now(timezone.utc))
                )
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating status for worker {self.worker_id}: {e}")
