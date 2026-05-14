from fastapi import APIRouter
from app.api.v1.admin import posts, reviews, reports, places, transport, users

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(posts.router)
router.include_router(reviews.router)
router.include_router(reports.router)
router.include_router(places.router)
router.include_router(transport.router)
router.include_router(users.router)
