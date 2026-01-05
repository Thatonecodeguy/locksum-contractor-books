from fastapi import APIRouter

from app.api.routes import auth, customers, items, invoices

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
