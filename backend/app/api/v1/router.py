from fastapi import APIRouter

from app.api.v1 import auth, users, places, posts, feed, uploads, reviews, search, directions, reports
from app.api.v1.admin import router as admin_router

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(places.router)
router.include_router(posts.router)
router.include_router(feed.router)
router.include_router(uploads.router)
router.include_router(reviews.router)
router.include_router(search.router)
router.include_router(directions.router)
router.include_router(reports.router)
router.include_router(admin_router)
