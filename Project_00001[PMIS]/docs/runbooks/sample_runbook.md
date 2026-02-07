# Sample Runbook: High Queue Backlog

Symptoms:
- Queue backlog > 1000
- Worker CPU all cores > 80%

Checks:
- Inspect queue length via metrics
- Check worker logs for errors

Mitigation Steps:
1. Scale worker replicas (safe, idempotent)
2. Clear stuck jobs (requires approval)
3. Enable safe-mode throttling (requires approval)

Rollback:
- If scaling causes errors, revert replica count

Verification:
- p95 latency returns to baseline
- backlog decreases

Runbook ID: `rb-high-queue-backlog`
