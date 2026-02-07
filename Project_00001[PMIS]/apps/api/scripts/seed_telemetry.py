"""
Seed telemetry spans for local demo to trigger supervision.
"""
from app.database import SessionLocal
from app.tools.models import TelemetrySpan
from datetime import datetime, timedelta

if __name__ == '__main__':
    db = SessionLocal()
    now = datetime.utcnow()
    # create a few long-running spans
    for i in range(3):
        s = TelemetrySpan(
            correlation_id=f"demo-{i}",
            service="api",
            name="request.process",
            payload={"path": "/api/demo"},
            started_at=now - timedelta(seconds=10 + i * 2),
            ended_at=now,
        )
        db.add(s)
    db.commit()
    print("Seeded telemetry spans.")
    db.close()
