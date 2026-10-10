import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import delete, select, tuple_, update

from app.api.v1.admin.schemas import ResolveReportBody
from app.core.deps import DB, AdminUserID
from app.core.pagination import decode_cursor, encode_cursor
from app.models.post import Post, PostComment
from app.models.report import Report
from app.models.review import Review
from app.models.user import User
from app.services.admin_service import get_or_404, log_action
from app.services.auth_service import revoke_all_sessions
from app.services.reviews_service import recompute_place_rating

router = APIRouter()


@router.get("/reports")
async def list_reports(
    db: DB,
    _admin: AdminUserID,
    status: Literal["open", "resolved", "dismissed"] = "open",
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
):
    query = (
        select(Report, User.name)
        .join(User, User.id == Report.reporter_id)
        .where(Report.status == status)
    )
    if cursor:
        c = decode_cursor(cursor, t=datetime, id=uuid.UUID)
        query = query.where(
            tuple_(Report.created_at, Report.id) > tuple_(c["t"], c["id"])
        )
    rows = (
        await db.execute(query.order_by(Report.created_at, Report.id).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [
            {
                "id": str(r.id),
                "reporter_id": str(r.reporter_id),
                "reporter_name": reporter,
                "target_type": r.target_type,
                "target_id": str(r.target_id),
                "reason": r.reason,
                "notes": r.notes,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r, reporter in rows
        ],
        "next_cursor": encode_cursor(t=rows[-1][0].created_at, id=rows[-1][0].id)
        if has_more
        else None,
    }


async def _target_author(db: DB, report: Report) -> uuid.UUID | None:
    model = {"post": Post, "review": Review, "comment": PostComment}.get(
        report.target_type
    )
    if report.target_type == "user":
        return report.target_id
    if model is None:
        return None
    return (
        await db.execute(select(model.user_id).where(model.id == report.target_id))
    ).scalar_one_or_none()


async def _remove_content(db: DB, report: Report) -> None:
    if report.target_type == "post":
        await db.execute(
            update(Post)
            .where(Post.id == report.target_id)
            .values(status="rejected", rejection_reason="Removed after report")
        )
    elif report.target_type == "review":
        review = (
            await db.execute(select(Review).where(Review.id == report.target_id))
        ).scalar_one_or_none()
        if review:
            review.status = "rejected"
            await db.flush()
            await recompute_place_rating(db, review.place_id)
    elif report.target_type == "comment":
        comment = (
            await db.execute(
                select(PostComment).where(PostComment.id == report.target_id)
            )
        ).scalar_one_or_none()
        if comment:
            await db.execute(delete(PostComment).where(PostComment.id == comment.id))
            await db.execute(
                update(Post)
                .where(Post.id == comment.post_id, Post.comment_count > 0)
                .values(comment_count=Post.comment_count - 1)
            )


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve_report(
    report_id: uuid.UUID, db: DB, admin: AdminUserID, body: ResolveReportBody
):
    report = await get_or_404(db, Report, report_id)
    if body.action == "remove_content":
        await _remove_content(db, report)
    elif body.action == "ban_user":
        author_id = await _target_author(db, report)
        if author_id:
            await db.execute(
                update(User)
                .where(User.id == author_id)
                .values(banned_at=datetime.now(UTC))
            )
            await revoke_all_sessions(db, author_id)

    report.status = "dismissed" if body.action == "dismiss" else "resolved"
    report.resolved_by = admin
    log_action(
        db,
        admin,
        f"resolve_report:{body.action}",
        "report",
        report_id,
        body.model_dump(),
    )
    await db.commit()
