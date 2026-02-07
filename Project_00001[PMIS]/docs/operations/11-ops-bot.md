# OpsBot (Execution Ops Agent)

OpsBot is an internal, admin-only assistant for O&M and engineering. It is controlled by the Execution Orchestrator (EO) and must not perform high-impact actions without approval.

Key behaviors:
- Admin-only access via `Role.ADMIN`.
- Deterministic arbitration: AUTO / APPROVAL_REQUIRED / ESCALATE.
- Evidence-first responses: all conclusions reference immutable artifacts.
- No shell or secret exposure.

See `apps/api/app/tools/ops_orchestrator.py` for the orchestrator scaffolding and `apps/api/app/tools` for helper tools.
