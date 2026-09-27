import sys
sys.path.insert(0, "scripts")

from build_unified_search import categories

def assert_has(title):
    cats = categories(title, "official", "통합게시판")
    assert "음악·예체능" in cats, (title, cats)

for title in (
    "운암고등학교 기간제 교사(음악) 채용 공고",
    "중학교 미술 기간제교원 채용",
    "고등학교 체육교사 채용",
    "예체능 프로그램 무용 강사 모집",
    "연극영화 교과 강사 채용",
):
    assert_has(title)

assert "음악·예체능" not in categories("중학교 수학 기간제교원 채용", "official", "통합게시판")

print("unified arts category semantics verified")
