# External watchdog heartbeat

This component is intentionally small and decision-free.

## Contract

- Railway runs it at `:11` and `:41` UTC.
- It only reads recent runs of `.github/workflows/production-operations-watchdog.yml`.
- If a watchdog run is active, it exits.
- If a watchdog run started within the last 20 minutes, it exits.
- It validates actual main-branch schedule/dispatch history and rechecks it immediately before calling GitHub. Empty or invalid history stops with an error.
- Otherwise it dispatches only `production-operations-watchdog.yml` with `ref=main`.
- It never dispatches Fast, Unified, Recovery, private-source, or foundation writers directly.
- `HEARTBEAT_ENABLED=false` keeps the service inert.
- `GH_DISPATCH_TOKEN` belongs in Railway secrets only and must not be committed.
