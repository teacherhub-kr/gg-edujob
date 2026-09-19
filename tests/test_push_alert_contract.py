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


# Browser filter, first-screen radar and server Push must agree on saved subject values.
ui = Path("unified-ui.js").read_text(encoding="utf-8")
radar = Path("job-radar.js").read_text(encoding="utf-8")
alerts = Path("supabase/functions/_shared/alerts.ts").read_text(encoding="utf-8")
build = Path("scripts/build_unified_search.py").read_text(encoding="utf-8")

subject_contract = {
    "국어": "국어|독서|논술",
    "영어": "영어|영어회화",
    "수학": "수학|수리",
    "과학": "과학|물리|화학|생명과학|생물|지구과학|통합과학",
    "사회·역사": "사회|역사|한국사|지리|윤리|도덕|통합사회",
    "음악": "음악|합창|오케스트라|관현악|밴드",
    "미술": "미술|디자인",
    "체육": "체육|스포츠|운동",
    "특수": "특수|특수교육",
    "보건": "보건|간호",
    "상담": "상담|전문상담|위클래스|wee",
    "사서": "사서|도서관",
    "영양": "영양|영양교사",
    "정보·컴퓨터": "정보|컴퓨터|코딩|소프트웨어|ai|인공지능",
    "유아": "유아|유치원|유치",
}
for label, terms in subject_contract.items():
    needle = f"'{label}':/(^|\\s)({terms})(\\s|$)/"
    for name, source in (("unified-ui", ui), ("job-radar", radar), ("push-alerts", alerts)):
        if needle not in source:
            raise SystemExit(f"profile matching contract drift: {name} missing {label}")

if "'사회':/(^|\\s)" in radar or "'역사':/(^|\\s)" in radar:
    raise SystemExit("radar must use the saved UI value 사회·역사, not split legacy values")
if "'사회':/(^|\\s)" in alerts or "'역사':/(^|\\s)" in alerts:
    raise SystemExit("Push must use the saved UI value 사회·역사, not split legacy values")

if "ARTS_SUBJECT_RE" not in build or "INSTRUMENT_RE.search(t) or ARTS_SUBJECT_RE.search(t)" not in build:
    raise SystemExit("official arts subject titles must map into 음악·예체능 category")

print("profile matching contract verified")


# A matching-contract upgrade must baseline silently before sending new-job alerts.
for needle in [
    "MATCH_CONTRACT_VERSION=2",
    "profileComparable",
    "stampedProfile",
]:
    if needle not in alerts:
        raise SystemExit("Push matching version contract missing: " + needle)
if "contractChanged" not in subscribe or "MATCH_CONTRACT_VERSION" not in subscribe:
    raise SystemExit("subscription endpoint must re-baseline on matching-contract upgrades")
if "contractVersion!==MATCH_CONTRACT_VERSION" not in dispatch or "seen_ids:currentIds" not in dispatch:
    raise SystemExit("dispatch must silently baseline old matching contracts before notifying")

print("Push matching migration contract verified")
