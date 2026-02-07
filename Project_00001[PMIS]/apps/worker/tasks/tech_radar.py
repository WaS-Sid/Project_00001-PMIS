from celery import shared_task
from datetime import datetime
from app.database import SessionLocal
from app.tools.models import TechRadarRun, TechRadarItem, TechRadarReport
import requests
import os

# Simple, allowlisted tech radar runner. In production, add HTTP client timeouts and retries.
ALLOWLISTED_SOURCES = [
    "https://raw.githubusercontent.com/nodejs/Release/main/schedule.json",
]

@shared_task(bind=True)
def run_tech_radar(self):
    db = SessionLocal()
    try:
        week_tag = datetime.utcnow().strftime("%Y-W%V")
        # idempotency: don't duplicate runs for same week_tag
        existing = db.query(TechRadarRun).filter(TechRadarRun.week_tag == week_tag).first()
        if existing:
            return {"run_id": existing.id, "created": False}

        run = TechRadarRun(week_tag=week_tag, sources=ALLOWLISTED_SOURCES)
        db.add(run)
        db.commit()
        db.refresh(run)

        items = []
        for url in ALLOWLISTED_SOURCES:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    title = url
                    summary = r.text[:2000]
                    item = TechRadarItem(run_id=run.id, url=url, title=title, summary=summary)
                    db.add(item)
                    items.append(item)
            except Exception:
                continue

        db.commit()

        # Create a simple markdown report
        reports_dir = os.path.join(os.getcwd(), "docs", "tech-radar")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"tech-radar-{week_tag}.md"
        path = os.path.join(reports_dir, filename)

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# Tech Radar {week_tag}\n\n")
            fh.write(f"Generated: {datetime.utcnow().isoformat()}\n\n")
            for it in items:
                fh.write(f"- Source: {it.url}\n")
                fh.write("```\n")
                fh.write((it.summary or "")[:1000])
                fh.write("\n```\n\n")

        report = TechRadarReport(run_id=run.id, path=path)
        db.add(report)
        db.commit()

        return {"run_id": run.id, "report_path": path}
    finally:
        db.close()
