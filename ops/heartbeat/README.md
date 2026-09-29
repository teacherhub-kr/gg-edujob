# External watchdog heartbeat

This component is intentionally small and decision-free.

## Contract

- Railway runs it at `:11` and `:41` UTC.
- It only reads recent runs of `.github/workflows/fast-refresh-watchdog.yml`.
- If a watchdog run is active, it exits.
- If a watchdog run started within the last 20 minutes, it exits.
- Otherwise it dispatches only `fast-refresh-watchdog.yml` with `ref=main`.
- It never dispatches Fast, Unified, Recovery, private-source, or foundation writers directly.
- `HEARTBEAT_ENABLED=false` keeps the service inert.
- `GH_DISPATCH_TOKEN` belongs in Railway secrets only and must not be committed.
