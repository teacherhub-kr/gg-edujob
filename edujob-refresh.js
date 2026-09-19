(()=>{
  if(window.__edujobBrightRefreshLoaded)return;
  window.__edujobBrightRefreshLoaded=true;

  const qs=(s,p=document)=>p.querySelector(s);
  const qsa=(s,p=document)=>[...p.querySelectorAll(s)];

  function installBrand(){
    const brand=qs('.brand');
    if(!brand||brand.dataset.refreshReady)return;
    brand.dataset.refreshReady='1';
    brand.innerHTML='<img class="brand-logo-img" src="edujob-logo.svg?v=20260919e" alt=""><span class="brand-copy"><span class="brand-title">수도권<em>에듀잡</em></span><span class="brand-subtitle">좋은 선생님이, 더 좋은 교육을 만듭니다</span></span>';
    const top=qs('.top');
    if(top&&!qs('.brand-note',top)){
      const note=document.createElement('div');
      note.className='brand-note';
      note.innerHTML='오늘도<br>교육의 내일을 응원합니다 ♥';
      top.appendChild(note);
    }
  }

  function syncSourceChecks(){
    if(typeof state==='undefined'||!(state.sources instanceof Set))return;
    qsa('#sourceKindFilters input').forEach(input=>{input.checked=state.sources.has(input.value)});
  }

  function syncScope(){
    if(typeof state==='undefined'||!(state.sources instanceof Set))return;
    let current='all';
    if(state.sources.size===1&&state.sources.has('공식'))current='official';
    else if(state.sources.size===1&&state.sources.has('민간'))current='private';
    qsa('.scope-chip').forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.scope===current)));
  }

  function setScope(scope){
    if(typeof state==='undefined'||!(state.sources instanceof Set))return;
    state.sources.clear();
    if(scope==='official')state.sources.add('공식');
    if(scope==='private')state.sources.add('민간');
    syncSourceChecks();
    syncScope();
    if(typeof render==='function')render();
  }

  function installScopeChips(){
    const search=qs('.searchbox');
    if(!search)return;
    const legacyTabs=qs('#edujobTabs');
    if(legacyTabs)legacyTabs.remove();
    qsa('.scope-chips').forEach(el=>{if(el.id!=='scopeChips')el.remove()});
    const existing=qs('#scopeChips');
    if(existing){
      if(existing.previousElementSibling!==search)search.insertAdjacentElement('afterend',existing);
      return;
    }
    const bar=document.createElement('div');
    bar.id='scopeChips';
    bar.className='scope-chips';
    bar.setAttribute('aria-label','구인 범위 빠른 선택');
    [['all','전체 구인'],['official','학교·교육청'],['private','학원·민간']].forEach(([scope,label])=>{
      const btn=document.createElement('button');
      btn.type='button';
      btn.className='scope-chip';
      btn.dataset.scope=scope;
      btn.textContent=label;
      btn.addEventListener('click',()=>setScope(scope));
      bar.appendChild(btn);
    });
    search.insertAdjacentElement('afterend',bar);
    syncScope();
    document.addEventListener('change',e=>{
      if(e.target?.closest?.('#sourceKindFilters'))setTimeout(syncScope,0);
    });
  }

  function addHeading(before,icon,title,sub,id){
    if(!before||qs('#'+id))return;
    const el=document.createElement('div');
    el.className='section-heading';
    el.id=id;
    el.innerHTML='<div class="section-heading-main"><span class="section-heading-icon">'+icon+'</span><div><h2>'+title+'</h2>'+(sub?'<small>'+sub+'</small>':'')+'</div></div>';
    before.parentNode.insertBefore(el,before);
  }

  function installHeadings(){
    const stats=qs('.stats');
    if(stats)addHeading(stats,'▥','채용 현황','모집 중인 수도권 교육 채용을 한눈에 확인하세요.','statusHeading');
    const toolbar=qs('.toolbar');
    if(toolbar)addHeading(toolbar,'▤','최신 채용 공고','조건에 맞는 공고를 빠르게 확인하세요.','jobsHeading');
  }

  function installMascot(){
    const radar=qs('#jobRadar');
    if(!radar)return false;
    if(!qs('.radar-mascot-wrap',radar)){
      const wrap=document.createElement('div');
      wrap.className='radar-mascot-wrap';
      wrap.setAttribute('aria-hidden','true');
      wrap.innerHTML='<span class="radar-speech">좋은 기회가<br>기다리고 있어요!</span><img class="radar-mascot" src="edujob-mascot.svg?v=20260919e" alt="">';
      radar.appendChild(wrap);
    }
    return true;
  }

  function alertState(){
    try{return Boolean(window.EduJobUserStore?.alerts?.get?.()?.enabled)}catch{return false}
  }

  function installAlertCard(){
    const overview=qs('#jobRadarOverview');
    const actual=qs('#jobRadarAlerts');
    if(!overview||!actual)return false;
    if(qs('#radarAlertCard',overview))return true;
    const card=document.createElement('button');
    card.type='button';
    card.id='radarAlertCard';
    card.className='radar-alert-card';
    card.addEventListener('click',()=>actual.click());
    overview.appendChild(card);
    const refresh=()=>{
      const on=alertState();
      card.innerHTML='<span class="alert-icon">🔔</span><strong>'+(on?'알림 켜짐':'새 공고 알림')+'</strong><span>'+(on?'새 공고가 있으면 알려드려요':'맞춤 공고를 바로 알려드려요')+'</span>';
      card.setAttribute('aria-pressed',String(on));
    };
    refresh();
    window.addEventListener('edujob:user-state-changed',refresh);
    actual.addEventListener('click',()=>setTimeout(refresh,250));
    return true;
  }

  function keepAlertCard(){
    const overview=qs('#jobRadarOverview');
    if(!overview||overview.dataset.refreshObserved)return;
    overview.dataset.refreshObserved='1';
    new MutationObserver(()=>{if(!qs('#radarAlertCard',overview))setTimeout(installAlertCard,0)}).observe(overview,{childList:true});
  }

  const iconSvg=name=>{
    const common='viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
    if(name==='home')return '<svg '+common+'><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></svg>';
    if(name==='search')return '<svg '+common+'><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>';
    if(name==='radar')return '<svg '+common+'><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3"/></svg>';
    return '<svg '+common+'><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>';
  };

  function installMobileNav(){
    if(qs('#edujobMobileNav'))return;
    const nav=document.createElement('nav');
    nav.id='edujobMobileNav';
    nav.className='edujob-mobile-nav';
    nav.setAttribute('aria-label','모바일 바로가기');
    [
      ['home','홈',()=>window.scrollTo({top:0,behavior:'smooth'})],
      ['search','공고검색',()=>{qs('#q')?.focus();qs('.searchbox')?.scrollIntoView({behavior:'smooth',block:'center'})}],
      ['radar','내 채용 레이더',()=>qs('#jobRadar')?.scrollIntoView({behavior:'smooth',block:'start'})],
      ['favorite','관심공고',()=>{qs('#jobRadarFavorites')?.click();qs('#jobsHeading')?.scrollIntoView({behavior:'smooth',block:'start'})}]
    ].forEach(([name,label,action])=>{
      const btn=document.createElement('button');
      btn.type='button';
      btn.innerHTML=iconSvg(name)+'<span>'+label+'</span>';
      btn.addEventListener('click',action);
      nav.appendChild(btn);
    });
    document.body.appendChild(nav);
  }

  function tuneSearch(){
    const q=qs('#q');
    if(q)q.placeholder='지역, 학교, 과목, 직종으로 검색해보세요';
  }

  function finish(){
    installBrand();
    tuneSearch();
    installScopeChips();
    installHeadings();
    const radarReady=installMascot();
    const alertReady=installAlertCard();
    if(radarReady)keepAlertCard();
    installMobileNav();
    if(radarReady&&alertReady)document.body.classList.add('edujob-refresh-ready');
    return radarReady&&alertReady;
  }

  let attempts=0;
  const timer=setInterval(()=>{
    attempts++;
    if(finish()||attempts>50)clearInterval(timer);
  },100);
  finish();
})();