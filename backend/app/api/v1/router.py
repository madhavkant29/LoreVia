from fastapi import APIRouter
from app.api.v1.routes import auth, billing, books, characters, reader, intelligence, admin, public, webhooks

api_router = APIRouter()
api_router.include_router(auth.router,          prefix="/auth",          tags=["auth"])
api_router.include_router(books.router,         prefix="/books",         tags=["books"])
api_router.include_router(public.router,        prefix="/public",        tags=["public"])
api_router.include_router(billing.router,       prefix="/billing",       tags=["billing"])
api_router.include_router(webhooks.router,      prefix="/webhooks",      tags=["webhooks"])
api_router.include_router(characters.router,    prefix="/characters",    tags=["characters"])
api_router.include_router(reader.router,        prefix="/reader",        tags=["reader"])
api_router.include_router(intelligence.router,  prefix="/intelligence",  tags=["intelligence"])
api_router.include_router(admin.router,         prefix="/admin",         tags=["admin"])
