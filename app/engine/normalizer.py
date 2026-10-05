from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.core.logger import logger

class UnifiedProduct(BaseModel):
    """
    Unified product structure (Unified Product Model).
    All Shopify (GraphQL/REST) and Vietful (push event) data must pass through
    DataNormalizer and be converted to this structure before being upserted into the database.
    """
    sku: str
    barcode: str
    product_name: str
    brand_name: Optional[str] = "Unknown"
    category_name: Optional[str] = "General"
    inventory_qty: int = 0
    price: Optional[float] = 0.0
    weight_kg: Optional[float] = 0.0
    raw_source: str # 'SHOPIFY' or 'VIETFUL'
    extra_info: Dict[str, Any] = {}

class DataNormalizer:
    """Maps and normalizes data from multiple sources into UnifiedProduct."""

    @staticmethod
    def normalize_shopify(raw_product: dict, variant: dict) -> UnifiedProduct:
        """
        Convert standard Shopify REST/GraphQL API data into UnifiedProduct.
        - Typical raw product: {id, title, vendor, product_type, ...}
        - Typical variant: {id, sku, price, inventory_quantity, barcode, weight, ...}
        """
        sku = variant.get("sku") or f"SHOPIFY-{variant.get('id')}"
        barcode = variant.get("barcode") or f"BC-{sku}"
        
        # Product name = original name + variant name (if present)
        product_title = raw_product.get("title", "Shopify Item")
        variant_title = variant.get("title", "")
        if variant_title and variant_title.lower() != "default title":
            product_name = f"{product_title} - {variant_title}"
        else:
            product_name = product_title

        unified = UnifiedProduct(
            sku=sku,
            barcode=barcode,
            product_name=product_name,
            brand_name=raw_product.get("vendor", "Shopify Merchant"),
            category_name=raw_product.get("product_type", "General"),
            inventory_qty=int(variant.get("inventory_quantity", 0)),
            price=float(variant.get("price", 0.0)),
            weight_kg=float(variant.get("weight", 0.0)),
            raw_source="SHOPIFY",
            extra_info={
                "shopify_product_id": raw_product.get("id"),
                "shopify_variant_id": variant.get("id"),
                "status": raw_product.get("status", "active")
            }
        )
        logger.info(f"Normalized Shopify product: SKU={sku}, Name='{product_name}'", extra={"extra_fields": {"sku": sku, "source": "SHOPIFY"}})
        return unified

    @staticmethod
    def normalize_vietful(raw_event: dict) -> UnifiedProduct:
        """
        Convert a standard push event from the Vietful Inventory Service into UnifiedProduct.
        - Typical payload: {event_type, tenant_code, data: {product_code, product_name, barcode, brand_name, available_quantity, ...}}
        """
        data = raw_event.get("data", {})
        
        # Perform basic validation to handle corrupt data
        sku = data.get("product_code")
        if not sku:
            raise ValueError("Vietful payload missing 'product_code' (SKU)!")

        barcode = data.get("barcode") or f"BC-{sku}"
        product_name = data.get("product_name", "Vietful Item")

        unified = UnifiedProduct(
            sku=sku,
            barcode=barcode,
            product_name=product_name,
            brand_name=data.get("brand_name", "Vietful Manufacturer"),
            category_name=data.get("category_name", "Warehouse Item"),
            inventory_qty=int(data.get("available_quantity", 0)),
            price=0.0, # Vietful WMS usually does not provide retail prices
            weight_kg=float(data.get("weight_kg", 0.0)),
            raw_source="VIETFUL",
            extra_info={
                "vietful_event_id": raw_event.get("event_id"),
                "tenant_code": raw_event.get("tenant_code"),
                "reserved_qty": data.get("reserved_quantity", 0)
            }
        )
        logger.info(f"Normalized Vietful event: SKU={sku}, Name='{product_name}'", extra={"extra_fields": {"sku": sku, "source": "VIETFUL"}})
        return unified
