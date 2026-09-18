from pathlib import Path

index = Path("index.html").read_text(encoding="utf-8")
config = Path("alert-config.js").read_text(encoding="utf-8")
client = Path("alert-client.js").read_text(encoding="utf-8")
sw = Path("sw.js").read_text(encoding="utf-8")
manifest = Path("manifest.webmanifest").read_text(encoding="utf-8")
store = Path("user-store.js").read_text(encoding="utf-8")
migration = Path("supabase/migrations/20260918_create_push_subscriptions.sql").read_text(encoding="utf-8")
subscribe = Path("supabase/functions/push-subscription/index.ts").read_text(encoding="utf-8")
dispatch = Path("supabase/functions/push-dispatch/index.ts").read_text(encoding="utf-8")
workflow = Path(".github/workflows/job-alerts.yml").read_text(encoding="utf-8")

required_client = {
    "explicit config gate": "!config.enabled",
    "user-gesture permission": "Notification.requestPermission()",
    "push subscription": "pushManager.subscribe",
    "saved profile sync": "edujob:user-state-changed",
    "iOS home-screen guard": "ios-home-screen-required",
    "unsubscribe support": "action:'unsubscribe'",
    "saved-profile requirement": "profile-required",
}
missing = [name for name, needle in required_client.items() if needle not in client]
if missing:
    raise SystemExit("push client contract missing: " + ", ".join(missing))

if "enabled:true" not in config:
    raise SystemExit("push must be enabled after backend provisioning")
if "ahghkusvbfwrdmrhkgwe.supabase.co/functions/v1/push-subscription" not in config:
    raise SystemExit("live push subscription endpoint missing")
if "BIzLo7Ri325DU7t4-FUQ3T1TMRgRGn7iI8mw875ZpEHIHniQXOoUMRGHtoBCNknlcFUdFEx9i6mTlul8KVpBh1U" not in config:
    raise SystemExit("live VAPID public key missing")

positions = [index.find(x) for x in ["user-store.js", "job-radar.js", "alert-config.js", "alert-client.js"]]
if any(x < 0 for x in positions) or positions != sorted(positions):
    raise SystemExit("push scripts must load after user store and radar in deterministic order")

if 'rel="manifest"' not in index or "manifest.webmanifest" not in index:
    raise SystemExit("PWA manifest must be linked")
if '"display": "standalone"' not in manifest:
    raise SystemExit("manifest must support Home Screen standalone mode for iOS Web Push")
if "self.addEventListener('push'" not in sw or "showNotification" not in sw or "notificationclick" not in sw:
    raise SystemExit("service worker push/click contract missing")
if "alerts:'edujob.alerts.v1'" not in store:
    raise SystemExit("alert state must be stored through account-ready user store")

for needle in ["enable row level security", "revoke all", "client_token_hash", "seen_ids"]:
    if needle not in migration.lower():
        raise SystemExit("push subscription privacy contract missing: " + needle)
if "baseline-unavailable" not in subscribe or "matchingKeys(jobs,profile)" not in subscribe:
    raise SystemExit("subscribe endpoint must fail closed if current-job baseline cannot be established")
if "x-edujob-alert-secret" not in dispatch or "webpush.sendNotification" not in dispatch:
    raise SystemExit("dispatch endpoint must require secret and use Web Push sender")
if "web-push@3.6.7" not in dispatch:
    raise SystemExit("Web Push sender dependency must stay pinned")
if "contents: read" not in workflow or "ALERT_ENDPOINT" not in workflow:
    raise SystemExit("isolated alert workflow contract missing")
for forbidden in ("schedule:", "workflow_run:", "repository_dispatch:"):
    if forbidden in workflow:
        raise SystemExit("push dispatch must remain manual while M0 maintenance freeze is active: " + forbidden)
if "push" in workflow.lower() and "git push" in workflow.lower():
    raise SystemExit("alert workflow must never write to the repository")

print("web push alert contract verified")
