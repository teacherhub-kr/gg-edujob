# 수도권에듀잡 운영 런북

이 문서는 `teacherhub-kr/gg-edujob`의 운영·장애대응 기준이다. GitHub Actions의 초록불 자체가 아니라 **서울·경기·인천 공식 채용공고의 실제 완전성, 최신성, 원문 연결성**을 서비스 건강의 기준으로 삼는다.

## 1. 데이터 흐름

정상 Fast 게시 경로:

`official sources -> scrape -> exact-link/detail enrichment -> reconcile stable IDs -> proof stamp -> publication guard -> commit jobs.json -> unified search`

핵심 단계는 다음과 같다.

1. `scripts/scrape_jobs.py`: 서울·경기 기본 수집.
2. `scripts/merge_incheon_official.py`: 인천 일반 채용게시판과 늘봄지원센터 외부강사 게시판을 모두 90일 경계까지 독립 순회한다.
3. support-office 재수집 및 링크 보강.
4. `scripts/reconcile_source_ids.py`: registry 전체의 source-native stable ID를 다시 수집하여 현재 candidate와 대조한다.
5. `scripts/stamp_reconciliation_scan.py`: 같은 scan의 proof artifact를 결속한다.
6. `scripts/validate_reconciliation_policy_v3.py`, `scripts/verify_central_reconciliation_consistency.py`, `scripts/verify_required_regions.py`: fail-closed publication guard.
7. 검증된 candidate만 `jobs.json` 등 canonical data로 게시한다.
8. unified search는 별도 검증 후 게시한다. unified 결과가 갱신됐다는 사실만으로 성공을 판정하지 않는다.

Recovery 경로는 Fast와 동일한 completeness invariant를 만족해야 한다. Recovery는 **데이터를 복구하는 workflow이지 source code를 수정하는 workflow가 아니다.** collector/hardener 변경은 별도 reviewed PR로만 수행한다.

## 2. 공식 source registry 계약

`sources.json`이 canonical official registry다.

- 경기: 경기도교육청 중앙 + 25개 교육지원청.
- 서울: 서울교육일자리포털 중앙 + 11개 교육지원청.
- 인천: 인천광역시교육청 logical central source 안에서 아래 두 official board를 모두 mandatory로 취급한다.
  - 일반 채용공고 `bbsId=1981`
  - 늘봄지원센터 개인위탁공고(외부강사) `bbsId=1534`

`missingOfficialIds=0`은 **현재 registry에 들어 있는 source들의 reconciliation 성공**만 의미한다. required official source 자체가 registry에서 빠져 있으면 completeness 증거가 아니다.

## 3. Artifact 소유권과 writer 규칙

| Artifact | Canonical/주요 writer | 허용된 보조 writer | 규칙 |
|---|---|---|---|
| `jobs.json` | `update-jobs.yml` | `recover-missing-jobs.yml` | 검증된 data candidate만 게시. source code와 같은 commit에 섞지 않는다. |
| `source_reconciliation_report.json` | Fast reconciliation | Recovery reconciliation | 같은 candidate/scan과 결속된 증거만 사용한다. |
| `source_id_ledger.json` | Fast reconciliation | Recovery reconciliation | source-native stable ID의 append-oriented evidence. |
| `central_pagination_report.json` | central verification | Recovery/Fast에서 재생성 | complete가 아니면 게시 중단. |
| `gyeonggi_central_90d_report.json` | independent Gyeonggi 90d verifier | 없음 | reconciliation crawler와 독립된 증거여야 한다. |
| `support_coverage_report.json` | support completeness gate | Recovery/Fast | 경기 25/25, 서울 11/11 및 board-level termination proof 필요. |
| `collector_status.json` | 각 collector workflow | 각 collector workflow | workflow 초록불보다 `state/stage/lastSuccessAt`와 artifact 신선도를 본다. |
| `incheon_official_report.json` | Incheon collector | Recovery/Fast | 두 mandatory board의 boardHealth를 모두 포함한다. |
| `sources.json` | reviewed code/config change | 첫 Incheon 전환 시 검증된 Fast migration | 반복적인 crawler self-patching 용도로 사용하지 않는다. |
| `unified_validation_report.json` | `unified-search.yml` | 없음 | `jobs.json`과 시간 드리프트를 별도로 감시해야 한다. |

