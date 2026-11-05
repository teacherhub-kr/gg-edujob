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
  function render(status){
    if(typeof document==='undefined')return;
    var main=document.getElementById('appMain');
    if(!main)return;
    var existing=document.getElementById('officialFreshnessNotice');
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
    if(!existing)main.insertBefore(box,main.firstChild);
  }
  async function start(){
    try{
      var response=await fetch('./collector_status.json',{cache:'no-store',credentials:'same-origin'});
      if(!response.ok)throw Error('status not available');
      render(classify(await response.json(),Date.now()));
    }catch(error){render({status:'unknown',lastVerified:null});}
  }
  if(typeof module==='object'&&module.exports)module.exports={classify:classify,verifiedAt:verifiedAt};
  if(typeof document!=='undefined'){
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});
    else start();
  }
})(typeof globalThis!=='undefined'?globalThis:this);
