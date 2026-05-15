from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import AdminUserID, DB
from app.models.place import Place
from app.models.post import Post
from app.models.report import Report
from app.models.review import Review
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_stats(db: DB, _admin: AdminUserID):
    async def count(model, where=None):
        q = select(func.count()).select_from(model)
        if where is not None:
            q = q.where(where)
        return (await db.execute(q)).scalar_one()

    return {
        "pending_reviews": await count(Review, Review.status == "pending"),
        "pending_posts": await count(Post, Post.status == "pending"),
        "open_reports": await count(Report, Report.status == "open"),
        "total_users": await count(User, User.deleted_at.is_(None)),
        "total_places": await count(Place),
        "total_posts": await count(Post, Post.status == "published"),
    }
