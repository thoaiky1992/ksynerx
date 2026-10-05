from pydantic import BaseModel
from typing import Optional

class VietfulInventoryInput(BaseModel):
    tenant_code: str
    product_code: str  # SKU
    product_name: str
    barcode: str
    brand_name: str = "Vietful Brand"
    category_name: str = "Warehouse Item"
    quantity: int
    weight_kg: Optional[float] = 0.5
    corrupt_data: Optional[bool] = False
