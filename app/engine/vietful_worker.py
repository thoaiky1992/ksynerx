import asyncio
import json
import redis.asyncio as aioredis
from app.engine.base_worker import BaseWorker
from app.engine.normalizer import DataNormalizer
from app.core.config import settings
from app.core.logger import logger

class VietfulWorker(BaseWorker):
    """
    Worker for the Vietful source (PUSH mode).
    - Maintains a real-time Redis Pub/Sub subscription
    - Listens to the vietful_tenant_<tenant_id> channel
    - Transforms data through DataNormalizer and upserts it into the database
    """
    def __init__(self, worker_id: str, tenant_id: str, checkpoint_data: dict = None):
        super().__init__(worker_id, tenant_id, source_type="VIETFUL", schedule_cron=None, checkpoint_data=checkpoint_data)
        self.redis_url = settings.REDIS_URL
        self.channel_name = f"vietful_tenant_{self.tenant_id}"
        self._listener_task = None

    async def start_listener(self):
        """Start the subscriber loop that listens to Redis Pub/Sub."""
        self.is_running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info(f"[VIETFUL WORKER {self.worker_id}] Started listening on Redis channel '{self.channel_name}'")

    async def _listen_loop(self):
        try:
            async with aioredis.from_url(self.redis_url, decode_responses=True) as r:
                async with r.pubsub() as pubsub:
                    await pubsub.subscribe(self.channel_name)

                    while self.is_running:
                        try:
                            # Read from the Redis channel with a one-second timeout for safe cancellation
                            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                            if message and message['type'] == 'message':
                                payload_str = message['data']
                                logger.info(f"[VIETFUL WORKER {self.worker_id}] Received Redis PUSH message: {payload_str}")

                                try:
                                    payload_json = json.loads(payload_str)
                                    # 1. Normalize
                                    unified = DataNormalizer.normalize_vietful(payload_json)
                                    # 2. UPSERT
                                    await self.upsert_unified_product(unified)
                                    # 3. Checkpoint
                                    event_id = payload_json.get("event_id", "evt_unknown")
                                    await self.save_checkpoint({"last_event_id": event_id})
                                except Exception as val_err:
                                    logger.error(f"[VIETFUL WORKER {self.worker_id}] Processing/Corrupt Data Error: {val_err}")
                        except asyncio.CancelledError:
                            break
                        except Exception as loop_err:
                            logger.error(f"[VIETFUL WORKER {self.worker_id}] Listen loop error: {loop_err}")
                            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[VIETFUL WORKER {self.worker_id}] Connection to Redis failed: {e}")

    async def stop_listener(self):
        """Stop the subscriber loop safely."""
        self.is_running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        logger.info(f"[VIETFUL WORKER {self.worker_id}] Stopped listener on Redis channel '{self.channel_name}'")
