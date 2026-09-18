(()=>{
  if(window.__edujobJobRadarLoaded)return;
  window.__edujobJobRadarLoaded=true;

  const PROFILE_KEY='edujob.jobRadar.profile.v1';
  const SNAPSHOT_KEY='edujob.jobRadar.snapshot.v1';
  const PROFILE_FIELDS=['provinces','regions','schools','types','categories','subjects'];
  let newOnly=false;
  let currentNewKeys=new Set();
  let currentMatchKeys=[];

  const safeJson=(raw,fallback=null)=>{try{return raw?JSON.parse(raw):fallback}catch(e){return fallback}};
  const readProfile=()=>safeJson(localStorage.getItem(PROFILE_KEY));
  const readSnapshot=()=>safeJson(localStorage.getItem(SNAPSHOT_KEY));
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

  const sourceKinds=j=>{
    const kinds=new Set([j?.feedKind==='private'?'민간':'공식']);
    if(Array.isArray(j?.alsoSeenOn)&&j.alsoSeenOn.some(x=>x&&x.source))kinds.add('민간');
    return kinds;
  };

  const subjectText=j=>` ${norm([j?.subject,j?.title,j?.schoolLevel,j?.type].filter(Boolean).join(' '))} `;
  const subjectRules={
    '국어':/(^|\s)(국어|한국어)(\s|$)/,
    '영어':/(^|\s)(영어|english)(\s|$)/,
    '수학':/(^|\s)(수학|math)(\s|$)/,
    '사회':/(^|\s)(사회|일반사회)(\s|$)/,
    '역사':/(^|\s)(역사|한국사)(\s|$)/,
    '과학':/(^|\s)(과학|물리|화학|생명과학|지구과학)(\s|$)/,
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

  const writeSnapshot=(p,keys)=>localStorage.setItem(SNAPSHOT_KEY,JSON.stringify({
    version:1,
    fingerprint:fingerprint(p),
    keys:[...new Set(keys)].slice(0,3000),
    checkedAt:new Date().toISOString()
  }));

  function installStyles(){
    if(document.getElementById('jobRadarStyles'))return;
    const style=document.createElement('style');
    style.id='jobRadarStyles';
    style.textContent=`
      .job-radar{margin:0 2px 10px;padding:12px 14px;border:1px solid #dbe6f4;background:linear-gradient(135deg,#f8fbff,#f3f8ff);border-radius:14px}
      .job-radar-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
      .job-radar-title{font-size:13px;font-weight:900;color:#20324d}
      .job-radar-copy{margin-top:4px;font-size:11px;line-height:1.5;color:#66758a}
      .job-radar-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
      .job-radar-btn{border:1px solid #d7e1ee;background:#fff;color:#40516a;border-radius:9px;padding:7px 9px;font-size:10px;font-weight:850;cursor:pointer}
      .job-radar-btn.primary{border-color:#93b8ef;background:#edf5ff;color:#1758b3}
      .job-radar-btn.new{border-color:#9ed9b6;background:#effcf4;color:#087a42}
      .job-radar-btn[disabled]{opacity:.45;cursor:not-allowed}
      .job-radar-count{display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:#e5484d;color:#fff;font-size:10px;font-weight:900;margin-left:5px}
      @media(max-width:650px){.job-radar-head{align-items:flex-start;flex-direction:column}.job-radar-actions{justify-content:flex-start;width:100%}.job-radar-btn{flex:1}}
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
          <div class="job-radar-copy" id="jobRadarCopy">필터와 검색어를 정한 뒤 현재 조건을 저장하면 다음 방문부터 새 공고를 구분해 드립니다.</div>
        </div>
        <div class="job-radar-actions">
          <button type="button" class="job-radar-btn primary" id="jobRadarSave">현재 조건 저장</button>
          <button type="button" class="job-radar-btn" id="jobRadarApply">내 조건 불러오기</button>
          <button type="button" class="job-radar-btn new" id="jobRadarNewOnly">새 공고만</button>
          <button type="button" class="job-radar-btn" id="jobRadarDelete">삭제</button>
        </div>
      </div>`;
    toolbar.parentElement.insertBefore(box,toolbar);

    document.getElementById('jobRadarSave').addEventListener('click',()=>{
      const p=currentProfile();
      if(!hasConditions(p)){document.getElementById('jobRadarCopy').textContent='지역·학교급·직종·과목 또는 검색어를 하나 이상 선택한 뒤 저장해 주세요.';return}
      localStorage.setItem(PROFILE_KEY,JSON.stringify(p));
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
      updatePanel();
      if(typeof render==='function')render();
    });

    document.getElementById('jobRadarDelete').addEventListener('click',()=>{
      localStorage.removeItem(PROFILE_KEY);localStorage.removeItem(SNAPSHOT_KEY);
      currentNewKeys=new Set();currentMatchKeys=[];newOnly=false;
      updatePanel('deleted');
      if(typeof render==='function')render();
    });
  }

  function updatePanel(mode=''){
    const p=readProfile(),copy=document.getElementById('jobRadarCopy'),count=document.getElementById('jobRadarNewCount'),apply=document.getElementById('jobRadarApply'),newBtn=document.getElementById('jobRadarNewOnly');
    if(!copy||!count)return;
    apply.disabled=!p;newBtn.disabled=!p||currentNewKeys.size===0;
    newBtn.textContent=newOnly?'전체 결과로':'새 공고만';
    count.innerHTML=currentNewKeys.size?`<span class="job-radar-count">${currentNewKeys.size}</span>`:'';
    if(mode==='saved'){copy.textContent=`현재 조건을 저장했습니다. 지금 보이는 ${currentMatchKeys.length.toLocaleString()}건을 기준으로 다음 방문부터 새 공고를 알려드립니다.`;return}
    if(mode==='missing'){copy.textContent='저장된 내 조건이 없습니다. 원하는 필터를 선택한 뒤 현재 조건 저장을 눌러 주세요.';return}
    if(mode==='deleted'){copy.textContent='저장된 내 조건과 방문 기준을 삭제했습니다.';return}
    if(!p){copy.textContent='필터와 검색어를 정한 뒤 현재 조건을 저장하면 다음 방문부터 새 공고를 구분해 드립니다.';return}
    if(currentNewKeys.size){copy.textContent=`지난 방문 이후 내 조건에 맞는 새 공고가 ${currentNewKeys.size.toLocaleString()}건 있습니다. 현재 조건 일치 공고는 ${currentMatchKeys.length.toLocaleString()}건입니다.`}
    else copy.textContent=`내 조건을 적용했습니다. 지난 방문 이후 새로 확인된 일치 공고는 없습니다. 현재 ${currentMatchKeys.length.toLocaleString()}건이 조건에 맞습니다.`;
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
      const rows=originalFiltered();
      return newOnly?rows.filter(j=>currentNewKeys.has(jobKey(j))):rows;
    };

    const p=readProfile();
    if(p)applyProfile(p);

    const waitForJobs=()=>{
      if(Array.isArray(jobs)&&jobs.length){recompute();return}
      setTimeout(waitForJobs,150);
    };
    waitForJobs();

    const persistVisit=()=>{
      const profile=readProfile();
      if(!profile||!Array.isArray(jobs)||!jobs.length)return;
      writeSnapshot(profile,matchingKeys(profile));
    };
    window.addEventListener('pagehide',persistVisit,{capture:true});\n    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')persistVisit()},{passive:true});
  };

  waitForApp();
})();