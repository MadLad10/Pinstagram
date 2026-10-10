from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.deps import DB, CurrentUserID
from app.models.report import Report
from app.schemas.social import ReportCreate

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", status_code=201)
async def create_report(body: ReportCreate, user_id: CurrentUserID, db: DB):
    report = Report(
        reporter_id=user_id,
        status="open",
        created_at=datetime.now(UTC),
        **body.model_dump(),
    )
    db.add(report)
    await db.commit()
    return {"id": str(report.id)}