현재 `jobs.json` 및 일부 proof artifact는 Fast/Recovery가 모두 쓸 수 있다. 따라서 publication transaction/동시성 제어와 candidate binding을 반드시 유지한다. 장기 목표는 artifact별 writer 책임을 더 좁히는 것이다.

## 4. 절대 약화하면 안 되는 불변조건

다음 값·가드는 수치만 보고 임의 완화하지 않는다.

- `LOOKBACK_DAYS = 90`: 공식 최근 공고 completeness window. `update-jobs.yml`에서도 해당 90일 필터 존재를 검증한다.
- `MAX_RECONCILIATION_AGE_HOURS = 4.0`: reconciliation proof가 이보다 오래되면 last-known-good publication을 유지한다.
- `MAX_SKEW_MINUTES = 45`: 독립 scan들의 audit window 일관성 한계.
- `scan_identity.require_scan_id()` 및 proof `scanId` binding: 서로 다른 scan의 artifact 혼합 금지.
- 경기/서울 support completeness: 경기 `25/25`, 서울 `11/11`.
- `missingAfter = 0`은 필요조건이지만 registry completeness를 대신하지 않는다.
- required regions: 서울·경기·인천 모두 registry와 runtime dataset에서 검증되어야 한다.
- 인천: `bbsId=1981`, `bbsId=1534` 두 board가 모두 access/pagination/lookback/identity 증거를 가져야 한다.

수치를 맞추기 위해 filtering, cutoff, identity 또는 guard를 완화하지 않는다. 기준 변경이 필요하면 원인과 영향, 새 completion proof를 reviewed PR에 명시한다.

## 5. M0 maintenance 상태

M0 maintenance 동안 대부분의 state-changing automatic trigger는 의도적으로 정지돼 있다. 자동 상태변경 예외는 **Fast freshness watchdog의 schedule** 하나이며, watchdog은 stale/active gate를 통과할 때에만 이미 검증된 Fast workflow를 dispatch한다.

M0 종료 전에는 일괄적으로 cron/push/workflow_run을 복원하지 않는다. 복원 순서는 다음 기준으로 별도 PR에서 결정한다.

1. production freshness와 누락 감시가 필요한 workflow인가.
2. writer 충돌 없이 단일 책임이 정의돼 있는가.
3. timeout/concurrency/backoff가 있는가.
4. 실패해도 unverified artifact를 canonical로 게시하지 않는가.
5. 무개입 1주기에서 실제 dataset이 전진하는가.

M0 해제 계획에 최소한 Fast, Recovery, Unified Search, Deep Audit, supervisor/alerting의 운영 주체와 cadence를 명시한다.

## 6. 수동 dispatch 검증 절차

M0 기간에는 dispatch-only workflow가 많다. 실행 전후에 다음을 확인한다.

1. 실행하려는 workflow와 branch/ref를 확인한다.
2. run의 `head_sha`가 검증하려는 변경을 실제 포함하는지 먼저 확인한다.
   - 로컬 git을 사용할 수 있으면 `git merge-base --is-ancestor <COMMIT> <HEAD_SHA>`로 확인한다.
3. cancelled/skipped run을 실제 실패로 분류하지 않는다.
4. success conclusion만 보지 말고 핵심 step과 artifact를 확인한다.
5. Fast의 완료 기준은 `jobs.json.updatedAt`/collector lastSuccessAt의 전진, registry completeness, reconciliation, publication guard 성공이다.
6. Recovery의 완료 기준은 fresh crawl 수행, `missing_recovery_report.json` 갱신, registry-wide reconciliation 성공, `collector_status.recovery=success`다.
7. Unified Search는 `Publish only verified unified dataset` 단계와 `unified_validation_report.json`의 validation을 같이 본다.

## 7. 장애 판정

### P0

- 서울/경기/인천 required official source가 registry에서 빠짐.
- repository watchdog freshness threshold를 넘도록 production이 갱신되지 않고 검증된 대체 게시경로도 없음.
- 현재 공식 공고가 user-visible dataset에서 실제 누락된 것이 확인됨.
- identity/dedupe/publication corruption으로 대량 누락 또는 잘못된 노출이 발생함.
- Fast와 대체 publication path가 모두 새 데이터를 게시하지 못함.

