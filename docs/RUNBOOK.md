# 수도권에듀잡 무인 운영 런북

## 운영 목표

수도권에듀잡은 서울·경기·인천 공식 교육채용 공고를 신선하고 완전하게 유지하되, 실패한 후보 데이터가 사용자에게 게시되지 않도록 한다. 사이트는 last-known-good 정적 데이터로 계속 서비스하며, 자동화 실패의 기본 결과는 사이트 다운이 아니라 데이터 갱신 보류다.

## 단일 자동 제어기

자동 schedule은 `.github/workflows/fast-refresh-watchdog.yml` 하나가 소유한다. writer workflow에 개별 cron을 복구하지 않는다. watchdog은 30분마다 상태를 읽고 아래 우선순위에서 정확히 한 작업만 dispatch한다.

1. `update-jobs.yml` — Fast verified publication
2. `recover-missing-jobs.yml` — 실패한 completeness 증거 복구
3. `official-completeness-audit.yml` — 일일 독립 공식 source 대사
4. `unified-search.yml` — `jobs.json` 이후 검색 데이터 동기화

동시에 writer가 실행 중이면 아무것도 새로 시작하지 않는다.

## 성공 계약

- 서울·경기·인천 canonical registry가 모두 존재해야 한다.
- 인천은 일반 채용공고와 늘봄지원센터 외부강사 게시판을 모두 필수로 본다.
- Fast last success가 repository freshness 임계(현재 3시간 15분) 안에 있어야 한다.
- reconciliation의 `missingAfter=0`은 registry 내부 대사 성공일 뿐 registry completeness 증거로 대체하지 않는다.
- independent completeness audit와 공식 원문 표본대조가 별도로 존재해야 한다.
- candidate 검증 실패 시 last-known-good를 보존한다.

## Circuit breaker

GitHub Actions의 실제 workflow run history를 상태 저장소로 사용한다. 별도 상태 커밋을 만들지 않는다.

- `failure`, `timed_out`, `startup_failure`만 실제 실패로 센다.
- `cancelled`, `skipped`, `neutral`은 실패 연속횟수에 포함하지 않는다.
- 같은 workflow가 최근 성공 이후 실제 실패 3회에 도달하면 자동 재시도를 일시 중단한다.
- Fast: 6시간, Recovery: 12시간, Completeness: 6시간, Unified: 6시간 backoff.
- collector 코드가 수정되면 Fast는 backoff 중에도 controlled probe 1회를 허용한다.
- 새 probe가 다시 실패하면 마지막 실패시각 기준으로 circuit이 다시 닫힌다.

## 자동 GitHub 이슈

### P0 production incident

다음 중 하나면 `[AUTO][P0] Production recruitment pipeline incident` 이슈를 한 개만 연다.

- 필수 3개 지역 registry 불완전
- Fast 성공 증거 없음
- Fast 성공 후 6시간 초과
- Fast circuit breaker open

조건이 정상으로 돌아오면 자동으로 완료 처리한다.

### P1 source-volume anomaly

`source_reconciliation_report.json`을 직전 committed report와 비교한다.

- `coverageComplete=false`
- `accessErrors>0`
- 이전 5건 이상이던 source가 0건
- 이전 20건 이상이던 source가 25% 이하로 급락

위 조건은 조기경보다. confirmed omission 판정은 completeness audit와 공식 원문 대조가 담당한다. 정상 범위로 복귀하면 이슈를 자동 종료한다.

## 주간 heartbeat

월요일 09시 이후 첫 watchdog run은 `[AUTO][WEEKLY] YYYY-Www operations heartbeat` 이슈를 한 번 생성하고 정상 heartbeat이면 즉시 완료 처리한다. 기록에는 Fast freshness, registry 상태, source anomaly 수, workflow 수, workflow별 연속 실제 실패 수가 남는다.

## 공식 원문 독립 대조

ChatGPT 컨트롤타워는 GitHub 내부 reconciliation과 별도로 서울·경기·인천 최신 공식공고 표본을 production 데이터와 대조한다. 자동 reconciliation이 초록색이어도 이 검증을 생략하지 않는다.

## 소스코드 변경 원칙

- 데이터 workflow는 `scripts/*.py`를 수정하거나 커밋하지 않는다.
- parser/hardener 변경은 branch/PR + regression test를 통해 반영한다.
- source count를 숫자로 하드코딩하지 않고 canonical registry에서 계산한다.
- force push, secrets/credentials, branch protection, 파괴적 데이터 재작성은 자동화하지 않는다.
- UX 또는 정책적 선택이 필요한 대규모 기능은 자동 merge하지 않는다.

## workflow 다이어트

장기 목표는 workflow 수를 줄이는 것이다. `probe-*`, `hotfix-*`, `install-*`, debug/one-off workflow는 주간 구조 감사에서 다음을 모두 만족할 때 제거 후보가 된다.

1. production watchdog에서 참조하지 않음
2. 다른 active workflow에서 dispatch/reuse하지 않음
3. 최근 운영 장애의 유일한 진단수단이 아님
4. 동일 회귀검사가 PR CI 또는 canonical audit에 흡수돼 있음

삭제는 한꺼번에 하지 않고 작은 PR 단위로 수행한다.

## 사람이 개입해야 하는 경계

자동 감시와 진단은 읽기·검색·분석까지 자동으로 수행한다. 컨트롤타워는 문제를 발견하면 원인, 최소 수정안, 영향 범위, 위험, rollback 가능성, 검증방법, 완료조건까지 준비한다.

다음 write action은 사용자 승인 후에만 수행한다.

- branch/commit/push/PR 생성·수정·merge
- workflow rerun/cancel
- repository 설정·권한·secrets/branch protection 변경
- production 데이터 변경
- 코드·파일 삭제 또는 파괴적 데이터 재작성

공식 사이트 구조가 바뀌어 parser 자체를 새로 설계해야 하는 경우, 공식 원문을 보아도 채용공고 포함 여부가 정책적으로 모호한 경우, 대규모 파괴적 마이그레이션은 특히 명시적 승인 대상으로 본다.

명확한 P0/P1/P2 운영 결함도 컨트롤타워가 자동으로 merge하지 않는다. 점검 → 원인 분석 → 최소 수정안 → 테스트·검증계획 → 완료조건까지 준비한 뒤, 사용자 승인 후 실제 변경을 실행하고 production을 재검증한다.
