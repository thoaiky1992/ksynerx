from datetime import datetime, timezone
from typing import Dict, List
from app.mock.schemas.shopify import ShopifyProductCreateInput
from app.core.logger import logger


class ShopifyMockService:
    """In-memory storage and business logic for the Shopify Mock API."""

    def __init__(self):
        self.products_db: Dict[str, Dict[int, dict]] = {}
        self.id_counters: Dict[str, int] = {}

    def get_products(self, tenant_id: str, since_id: int = 0, limit: int = 5) -> List[dict]:
        """Return products from this tenant's mock shop only."""
        all_sorted = sorted(
            [
                p
                for p_id, p in self.products_db.get(tenant_id, {}).items()
                if p_id > since_id
            ],
            key=lambda x: x["id"],
        )
        result = all_sorted[:limit]
        logger.info(
            f"[SHOPIFY MOCK SERVICE] Served {len(result)} products for tenant={tenant_id} (since_id={since_id}, limit={limit})"
        )
        return result

    def create_product(self, tenant_id: str, input_data: ShopifyProductCreateInput) -> dict:
        new_id = self.id_counters.get(tenant_id, 1000) + 1
        self.id_counters[tenant_id] = new_id

        variants_list = []
        for idx, v in enumerate(input_data.variants):
            variants_list.append(
                {
                    "id": new_id * 10 + idx,
                    "product_id": new_id,
                    "title": f"Variant-{idx+1}",
                    "sku": v.sku,
                    "price": v.price,
                    "inventory_quantity": v.inventory_quantity,
                    "barcode": v.barcode,
                    "weight": v.weight,
                    "created_at": datetime.now(timezone.utc).isoformat() + "Z",
                    "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
                }
            )

        product = {
            "id": new_id,
            "title": input_data.title,
            "vendor": input_data.vendor,
            "product_type": input_data.product_type,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z",
            "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "variants": variants_list,
        }
        self.products_db.setdefault(tenant_id, {})[new_id] = product
        logger.info(
            f"[SHOPIFY MOCK SERVICE] Created product id={new_id} for tenant={tenant_id}, title='{input_data.title}'"
        )
        return product


shopify_mock_service = ShopifyMockService()
