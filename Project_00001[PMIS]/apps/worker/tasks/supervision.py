from celery import shared_task
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.tools.models import TelemetrySpan, Incident, IncidentSeverity

# Simple supervision task that checks for recent high-latency spans and creates incidents.
@shared_task(bind=True)
def continuous_supervision(self):
    db = SessionLocal()
    try:
        # Example threshold: any TelemetrySpan with name containing 'request' and duration > 5s in last 1 minute
        window_start = datetime.utcnow() - timedelta(minutes=5)
        spans = db.query(TelemetrySpan).filter(TelemetrySpan.started_at >= window_start).all()
        high = []
        for s in spans:
            try:
                if s.started_at and s.ended_at:
                    duration = (s.ended_at - s.started_at).total_seconds()
                    if duration > 5.0:
                        high.append((s, duration))
            except Exception:
                continue

        if high:
            # create an incident (tenant_id placeholder 'internal')
            evidence = [
                {
                    "span_id": s.id,
                    "service": s.service,
                    "name": s.name,
                    "duration": d,
                }
                for s, d in high
            ]
            incident = Incident(
                tenant_id="internal",
                created_by="opsbot",
                severity=IncidentSeverity.SEV1,
                title=f"High latency detected: {len(high)} spans",
                description="Automated supervision detected spans exceeding latency threshold.",
                evidence=evidence,
            )
            db.add(incident)
            db.commit()
            db.refresh(incident)
            return {"incident_id": incident.id, "created": True}

        return {"incident_id": None, "created": False}
    finally:
        db.close()
