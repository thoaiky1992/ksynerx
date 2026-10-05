from fastapi import APIRouter, Query

from app.mock.schemas.shopify import ShopifyProductCreateInput
from app.mock.services.shopify_service import shopify_mock_service


router = APIRouter(prefix="/mock/shopify", tags=["Shopify Mock Service (PULL)"])


@router.get(
    "/admin/api/{tenant_id}/products.json",
    summary="GET tenant-scoped mock Shopify products",
)
def get_shopify_products(
    tenant_id: str,
    since_id: int = Query(0),
    limit: int = Query(5),
):
    products = shopify_mock_service.get_products(
        tenant_id,
        since_id=since_id,
        limit=limit,
    )
    return {"products": products}


@router.post(
    "/{tenant_id}/products",
    summary="POST a product to one tenant's mock Shopify shop",
)
def create_shopify_product(
    tenant_id: str,
    payload: ShopifyProductCreateInput,
):
    product = shopify_mock_service.create_product(tenant_id, payload)
    return {"message": "Created Shopify product", "product": product}
