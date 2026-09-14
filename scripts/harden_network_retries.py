#!/usr/bin/env python3
"""Idempotently add standard resilient HTTP retry/backoff to crawler and verifier sessions."""
import re
import runpy
import ast
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "scripts/scrape_jobs.py",
    "scripts/repair_gyeonggi_support.py",
    "scripts/complete_support_coverage.py",
    "scripts/resolve_support_links.py",
    "scripts/enrich_support_periods.py",
    "scripts/enrich_seoul_get_fallback.py",
]
IMPORTS = "from requests.adapters import HTTPAdapter\nfrom urllib3.util.retry import Retry\n"
POLICY = '''\nRETRY_POLICY = Retry(\n    total=3, connect=3, read=3, status=3, backoff_factor=0.8,\n    status_forcelist=(408, 429, 500, 502, 503, 504),\n    allowed_methods=frozenset(("GET", "POST")),\n    respect_retry_after_header=True, raise_on_status=False,\n)\nS.mount("https://", HTTPAdapter(max_retries=RETRY_POLICY))\nS.mount("http://", HTTPAdapter(max_retries=RETRY_POLICY))\n'''
REPAIR_POLICY = '''    retry_policy = Retry(\n        total=3, connect=3, read=3, status=3, backoff_factor=0.8,\n        status_forcelist=(408, 429, 500, 502, 503, 504),\n        allowed_methods=frozenset(("GET",)),\n        respect_retry_after_header=True, raise_on_status=False,\n    )\n    session.mount("https://", HTTPAdapter(max_retries=retry_policy))\n    session.mount("http://", HTTPAdapter(max_retries=retry_policy))\n'''
VERIFIER_POLICY = '''\n    retry_policy = Retry(\n        total=3, connect=3, read=3, status=3, backoff_factor=0.8,\n        status_forcelist=(408, 429, 500, 502, 503, 504),\n        allowed_methods=frozenset(("GET", "POST")),\n        respect_retry_after_header=True, raise_on_status=False,\n    )\n    session.mount("https://", HTTPAdapter(max_retries=retry_policy))\n    session.mount("http://", HTTPAdapter(max_retries=retry_policy))\n'''

patched = 0
skipped = 0


def validate_retry(text, policy, rel):
    """Recognize a complete policy and both mounts in the same executable scope."""
    tree = ast.parse(text, filename=rel)
    compile(tree, rel, "exec")
    expected = [ast.dump(n) for n in ast.parse(textwrap.dedent(policy)).body]
    imports = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) for a in n.names if a.asname is None}
    if not {("requests.adapters", "HTTPAdapter"), ("urllib3.util.retry", "Retry")} <= imports:
        raise SystemExit(f"Incomplete retry imports in {rel}")
    for scope in (tree, *(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))):
        statements = [ast.dump(n) for n in scope.body]
        if any(statements[i:i + len(expected)] == expected for i in range(len(statements))):
            retries = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Name) and n.func.id == "Retry"]
            if len(retries) == 1:
                return
    raise SystemExit(f"Partial or unrecognized retry policy in {rel}")


def has_retry(text):
    tree = ast.parse(text)
    return any(isinstance(n, ast.Call) and (
        isinstance(n.func, ast.Name) and n.func.id in {"Retry", "HTTPAdapter"}
        or isinstance(n.func, ast.Attribute) and n.func.attr == "mount"
    ) for n in ast.walk(tree))


