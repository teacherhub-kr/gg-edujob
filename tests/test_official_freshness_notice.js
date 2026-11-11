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
const regional={regionalPublication:{
 policy:'seoul-gyeonggi-isolated-verified-v1',state:'verified',
 refreshedRegions:['경기','서울'],
 refreshedOfficialSourceCount:38,heldRegions:{'인천':{state:'stale'}},
 generatedAt:'2026-11-05T00:00:00Z'
},jobs:[
 {feedKind:'official',sourceSurface:'official',province:'경기'},
 {feedKind:'official',sourceSurface:'official',province:'서울'}
]};
assert.equal(freshness.classifyRegional(regional,now).status,'regional-fresh');
assert.equal(freshness.classifyRegional(regional,now+8*60*60*1000).status,'regional-stale');
regional.jobs.splice(1,1);
assert.equal(freshness.classifyRegional(regional,now).status,'regional-stale',
 'A region without official displayed postings must not appear fresh');
regional.jobs.push({feedKind:'official',sourceSurface:'official',province:'서울'});
regional.jobs.push({feedKind:'official',sourceSurface:'official',province:'인천'});
assert.equal(freshness.classifyRegional(regional,now).status,'regional-stale',
 'Held Incheon education postings cannot masquerade as refreshed');
regional.jobs.pop();
regional.regionalPublication.heldRegions['인천'].state='fresh';
assert.equal(freshness.classifyRegional(regional,now).status,'regional-stale',
 'Incheon cannot be marked current by a regional snapshot');
const html=fs.readFileSync('index.html','utf8');
assert(html.includes('official-freshness-notice.js?v=20261111private1'));
assert(html.includes('official-freshness-notice.css?v=20261105p0'));
assert(fs.readFileSync('official-freshness-notice.js','utf8').includes("credentials:'same-origin'"));
const linkSource=fs.readFileSync('official-freshness-notice.js','utf8');
for(const host of ['work.sen.go.kr','www.goe.go.kr','www.ice.go.kr']) {
  assert(linkSource.includes(host),'Missing official region source '+host);
}
assert(linkSource.includes("link.rel='noopener noreferrer'"),'External links must isolate opener');
assert(linkSource.includes("link.textContent=item[0]"),'Source link labels must be safe text');

const priv={
 privateSources:{
   lessoninfo:{name:'레슨인포',publicationEnabled:true,count:1589,
     verificationFreshness:{state:'stale',maxAgeHours:6,evidenceAt:'2026-10-16T02:36:32+09:00'}},
   jobteacher:{name:'잡티처',publicationEnabled:true,count:4054,
     verificationFreshness:{state:'fresh',maxAgeHours:6,evidenceAt:'2026-11-05T00:00:00Z'}},
   cleaneye:{name:'클린아이',publicationEnabled:true,count:0,
     verificationFreshness:{state:'stale',maxAgeHours:24,evidenceAt:'2026-10-12T00:00:00Z'}}
 }
};
assert.deepEqual(freshness.classifyPrivate(priv,now).stale,['레슨인포']);
assert.equal(freshness.classifyPrivate(priv,now).status,'attention');
assert.equal(freshness.classifyPrivate({privateSources:{}},now).status,'fresh');
assert.equal(freshness.classifyPrivate({},now).status,'unknown');
priv.privateSources.lessoninfo.verificationFreshness={
 state:'fresh',maxAgeHours:6,evidenceAt:'2026-11-05T00:00:00Z'
};
assert.equal(freshness.classifyPrivate(priv,now).status,'fresh');
assert.equal(freshness.classifyPrivate(priv,now+8*60*60*1000).status,'attention',
 'Client must not trust stale server-side freshness classification after UI TTL expires');
priv.privateSources.jobteacher.verificationFreshness={
 state:'unknown',maxAgeHours:6,evidenceAt:null
};
assert.deepEqual(freshness.classifyPrivate(priv,now).unverified,['잡티처']);

console.log('Official+private recruitment freshness warnings + official direct links: PASS');
