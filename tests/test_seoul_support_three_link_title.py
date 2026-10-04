from bs4 import BeautifulSoup
import scripts.scrape_jobs as scraper
import scripts.complete_support_coverage as coverage


def _rows():
    html = '''
    <table>
      <thead><tr><th>학교명</th><th>구분</th><th>분야1</th><th>분야2</th><th>등록일</th><th>마감일</th></tr></thead>
      <tbody>
        <tr>
          <td>서울신은초등학교병설유치원</td>
          <td><a href="#" onclick="fncDetailView('15140');">대체강사</a></td>
          <td><a href="#" onclick="fncDetailView('15140');">가을 단기방학 에듀케어 대체강사</a></td>
          <td><a href="#" onclick="fncDetailView('15140');">-</a></td>
          <td>2026.10.01</td><td>-</td>
        </tr>
        <tr>
          <td>예시초등학교</td>
          <td><a href="#" onclick="fncDetailView('15136');">기간제</a></td>
          <td><a href="#" onclick="fncDetailView('15136');">6학년</a></td>
          <td><a href="#" onclick="fncDetailView('15136');">영어</a></td>
          <td>2026.10.01</td><td>2026.10.10</td>
        </tr>
      </tbody>
    </table>'''
    soup = BeautifulSoup(html, 'html.parser')
    return soup.table, soup.tbody.find_all('tr')


def test_scraper_uses_labelled_fields_not_final_repeated_anchor():
    table, rows = _rows()
    vals = scraper.seoul_row_values(table, rows[0])
    assert scraper.seoul_seq_from_row(rows[0]) == '15140'
    assert scraper.clean(scraper.seoul_detail_anchor_for_seq(rows[0], '15140').get_text(' ', strip=True)) == '-'
    assert scraper.seoul_title_from_values(vals) == '가을 단기방학 에듀케어 대체강사'
    assert scraper.seoul_subject_from_values(vals) == '가을 단기방학 에듀케어 대체강사'


def test_two_short_fields_are_kept_and_combined():
    table, rows = _rows()
    vals = scraper.seoul_row_values(table, rows[1])
    assert scraper.seoul_title_from_values(vals) == '6학년 영어'
    assert scraper.seoul_subject_from_values(vals) == '6학년 / 영어'


def test_coverage_parser_uses_same_raw_label_evidence():
    table, rows = _rows()
    vals = coverage.seoul_values(table, rows[0])
    assert coverage.seoul_title_from_values(vals) == '가을 단기방학 에듀케어 대체강사'
    vals2 = coverage.seoul_values(table, rows[1])
    assert coverage.seoul_title_from_values(vals2) == '6학년 영어'
