from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.deps import CurrentUserID, DB
from app.models.report import Report
from app.schemas.social import ReportCreate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201)
async def create_report(body: ReportCreate, user_id: CurrentUserID, db: DB):
    report = Report(
        reporter_id=user_id,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        notes=body.notes,
        status="open",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(report)
    await db.commit()
    return {"id": str(report.id)}
