from typing import Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.worker import WorkerConfig
from app.engine.shopify_worker import (
    ShopifyWorker,
    default_shopify_mock_domain,
    validate_shopify_mock_domain,
)
from app.engine.vietful_worker import VietfulWorker
from app.core.logger import logger


class WorkerManager:
    """
    Centralized worker lifecycle manager.
    - Manages startup recovery from the database
    - Manages APScheduler for cron-based workers (Shopify)
    - Manages Redis Pub/Sub tasks for event-driven workers (Vietful)
    - Provides CRUD operations (Create, Start, Stop, Delete)
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.active_shopify_workers: Dict[str, ShopifyWorker] = {}
        self.active_vietful_workers: Dict[str, VietfulWorker] = {}
        logger.info("WorkerManager initialized with AsyncIOScheduler")

    async def restore_running_workers_from_db(self):
        """Restore all RUNNING workers from the database when FastAPI starts."""
        logger.info("Restoring RUNNING workers from database...")
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(WorkerConfig).where(WorkerConfig.status == "RUNNING")
                result = await session.execute(stmt)
                running_configs = result.scalars().all()

                logger.info(f"Found {len(running_configs)} RUNNING workers in database")
                for config in running_configs:
                    await self.start_worker_instance(config)
            except Exception as e:
                logger.error(f"Error restoring running workers from DB: {e}")

    async def create_worker_config(
        self,
        worker_id: str,
        tenant_id: str,
        source_type: str,
        schedule_cron: str = None,
        domain: str = None,
    ) -> dict:
        """Create a new worker configuration in the database."""
        source_type_upper = source_type.upper()
        if source_type_upper not in ["SHOPIFY", "VIETFUL"]:
            raise ValueError("source_type must be 'SHOPIFY' or 'VIETFUL'")

        if source_type_upper == "SHOPIFY" and not schedule_cron:
            schedule_cron = "*/1 * * * *"  # Default 1 minute cron for testing

        config_json = {}
        if source_type_upper == "SHOPIFY":
            config_json["domain"] = validate_shopify_mock_domain(
                tenant_id, domain or default_shopify_mock_domain(tenant_id)
            )
        elif domain is not None:
            raise ValueError("domain is only supported for SHOPIFY workers")

        async with AsyncSessionLocal() as session:
            # Check whether the worker already exists
            existing = await session.get(WorkerConfig, worker_id)
            if existing:
                raise ValueError(f"Worker with ID '{worker_id}' already exists!")

            new_config = WorkerConfig(
                id=worker_id,
                tenant_id=tenant_id,
                source_type=source_type_upper,
                status="STOPPED",
                schedule_cron=schedule_cron,
                config_json=config_json,
                checkpoint_data={},
            )
            session.add(new_config)
            await session.commit()
            await session.refresh(new_config)
            logger.info(
                f"Created new worker config '{worker_id}' in DB",
                extra={"extra_fields": {"worker_id": worker_id}},
            )
            return new_config.to_dict()

    async def start_worker_instance(self, config: WorkerConfig):
        """Start a worker instance from its configuration."""
        worker_id = config.id
        source_type = config.source_type.upper()

        if source_type == "SHOPIFY":
            if worker_id in self.active_shopify_workers:
                logger.info(f"Shopify Worker {worker_id} is already running.")
                return

            worker = ShopifyWorker(
                worker_id=worker_id,
                tenant_id=config.tenant_id,
                schedule_cron=config.schedule_cron or "*/1 * * * *",
                checkpoint_data=config.checkpoint_data or {},
                domain=(config.config_json or {}).get("domain"),
            )
            worker.is_running = True
            self.active_shopify_workers[worker_id] = worker

            # Register the worker with APScheduler using a cron trigger
            trigger = CronTrigger.from_crontab(worker.schedule_cron)
            self.scheduler.add_job(
                func=worker.execute_cron_job,
                trigger=trigger,
                id=worker_id,
                replace_existing=True,
            )
            await worker.update_status_in_db("RUNNING")
            logger.info(
                f"Started Shopify Worker '{worker_id}' with cron schedule '{worker.schedule_cron}'"
            )

        elif source_type == "VIETFUL":
            if worker_id in self.active_vietful_workers:
                logger.info(f"Vietful Worker {worker_id} is already running.")
                return

            worker = VietfulWorker(
                worker_id=worker_id,
                tenant_id=config.tenant_id,
                checkpoint_data=config.checkpoint_data or {},
            )
            await worker.start_listener()
            self.active_vietful_workers[worker_id] = worker
            await worker.update_status_in_db("RUNNING")
            logger.info(f"Started Vietful Worker '{worker_id}' subscribed to Redis")

    async def start_worker_by_id(self, worker_id: str):
        """Start a worker by ID from the API or dashboard."""
        async with AsyncSessionLocal() as session:
            config = await session.get(WorkerConfig, worker_id)
            if not config:
                raise ValueError(f"Worker '{worker_id}' not found in DB")
            await self.start_worker_instance(config)
            return {"message": f"Worker '{worker_id}' started successfully"}

    async def stop_worker_by_id(self, worker_id: str):
        """Stop a worker by ID."""
        stopped = False
        if worker_id in self.active_shopify_workers:
            worker = self.active_shopify_workers.pop(worker_id)
            worker.is_running = False
            if self.scheduler.get_job(worker_id):
                self.scheduler.remove_job(worker_id)
            await worker.update_status_in_db("STOPPED")
            stopped = True

        if worker_id in self.active_vietful_workers:
            worker = self.active_vietful_workers.pop(worker_id)
            await worker.stop_listener()
            await worker.update_status_in_db("STOPPED")
            stopped = True

        if not stopped:
            # Update the database status if the worker is not in memory
            async with AsyncSessionLocal() as session:
                config = await session.get(WorkerConfig, worker_id)
                if config:
                    config.status = "STOPPED"
                    await session.commit()

        logger.info(f"Stopped worker '{worker_id}'")
        return {"message": f"Worker '{worker_id}' stopped successfully"}

    async def delete_worker_by_id(self, worker_id: str):
        """Stop the runtime instance and permanently delete the worker from the database."""
        await self.stop_worker_by_id(worker_id)
        async with AsyncSessionLocal() as session:
            config = await session.get(WorkerConfig, worker_id)
            if config:
                await session.delete(config)
                await session.commit()
                logger.info(f"Deleted worker '{worker_id}' from DB")
                return {"message": f"Worker '{worker_id}' deleted successfully"}
            else:
                raise ValueError(f"Worker '{worker_id}' not found in DB")

    async def list_workers_from_db(self) -> List[dict]:
        """List all worker configurations in the database."""
        async with AsyncSessionLocal() as session:
            stmt = select(WorkerConfig)
            result = await session.execute(stmt)
            configs = result.scalars().all()
            return [c.to_dict() for c in configs]


# Global Singleton Instance
worker_manager = WorkerManager()
