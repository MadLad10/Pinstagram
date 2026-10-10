from fastapi import APIRouter

from app.api.v1.admin import (
    audit,
    places,
    posts,
    reports,
    reviews,
    stats,
    transport,
    users,
)

router = APIRouter(prefix="/admin", tags=["admin"])
for module in (stats, posts, reviews, reports, places, transport, users, audit):
    router.include_router(module.router)
