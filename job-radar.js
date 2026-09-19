(()=>{
  if(window.__edujobJobRadarLoaded)return;
  window.__edujobJobRadarLoaded=true;

  const userStore=window.EduJobUserStore;
  if(!userStore)return;
  const PROFILE_FIELDS=['provinces','regions','schools','types','categories','subjects'];
  let newOnly=false;
  let favoriteOnly=false;
  let currentNewKeys=new Set();
  let currentMatchKeys=[];

  const readProfile=()=>userStore.profile.get();
  const readSnapshot=()=>userStore.snapshot.get();
  const arr=v=>Array.isArray(v)?v.filter(Boolean):[];
  const setValues=key=>state?.[key] instanceof Set?[...state[key]]:[];

  const currentProfile=()=>({
    version:1,
    provinces:setValues('provinces'),
    regions:setValues('regions'),
    schools:setValues('schools'),
    types:setValues('types'),
    categories:setValues('categories'),
    subjects:setValues('subjects'),
    q:String(document.getElementById('q')?.value??state?.q??'').trim(),
    savedAt:new Date().toISOString()
  });

  const fingerprint=p=>JSON.stringify({
    provinces:arr(p?.provinces).sort(),
    regions:arr(p?.regions).sort(),
    schools:arr(p?.schools).sort(),
    types:arr(p?.types).sort(),
    categories:arr(p?.categories).sort(),
    subjects:arr(p?.subjects).sort(),
    q:String(p?.q||'').trim()
  });

  const hasConditions=p=>PROFILE_FIELDS.some(k=>arr(p?.[k]).length>0)||Boolean(String(p?.q||'').trim());

  const jobKey=j=>String(
    j?.sourceIdentity||j?.id||j?.verifiedUrl||j?.detailUrl||j?.url||
    [j?.source,j?.school,j?.title,j?.registered].filter(Boolean).join('|')
  );

  const readFavorites=()=>new Set(arr(userStore.favorites.get()));
  const writeFavorites=set=>userStore.favorites.set([...set].slice(0,1000));
  const isFavorite=j=>readFavorites().has(jobKey(j));
  const toggleFavorite=j=>{
    const key=jobKey(j);if(!key)return false;
    const set=readFavorites();
    const next=!set.has(key);
    next?set.add(key):set.delete(key);
    writeFavorites(set);
    return next;
  };

  const sourceKinds=j=>{
    const kinds=new Set([j?.feedKind==='private'?'민간':'공식']);
    if(Array.isArray(j?.alsoSeenOn)&&j.alsoSeenOn.some(x=>x&&x.source))kinds.add('민간');
    return kinds;
  };

  const subjectText=j=>` ${norm([j?.subject,j?.title,j?.schoolLevel,j?.type].filter(Boolean).join(' '))} `;
  const subjectRules={
    '국어':/(^|\s)(국어|독서|논술)(\s|$)/,
    '영어':/(^|\s)(영어|영어회화)(\s|$)/,
    '수학':/(^|\s)(수학|수리)(\s|$)/,
    '과학':/(^|\s)(과학|물리|화학|생명과학|생물|지구과학|통합과학)(\s|$)/,
    '사회·역사':/(^|\s)(사회|역사|한국사|지리|윤리|도덕|통합사회)(\s|$)/,
    '사회':/(^|\s)(사회|일반사회|통합사회|지리|윤리|도덕)(\s|$)/,
    '역사':/(^|\s)(역사|한국사)(\s|$)/,
    '음악':/(^|\s)(음악|합창|오케스트라|관현악|밴드)(\s|$)/,
    '미술':/(^|\s)(미술|디자인)(\s|$)/,
    '체육':/(^|\s)(체육|스포츠|운동)(\s|$)/,
    '특수':/(^|\s)(특수|특수교육)(\s|$)/,
    '보건':/(^|\s)(보건|간호)(\s|$)/,
    '상담':/(^|\s)(상담|전문상담|위클래스|wee)(\s|$)/,
    '사서':/(^|\s)(사서|도서관)(\s|$)/,
    '영양':/(^|\s)(영양|영양교사)(\s|$)/,
    '정보·컴퓨터':/(^|\s)(정보|컴퓨터|코딩|소프트웨어|ai|인공지능)(\s|$)/,
    '유아':/(^|\s)(유아|유치원|유치)(\s|$)/
  };

  const matchesProfile=(j,p)=>{
    const ps=arr(p?.provinces),rs=arr(p?.regions),ss=arr(p?.schools),ts=arr(p?.types),cs=arr(p?.categories),subs=arr(p?.subjects);
    if(ps.length&&!jobProvinces(j).some(x=>ps.includes(x)))return false;
    if(rs.length&&!jobRegions(j).some(x=>rs.includes(x)))return false;
    if(ss.length&&!ss.includes(schoolLevel(j)))return false;
    if(ts.length&&!ts.includes(jobType(j)))return false;
    if(cs.length){
      const jc=new Set(Array.isArray(j?.categories)?j.categories:[]);
      if(!cs.some(x=>jc.has(x)))return false;
    }
    if(subs.length){
      const hay=subjectText(j);
      if(!subs.some(x=>subjectRules[x]?.test(hay)===true))return false;
    }
    if(String(p?.q||'').trim()&&!matchesQuery(j,p.q))return false;
    const d=diffDay(j?.applyEnd);
    if(d!==null&&d<0)return false;
    return true;
  };

  const syncInputs=()=>{
    document.querySelectorAll('#provinceChecks input').forEach(i=>i.checked=state.provinces.has(i.value));
    document.querySelectorAll('#gyeonggiRegionChecks input,#seoulRegionChecks input').forEach(i=>i.checked=state.regions.has(i.value));
    document.querySelectorAll('#schoolChecks input').forEach(i=>i.checked=state.schools.has(i.value));
    document.querySelectorAll('#typeChecks input').forEach(i=>i.checked=state.types.has(i.value));
    if(state.categories instanceof Set)document.querySelectorAll('#categoryFilters input').forEach(i=>i.checked=state.categories.has(i.value));
    if(state.subjects instanceof Set)document.querySelectorAll('#subjectFilters input').forEach(i=>i.checked=state.subjects.has(i.value));
    const q=document.getElementById('q');if(q)q.value=state.q||'';
  };

  const applyProfile=p=>{
    if(!p)return;
    for(const key of PROFILE_FIELDS){
      if(!(state?.[key] instanceof Set))continue;
      state[key].clear();
      arr(p[key]).forEach(v=>state[key].add(v));
    }
    state.q=String(p.q||'');
    if(typeof renderAll==='function')renderAll(true);
    syncInputs();
    if(typeof selectionSummary==='function')selectionSummary();
    if(typeof render==='function')render();
  };

  const matchingKeys=p=>(Array.isArray(jobs)?jobs:[]).filter(j=>matchesProfile(j,p)).map(jobKey).filter(Boolean);

  const writeSnapshot=(p,keys)=>userStore.snapshot.set({
    version:1,
    fingerprint:fingerprint(p),
    keys:[...new Set(keys)].slice(0,3000),
    checkedAt:new Date().toISOString()
  });

  function installStyles(){
    if(document.getElementById('jobRadarStyles'))return;
    const style=document.createElement('style');
    style.id='jobRadarStyles';
    style.textContent=`
      .job-radar{flex:0 0 auto;margin:10px 0 0;padding:14px 16px;border:1px solid #dbe6f4;background:linear-gradient(135deg,#f8fbff,#f3f8ff);border-radius:15px;transition:.15s ease}.job-radar.has-new{border-color:#8fd0aa;background:linear-gradient(135deg,#f4fff8,#eefbf3);box-shadow:0 6px 18px rgba(15,159,110,.08)}
      .job-radar-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
      .job-radar-title{font-size:13px;font-weight:900;color:#20324d}
      .job-radar-copy{margin-top:4px;font-size:11px;line-height:1.5;color:#66758a}
      .job-radar-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
      .job-radar-btn{border:1px solid #d7e1ee;background:#fff;color:#40516a;border-radius:9px;padding:7px 9px;font-size:10px;font-weight:850;cursor:pointer}
      .job-radar-btn.primary{border-color:#93b8ef;background:#edf5ff;color:#1758b3}
      .job-radar-btn.new{border-color:#9ed9b6;background:#effcf4;color:#087a42}
      .job-radar-btn[disabled]{opacity:.45;cursor:not-allowed}
      .job-radar-count{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:#e5484d;color:#fff;font-size:10px;font-weight:900;margin-left:5px}.job-radar-overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:11px}.job-radar-metric{background:rgba(255,255,255,.82);border:1px solid #e0e8f2;border-radius:10px;padding:8px 10px}.job-radar-metric b{display:block;font-size:17px;line-height:1.1;color:#1d3557}.job-radar-metric span{display:block;margin-top:3px;font-size:9px;color:#7a8798}.job-radar-profile{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.job-radar-chip{font-size:9px;font-weight:750;padding:5px 7px;border-radius:999px;background:#fff;border:1px solid #e0e7f0;color:#5b697b}.job-radar-preview{display:grid;gap:6px;margin-top:9px}.job-radar-preview-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border-radius:10px;background:#fff;border:1px solid #dce9e2}.job-radar-preview-main{min-width:0}.job-radar-preview-title{font-size:11px;font-weight:850;color:#26384f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.job-radar-preview-meta{margin-top:2px;font-size:9px;color:#788596;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.job-radar-preview-go{flex:0 0 auto;font-size:9px;font-weight:850;color:#087a42}.job-card-wrap{position:relative}.job-card-wrap>.job{padding-right:54px}.job-favorite-btn{position:absolute;z-index:3;top:12px;right:12px;width:34px;height:34px;border:1px solid #dce4ee;border-radius:10px;background:#fff;color:#7b8797;font-size:19px;line-height:1;cursor:pointer;box-shadow:0 2px 8px rgba(22,32,51,.06)}.job-favorite-btn[aria-pressed="true"]{border-color:#f0c36d;background:#fff9e9;color:#d99400}.badge.radar-new{background:#eaf9f0;color:#087a42;border:1px solid #bfe7cf}.job-card-wrap.is-radar-new>.job{border-color:#bfe7cf;box-shadow:0 4px 14px rgba(15,159,110,.07)}
      @media(max-width:650px){.job-radar{margin-top:8px;padding:12px}.job-radar-head{align-items:flex-start;flex-direction:column}.job-radar-actions{justify-content:flex-start;width:100%}.job-radar-btn{flex:1}.job-radar-overview{grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.job-radar-metric{padding:7px}.job-radar-metric b{font-size:15px}}
    `;
    document.head.appendChild(style);
  }

  function installPanel(){
    if(document.getElementById('jobRadar'))return;
    const toolbar=document.querySelector('.toolbar');
    if(!toolbar)return;
    const box=document.createElement('div');
    box.id='jobRadar';box.className='job-radar';
    box.innerHTML=`
      <div class="job-radar-head">
        <div>
          <div class="job-radar-title">🎯 내 채용 레이더 <span id="jobRadarNewCount"></span></div>
          <div class="job-radar-copy" id="jobRadarCopy"><span class="radar-copy-line">원하는 조건을 고른 뒤 저장해 주세요.</span><span class="radar-copy-line">다음 방문부터 새 공고를 구분합니다.</span></div>
        </div>
        <div class="job-radar-actions">
          <button type="button" class="job-radar-btn primary" id="jobRadarSave" aria-label="현재 조건 저장"><span class="radar-action-label">현재<br>조건<br>저장</span></button>
          <button type="button" class="job-radar-btn" id="jobRadarApply" aria-label="내 조건 불러오기"><span class="radar-action-label">내 조건<br>불러<br>오기</span></button>
          <button type="button" class="job-radar-btn new" id="jobRadarNewOnly" aria-label="새 공고"><span class="radar-action-label">새<br>공고</span></button>
          <button type="button" class="job-radar-btn" id="jobRadarFavorites" aria-label="관심공고"><span class="radar-action-label">♡<br>관심<br>공고</span></button>
          <button type="button" class="job-radar-btn" id="jobRadarDelete" aria-label="삭제"><span class="radar-action-label">삭제</span></button>
        </div>
      </div>
      <div class="job-radar-overview" id="jobRadarOverview"></div>
      <div class="job-radar-profile" id="jobRadarProfile"></div>
      <div class="job-radar-preview" id="jobRadarPreview"></div>`;
    const main=document.querySelector('main.wrap');
    const stats=main?.querySelector('.stats');
    if(main&&stats)main.insertBefore(box,stats);
    else toolbar.parentElement.insertBefore(box,toolbar);

    document.getElementById('jobRadarSave').addEventListener('click',()=>{
      const p=currentProfile();
      if(!hasConditions(p)){document.getElementById('jobRadarCopy').textContent='지역·학교급·직종·과목 또는 검색어를 하나 이상 선택한 뒤 저장해 주세요.';return}
      userStore.profile.set(p);
      const keys=matchingKeys(p);writeSnapshot(p,keys);
      currentNewKeys=new Set();currentMatchKeys=keys;newOnly=false;
      updatePanel('saved');
      if(typeof render==='function')render();
    });

    document.getElementById('jobRadarApply').addEventListener('click',()=>{
      const p=readProfile();
      if(!p){updatePanel('missing');return}
      applyProfile(p);recompute();
    });

    document.getElementById('jobRadarNewOnly').addEventListener('click',()=>{
      if(!currentNewKeys.size)return;
      newOnly=!newOnly;
      if(newOnly)favoriteOnly=false;
      updatePanel();
      if(typeof render==='function')render();
    });

    document.getElementById('jobRadarFavorites').addEventListener('click',()=>{
      favoriteOnly=!favoriteOnly;
      if(favoriteOnly)newOnly=false;
      updatePanel();
      if(typeof render==='function')render();
    });


    document.getElementById('jobRadarDelete').addEventListener('click',()=>{
      userStore.profile.remove();userStore.snapshot.remove();
      currentNewKeys=new Set();currentMatchKeys=[];newOnly=false;favoriteOnly=false;
      updatePanel('deleted');
      if(typeof render==='function')render();
    });
  }

  function activeFavoriteCount(){
    const favs=readFavorites();
    return (Array.isArray(jobs)?jobs:[]).filter(j=>{
      if(!favs.has(jobKey(j)))return false;
      const d=diffDay(j?.applyEnd);
      return d===null||d>=0;
    }).length;
  }

  function profileChips(p){
    if(!p)return [];
    const chips=[];
    const push=(label,values,max=2)=>{
      const xs=arr(values);if(!xs.length)return;
      const shown=xs.slice(0,max).join('·');
      chips.push(`${label} ${shown}${xs.length>max?` +${xs.length-max}`:''}`);
    };
    push('지역',p.regions);
    push('학교급',p.schools);
    push('직종',p.types);
    push('과목',p.subjects);
    if(String(p.q||'').trim())chips.push(`검색 “${String(p.q).trim()}”`);
    return chips.slice(0,5);
  }

  function newPreviewJobs(){
    const rows=(Array.isArray(jobs)?jobs:[]).filter(j=>currentNewKeys.has(jobKey(j)));
    rows.sort((x,y)=>compareDeadline(x,y));
    return rows.slice(0,3);
  }

  function renderDashboard(p){
    const overview=document.getElementById('jobRadarOverview');
    const profile=document.getElementById('jobRadarProfile');
    const preview=document.getElementById('jobRadarPreview');
    if(!overview||!profile||!preview)return;
    if(!p){
      overview.innerHTML='<div class="job-radar-metric"><b>-</b><span data-short="신규">내 신규</span></div><div class="job-radar-metric"><b>-</b><span data-short="관심">관심공고</span></div><div class="job-radar-metric"><b>-</b><span data-short="일치">조건 일치</span></div>';
      profile.innerHTML='';
      preview.innerHTML='';
      return;
    }
    const favCount=activeFavoriteCount();
    overview.innerHTML=`<div class="job-radar-metric"><b>${currentNewKeys.size.toLocaleString()}</b><span data-short="신규">지난 방문 이후 신규</span></div><div class="job-radar-metric"><b>${favCount.toLocaleString()}</b><span data-short="관심">모집 중 관심공고</span></div><div class="job-radar-metric"><b>${currentMatchKeys.length.toLocaleString()}</b><span data-short="일치">현재 조건 일치</span></div>`;
    profile.innerHTML=profileChips(p).map(x=>`<span class="job-radar-chip">${esc(x)}</span>`).join('');
    preview.innerHTML=newPreviewJobs().map(j=>{
      const href=postingLink(j);
      const tag=href?'a':'div';
      const attrs=href?` href="${esc(href)}" target="_blank" rel="noopener"`:'';
      const d=diffDay(j.applyEnd);
      const deadline=d===0?'오늘 마감':d!==null&&d>0?`D-${d}`:'마감 원문확인';
      const region=(j.location||j.region||(Array.isArray(j.regions)?j.regions.join('·'):'')||province(j));
      return `<${tag} class="job-radar-preview-row"${attrs}><div class="job-radar-preview-main"><div class="job-radar-preview-title">${esc(j.title||'채용 공고')}</div><div class="job-radar-preview-meta">${esc(j.school||'기관명 확인')} · ${esc(region)} · ${esc(deadline)}</div></div><div class="job-radar-preview-go">${href?'원문 ↗':'링크 점검 중'}</div></${tag}>`;
    }).join('');
  }
  function updatePanel(mode=''){
    const p=readProfile(),box=document.getElementById('jobRadar'),copy=document.getElementById('jobRadarCopy'),count=document.getElementById('jobRadarNewCount'),apply=document.getElementById('jobRadarApply'),newBtn=document.getElementById('jobRadarNewOnly'),favBtn=document.getElementById('jobRadarFavorites');
    if(!copy||!count)return;
    const actionLabel=(button,html,aria)=>{if(!button)return;button.innerHTML=`<span class="radar-action-label">${html}</span>`;button.setAttribute('aria-label',aria)};
    const copyLines=(...lines)=>{copy.innerHTML=lines.map(line=>`<span class="radar-copy-line">${line}</span>`).join('')};
    apply.disabled=!p;newBtn.disabled=!p||currentNewKeys.size===0;
    if(box)box.classList.toggle('has-new',Boolean(p&&currentNewKeys.size));
    actionLabel(newBtn,newOnly?'전체<br>공고':'새<br>공고',newOnly?'전체 공고':'새 공고');
    if(favBtn){actionLabel(favBtn,favoriteOnly?'전체<br>공고':'♡<br>관심<br>공고',favoriteOnly?'전체 공고':'관심공고');favBtn.classList.toggle('primary',favoriteOnly)}
    count.innerHTML=currentNewKeys.size?`<span class="job-radar-count">${currentNewKeys.size}</span>`:'';
    renderDashboard(p);
    if(mode==='saved'){copyLines('조건을 저장했습니다.',`현재 조건 일치 ${currentMatchKeys.length.toLocaleString()}건`);return}
    if(mode==='missing'){copyLines('저장된 내 조건이 없습니다.','원하는 조건을 고른 뒤 저장해 주세요.');return}
    if(mode==='deleted'){copyLines('저장 조건을 삭제했습니다.','필터를 다시 선택해 저장할 수 있습니다.');return}
    if(!p){copyLines('원하는 조건을 고른 뒤 저장해 주세요.','다음 방문부터 새 공고를 구분합니다.');return}
    if(currentNewKeys.size)copyLines(`지난 방문 이후 새 공고 ${currentNewKeys.size.toLocaleString()}건`,`현재 조건 일치 ${currentMatchKeys.length.toLocaleString()}건`);
    else copyLines('지난 방문 이후 신규 공고 0건',`현재 조건 일치 ${currentMatchKeys.length.toLocaleString()}건`);
  }

  function decorateCards(){
    const list=document.getElementById('list');if(!list)return;
    const rows=filtered().slice(0,typeof visibleLimit==='number'?visibleLimit:80);
    const cards=[...list.querySelectorAll(':scope > .job')];
    cards.forEach((cardEl,index)=>{
      const j=rows[index];if(!j)return;
      const wrap=document.createElement('div');wrap.className='job-card-wrap';
      if(currentNewKeys.has(jobKey(j)))wrap.classList.add('is-radar-new');
      cardEl.parentNode.insertBefore(wrap,cardEl);wrap.appendChild(cardEl);
      if(currentNewKeys.has(jobKey(j))){
        const badges=cardEl.querySelector('.badges');
        if(badges&&!badges.querySelector('.radar-new'))badges.insertAdjacentHTML('afterbegin','<span class="badge radar-new">내 신규</span>');
      }
      const btn=document.createElement('button');
      btn.type='button';btn.className='job-favorite-btn';
      const active=isFavorite(j);
      btn.setAttribute('aria-pressed',String(active));
      btn.setAttribute('aria-label',active?'관심공고 해제':'관심공고 저장');
      btn.title=active?'관심공고 해제':'관심공고 저장';
      btn.textContent=active?'★':'☆';
      btn.addEventListener('click',e=>{
        e.preventDefault();e.stopPropagation();
        const next=toggleFavorite(j);
        btn.setAttribute('aria-pressed',String(next));
        btn.setAttribute('aria-label',next?'관심공고 해제':'관심공고 저장');
        btn.title=next?'관심공고 해제':'관심공고 저장';
        btn.textContent=next?'★':'☆';
        updatePanel();
        if(favoriteOnly&&typeof render==='function')render();
      });
      wrap.appendChild(btn);
    });
  }

  function recompute(){
    const p=readProfile();
    if(!p){currentNewKeys=new Set();currentMatchKeys=[];updatePanel();return}
    currentMatchKeys=matchingKeys(p);
    const snap=readSnapshot();
    if(!snap||snap.fingerprint!==fingerprint(p)){writeSnapshot(p,currentMatchKeys);currentNewKeys=new Set()}
    else{
      const prev=new Set(arr(snap.keys));
      currentNewKeys=new Set(currentMatchKeys.filter(k=>!prev.has(k)));
    }
    updatePanel();
  }

  const waitForApp=()=>{
    if(typeof state==='undefined'||typeof jobs==='undefined'||typeof filtered!=='function'||typeof render!=='function'){setTimeout(waitForApp,120);return}
    installStyles();installPanel();

    const originalFiltered=filtered;
    filtered=function(){
      if(favoriteOnly){
        const favs=readFavorites();
        const rows=(Array.isArray(jobs)?jobs:[]).filter(j=>{
          if(!favs.has(jobKey(j)))return false;
          const d=diffDay(j?.applyEnd);
          return d===null||d>=0;
        });
        rows.sort((x,y)=>state.sort==='newest'
          ?(parseDate(y.registered)||0)-(parseDate(x.registered)||0)
          :compareDeadline(x,y));
        return rows;
      }
      let rows=originalFiltered();
      if(newOnly)rows=rows.filter(j=>currentNewKeys.has(jobKey(j)));
      return rows;
    };

    const originalRender=render;
    render=function(resetLimit=true){
      originalRender(resetLimit);
      decorateCards();
    };

    const p=readProfile();
    if(p)applyProfile(p);

    const waitForJobs=()=>{
      if(Array.isArray(jobs)&&jobs.length){recompute();render();return}
      setTimeout(waitForJobs,150);
    };
    waitForJobs();

    const persistVisit=()=>{
      const profile=readProfile();
      if(!profile||!Array.isArray(jobs)||!jobs.length)return;
      writeSnapshot(profile,matchingKeys(profile));
    };
    window.addEventListener('pagehide',persistVisit,{capture:true});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')persistVisit()},{passive:true});
  };

  waitForApp();
})();