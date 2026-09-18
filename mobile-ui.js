(()=>{
  // index.html may include this bundle more than once while cache-busting versions overlap.
  // Make initialization idempotent so duplicate loads cannot attach duplicate click handlers.
  if(window.__edujobMobileUiLoaded)return;
  window.__edujobMobileUiLoaded=true;

  // Range selection now lives below the search box in edujob-refresh.js.
  // Remove any legacy top tabs left in the DOM by an older cached bundle.
  const legacyTabs=document.getElementById('edujobTabs');
  if(legacyTabs)legacyTabs.remove();

  // Search results must open the exact posting, not a source's generic list page.
  // Reconstruct known private-source detail URLs from stable identities when needed,
  // and refuse a list/home fallback for those sources if no exact detail identity exists.
  const basePostingLink=typeof postingLink==='function'?postingLink:null;
  const sidText=j=>String(j?.sourceIdentity||'');
  const isLessoninfoCulture=j=>j?.source==='레슨인포'&&j?.sourceSurface==='culture-arts';
  const verifiedLessoninfoCulture=j=>{
    if(!isLessoninfoCulture(j))return null;
    if(j?.sourceIdentity==='culture:id:94673'||j?.detailLinkVerified!==true)return '';
    return String(j?.verifiedUrl||'').trim();
  };
  const knownPrivate=j=>/^(?:artmore|jobteacher|gonggonggangsa|culture:id|board):/.test(sidText(j))||['아트모아','잡티처','공공강사','레슨인포'].includes(String(j?.source||''));
  const validPrivateCandidate=(j,raw)=>{
    if(!raw)return '';
    try{
      const u=new URL(String(raw),location.href),sid=sidText(j),src=String(j?.source||'');
      if(sid.startsWith('artmore:')||src==='아트모아')return /\/sub\/recruit\/search_view\.do$/.test(u.pathname)&&/^\d+$/.test(u.searchParams.get('rec_idx')||'')?u.href:'';
      if(sid.startsWith('jobteacher:')||src==='잡티처')return /\/employ\/detail\/\d+\/?$/.test(u.pathname)?u.href:'';
      if(sid.startsWith('gonggonggangsa:')||src==='공공강사')return /\/recruitments\/\d+\/?$/.test(u.pathname)?u.href:'';
      if(sid.startsWith('culture:id:')||src==='레슨인포'){
        if(/\/culture-jobs\/detail\.php$/.test(u.pathname)&&/^\d+$/.test(u.searchParams.get('id')||''))return u.href;
        if(/\/board\/board\.php$/.test(u.pathname)&&u.searchParams.get('bo_table')&&/^\d+$/.test(u.searchParams.get('wr_no')||''))return u.href;
        return '';
      }
    }catch(e){}
    return '';
  };
  const reconstructedPrivateDetail=j=>{
    const sid=sidText(j),candidates=[j?.detailUrl,j?.originalUrl,j?.openUrl,j?.url];
    for(const raw of candidates){const valid=validPrivateCandidate(j,raw);if(valid)return valid}
    let m=sid.match(/^artmore:(\d+)$/);if(m)return `https://www.artmore.kr/sub/recruit/search_view.do?rec_idx=${m[1]}`;
    m=sid.match(/^jobteacher:(\d+)$/);if(m)return `https://www.jobteacher.kr/employ/detail/${m[1]}`;
    m=sid.match(/^gonggonggangsa:(\d+)$/);if(m)return `https://00gangsa.com/recruitments/${m[1]}`;
    m=sid.match(/^culture:id:(\d+)$/);if(m)return `https://www.lessoninfo.co.kr/culture-jobs/detail.php?id=${m[1]}`;
    m=sid.match(/^board:([^:]+):(\d+)$/);if(m)return `https://www.lessoninfo.co.kr/board/board.php?bo_table=${encodeURIComponent(m[1])}&wr_no=${m[2]}`;
    return '';
  };
  if(basePostingLink){
    postingLink=function(j){
      // Culture-arts is never reconstructed from a stable ID. Its independent cold-browser
      // verdict is authoritative and may intentionally point to a verified external detail.
      const culture=verifiedLessoninfoCulture(j);
      if(culture!==null)return culture;
      if(j?.detailLinkVerified===false)return '';
      if(j?.feedKind==='private'&&knownPrivate(j))return reconstructedPrivateDetail(j);
      return basePostingLink(j);
    };
  }

  // Expose an explicit readiness marker so deployed black-box tests can wait until all
  // frontend wrappers have finished installing before testing link policy.
  window.__edujobMobileUiReady='20260907d';

  const bp=900;
  const panel=document.querySelector('.filter-panel');if(!panel)return;
  const head=panel.querySelector('.filter-head');if(!head)return;
  let btn=document.getElementById('mobileFilterToggle');
  if(!btn){btn=document.createElement('button');btn.type='button';btn.id='mobileFilterToggle';btn.className='mobile-filter-toggle';btn.setAttribute('aria-controls','mobileFilters');head.appendChild(btn)}
  panel.id=panel.id||'mobileFilters';
  const apply=()=>{const mobile=window.matchMedia(`(max-width:${bp}px)`).matches;if(mobile){if(!panel.dataset.mobileInit){panel.classList.add('mobile-collapsed');panel.dataset.mobileInit='1'}btn.hidden=false;btn.setAttribute('aria-expanded',String(!panel.classList.contains('mobile-collapsed')));btn.textContent=panel.classList.contains('mobile-collapsed')?'필터 열기':'필터 닫기'}else{panel.classList.remove('mobile-collapsed');delete panel.dataset.mobileInit;btn.hidden=true;btn.setAttribute('aria-expanded','true')}};
  btn.addEventListener('click',()=>{panel.classList.toggle('mobile-collapsed');btn.setAttribute('aria-expanded',String(!panel.classList.contains('mobile-collapsed')));btn.textContent=panel.classList.contains('mobile-collapsed')?'필터 열기':'필터 닫기'});
  window.addEventListener('resize',apply,{passive:true});apply();
})();