from sqlalchemy import Column, String, Integer, Numeric, DateTime, JSON, func, Table
from app.core.database import Base


class MasterProduct(Base):
    """Central master_products table shared across the entire CDMS."""

    __tablename__ = "master_products"

    # A master product is uniquely identified by the barcode + SKU pair.
    barcode = Column(String(100), primary_key=True, index=True)
    sku = Column(String(100), primary_key=True, index=True)
    brand_name = Column(String(100), nullable=True)
    normalized_name = Column(String(255), nullable=False)
    category_name = Column(String(100), nullable=True)
    weight_kg = Column(Numeric(10, 3), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Dynamic Tenant Product Table Cache
_tenant_models = {}


def get_tenant_product_model(tenant_id: str):
    """
    Create or retrieve the dynamic SQLAlchemy model for products_{tenant_id}.
    Each tenant is stored in a separate table to satisfy the data-isolation requirement.
    """
    clean_tenant_id = tenant_id.lower().replace("-", "_")
    table_name = f"products_{clean_tenant_id}"

    if table_name in _tenant_models:
        return _tenant_models[table_name]

    class TenantProduct(Base):
        __tablename__ = table_name
        __table_args__ = {"extend_existing": True}

        sku = Column(String(100), primary_key=True, index=True)
        barcode = Column(String(100), nullable=True, index=True)
        product_name = Column(String(255), nullable=False)
        inventory_qty = Column(Integer, default=0)
        price = Column(Numeric(12, 2), nullable=True)
        raw_source = Column(String(20), nullable=False)  # 'SHOPIFY' or 'VIETFUL'
        extra_info = Column(JSON, nullable=True, default={})
        updated_at = Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )

    _tenant_models[table_name] = TenantProduct
    return TenantProduct