### P1

- source-level parser/pagination 실패 또는 부분 누락 위험.
- Fast production은 정상인데 Recovery/Deep Audit가 반복 실패.
- 특정 지역/source freshness 이상.
- localized publication/reconciliation/detail-link quality failure 반복.

### P2

- 현재 completeness 영향 증거가 없는 diagnostic/test/UI/운영 편의 문제.

## 8. 알려진 함정

- 과거 data workflow가 hardener를 실행하고 `scripts/*.py`를 같은 commit에 넣은 적이 있다. 수집 workflow에서 source patching을 다시 도입하지 않는다.
- bot/data commit 때문에 `HEAD`가 계속 이동할 수 있다. run의 실제 head SHA를 확인한다.
- workflow가 실패하면서 diagnostic/report 파일을 만들 수 있다. 파일 존재 또는 timestamp만으로 성공이라 판단하지 않는다.
- 90일 rolling window가 있는 서로 다른 시점의 snapshot을 단순 diff하면 자연 롤아웃이 누락처럼 보인다. support diff는 양쪽에 동일한 common temporal cutoff를 적용한 뒤 판단한다.
- HTTP 200은 현재 지원 가능한 공고라는 증거가 아니다. 접수기간/종료/선정결과 등 원문 의미를 확인한다.
- `missingOfficialIds=0`은 registry 밖 source 누락을 탐지하지 못한다.
- watchdog cron 존재만으로 publication 성공을 증명하지 않는다. 실제 dispatch와 `jobs.json` 전진을 확인한다.

## 9. 공식 원문 표본 대조

정상 판정 시 가능하면 서울·경기·인천 각각 최신 공식 공고 3건을 user-visible production dataset과 독립 대조한다.

각 표본은 최소한 다음을 기록한다.

- official source/board
- official posting ID
- title/기관
- 게시일
- 접수기간 또는 현재 유효성
- direct official URL
- production dataset 존재 여부

의심 누락은 `confirmed omission / suspected / expired / not verified`로 구분한다. 확정된 것만 실제 누락으로 센다.

## 10. GREEN 판정 체크리스트

- [ ] `sources.json`에 서울·경기·인천 required network가 모두 존재한다.
- [ ] 인천 두 mandatory board가 모두 registry와 runtime proof에 존재한다.
- [ ] production freshness가 현재 watchdog threshold 이내다.
- [ ] Fast 또는 동등한 production path의 verified publication이 확인된다.
- [ ] registry 전체 reconciliation의 `missingAfter=0`이고 모든 source가 `coverageComplete/reconciled`다.
- [ ] central pagination 및 independent proof가 complete다.
- [ ] 경기 25/25, 서울 11/11 support completeness와 exact link가 확인된다.
- [ ] identity collision/parse failure가 현재 publication에 영향을 주지 않는다.
- [ ] 서울·경기·인천 최신 공식공고 표본대조에서 confirmed omission이 없다.
- [ ] cancelled/skipped run을 오류로 오분류하지 않았다.

하나라도 completeness 핵심 조건을 만족하지 못하면 Actions가 초록색이어도 GREEN으로 판정하지 않는다.

## 11. 운영 주체와 변경 원칙

- **검증/감사:** ChatGPT 또는 운영자가 registry, production, Actions, 공식 원문을 교차검증한다.
- **코드 변경:** 가능한 한 작은 reviewed PR로 수행한다. collector data workflow가 source를 스스로 고치게 하지 않는다.
- **Codex:** 광범위한 refactor, 대량 파일 정리처럼 직접 변경보다 전문 코드 작업이 유리할 때만 제한적으로 사용한다.
- **사람 확인이 필요한 작업:** 위험도가 높은 대규모 삭제·역할이 끝난 workflow 제거 등은 목록과 영향 검토 후 시행한다.

운영의 최종 기준은 “workflow가 실행됐는가”가 아니라 **공식 공고가 빠짐없이, 정확한 direct source identity와 함께 사용자에게 최신 상태로 노출되는가**다.
