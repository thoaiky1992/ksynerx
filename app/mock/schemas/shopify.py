from pydantic import BaseModel
from typing import List, Optional

class ShopifyVariantInput(BaseModel):
    sku: str
    price: str
    inventory_quantity: int
    barcode: str
    weight: Optional[float] = 0.25

class ShopifyProductCreateInput(BaseModel):
    title: str
    vendor: str
    product_type: Optional[str] = "Apparel"
    variants: List[ShopifyVariantInput]
