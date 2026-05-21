from fastapi import APIRouter, Depends

from app.core.security import get_current_user, require_roles
from app.db.session import get_db
from app.services.alert_scheduler import run_alert_checks
from app.services.scheduler import run_scheduled_maintenance
from sqlalchemy.orm import Session

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/jobs/daily", dependencies=[Depends(require_roles("SUPERADMIN"))])
def run_daily_jobs(user=Depends(get_current_user), db: Session = Depends(get_db)):
    maintenance = run_scheduled_maintenance(db)
    alerts = run_alert_checks(db)
    return {"maintenance": maintenance, "alerts": alerts}
