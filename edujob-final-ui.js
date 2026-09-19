(()=>{
  if(window.__edujobFinalUiLoaded)return;
  window.__edujobFinalUiLoaded=true;

  const qs=(s,p=document)=>p.querySelector(s);
  const qsa=(s,p=document)=>[...p.querySelectorAll(s)];
  const esc=s=>(s??'').toString().replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  const icon=name=>{
    const c='viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
    if(name==='home')return `<svg ${c}><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></svg>`;
    if(name==='search')return `<svg ${c}><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>`;
    if(name==='radar')return `<svg ${c}><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3"/></svg>`;
    if(name==='heart')return `<svg ${c}><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>`;
    if(name==='user')return `<svg ${c}><circle cx="12" cy="8" r="4"/><path d="M4 21c.8-4.2 3.5-6.5 8-6.5s7.2 2.3 8 6.5"/></svg>`;
    if(name==='bell')return `<svg ${c}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></svg>`;
    if(name==='menu')return `<svg ${c}><path d="M4 6h16M4 12h16M4 18h16"/></svg>`;
    if(name==='filter')return `<svg ${c}><path d="M4 5h16l-6 7v6l-4 2v-8z"/></svg>`;
    if(name==='bookmark')return `<svg ${c}><path d="M6 3h12v18l-6-4-6 4z"/></svg>`;
    if(name==='settings')return `<svg ${c}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.1A1.7 1.7 0 0 0 8 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 3.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H2v-4h.1A1.7 1.7 0 0 0 3.6 8a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 8 3.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V2h4v.1A1.7 1.7 0 0 0 15 3.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 8c.2.4.6.8 1 1 .3.2.7.3 1.1.3h.1v4h-.1c-.4 0-.8.1-1.1.3-.4.2-.8.6-1 1.4Z"/></svg>`;
    return '';
  };

  function installHeaderActions(){
    const top=qs('.top');
    if(!top||qs('#finalHeaderActions'))return;
    const actions=document.createElement('div');
    actions.id='finalHeaderActions';
    actions.className='final-header-actions';
    actions.innerHTML=`<button type="button" id="finalAlertButton" aria-label="알림 설정">${icon('bell')}</button><button type="button" id="finalMenuButton" aria-label="메뉴 열기">${icon('menu')}</button>`;
    top.appendChild(actions);
    qs('#finalAlertButton')?.addEventListener('click',()=>qs('#jobRadarAlerts')?.click());
    qs('#finalMenuButton')?.addEventListener('click',()=>{
      activate('mypage');
      setTimeout(()=>qs('#finalMyPage')?.scrollIntoView({behavior:'smooth',block:'start'}),0);
    });
  }

  function installSearchClear(){
    const box=qs('.searchbox'), input=qs('#q'), button=qs('#searchBtn');
    if(!box||!input||!button||qs('#finalSearchClear'))return;
    const clear=document.createElement('button');
    clear.type='button';clear.id='finalSearchClear';clear.className='final-search-clear';clear.setAttribute('aria-label','검색어 지우기');clear.textContent='×';
    box.insertBefore(clear,button);
    clear.addEventListener('click',()=>{
      input.value='';
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.focus();
    });
    const sync=()=>clear.classList.toggle('show',Boolean(input.value));
    input.addEventListener('input',sync);sync();
  }

  function installHeadingLinks(){
    const status=qs('#statusHeading'), jobs=qs('#jobsHeading');
    if(status&&!qs('.final-heading-link',status)){
      const b=document.createElement('button');b.type='button';b.className='final-heading-link';b.textContent='전체보기 ›';b.addEventListener('click',()=>activate('search'));status.appendChild(b);
    }
    if(jobs&&!qs('.final-heading-link',jobs)){
      const b=document.createElement('button');b.type='button';b.className='final-heading-link';b.textContent='전체보기 ›';b.addEventListener('click',()=>activate('search'));jobs.appendChild(b);
    }
  }

  function ensureFavoriteMode(on){
    const btn=qs('#jobRadarFavorites');
    if(!btn)return;
    const active=btn.classList.contains('primary');
    if(active!==on)btn.click();
  }

  function profile(){try{return window.EduJobUserStore?.profile?.get?.()||null}catch{return null}}
  function alerts(){try{return window.EduJobUserStore?.alerts?.get?.()||{enabled:false}}catch{return {enabled:false}}}
  function favorites(){try{return window.EduJobUserStore?.favorites?.get?.()||[]}catch{return []}}
  function snapshot(){try{return window.EduJobUserStore?.snapshot?.get?.()||null}catch{return null}}

  const fmtValues=(label,values)=>{
    const a=Array.isArray(values)?values.filter(Boolean):[];
    return a.length?`<span class="final-profile-chip"><b>${esc(label)}</b> ${esc(a.slice(0,3).join(' · '))}${a.length>3?` +${a.length-3}`:''}</span>`:'';
  };

  function radarManagerHtml(){
    const p=profile(), a=alerts();
    const newCount=qs('#jobRadarOverview .job-radar-metric b')?.textContent?.trim()||'0';
    const favCount=favorites().length;
    const saved=p?1:0;
    const chips=p?[fmtValues('지역',p.regions),fmtValues('학교급',p.schools),fmtValues('직종',p.types),fmtValues('과목',p.subjects),p.q?`<span class="final-profile-chip"><b>검색</b> “${esc(p.q)}”</span>`:''].filter(Boolean).join(''):'';
    return `<section class="final-radar-manager" aria-label="내 채용 레이더 관리">
      <div class="final-page-head"><div><h2>🎯 내 채용 레이더</h2><p>내가 원하는 조건에 맞는 공고를 자동으로 찾아드려요.</p></div><img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"></div>
      <div class="final-segment"><button type="button" class="active">내 조건</button><button type="button" id="finalRadarMatched">맞춤 공고</button></div>
      <div class="final-manager-card">
        <div class="final-manager-title"><strong>저장된 검색 조건 (${saved})</strong><button type="button" id="finalAddCondition">＋ 새 조건 추가</button></div>
        ${p?`<div class="final-saved-condition"><div><strong>${esc(p.q||'저장한 채용 조건')}</strong><p>${chips||'저장한 조건을 불러와 사용할 수 있습니다.'}</p><em>새 공고 ${esc(newCount)}건 · 관심공고 ${favCount}건</em></div><button type="button" class="final-switch on" id="finalApplySaved" aria-label="저장 조건 불러오기"></button></div>`:`<div class="final-empty-condition"><strong>저장된 조건이 없습니다.</strong><p>공고검색에서 원하는 조건을 선택한 뒤 저장해 주세요.</p></div>`}
      </div>
      <div class="final-manager-card final-alert-setting"><div>${icon('bell')}<div><strong>알림 설정</strong><p>새로운 공고가 등록되면 바로 알려드릴게요.</p></div></div><button type="button" class="final-switch ${a.enabled?'on':''}" id="finalAlertToggle" aria-label="새 공고 알림 ${a.enabled?'켜짐':'꺼짐'}"></button></div>
      <div class="final-radar-tip"><img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"><div><strong>내 조건에 딱 맞는 좋은 기회를 찾아드릴게요!</strong><p>새로운 공고 자동 확인 · 조건별 맞춤 알림 · 관심 공고와 쉽게 비교</p></div></div>
    </section>`;
  }

  function installRadarManager(){
    let holder=qs('#finalRadarManager');
    if(!holder){
      holder=document.createElement('div');holder.id='finalRadarManager';holder.className='final-view-panel';
      qs('main.wrap')?.appendChild(holder);
    }
    holder.innerHTML=radarManagerHtml();
    qs('#finalAddCondition')?.addEventListener('click',()=>activate('search'));
    qs('#finalApplySaved')?.addEventListener('click',()=>qs('#jobRadarApply')?.click());
    qs('#finalAlertToggle')?.addEventListener('click',()=>qs('#jobRadarAlerts')?.click());
    qs('#finalRadarMatched')?.addEventListener('click',()=>{activate('search');qs('#jobRadarApply')?.click()});
  }

  function myPageHtml(){
    const p=profile(), fav=favorites(), snap=snapshot(), a=alerts();
    const savedCount=p?1:0;
    const seenCount=Array.isArray(snap?.keys)?snap.keys.length:0;
    return `<section class="final-my-page" aria-label="마이페이지">
      <div class="final-profile-card"><div class="final-avatar">${icon('user')}</div><div><strong>선생님</strong><p>안녕하세요!</p></div><span class="final-profile-gear">${icon('settings')}</span></div>
      <div class="final-my-stats"><div><span>저장핔 공고</span><b>${fav.length}</b></div><div><span>저장한 조건</span><b>${savedCount}</b></div><div><span>확인한 맞춤공고</span><b>${seenCount}</b></div></div>
      <div class="final-menu-card">
        <button type="button" data-action="profile">${icon('user')}<span>내 정보 관리</span><em>›</em></button>
        <button type="button" data-action="alerts">${icon('bell')}<span>알림 설정 ${a.enabled?'· 켜짐':''}</span><em>›</em></button>
        <button type="button" data-action="saved">${icon('bookmark')}<span>저장한 조건</span><em>›</em></button>
        <button type="button" data-action="favorites">${icon('heart')}<span>관심공고</span><em>›</em></button>
        <button type="button" data-action="search">${icon('search')}<span>공고검색</span><em>›</em></button>
      </div>
      <div class="final-menu-card final-menu-card-secondary">
        <button type="button" data-action="guide"><span>▣</span><span>이용 가이드</span><em>›</em></button>
        <button type="button" data-action="about"><span>ⓘ</span><span>서비스 소개</span><em>›</em></button>
      </div>
      <p class="final-my-note">서울·경기·인천 교육 채용공고를 한곳에서 확인하세요.</p>
    </section>`;
  }

  function installMyPage(){
    let holder=qs('#finalMyPage');
    if(!holder){holder=document.createElement('div');holder.id='finalMyPage';holder.className='final-view-panel';qs('main.wrap')?.appendChild(holder)}
    holder.innerHTML=myPageHtml();
    qsa('[data-action]',holder).forEach(btn=>btn.addEventListener('click',()=>{
      const action=btn.dataset.action;
      if(action==='alerts')qs('#jobRadarAlerts')?.click();
      else if(action==='saved')activate('radar');
      else if(action==='favorites')activate('favorites');
      else if(action==='search')activate('search');
      else if(action==='guide'||action==='about')window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});
    }));
  }

  function installNav(){
    let nav=qs('#edujobMobileNav');
    if(!nav){nav=document.createElement('nav');nav.id='edujobMobileNav';document.body.appendChild(nav)}
    nav.className='edujob-mobile-nav final-mobile-nav';
    nav.setAttribute('aria-label','주요 메뉴');
    nav.innerHTML='';
    [['home','홈','home'],['search','공고검색','search'],['radar','내 채용 레이더','radar'],['heart','관심공고','favorites'],['user','마이페이지','mypage']].forEach(([ic,label,view])=>{
      const b=document.createElement('button');b.type='button';b.dataset.view=view;b.innerHTML=icon(ic)+`<span>${label}</span>`;b.addEventListener('click',()=>activate(view));nav.appendChild(b);
    });
  }

  function activate(view){
    if(!['home','search','radar','favorites','mypage'].includes(view))view='home';
    if(view==='favorites')ensureFavoriteMode(true);else ensureFavoriteMode(false);
    document.body.dataset.edujobView=view;
    qsa('#edujobMobileNav [data-view]').forEach(b=>{
      const on=b.dataset.view===view;b.classList.toggle('active',on);b.setAttribute('aria-current',on?'page':'false');
    });
    if(view==='radar')installRadarManager();
    if(view==='mypage')installMyPage();
    if(view==='search')setTimeout(()=>qs('#q')?.focus({preventScroll:true}),50);
    window.scrollTo({top:0,behavior:'instant'});
  }

  function decorateHome(){
    const radar=qs('#jobRadar');
    if(radar&&!qs('.final-radar-kicker',radar)){
      const title=qs('.job-radar-title',radar);
      if(title)title.innerHTML='<span class="final-radar-kicker">🎯</span> 내 채용 레이더 <span id="jobRadarNewCount"></span>';
    }
    const scope=qs('#scopeChips');
    qsa('.scope-chip',scope||document).forEach(btn=>{
      const label=btn.textContent.trim();
      if(label==='학교·교육청')btn.dataset.icon='school';
      if(label==='학원·민간')btn.dataset.icon='academy';
    });
  }

  function refreshDynamic(){
    if(document.body.dataset.edujobView==='radar')installRadarManager();
    if(document.body.dataset.edujobView==='mypage')installMyPage();
  }

  function finish(){
    if(!qs('.brand-logo-img')||!qs('#jobRadar')||!qs('#jobsHeading'))return false;
    installHeaderActions();installSearchClear();installHeadingLinks();decorateHome();installNav();
    if(!document.body.dataset.edujobView)activate('home');
    window.addEventListener('edujob:user-state-changed',()=>setTimeout(refreshDynamic,50));
    return true;
  }

  let attempts=0;
  const timer=setInterval(()=>{attempts++;if(finish()||attempts>80)clearInterval(timer)},100);
  finish();
})();
