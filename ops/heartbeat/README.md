# Railway heartbeat

This branch exists only to run a tiny external heartbeat for `teacherhub-kr/gg-edujob`.

- Railway cron: `:11` and `:41` UTC.
- It checks recent `Production operations watchdog` activity.
- If a watchdog run is active, it exits.
- If a watchdog run started within the last 20 minutes, it exits.
- Otherwise it dispatches only `.github/workflows/fast-refresh-watchdog.yml` on `main`.
- It never selects or dispatches Fast, Unified, Recovery, private-source, or foundation workflows directly.
- `HEARTBEAT_ENABLED` defaults to false. The service is inert until explicitly enabled.
- `GH_DISPATCH_TOKEN` must be stored only as a Railway secret variable.
