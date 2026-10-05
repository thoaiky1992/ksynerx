from fastapi import APIRouter

from app.mock.schemas.vietful import VietfulInventoryInput
from app.mock.services.vietful_service import vietful_mock_service


router = APIRouter(prefix="/mock/vietful", tags=["Vietful Mock Service (PUSH)"])


@router.post(
    "/inventory-event",
    summary="POST endpoint that creates a Vietful inventory event and pushes it to Redis",
)
async def push_vietful_inventory_event(payload: VietfulInventoryInput):
    return await vietful_mock_service.push_inventory_event(payload)
