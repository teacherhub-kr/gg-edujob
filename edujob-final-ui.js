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
    if(name==='users')return `<svg ${c}><circle cx="9" cy="8" r="3"/><path d="M3.5 20c.5-4 2.4-6 5.5-6s5 2 5.5 6"/><path d="M15 6.5a2.7 2.7 0 0 1 0 5.2M16 14c2.7.4 4.2 2.4 4.5 6"/></svg>`;
    if(name==='calendar')return `<svg ${c}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></svg>`;
    if(name==='document')return `<svg ${c}><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 12h6M9 16h6"/></svg>`;
    if(name==='database')return `<svg ${c}><ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>`;
    if(name==='school')return `<svg ${c}><path d="M3 10h18L12 4 3 10Z"/><path d="M5 10v9h14v-9M9 19v-5h6v5"/></svg>`;
    if(name==='history')return `<svg ${c}><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5M12 7v5l3 2"/></svg>`;
    if(name==='chat')return `<svg ${c}><path d="M21 12a8 8 0 1 1-4-6.9"/><path d="M21 4v6h-6"/></svg>`;
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
  const RECENT_KEY='edujob.recentJobs.v1';
  function recentJobs(){try{const v=JSON.parse(localStorage.getItem(RECENT_KEY)||'[]');return Array.isArray(v)?v:[]}catch{return []}}
  function recordRecent(card){
    if(!card)return;
    const title=card.querySelector('h2')?.textContent?.trim()||'';
    const school=card.querySelector('.school')?.textContent?.trim()||'';
    const href=card.matches('a.job')?card.href:(card.querySelector('a.job')?.href||'');
    const key=href||[school,title].filter(Boolean).join('|');
    if(!key)return;
    const next=recentJobs().filter(x=>x&&x.key!==key);
    next.unshift({key,title,school,href,seenAt:new Date().toISOString()});
    try{localStorage.setItem(RECENT_KEY,JSON.stringify(next.slice(0,30)))}catch(e){}
  }

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
      <div class="final-page-head"><div><div class="final-page-title-line"><button type="button" id="finalRadarBack" aria-label="홈으로 돌아가기">←</button><h2>내 채용 레이더</h2></div><p>내가 원하는 조건에 맞는 공고를 자동으로 찾아드려요.</p></div><img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"></div>
      <div class="final-segment"><button type="button" class="active">내 조건</button><button type="button" id="finalRadarMatched">맞춤 공고</button></div>
      <div class="final-manager-card">
        <div class="final-manager-title"><strong>저장된 검색 조건 (${saved})</strong><button type="button" id="finalAddCondition">＋ 새 조건 추가</button></div>
        ${p?`<div class="final-saved-condition"><div><strong>${esc(p.q||'저장한 채용 조건')}</strong><p>${chips||'저장한 조건을 불러와 사용할 수 있습니다.'}</p><em>새 공고 ${esc(newCount)}건 · 관심공고 ${favCount}건</em></div><button type="button" class="final-switch on" id="finalApplySaved" aria-label="저장 조건 불러오기"></button></div>`:`<div class="final-empty-condition"><strong>저장된 조건이 없습니다.</strong><p>공고검색에서 원하는 조건을 선택한 뒤 저장해 주세요.</p></div>`}
      </div>
      <div class="final-manager-card final-alert-setting"><div>${icon('bell')}<div><strong>알림 설정</strong><p>새로운 공고가 등록되면 바로 알려드릴게요.</p></div></div><button type="button" class="final-switch ${a.enabled?'on':''}" id="finalAlertToggle" aria-label="새 공고 알림 ${a.enabled?'켜짐':'꺼짐'}"></button></div>
      <div class="final-radar-tip"><img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"><div><strong>내 조건에 딱 맞는 좋은 기회를 찾아드릴게요!</strong><p>✓ 새로운 공고 자동 확인<br>✓ 조건별 맞춤 알림<br>✓ 관심 공고와 쉽게 비교</p></div></div>
    </section>`;
  }

  function installRadarManager(){
    let holder=qs('#finalRadarManager');
    if(!holder){
      holder=document.createElement('div');holder.id='finalRadarManager';holder.className='final-view-panel';
      qs('main.wrap')?.appendChild(holder);
    }
    holder.innerHTML=radarManagerHtml();
    qs('#finalRadarBack')?.addEventListener('click',()=>activate('home'));
    qs('#finalAddCondition')?.addEventListener('click',()=>activate('search'));
    qs('#finalApplySaved')?.addEventListener('click',()=>qs('#jobRadarApply')?.click());
    qs('#finalAlertToggle')?.addEventListener('click',()=>qs('#jobRadarAlerts')?.click());
    qs('#finalRadarMatched')?.addEventListener('click',()=>{activate('search');qs('#jobRadarApply')?.click()});
  }

  function myPageHtml(){
    const p=profile(), fav=favorites(), a=alerts(), recent=recentJobs();
    const savedCount=p?1:0;
    return `<section class="final-my-page" aria-label="마이페이지">
      <div class="final-profile-card"><div class="final-avatar">${icon('user')}</div><div><strong>선생님</strong><p>안녕하세요!</p></div><span class="final-profile-gear">${icon('settings')}</span></div>
      <div class="final-my-stats"><div><span>저장한 공고</span><b>${fav.length}</b></div><div><span>저장한 조건</span><b>${savedCount}</b></div><div><span>최근 본 공고</span><b>${recent.length}</b></div></div>
      <div class="final-menu-card">
        <button type="button" data-action="profile">${icon('user')}<span>내 정보 관리</span><em>›</em></button>
        <button type="button" data-action="alerts">${icon('bell')}<span>알림 설정 ${a.enabled?'· 켜짐':''}</span><em>›</em></button>
        <button type="button" data-action="saved">${icon('bookmark')}<span>저장한 조건</span><em>›</em></button>
        <button type="button" data-action="favorites">${icon('heart')}<span>관심공고</span><em>›</em></button>
        <button type="button" data-action="recent">${icon('history')}<span>최근 본 공고</span><em>›</em></button>
      </div>
      <div class="final-menu-card final-menu-card-secondary">
        <button type="button" data-action="guide"><span>▣</span><span>이용 가이드</span><em>›</em></button>
        <button type="button" data-action="contact"><span>?</span><span>문의하기</span><em>›</em></button>
        <button type="button" data-action="about"><span>▣</span><span>서비스 소개</span><em>›</em></button>
      </div>
      <button type="button" class="final-logout" aria-disabled="true">↻ 로그아웃</button>
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
      else if(action==='recent'){installFavoritesChrome('recent');activate('favorites')}
      else if(action==='guide'||action==='contact'||action==='about')window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'});
    }));
  }

  function newCount(){
    return qs('#jobRadarOverview .job-radar-metric b')?.textContent?.trim()||'0';
  }

  function homeRadarHtml(){
    const p=profile(), fav=favorites(), a=alerts();
    return `<section class="final-home-radar" aria-label="내 채용 레이더 요약">
      <div class="final-home-radar-head"><div><h2>🎯 내 채용 레이더</h2><p>내 조건에 맞는 새로운 일자리를 찾아드려요!</p></div><div class="final-home-mascot"><img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"><span>좋은 기회가<br>기다리고 있어요!</span></div></div>
      <div class="final-home-radar-metrics">
        <button type="button" data-home-radar="new"><span class="metric-icon blue">${icon('document')}</span><b>${esc(newCount())}</b><strong>새 공고</strong><small>지난 방문 이후</small></button>
        <button type="button" data-home-radar="favorites"><span class="metric-icon pink">${icon('heart')}</span><b>${fav.length}</b><strong>관심 공고</strong><small>저장한 공고</small></button>
        <button type="button" data-home-radar="saved"><span class="metric-icon navy">${icon('bookmark')}</span><b>${p?1:0}</b><strong>저장 조건</strong><small>내 검색 조건</small></button>
        <button type="button" data-home-radar="alerts" class="alert ${a.enabled?'on':''}"><span class="metric-icon green">${icon('bell')}</span><b>${a.enabled?'✓':'-'}</b><strong>알림 ${a.enabled?'켜짐':'꺼짐'}</strong><small>새로운 공고 알림</small></button>
      </div>
      <div class="final-home-radar-actions">
        <button type="button" data-home-action="save">${icon('document')}<span>현재 조건 저장</span></button>
        <button type="button" data-home-action="apply">${icon('bookmark')}<span>내 조건 불러오기</span></button>
        <button type="button" data-home-action="new">${icon('filter')}<span>새 공고만</span></button>
        <button type="button" data-home-action="favorites">${icon('heart')}<span>관심공고</span></button>
      </div>
    </section>`;
  }

  function installHomeRadar(){
    let holder=qs('#finalHomeRadar');
    if(!holder){
      holder=document.createElement('div');holder.id='finalHomeRadar';holder.className='final-view-panel';
      const status=qs('#statusHeading'),stats=qs('.stats'),main=qs('main.wrap');
      if(status)main?.insertBefore(holder,status);else if(stats)main?.insertBefore(holder,stats);else main?.prepend(holder);
    }
    holder.innerHTML=homeRadarHtml();
    qsa('[data-home-radar]',holder).forEach(btn=>btn.addEventListener('click',()=>{
      const a=btn.dataset.homeRadar;
      if(a==='favorites')activate('favorites');
      else if(a==='saved')activate('radar');
      else if(a==='alerts')qs('#jobRadarAlerts')?.click();
      else if(a==='new'){activate('search');qs('#jobRadarApply')?.click();setTimeout(()=>qs('#jobRadarNewOnly')?.click(),80)}
    }));
    qsa('[data-home-action]',holder).forEach(btn=>btn.addEventListener('click',()=>{
      const a=btn.dataset.homeAction;
      if(a==='save'){qs('#jobRadarSave')?.click();setTimeout(refreshDynamic,80)}
      else if(a==='apply'){activate('search');setTimeout(()=>qs('#jobRadarApply')?.click(),40)}
      else if(a==='new'){activate('search');qs('#jobRadarApply')?.click();setTimeout(()=>qs('#jobRadarNewOnly')?.click(),80)}
      else if(a==='favorites')activate('favorites');
    }));
  }

  function openFilters(sectionLabel=''){
    const panel=qs('.filter-panel'),toggle=qs('#mobileFilterToggle');
    if(!panel)return;
    if(panel.classList.contains('mobile-collapsed'))toggle?.click();
    setTimeout(()=>{
      if(sectionLabel){
        const heads=qsa('.filter-title h3',panel);
        const target=heads.find(h=>h.textContent.trim()===sectionLabel)?.closest('.filter-section');
        (target||panel).scrollIntoView({behavior:'smooth',block:'start'});
      }else panel.scrollIntoView({behavior:'smooth',block:'start'});
    },30);
  }

  function updateSearchTools(){
    const box=qs('#finalSearchTools');if(!box)return;
    const count=(key)=>{try{return state?.[key] instanceof Set?state[key].size:0}catch{return 0}};
    const set=(id,label,n)=>{const b=qs(id,box);if(b)b.querySelector('span').textContent=n?`${label} ${n}`:label};
    set('#finalRegionFilter','지역',count('regions'));
    set('#finalSchoolFilter','학교급',count('schools'));
    set('#finalSubjectFilter','과목',count('subjects'));
  }

  function installSearchTools(){
    let box=qs('#finalSearchTools');
    if(!box){
      box=document.createElement('div');box.id='finalSearchTools';box.className='final-view-panel final-search-tools';
      box.innerHTML=`<button type="button" class="main" id="finalOpenFilters">${icon('filter')}<span>필터</span></button><button type="button" id="finalRegionFilter"><span>지역</span>⌄</button><button type="button" id="finalSchoolFilter"><span>학교급</span>⌄</button><button type="button" id="finalSubjectFilter"><span>과목</span>⌄</button><button type="button" class="sort" id="finalSortToggle" aria-label="정렬 바꾸기">⇅</button>`;
      const layout=qs('.layout');layout?.parentNode?.insertBefore(box,layout);
      qs('#finalOpenFilters',box)?.addEventListener('click',()=>openFilters());
      qs('#finalRegionFilter',box)?.addEventListener('click',()=>openFilters('지역'));
      qs('#finalSchoolFilter',box)?.addEventListener('click',()=>openFilters('학교급'));
      qs('#finalSubjectFilter',box)?.addEventListener('click',()=>openFilters('과목'));
      qs('#finalSortToggle',box)?.addEventListener('click',()=>{
        const s=qs('#sort');if(!s)return;s.value=s.value==='deadline'?'newest':'deadline';s.dispatchEvent(new Event('change',{bubbles:true}));
      });
      document.addEventListener('change',e=>{if(e.target?.closest?.('.filter-panel'))setTimeout(updateSearchTools,0)});
    }
    updateSearchTools();
  }

  let favoritesTab='saved';
  function recentListHtml(){
    const rows=recentJobs();
    if(!rows.length)return '<div class="final-recent-empty"><strong>최근 본 공고가 없습니다.</strong><p>공고를 열어보면 여기에 최근 기록이 표시됩니다.</p></div>';
    return rows.map(r=>`<a class="final-recent-row" href="${esc(r.href||'#')}" ${r.href?'target="_blank" rel="noopener"':''}><div><strong>${esc(r.school||'기관명 확인')}</strong><span>${esc(r.title||'채용 공고')}</span></div><em>›</em></a>`).join('');
  }

  function installFavoritesChrome(tab=favoritesTab){
    favoritesTab=tab==='recent'?'recent':'saved';
    let box=qs('#finalFavoritesHeader');
    if(!box){box=document.createElement('div');box.id='finalFavoritesHeader';box.className='final-view-panel final-favorites-page';const layout=qs('.layout');layout?.parentNode?.insertBefore(box,layout)}
    box.innerHTML=`<div class="final-segment final-favorites-segment"><button type="button" id="finalFavSaved" class="${favoritesTab==='saved'?'active':''}">저장한 공고 (${favorites().length})</button><button type="button" id="finalFavRecent" class="${favoritesTab==='recent'?'active':''}">최근 본 공고</button></div><div id="finalFavoritesRecent" class="${favoritesTab==='recent'?'show':''}">${recentListHtml()}</div>`;
    qs('#finalFavSaved',box)?.addEventListener('click',()=>{favoritesTab='saved';document.body.classList.remove('final-recent-mode');installFavoritesChrome('saved')});
    qs('#finalFavRecent',box)?.addEventListener('click',()=>{favoritesTab='recent';document.body.classList.add('final-recent-mode');installFavoritesChrome('recent')});
    document.body.classList.toggle('final-recent-mode',favoritesTab==='recent');
    let tip=qs('#finalFavoriteTip');
    if(!tip){tip=document.createElement('div');tip.id='finalFavoriteTip';tip.className='final-view-panel final-favorite-tip';tip.innerHTML=`<img src="edujob-mascot.svg?v=20260919g" alt="" aria-hidden="true"><div><strong>관심 있는 공고를 저장하고 놓치지 마세요!</strong><p>✓ 중요한 공고 따로 관리<br>✓ 마감 임박 공고 확인<br>✓ 내 채용 레이더와 함께 활용</p></div>`;const layout=qs('.layout');layout?.insertAdjacentElement('afterend',tip)}
  }

  function installStatIcons(){
    const names=['users','calendar','document','database'];
    qsa('.stats .stat').forEach((el,i)=>{
      if(qs('.final-stat-icon',el))return;
      const s=document.createElement('span');s.className='final-stat-icon i'+i;s.innerHTML=icon(names[i]||'document');el.insertBefore(s,el.firstChild);
    });
  }

  function installRecentTracking(){
    if(document.body.dataset.recentTracking==='1')return;
    document.body.dataset.recentTracking='1';
    document.addEventListener('click',e=>{const card=e.target?.closest?.('#list .job');if(card)recordRecent(card)},true);
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
    if(view==='home')installHomeRadar();
    if(view==='search'){installSearchTools();setTimeout(()=>qs('#q')?.focus({preventScroll:true}),50)}
    if(view==='radar')installRadarManager();
    if(view==='favorites')installFavoritesChrome();
    if(view==='mypage')installMyPage();
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
      if(label==='학교·교육청'){btn.dataset.icon='school';btn.innerHTML=icon('school')+'<span>학교·교육청</span>'}
      if(label==='학원·민간'){btn.dataset.icon='academy';btn.innerHTML=icon('school')+'<span>학원·민간</span>'}
    });
  }

  function refreshDynamic(){
    const view=document.body.dataset.edujobView;
    if(view==='home')installHomeRadar();
    if(view==='search')updateSearchTools();
    if(view==='radar')installRadarManager();
    if(view==='favorites')installFavoritesChrome();
    if(view==='mypage')installMyPage();
  }

  function finish(){
    if(!qs('.brand-logo-img')||!qs('#jobRadar')||!qs('#jobsHeading'))return false;
    installHeaderActions();installSearchClear();installHeadingLinks();decorateHome();installNav();installHomeRadar();installSearchTools();installFavoritesChrome();installStatIcons();installRecentTracking();
    if(!document.body.dataset.edujobView)activate('home');
    window.addEventListener('edujob:user-state-changed',()=>setTimeout(refreshDynamic,50));
    return true;
  }

  let attempts=0;
  const timer=setInterval(()=>{attempts++;if(finish()||attempts>80)clearInterval(timer)},100);
  finish();
})();
