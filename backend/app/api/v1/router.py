from fastapi import APIRouter, Depends
from app.api.v1.routes import auth, billing, books, characters, reader, intelligence, admin, public, webhooks
from app.api.deps.rate_limit import rate_limit_api

api_router = APIRouter()
api_router.include_router(auth.router,          prefix="/auth",          tags=["auth"])
api_router.include_router(books.router,         prefix="/books",         tags=["books"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(public.router,        prefix="/public",        tags=["public"])
api_router.include_router(billing.router,       prefix="/billing",       tags=["billing"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(webhooks.router,      prefix="/webhooks",      tags=["webhooks"])
api_router.include_router(characters.router,    prefix="/characters",    tags=["characters"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(reader.router,        prefix="/reader",        tags=["reader"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(intelligence.router,  prefix="/intelligence",  tags=["intelligence"], dependencies=[Depends(rate_limit_api)])
api_router.include_router(admin.router,         prefix="/admin",         tags=["admin"], dependencies=[Depends(rate_limit_api)])
