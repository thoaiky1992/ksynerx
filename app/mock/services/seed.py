from app.mock.services.shopify_service import shopify_mock_service
from app.mock.schemas.shopify import ShopifyProductCreateInput, ShopifyVariantInput
from app.mock.services.vietful_service import vietful_mock_service
from app.mock.schemas.vietful import VietfulInventoryInput
from app.core.logger import logger


async def seed_local_dummy_data():
    """Automatically seed 15 Shopify products and 15 Vietful products."""
    logger.info("Initializing Local Dummy Seed Data (15 Shopify & 15 Vietful)...")

    # 1. Seed 15 Shopify products for the tenant used in the README example.
    shopify_tenant_id = "tenant01"
    for i in range(1, 16):
        shopify_input = ShopifyProductCreateInput(
            title=f"Shopify Product Item #{i:02d}",
            vendor=f"Brand {chr(65 + (i % 5))}",  # Brand A, B, C...
            product_type="Apparel" if i % 2 == 0 else "Footwear",
            variants=[
                ShopifyVariantInput(
                    sku=f"SP-SKU-{i:03d}",
                    price=str(100000 + i * 25000),
                    inventory_quantity=50 + i * 5,
                    barcode=f"888123456{i:03d}",
                    weight=0.2 + (i * 0.05),
                )
            ],
        )
        shopify_mock_service.create_product(shopify_tenant_id, shopify_input)

    logger.info(f"Seeded 15 dummy products into Mock Shopify Storage for {shopify_tenant_id}.")

    # 2. Seed 15 Vietful Products (Push to Redis for tenant-01)
    for i in range(1, 16):
        vietful_input = VietfulInventoryInput(
            tenant_code="tenant_01",
            product_code=f"VF-SKU-{i:03d}",
            product_name=f"Vietful Inventory Item #{i:02d}",
            barcode=f"999123456{i:03d}",
            brand_name=f"Manufacturer {chr(70 + (i % 5))}",
            category_name="Warehouse",
            quantity=100 + i * 10,
            weight_kg=0.5 + (i * 0.1),
        )
        await vietful_mock_service.push_inventory_event(vietful_input)

    logger.info(
        "Seeded 15 dummy inventory events into Vietful Redis Channel (tenant_01)."
    )
