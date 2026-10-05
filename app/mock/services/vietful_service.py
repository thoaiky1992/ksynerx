import json
import redis.asyncio as aioredis
from datetime import datetime, timezone
from app.mock.schemas.vietful import VietfulInventoryInput
from app.core.config import settings
from app.core.logger import logger


class VietfulMockService:
    """Publishes Vietful Mock push events to a Redis channel."""

    def __init__(self):
        self.redis_url = settings.REDIS_URL

    async def push_inventory_event(self, input_data: VietfulInventoryInput) -> dict:
        channel_name = f"vietful_tenant_{input_data.tenant_code}"

        if input_data.corrupt_data:
            event_payload = {
                "event_type": "PRODUCT_INVENTORY_UPDATE",
                "event_id": f"evt_corrupt_{int(datetime.now(timezone.utc).timestamp())}",
                "tenant_code": input_data.tenant_code,
                "data": {
                    "corrupt_field": "Missing required SKU product_code!"
                },  # Invalid data with a missing SKU
            }
        else:
            event_payload = {
                "event_type": "PRODUCT_INVENTORY_UPDATE",
                "event_id": f"evt_{input_data.product_code}_{int(datetime.now(timezone.utc).timestamp())}",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "tenant_code": input_data.tenant_code,
                "data": {
                    "product_code": input_data.product_code,
                    "product_name": input_data.product_name,
                    "barcode": input_data.barcode,
                    "brand_name": input_data.brand_name,
                    "category_name": input_data.category_name,
                    "available_quantity": input_data.quantity,
                    "weight_kg": input_data.weight_kg,
                    "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
                },
            }

        try:
            async with aioredis.from_url(self.redis_url, decode_responses=True) as r:
                await r.publish(channel_name, json.dumps(event_payload))
            logger.info(
                f"[VIETFUL MOCK SERVICE] Pushed event {event_payload.get('event_id')} to Redis channel '{channel_name}'"
            )
            return {
                "status": "SUCCESS",
                "channel": channel_name,
                "payload": event_payload,
            }
        except Exception as e:
            logger.error(f"[VIETFUL MOCK SERVICE] Redis publish error: {e}")
            return {"status": "ERROR", "message": str(e)}


vietful_mock_service = VietfulMockService()
