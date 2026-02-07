# Tech Radar Pipeline

Weekly pipeline that fetches allowlisted sources, stores items in the DB, and generates a Markdown report in `/docs/tech-radar`.

- Implemented as a Celery scheduled task: `apps.worker.tasks.tech_radar.run_tech_radar`.
- Writes reports to `docs/tech-radar/tech-radar-<week_tag>.md`.
- Creates DB rows in `tech_radar_runs`, `tech_radar_items`, and `tech_radar_reports`.
- Pipeline does NOT auto-deploy; it opens a ticket/change request for recommended upgrades.