for rel in FILES:
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"Required retry target missing: {rel}")
    s = p.read_text(encoding="utf-8")
    original = s

    # The Gyeonggi second-pass collector intentionally owns a local session in main().
    # Harden that session explicitly: otherwise one transient 408/429/5xx/read failure
    # makes the entire fail-closed fast refresh abort even though the published baseline
    # remains valid. Retries are GET-only because this collector never mutates a source.
    if rel == "scripts/repair_gyeonggi_support.py" and "    session = requests.Session()\n" in s:
        if has_retry(s):
            validate_retry(s, REPAIR_POLICY, rel)
            patched += 1
            print("already hardened; retry validation passed", rel)
            continue
        if "from requests.adapters import HTTPAdapter" not in s:
            if "import requests\n" not in s:
                raise SystemExit(f"requests import marker missing in {rel}")
            s = s.replace("import requests\n", "import requests\n" + IMPORTS, 1)
        marker = "    session = requests.Session()\n"
        if "session.mount(\"https://\", HTTPAdapter(max_retries=retry_policy))" not in s:
            s = s.replace(marker, marker + REPAIR_POLICY, 1)
        validate_retry(s, REPAIR_POLICY, rel)
        if s != original:
            p.write_text(s, encoding="utf-8")
        patched += 1
        print("retry policy ready", rel)
        continue

    # Some enrichers use thread-local or per-request sessions. Do not rewrite those blindly.
    if "S = requests.Session()" not in s or "S.headers.update" not in s:
        if rel not in {"scripts/enrich_support_periods.py", "scripts/enrich_seoul_get_fallback.py"}:
            raise SystemExit(f"Required collector session missing: {rel}")
        print("retry policy skipped (custom/no shared session)", rel)
        skipped += 1
        continue
    if has_retry(s):
        validate_retry(s, POLICY, rel)
        patched += 1
        print("already hardened; retry validation passed", rel)
        continue
    if "from requests.adapters import HTTPAdapter" not in s:
        if "import requests\n" not in s:
            raise SystemExit(f"requests import marker missing in {rel}")
        s = s.replace("import requests\n", "import requests\n" + IMPORTS, 1)
    if "RETRY_POLICY = Retry(" not in s:
        m = re.search(r"S\.headers\.update\(\{.*?\}\)\n", s, re.S)
        if not m:
            raise SystemExit(f"Cannot locate shared session header setup in {rel}")
        s = s[:m.end()] + POLICY + s[m.end():]
    validate_retry(s, POLICY, rel)
    if s != original:
        p.write_text(s, encoding="utf-8")
    patched += 1
    print("retry policy ready", rel)

# The publication verifier intentionally rejects a fresh dataset when even one sampled
# support-office detail page is dead or mismatched. Give that live HTTP check the same
# retry/backoff protection as the collectors so a momentary timeout/5xx is not mistaken
# for a broken exact-link invariant.
verify = ROOT / "scripts/verify_jobs.py"
if not verify.exists():
    raise SystemExit("Required retry target missing: scripts/verify_jobs.py")
if verify.exists():
    s = verify.read_text(encoding="utf-8")
    original = s
    # The verifier already owns a pooled adapter. Validate its actual policy instead
    # of inserting mounts that the existing adapter immediately overwrites.
    pooled_policy = '''
    retry = Retry(total=3, connect=3, read=3, status=3, backoff_factor=0.8, status_forcelist=RETRY_STATUSES, allowed_methods=frozenset(["GET", "POST"]), raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=12, pool_maxsize=12)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    '''
    if has_retry(s):
        if "pool_connections" in s:
            validate_retry(s, pooled_policy, "scripts/verify_jobs.py")
            constants = [n for n in ast.parse(s).body if isinstance(n, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == "RETRY_STATUSES" for t in n.targets)]
            if len(constants) != 1 or ast.literal_eval(constants[0].value) != (408, 429, 500, 502, 503, 504):
                raise SystemExit("Verifier retry statuses are incomplete")
        else:
            validate_retry(s, VERIFIER_POLICY, "scripts/verify_jobs.py")
        print("already hardened; retry validation passed scripts/verify_jobs.py")
    if "from requests.adapters import HTTPAdapter" not in s:
        if "import requests\n" not in s:
            raise SystemExit("requests import marker missing in scripts/verify_jobs.py")
        s = s.replace("import requests\n", "import requests\n" + IMPORTS, 1)
    marker = "    session = requests.Session()\n"
    if not has_retry(s):
        if marker not in s:
            raise SystemExit("Verifier session marker missing in scripts/verify_jobs.py")
        s = s.replace(marker, marker + VERIFIER_POLICY, 1)
    if s != original:
        validate_retry(s, VERIFIER_POLICY, "scripts/verify_jobs.py")
        verify.write_text(s, encoding="utf-8")
    patched += 1
    print("retry policy ready scripts/verify_jobs.py")

# Keep the central population boundary on a mandatory fast/recovery path. The active-only filter
# stays disabled so recently closed postings are retained, but the crawl must not expand into
# all-history data and pollute search results with tens of thousands of stale postings.
runpy.run_path(str(ROOT / "scripts/harden_gyeonggi_central_retention.py"), run_name="__main__")

# Every fast/recovery/deep workflow already executes this hardener. Keep the Seoul row-date
# safety fix on the same mandatory path so the primary collector cannot invent a future
# registration date before sanitize_job_dates.py gets a chance to clean it up.
runpy.run_path(str(ROOT / "scripts/harden_seoul_registration_dates.py"), run_name="__main__")

if patched == 0:
    raise SystemExit("No crawler/verifier sessions were hardened; expected at least one")
print(f"network retry hardening complete: patched={patched}, skipped={skipped}")
