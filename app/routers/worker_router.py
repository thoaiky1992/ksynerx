from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.engine.worker_manager import worker_manager

router = APIRouter(prefix="/api/workers", tags=["CDMS Worker Management"])


class CreateWorkerSchema(BaseModel):
    worker_id: str
    tenant_id: str
    source_type: str  # 'SHOPIFY' or 'VIETFUL'
    schedule_cron: Optional[str] = "*/1 * * * *"
    domain: Optional[str] = None


@router.get("", summary="List all workers from the database")
async def list_workers():
    workers = await worker_manager.list_workers_from_db()
    active_shopify = list(worker_manager.active_shopify_workers)
    active_vietful = list(worker_manager.active_vietful_workers)
    return {
        "workers": workers,
        "active_shopify_workers": active_shopify,
        "active_vietful_workers": active_vietful,
        "active_worker_count": len(active_shopify) + len(active_vietful),
    }


@router.post("", summary="Create a new worker configuration in the database")
async def create_worker(payload: CreateWorkerSchema):
    try:
        config = await worker_manager.create_worker_config(
            worker_id=payload.worker_id,
            tenant_id=payload.tenant_id,
            source_type=payload.source_type,
            schedule_cron=payload.schedule_cron,
            domain=payload.domain,
        )
        return {"message": "Worker created successfully", "worker": config}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{worker_id}/start", summary="Start a worker")
async def start_worker(worker_id: str):
    try:
        result = await worker_manager.start_worker_by_id(worker_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{worker_id}/stop", summary="Stop a worker safely")
async def stop_worker(worker_id: str):
    try:
        result = await worker_manager.stop_worker_by_id(worker_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{worker_id}", summary="Stop a worker and permanently delete it from the database"
)
async def delete_worker(worker_id: str):
    try:
        result = await worker_manager.delete_worker_by_id(worker_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
