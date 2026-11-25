/* Regression tests: only live recruitment appears on the Edujob search UI. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');

const source = fs.readFileSync('app.js', 'utf8');
const start = source.indexOf('const today0=');
const end = source.indexOf('function postingLink', start);
assert(start > 0 && end > start, 'Date and activeJob helpers must be present');
const helpers = source.slice(start, end);

function at(instant) {
  class FrozenDate extends Date {
    static now() { return Date.parse(instant); }
  }
  return new Function('Date', helpers + '\nreturn {activeJob,deadlineLabel,dayDiff};')(FrozenDate);
}

const beforeCutoff = at('2026-11-25T07:59:00Z'); // 16:59 KST
const afterCutoff = at('2026-11-25T08:01:00Z');  // 17:01 KST
const j = (applyEnd, more = {}) => ({ applyEnd, statusGroup: 'current', registered: '2026-11-20', ...more });

assert.equal(beforeCutoff.activeJob(j('2026-11-25 17:00')), true);
assert.equal(afterCutoff.activeJob(j('2026-11-25 17:00')), false,
  'same-day 17:00 cutoff must close after 17:00 KST');
assert.equal(afterCutoff.activeJob(j('2026-11-25T17:00:00')), false);
assert.equal(afterCutoff.activeJob(j('2026-11-25')), true,
  'date-only deadline is allowed through the closing date');
assert.equal(afterCutoff.activeJob(j('2026-11-24')), false);
assert.equal(afterCutoff.activeJob(j('2026-11-26')), true);
assert.equal(afterCutoff.activeJob(j('', { statusGroup: 'closed' })), false,
  'missing deadline must not resurrect explicitly closed jobs');
assert.equal(afterCutoff.activeJob(j('', { statusLabel: '접수마감' })), false);
assert.equal(afterCutoff.activeJob(j('', { statusGroup: 'deadline-unknown', registered: '2026-11-10' })), false);
assert.equal(afterCutoff.activeJob(j('', { statusGroup: 'deadline-unknown', registered: '2026-11-25' })), true);
assert.match(afterCutoff.deadlineLabel(j('')), /마감일 미확인/);
assert(!/\br\.active\b/.test(source),
  'cached isActive flags should never persist across date changes');
assert(source.includes("visibilitychange"),
  'returning to the tab must refresh expired results');

for (const title of [
  '[푸른솔유치원] 방과후 인력 채용(2차)(접수마감)',
  '평택새빛초등학교 강사 구인 [구인완료]',
  '대신초병설유치원 운영 인력 모집 재공고(채용마감)',
  '방과후·돌봄 자원봉사자 모집 공고(2차)-접수 마감',
]) {
  assert.equal(afterCutoff.activeJob(j('2027-01-04', { title })), false,
    'explicit title closure must override future deadline: ' + title);
}
for (const title of [
  '2027년 서류 접수 마감일 변경 안내',
  '기간제교사 채용 공고(2차)',
  '서류 접수마감 시간 18시 공지',
]) {
  assert.equal(afterCutoff.activeJob(j('2027-01-04', { title })), true,
    'ordinary deadline notice must not be falsely classified as closed: ' + title);
}
console.log('Closed and expired recruitment UI gates verified for KST cutoff and midnight');
