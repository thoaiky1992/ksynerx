import httpx
from urllib.parse import urlsplit
from app.engine.base_worker import BaseWorker
from app.engine.normalizer import DataNormalizer
from app.core.config import settings
from app.core.logger import logger


def default_shopify_mock_domain(tenant_id: str) -> str:
    return f"http://localhost:{settings.PORT}/mock/shopify/admin/api/{tenant_id}/products.json"


def validate_shopify_mock_domain(tenant_id: str, domain: str) -> str:
    """Ensure a configured mock endpoint cannot fetch another tenant's products."""
    parsed = urlsplit(domain)
    expected_path = f"/mock/shopify/admin/api/{tenant_id}/products.json"
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path != expected_path
    ):
        raise ValueError(f"Shopify domain must point to this tenant's mock endpoint: {expected_path}")
    return domain


class ShopifyWorker(BaseWorker):
    """
    Worker for the Shopify source (PULL mode).
    - Runs on the cron schedule defined by schedule_cron
    - Fetches batches of five products until the source is exhausted
    - Saves the since_id cursor after each batch; an empty response ends this run
      and resets the cursor for the next cron run
    """

    def __init__(
        self,
        worker_id: str,
        tenant_id: str,
        schedule_cron: str = "*/1 * * * *",
        checkpoint_data: dict = None,
        batch_size: int = 5,
        domain: str = None,
    ):
        super().__init__(
            worker_id,
            tenant_id,
            source_type="SHOPIFY",
            schedule_cron=schedule_cron,
            checkpoint_data=checkpoint_data,
        )
        self.batch_size = batch_size
        self.mock_url = validate_shopify_mock_domain(
            tenant_id, domain or default_shopify_mock_domain(tenant_id)
        )

    async def execute_cron_job(self):
        """Fetch all remaining batches, resuming from the saved cursor."""
        if not self.is_running:
            return

        last_since_id = self.checkpoint_data.get("last_since_id", 0)
        logger.info(
            f"[SHOPIFY WORKER {self.worker_id}] Triggered cron job. Fetching batches of {self.batch_size} from since_id={last_since_id}"
        )

        async with httpx.AsyncClient() as client:
            try:
                while self.is_running:
                    response = await client.get(
                        self.mock_url,
                        params={"since_id": last_since_id, "limit": self.batch_size},
                    )
                    if response.status_code != 200:
                        logger.error(
                            f"Shopify Mock API returned status {response.status_code}"
                        )
                        return

                    products = response.json().get("products", [])
                    if not products:
                        await self.save_checkpoint({"last_since_id": 0})
                        logger.info(
                            f"[SHOPIFY WORKER {self.worker_id}] No more products. Reset checkpoint since_id=0; waiting for the next cron run"
                        )
                        return

                    batch_products = products[: self.batch_size]
                    max_processed_id = max(product["id"] for product in batch_products)
                    if max_processed_id <= last_since_id:
                        logger.error(
                            f"[SHOPIFY WORKER {self.worker_id}] Batch did not advance since_id={last_since_id}"
                        )
                        return

                    for raw_prod in batch_products:
                        for variant in raw_prod.get("variants", []):
                            unified = DataNormalizer.normalize_shopify(
                                raw_prod, variant
                            )
                            await self.upsert_unified_product(unified)

                    await self.save_checkpoint({"last_since_id": max_processed_id})
                    last_since_id = max_processed_id
                    logger.info(
                        f"[SHOPIFY WORKER {self.worker_id}] Processed batch of {len(batch_products)} items. New checkpoint since_id={last_since_id}"
                    )
            except Exception as e:
                logger.error(
                    f"[SHOPIFY WORKER {self.worker_id}] Batch processing failed: {e}"
                )
