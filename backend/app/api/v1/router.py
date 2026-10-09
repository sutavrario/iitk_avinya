from fastapi import APIRouter

from app.api.v1 import businesses, documents, health, me, records

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(businesses.router)
api_router.include_router(records.router)
api_router.include_router(documents.router)
