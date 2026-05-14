import uuid
from fastapi import APIRouter, Query
from app.core.deps import AdminUserID, DB
from app.models.report import Report
from sqlalchemy import select

router = APIRouter()


@router.get("/reports")
async def list_reports(db: DB, _admin: AdminUserID, status: str = "open", cursor: str | None = None, limit: int = Query(20, le=50)):
    import base64, json
    result = await db.execute(select(Report).where(Report.status == status).order_by(Report.created_at.asc()).limit(limit + 1))
    reports = result.scalars().all()
    has_more = len(reports) > limit
    reports = reports[:limit]
    items = [{"id": str(r.id), "reporter_id": str(r.reporter_id), "target_type": r.target_type,
              "target_id": str(r.target_id), "reason": r.reason, "notes": r.notes,
              "status": r.status, "created_at": r.created_at} for r in reports]
    next_cursor = base64.b64encode(json.dumps({"id": str(reports[-1].id)}).encode()).decode() if has_more and reports else None
    return {"items": items, "next_cursor": next_cursor}


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve_report(report_id: uuid.UUID, db: DB, _admin: AdminUserID, body: dict):
    from app.services.admin_service import log_action
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if report:
        action = body.get("action", "dismiss")
        report.status = "resolved" if action != "dismiss" else "dismissed"
        report.resolved_by = _admin
        await db.commit()
        await log_action(db, _admin, f"resolve_report:{action}", "report", report_id, body)
