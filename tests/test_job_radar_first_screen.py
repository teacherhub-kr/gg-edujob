from pathlib import Path

text = Path('job-radar.js').read_text(encoding='utf-8')

required = {
    'first-screen insertion': "main.insertBefore(box,stats)",
    'overview surface': 'jobRadarOverview',
    'profile chips': 'jobRadarProfile',
    'preview surface': 'jobRadarPreview',
    'preview limit': 'return rows.slice(0,3)',
    'safe posting-link reuse': 'const href=postingLink(j)',
    'new metric': '지난 방문 이후 신규',
    'favorites metric': '모집 중 관심공고',
    'match metric': '현재 조건 일치',
}

missing = [label for label, needle in required.items() if needle not in text]
if missing:
    raise SystemExit('first-screen radar contract missing: ' + ', '.join(missing))

if "toolbar.parentElement.insertBefore(box,toolbar)" not in text:
    raise SystemExit('fallback radar placement must remain available')

if "renderDashboard(p);" not in text:
    raise SystemExit('dashboard must refresh with radar state changes')

print('first-screen radar contract verified')
