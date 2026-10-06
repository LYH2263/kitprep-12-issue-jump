from fastapi import APIRouter
from app.api import bom, dishes, inventory, orders, prep
api_router = APIRouter()

@api_router.get("/health")
def health():
    return {"status": "ok"}

api_router.include_router(dishes.router)
api_router.include_router(bom.router)
api_router.include_router(orders.router)
api_router.include_router(inventory.router)
api_router.include_router(prep.router)
