# Continuous Supervision

This document describes the Execution Orchestrator (EO) continuous supervision loop.

- Supervisor runs as a scheduled Celery task (`opsbot-supervision-every-1m`).
- It monitors telemetry spans, metrics, traces, and queue lag.
- On threshold breach, it creates an `Incident` (internal tenant), attaches evidence, and records immutable telemetry.
- Risky actions are proposed and require admin approval before execution.

See `apps/worker/tasks/supervision.py` for the implementation scaffold.
