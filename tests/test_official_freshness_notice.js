'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const freshness=require('../official-freshness-notice.js');
const now=Date.parse('2026-11-05T02:00:00Z');
function item(time,complete=true){
 return {state:'success',lastSuccessAt:time,coverageEvidence:{
   sourceReconciliation:{currentComplete:complete,missingOfficialIdsFromCurrentDataset:complete?0:1}}};
}
assert.equal(freshness.classify({fast:item('2026-11-05T00:00:00Z')},now).status,'fresh');
assert.equal(freshness.classify({fast:item('2026-10-12T06:54:54Z')},now).status,'stale');
assert.equal(freshness.classify({fast:item('2026-10-12T06:54:54Z'),
 recovery:item('2026-11-05T00:00:00Z')},now).status,'fresh',
 'A verified recent recovery outranks an old Fast run');
assert.equal(freshness.classify({fast:item('2026-11-05T00:00:00Z',false)},now).status,'unknown',
 'A failed/incomplete reconciliation is never fresh evidence');
assert.equal(freshness.classify({fast:{state:'success',lastSuccessAt:'2026-11-05T00:00:00Z'}},now).status,'unknown');
assert.equal(freshness.classify({},now).status,'unknown');
assert.equal(freshness.classify(null,now).status,'unknown');
assert.equal(freshness.classify({fast:item('2030-01-01T00:00:00Z')},now).status,'unknown');
const html=fs.readFileSync('index.html','utf8');
assert(html.includes('official-freshness-notice.js?v=20261105p0'));
assert(html.includes('official-freshness-notice.css?v=20261105p0'));
assert(fs.readFileSync('official-freshness-notice.js','utf8').includes("credentials:'same-origin'"));
const linkSource=fs.readFileSync('official-freshness-notice.js','utf8');
for(const host of ['work.sen.go.kr','www.goe.go.kr','www.ice.go.kr']) {
  assert(linkSource.includes(host),'Missing official region source '+host);
}
assert(linkSource.includes("link.rel='noopener noreferrer'"),'External links must isolate opener');
assert(linkSource.includes("link.textContent=item[0]"),'Source link labels must be safe text');
console.log('Official recruitment freshness warning + official direct links: PASS');
