/* Official recruitment freshness: public, read-only, never implies a stale feed is current. */
(function(root){
  'use strict';
  var STALE_AFTER_MS = 6 * 60 * 60 * 1000; // production_supervisor.P0_STALE_AFTER
  function verifiedAt(item){
    if(!item || item.state!=='success')return NaN;
    var evidence=item.coverageEvidence&&item.coverageEvidence.sourceReconciliation;
    if(!evidence || evidence.currentComplete!==true ||
        Number(evidence.missingOfficialIdsFromCurrentDataset)!==0)return NaN;
    var t=Date.parse(String(item.lastSuccessAt||''));
    return Number.isFinite(t)?t:NaN;
  }
  function classify(payload,nowMs){
    var now=Number.isFinite(nowMs)?nowMs:Date.now();
    if(!payload||typeof payload!=='object')return {status:'unknown',lastVerified:null};
    var times=[verifiedAt(payload.fast),verifiedAt(payload.recovery)].filter(Number.isFinite);
    if(!times.length)return {status:'unknown',lastVerified:null};
    var latest=Math.max.apply(null,times);
    if(latest>now+5*60*1000)return {status:'unknown',lastVerified:null};
    return {status:now-latest>STALE_AFTER_MS?'stale':'fresh',lastVerified:new Date(latest).toISOString()};
  }
  function classifyRegional(payload, nowMs){
    var meta=payload&&payload.regionalPublication;
    if(!meta || meta.policy!=='seoul-gyeonggi-isolated-verified-v1')return null;
    // A status marker alone is not evidence that the user-facing search
    // actually contains fresh official entries for BOTH supported provinces.
    var rows=payload&&Array.isArray(payload.jobs)?payload.jobs:[];
    var official=rows.filter(function(row){return row&&row.feedKind==='official'&&row.sourceSurface==='official';});
    var valid=meta.state==='verified' &&
      meta.refreshedOfficialSourceCount===38 &&
      Array.isArray(meta.refreshedRegions) &&
      meta.refreshedRegions.join('|')==='경기|서울' &&
      meta.heldRegions&&meta.heldRegions['인천']&&meta.heldRegions['인천'].state==='stale' &&
      official.some(function(row){return row.province==='경기';}) &&
      official.some(function(row){return row.province==='서울';}) &&
      !official.some(function(row){return row.province==='인천';});
    var then=Date.parse(String(meta.generatedAt||''));
    var now=Number.isFinite(nowMs)?nowMs:Date.now();
    return {status:valid && Number.isFinite(then) && then<=now+5*60*1000 &&
      now-then<=STALE_AFTER_MS ? 'regional-fresh':'regional-stale',
      lastVerified:Number.isFinite(then)?new Date(then).toISOString():null};
  }
  function render(status){
    if(typeof document==='undefined')return;
    var main=document.getElementById('appMain');
    if(!main)return;
    var existing=document.getElementById('officialFreshnessNotice');
    if(status.status==='regional-fresh'||status.status==='regional-stale'){
      var box=existing||document.createElement('aside');
      box.id='officialFreshnessNotice';
      box.className='official-freshness-notice';
      box.setAttribute('role','status');
      box.setAttribute('aria-live','polite');
      box.replaceChildren();
      var heading=document.createElement('strong');
      heading.textContent=status.status==='regional-fresh'?
        '서울·경기 공식공고 갱신 · 인천은 보류':
        '서울·경기 공식공고 갱신 지연 · 인천은 보류';
      var detail=document.createElement('span');
      detail.textContent=(status.lastVerified?
        '서울·경기 마지막 검증: '+new Intl.DateTimeFormat('ko-KR',{
          timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',
          hour:'2-digit',minute:'2-digit',hour12:false
        }).format(new Date(status.lastVerified))+'. ':'')+
        '인천교육청 공식공고는 갱신을 중단했으며 최신 공고가 이 검색에 포함되지 않습니다. 지원 전 채용기관 원문을 확인하세요.';
      box.appendChild(heading);box.appendChild(detail);
      var link=document.createElement('a');
      link.href='https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997';
      link.target='_blank';link.rel='noopener noreferrer';link.textContent='인천교육청 원문 보기';
      box.appendChild(link);
      if(!existing)main.insertBefore(box,main.firstChild);
      return;
    }
    if(status.status==='fresh'){if(existing)existing.remove();return;}
    var box=existing||document.createElement('aside');
    box.id='officialFreshnessNotice';
    box.className='official-freshness-notice';
    box.setAttribute('role','alert');
    box.setAttribute('aria-live','polite');
    box.replaceChildren();
    var heading=document.createElement('strong');
    var detail=document.createElement('span');
    if(status.status==='stale'){
      heading.textContent='공식공고 갱신 지연 안내';
      var dateText='확인 불가';
      try{dateText=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',
        month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})
        .format(new Date(status.lastVerified));}catch(e){}
      detail.textContent='마지막 검증된 공식공고 수집: '+dateText+
        '. 화면에 새 공고가 누락될 수 있습니다. 지원 전 반드시 채용기관 원문을 확인하세요.';
    }else{
      heading.textContent='공식공고 갱신 상태를 확인할 수 없습니다';
      detail.textContent='현재 표시된 공고의 최신성을 보장할 수 없습니다. 지원 전 반드시 채용기관 원문을 확인하세요.';
    }
    box.appendChild(heading);
    box.appendChild(detail);
    var links=document.createElement('nav');
    links.className='official-freshness-links';
    links.setAttribute('aria-label','최신 공식 채용 공고 원문 바로가기');
    [
      ['서울교육일자리포털','https://work.sen.go.kr/work/search/recInfo/BD_selectSrchRecInfo.do?type=term'],
      ['경기도교육청 구인구직','https://www.goe.go.kr/recruit/ad/func/pb/hnfpPbancList.do?mi=10502'],
      ['인천교육청 채용공고','https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997'],
      ['인천 늘봄강사 공고','https://www.ice.go.kr/afterschool/na/ntt/selectNttList.do?bbsId=1534&mi=10571']
    ].forEach(function(item){
      var link=document.createElement('a');
      link.href=item[1];link.textContent=item[0];
      link.target='_blank';link.rel='noopener noreferrer';
      links.appendChild(link);
    });
    box.appendChild(links);
    if(!existing)main.insertBefore(box,main.firstChild);
  }
  async function start(){
    // Regional truth comes from the published search itself, not the legacy
    // 44-source collector_status.json that is intentionally frozen with Incheon.
    try{
      var unified=await fetch('./unified_jobs.json',{cache:'no-store',credentials:'same-origin'});
      if(unified.ok){
        var regional=classifyRegional(await unified.json(),Date.now());
        if(regional){render(regional);return;}
      }
    }catch(error){/* no regional proof: retain strict legacy stale warning */}
    try{
      var response=await fetch('./collector_status.json',{cache:'no-store',credentials:'same-origin'});
      if(!response.ok)throw Error('official collector status unavailable');
      render(classify(await response.json(),Date.now()));
    }catch(error){render({status:'unknown',lastVerified:null});}
  }
  if(typeof module==='object'&&module.exports)module.exports={classify:classify,classifyRegional:classifyRegional,verifiedAt:verifiedAt};
  if(typeof document!=='undefined'){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
    else start();
  }
})(typeof globalThis!=='undefined'?globalThis:this);
