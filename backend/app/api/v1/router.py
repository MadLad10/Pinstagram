from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auth,
    directions,
    feed,
    notifications,
    places,
    posts,
    reports,
    reviews,
    search,
    uploads,
    users,
)
from app.api.v1.admin import router as admin_router

router = APIRouter()
for module in (
    auth,
    users,
    places,
    posts,
    feed,
    uploads,
    reviews,
    search,
    directions,
    reports,
    notifications,
    assistant,
):
    router.include_router(module.router)
router.include_router(admin_router)
