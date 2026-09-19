(()=>{
'use strict';

const $=(s,p=document)=>p.querySelector(s);
const $$=(s,p=document)=>[...p.querySelectorAll(s)];
const store=()=>window.EduJobUserStore;
const PAGE_SIZE=80;
const HOME_LIMIT=10;
const SUBJECT_LIMIT=24;
const ROUTES=new Set(['home','search','radar','saved','me']);

const state={
  payload:null,
  jobs:[],
  indexed:[],
  route:'home',
  q:'',
  surface:'',
  provinces:new Set(),
  regions:new Set(),
  schools:new Set(),
  subjects:new Set(),
  quickFlags:new Set(),
  sort:'newest',
  visible:PAGE_SIZE,
  filterOpen:false,
  filterFocus:'',
  regionQuery:'',
  regionExpanded:false,
  subjectQuery:'',
  subjectExpanded:false,
  radarTab:'conditions',
  savedTab:'saved',
  loading:true,
  error:''
};

const icon=(name)=>{
  const c='viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
  const map={
    home:'<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/>',
    search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    radar:'<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3"/>',
    heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
    user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c.8-4.2 3.5-6.5 8-6.5s7.2 2.3 8 6.5"/>',
    bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    filter:'<path d="M4 5h16l-6 7v6l-4 2v-8z"/>',
    bookmark:'<path d="M6 3h12v18l-6-4-6 4z"/>',
    document:'<path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 12h6M9 16h6"/>',
    users:'<circle cx="9" cy="8" r="3"/><path d="M3.5 20c.5-4 2.4-6 5.5-6s5 2 5.5 6"/><path d="M15 6.5a2.7 2.7 0 0 1 0 5.2M16 14c2.7.4 4.2 2.4 4.5 6"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    database:'<ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 14.8 6L14.5 3h-5L9.2 6a7 7 0 0 0-1.7 1.1l-2.4-1-2 3.4L5.1 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1A7 7 0 0 0 9.2 18l.3 3h5l.3-3a7 7 0 0 0 1.7-1.1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z"/>',
    history:'<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5M12 7v5l3 2"/>',
    pin:'<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2"/>',
    school:'<path d="M3 10h18L12 4 3 10Z"/><path d="M5 10v9h14v-9M9 19v-5h6v5"/>',
    book:'<path d="M4 5a3 3 0 0 1 3-2h5v17H7a3 3 0 0 0-3 2z"/><path d="M20 5a3 3 0 0 0-3-2h-5v17h5a3 3 0 0 1 3 2z"/>'
  };
  return `<svg ${c}>${map[name]||''}</svg>`;
};

const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const norm=(v)=>String(v??'').toLowerCase().replace(/\s+/g,' ').trim();
const arr=(v)=>Array.isArray(v)?v.filter(Boolean):[];
const keyOf=(j)=>String(j?.sourceIdentity||j?.id||j?.verifiedUrl||j?.detailUrl||j?.url||[j?.source,j?.school,j?.title,j?.registered].filter(Boolean).join('|'));
const province=(j)=>String(j?.province||'').trim();
const schoolLevel=(j)=>String(j?.schoolLevel||'미분류').trim()||'미분류';
const jobType=(j)=>String(j?.type||'미분류').trim()||'미분류';
const regionsOf=(j)=>arr(j?.regions).length?arr(j.regions):[j?.region].filter(Boolean);
const today0=()=>{const n=new Date();return new Date(n.getFullYear(),n.getMonth(),n.getDate())};
const parseDate=(v)=>{
  if(!v)return null;
  const m=String(v).match(/(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})/);
  if(!m)return null;
  const d=new Date(+m[1],+m[2]-1,+m[3]);
  return Number.isNaN(d.getTime())?null:d;
};
const dayDiff=(v)=>{
  const d=parseDate(v);if(!d)return null;
  return Math.round((d-today0())/86400000);
};
const isToday=(v)=>{const d=parseDate(v),t=today0();return !!d&&d.getFullYear()===t.getFullYear()&&d.getMonth()===t.getMonth()&&d.getDate()===t.getDate()};
const activeJob=(j)=>{const d=dayDiff(j.applyEnd);return d===null||d>=0};
const fmtDate=(v)=>{const d=parseDate(v);return d?`${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')}`:''};
const registeredLabel=(v)=>{
  const d=parseDate(v);if(!d)return '';
  const diff=Math.floor((today0()-d)/86400000);
  if(diff<=0)return '오늘 등록';
  if(diff===1)return '1일 전';
  if(diff<=6)return `${diff}일 전`;
  return fmtDate(v);
};
const summaryOf=(j)=>{
  const s=String(j.subject||'').trim();
  if(s)return s;
  const fallback=[j.type,j.schoolLevel].filter(Boolean).join(' · ').trim();
  return fallback||'';
};
const regionLabel=(j)=>regionsOf(j).join('·')||province(j)||'지역 미분류';
const deadlineLabel=(j)=>{
  const d=dayDiff(j.applyEnd);
  if(d===null)return '마감일 미정';
  if(d===0)return '오늘 마감';
  if(d>0)return `~ ${fmtDate(j.applyEnd)}`;
  return '마감';
};

function postingLink(j){
  if(j&&j.detailLinkVerified===false)return '';
  if(j&&j.source==='레슨인포'&&j.sourceSurface==='culture-arts'){
    if(j.sourceIdentity==='culture:id:94673'||j.detailLinkVerified!==true)return '';
    return String(j.verifiedUrl||'').trim();
  }
  const board=j?.boardUrl||'';
  const raw=j?.url||'';
  if(j?.openMethod==='POST'&&j.openUrl&&j.openParams&&j.openParams.job_seq){
    const p=new URLSearchParams({url:j.openUrl,job_seq:String(j.openParams.job_seq)});
    return `open-job.html?${p.toString()}`;
  }
  if(province(j)==='서울'&&j?.sourceType==='교육지원청 개별 게시판'){
    try{
      const u=new URL(raw||'',location.href);
      const seq=u.searchParams.get('job_seq');
      if(seq&&/^\d+$/.test(seq)&&u.pathname.endsWith('/FUS/JO/JOV11.do')){
        const p=new URLSearchParams({url:`${u.origin}/FUS/JO/JOV11.do`,job_seq:seq});
        return `open-job.html?${p.toString()}`;
      }
    }catch(e){}
    return '';
  }
  if(province(j)==='경기'&&j?.sourceType==='교육지원청 개별 게시판'){
    try{
      if(raw){
        const u=new URL(raw,location.href);
        if(u.pathname.includes('selectNttInfo.do')&&u.searchParams.get('nttSn'))return u.href;
      }
      if(j?.nttSn&&j?.bbsId&&board){
        const b=new URL(board,location.href);
        const detail=new URL(b.pathname.replace('selectNttList.do','selectNttInfo.do'),b.origin);
        detail.searchParams.set('bbsId',String(j.bbsId));
        if(j.mi)detail.searchParams.set('mi',String(j.mi));
        detail.searchParams.set('nttSn',String(j.nttSn));
        return detail.href;
      }
      if(j?.detailLinkResolved===true&&raw){
        const u=new URL(raw,location.href);
        if(!u.pathname.includes('selectNttList.do'))return u.href;
      }
    }catch(e){}
    return '';
  }
  return raw||'';
}
window.postingLink=postingLink;

const toast=(msg)=>{
  const el=$('#toast');if(!el)return;
  el.textContent=msg;el.classList.add('show');
  clearTimeout(toast._t);toast._t=setTimeout(()=>el.classList.remove('show'),2200);
};

const favoriteKeys=()=>new Set(arr(store()?.favorites?.get?.()));
const setFavoriteKeys=(set)=>store()?.favorites?.set?.([...set].slice(0,1000));
const isFavorite=(j)=>favoriteKeys().has(keyOf(j));
const toggleFavorite=(j)=>{
  const key=keyOf(j);if(!key)return false;
  const set=favoriteKeys(),on=!set.has(key);
  on?set.add(key):set.delete(key);setFavoriteKeys(set);
  return on;
};
const recentRows=()=>arr(store()?.recent?.get?.());
const recordRecent=(j)=>{
  const key=keyOf(j);if(!key)return;
  const next=recentRows().filter(x=>x&&x.key!==key);
  next.unshift({key,seenAt:new Date().toISOString()});
  store()?.recent?.set?.(next.slice(0,50));
};

const buildIndex=(jobs)=>jobs.map((j,i)=>({
  j,i,key:keyOf(j),
  search:norm(j.searchText||[j.school,j.title,j.subject,j.type,j.schoolLevel,j.source,province(j),...regionsOf(j),...arr(j.categories)].filter(Boolean).join(' ')),
  surface:String(j.sourceSurfaceLabel||((j.feedKind==='private')?'학원·민간':'학교·교육청')),
  province:province(j),
  regions:regionsOf(j),
  school:schoolLevel(j),
  subject:String(j.subject||'').trim()||'미분류',
  registered:parseDate(j.registered)?.getTime()||0,
  deadline:parseDate(j.applyEnd)?.getTime()||Number.POSITIVE_INFINITY,
  active:activeJob(j)
}));

const selectedCount=(set)=>set.size;
const matchesFilters=(r)=>{
  if(!r.active)return false;
  if(state.surface&&r.surface!==state.surface)return false;
  if(state.provinces.size&&!state.provinces.has(r.province))return false;
  if(state.regions.size&&!r.regions.some(x=>[...state.regions].some(s=>shortRegion(s)===shortRegion(x))))return false;
  if(state.schools.size&&!state.schools.has(r.school))return false;
  if(state.subjects.size&&!state.subjects.has(r.subject))return false;
  if(state.quickFlags.has('today')&&!isToday(r.j.registered))return false;
  if(state.quickFlags.has('soon')){const d=dayDiff(r.j.applyEnd);if(d===null||d<0||d>3)return false}
  if(state.quickFlags.has('term')&&jobType(r.j)!=='기간제교원')return false;
  if(state.quickFlags.has('office')&&!String(r.j.sourceType||'').includes('교육청'))return false;
  if(state.q&&!r.search.includes(norm(state.q)))return false;
  return true;
};
const filteredRows=()=>{
  const out=state.indexed.filter(matchesFilters);
  out.sort((a,b)=>{
    if(state.sort==='deadline')return a.deadline-b.deadline||b.registered-a.registered;
    if(state.sort==='relevance'&&state.q){
      const q=norm(state.q);
      const score=x=>(norm(x.j.title).includes(q)?4:0)+(norm(x.j.school).includes(q)?2:0)+(norm(x.j.subject).includes(q)?1:0);
      return score(b)-score(a)||b.registered-a.registered;
    }
    return b.registered-a.registered;
  });
  return out;
};

const currentProfile=()=>({
  version:1,
  provinces:[...state.provinces],
  regions:[...state.regions],
  schools:[...state.schools],
  types:[],
  categories:[],
  subjects:[...state.subjects],
  quickFlags:[...state.quickFlags],
  q:String(state.q||'').trim(),
  savedAt:new Date().toISOString()
});
const hasProfileConditions=(p)=>['provinces','regions','schools','types','categories','subjects','quickFlags'].some(k=>arr(p?.[k]).length)||Boolean(String(p?.q||'').trim());
const matchesProfile=(r,p)=>{
  const ps=arr(p?.provinces),rs=arr(p?.regions),ss=arr(p?.schools),subs=arr(p?.subjects),ts=arr(p?.types),cs=arr(p?.categories);
  if(!r.active)return false;
  if(ps.length&&!ps.includes(r.province))return false;
  if(rs.length&&!r.regions.some(x=>rs.some(s=>shortRegion(s)===shortRegion(x))))return false;
  if(ss.length&&!ss.includes(r.school))return false;
  if(subs.length&&!subs.includes(r.subject))return false;
  const qf=new Set(arr(p?.quickFlags));
  if(qf.has('today')&&!isToday(r.j.registered))return false;
  if(qf.has('soon')){const d=dayDiff(r.j.applyEnd);if(d===null||d<0||d>3)return false}
  if(qf.has('term')&&jobType(r.j)!=='기간제교원')return false;
  if(qf.has('office')&&!String(r.j.sourceType||'').includes('교육청'))return false;
  if(ts.length&&!ts.includes(jobType(r.j)))return false;
  if(cs.length&&!arr(r.j.categories).some(x=>cs.includes(x)))return false;
  if(String(p?.q||'').trim()&&!r.search.includes(norm(p.q)))return false;
  return true;
};
const profileMatches=(p)=>state.indexed.filter(r=>matchesProfile(r,p));

const snapshotNewCount=(p)=>{
  if(!p)return 0;
  const current=profileMatches(p).map(r=>r.key);
  const snap=store()?.snapshot?.get?.();
  if(!snap||!Array.isArray(snap.keys))return current.length;
  const old=new Set(snap.keys);
  return current.filter(k=>!old.has(k)).length;
};
const writeSnapshot=(p)=>{
  if(!p)return;
  store()?.snapshot?.set?.({
    version:1,
    keys:profileMatches(p).map(r=>r.key).slice(0,3000),
    checkedAt:new Date().toISOString()
  });
};

const badgeData=(j)=>{
  const out=[];
  const d=dayDiff(j.applyEnd);
  if(d!==null&&d>=0&&d<=3)out.push(['deadline','마감임박']);
  if(isToday(j.registered))out.push(['new','신규']);
  if(jobType(j)==='기간제교원')out.push(['term','기간제']);
  if(String(j.sourceType||'').includes('교육청'))out.push(['gov','교육청']);
  return out.slice(0,2);
};

const cardHtml=(r,{forceFavorite=false}={})=>{
  const j=r.j,on=forceFavorite||isFavorite(j);
  const badges=badgeData(j).map(([cls,label])=>`<span class="badge ${cls}">${esc(label)}</span>`).join('');
  const summary=summaryOf(j);
  const deadline=deadlineLabel(j);
  const showDeadline=Boolean(parseDate(j.applyEnd));
  return `<article class="job-card" data-job-key="${esc(r.key)}" tabindex="0" role="link" aria-label="${esc(j.title||'채용 공고')}">
    <div class="badge-row">${badges}</div>
    <div class="job-content">
      <span class="school-emblem">${icon('school')}</span>
      <div class="job-body">
        <div class="job-school">${esc(j.school||j.source||'기관명 확인')}</div>
        <h3 class="job-title">${esc(j.title||'채용 공고')}</h3>
        ${summary?`<div class="job-summary">${esc(summary)}</div>`:''}
        <div class="job-meta">
          <div class="chip-row">
            <span class="meta-chip">${icon('pin')}${esc(regionLabel(j))}</span>
            <span class="meta-chip">${icon('school')}${esc(schoolLevel(j))}</span>
            ${j.subject?`<span class="meta-chip">${icon('book')}${esc(j.subject)}</span>`:''}
          </div>
          ${showDeadline?`<span class="job-deadline">${esc(deadline)}</span>`:''}
        </div>
      </div>
    </div>
    <span class="job-time">${esc(registeredLabel(j.registered))}</span>
    <button type="button" class="favorite-btn ${on?'on':''}" aria-pressed="${on}" aria-label="${on?'관심공고 해제':'관심공고 저장'}" data-favorite="${esc(r.key)}">${icon('heart')}</button>
  </article>`;
};

const jobsListHtml=(rows,limit,{emptyText='조건에 맞는 모집 중 공고가 없습니다.',forceFavorite=false}={})=>{
  if(!rows.length)return `<div class="empty-state"><strong>${esc(emptyText)}</strong><p>검색 조건을 일부 해제하거나 다른 검색어를 사용해 보세요.</p></div>`;
  const shown=rows.slice(0,limit);
  return `<div class="job-list">${shown.map(r=>cardHtml(r,{forceFavorite})).join('')}${rows.length>shown.length?`<button type="button" class="more-btn" id="moreJobs">공고 더 보기 (${shown.length.toLocaleString()} / ${rows.length.toLocaleString()})</button>`:''}</div>`;
};

const skeleton=()=>`<div class="skeleton"><div class="skeleton-card"></div><div class="skeleton-card"></div><div class="skeleton-card"></div><div class="loading-note">최신 채용정보를 불러오고 있습니다.</div></div>`;

const optionCounts=(getter,rows=state.indexed.filter(r=>r.active))=>{
  const m=new Map();
  rows.forEach(r=>{
    const vals=arr(getter(r));
    vals.forEach(v=>{if(v)m.set(v,(m.get(v)||0)+1)});
  });
  return [...m.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'ko'));
};
const provinceOptions=()=>optionCounts(r=>[r.province]).filter(([v])=>['경기','서울','인천'].includes(v));
const regionOptions=()=>optionCounts(r=>r.regions);
const schoolOptions=()=>optionCounts(r=>[r.school]);
const subjectOptions=()=>{
  const rows=optionCounts(r=>[r.subject]);
  const main=rows.filter(([v])=>v!=='미분류').slice(0,SUBJECT_LIMIT);
  const missing=rows.find(([v])=>v==='미분류');
  return missing?[...main,missing]:main;
};
const regionOptionsForSelectedProvinces=()=>{
  const selectedProvince=[...state.provinces][0];
  if(!selectedProvince)return [];
  const counts=new Map();
  state.indexed.filter(r=>r.active&&r.province===selectedProvince).forEach(r=>{
    r.regions.forEach(raw=>{
      const label=shortRegion(raw);
      if(label)counts.set(label,(counts.get(label)||0)+1);
    });
  });
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],'ko'));
};
const shortRegion=(v)=>String(v||'').replace(/^(경기|서울|인천)\s+/,'');
const optionButton=(name,v,n,selected,label=v)=>`<button type="button" class="quick-option ${selected?'selected':''}" data-quick-filter="${name}" data-value="${esc(v)}"><span>${esc(label)}</span><small>${n.toLocaleString()}</small></button>`;
const selectedSummary=(set,label)=>{
  const n=set.size;
  if(!n)return label;
  const first=[...set][0];
  return n===1?`${label} · ${shortRegion(first)}`:`${label} · ${n}`;
};
const quickCountLabel=()=>state.quickFlags.size?`필터 · ${state.quickFlags.size}`:'필터';

const regionPanelHtml=()=>{
  const provinces=provinceOptions();
  const all=regionOptionsForSelectedProvinces();
  const q=norm(state.regionQuery);
  const filtered=q?all.filter(([v])=>norm(v).includes(q)):all;
  const selected=new Set([...state.regions].map(shortRegion));
  const mustShow=filtered.filter(([v])=>selected.has(v));
  const base=state.regionExpanded||q?filtered:filtered.slice(0,8);
  const merged=[...new Map([...mustShow,...base].map(x=>[x[0],x])).values()];
  return `<div class="quick-filter-panel" data-panel="regions">
    <div class="quick-panel-head"><div><strong>지역</strong><p>시·도를 먼저 고른 뒤 필요한 지역만 선택하세요.</p></div><button type="button" class="panel-close" id="filterClose" aria-label="닫기">×</button></div>
    <div class="province-pills">${provinces.map(([v,n])=>optionButton('provinces',v,n,state.provinces.has(v),v)).join('')}</div>
    ${state.provinces.size?`<label class="filter-search"><span>${icon('search')}</span><input id="regionFilterSearch" type="search" value="${esc(state.regionQuery)}" placeholder="지역 검색"></label>
      <div class="quick-option-grid">${merged.map(([v,n])=>optionButton('regions',v,n,selected.has(v),v)).join('')}</div>
      ${!q&&filtered.length>8?`<button type="button" class="quick-more" id="regionMore">${state.regionExpanded?'간단히 보기':'지역 더보기'}</button>`:''}`
      :'<div class="quick-hint">서울 · 경기 · 인천 중 하나를 먼저 선택하세요.</div>'}
    ${quickPanelFooter()}
  </div>`;
};

const schoolPanelHtml=()=>{
  const opts=schoolOptions().filter(([v])=>v!=='미분류').slice(0,8);
  return `<div class="quick-filter-panel" data-panel="schools">
    <div class="quick-panel-head"><div><strong>학교급</strong><p>필요한 학교급만 빠르게 선택하세요.</p></div><button type="button" class="panel-close" id="filterClose" aria-label="닫기">×</button></div>
    <div class="quick-option-grid two-col">${opts.map(([v,n])=>optionButton('schools',v,n,state.schools.has(v),v)).join('')}</div>
    ${quickPanelFooter()}
  </div>`;
};

const subjectPanelHtml=()=>{
  const all=subjectOptions().filter(([v])=>v!=='미분류');
  const q=norm(state.subjectQuery);
  const filtered=q?all.filter(([v])=>norm(v).includes(q)):all;
  const selected=new Set(state.subjects);
  const mustShow=filtered.filter(([v])=>selected.has(v));
  const base=state.subjectExpanded||q?filtered:filtered.slice(0,8);
  const merged=[...new Map([...mustShow,...base].map(x=>[x[0],x])).values()];
  return `<div class="quick-filter-panel" data-panel="subjects">
    <div class="quick-panel-head"><div><strong>과목·직종</strong><p>자주 찾는 항목만 먼저 보여드립니다.</p></div><button type="button" class="panel-close" id="filterClose" aria-label="닫기">×</button></div>
    <label class="filter-search"><span>${icon('search')}</span><input id="subjectFilterSearch" type="search" value="${esc(state.subjectQuery)}" placeholder="과목 또는 직종 검색"></label>
    <div class="quick-option-grid two-col">${merged.map(([v,n])=>optionButton('subjects',v,n,selected.has(v),v)).join('')}</div>
    ${!q&&filtered.length>8?`<button type="button" class="quick-more" id="subjectMore">${state.subjectExpanded?'간단히 보기':'더보기'}</button>`:''}
    ${quickPanelFooter()}
  </div>`;
};

const morePanelHtml=()=>{
  const opts=[
    ['today','오늘 등록',state.indexed.filter(r=>r.active&&isToday(r.j.registered)).length],
    ['soon','3일 내 마감',state.indexed.filter(r=>{if(!r.active)return false;const d=dayDiff(r.j.applyEnd);return d!==null&&d>=0&&d<=3}).length],
    ['term','기간제',state.indexed.filter(r=>r.active&&jobType(r.j)==='기간제교원').length],
    ['office','교육청',state.indexed.filter(r=>r.active&&String(r.j.sourceType||'').includes('교육청')).length]
  ];
  return `<div class="quick-filter-panel" data-panel="more">
    <div class="quick-panel-head"><div><strong>빠른 필터</strong><p>많이 쓰는 조건만 남겼습니다.</p></div><button type="button" class="panel-close" id="filterClose" aria-label="닫기">×</button></div>
    <div class="quick-option-grid two-col">${opts.map(([v,label,n])=>optionButton('quickFlags',v,n,state.quickFlags.has(v),label)).join('')}</div>
    ${quickPanelFooter()}
  </div>`;
};

const quickPanelFooter=()=>`<div class="quick-panel-footer"><button type="button" class="panel-reset" id="filterReset">초기화</button><button type="button" class="panel-apply" id="filterApply">${filteredRows().length.toLocaleString()}건 공고 보기</button></div>`;

const quickFilterPanelHtml=()=>{
  if(!state.filterOpen)return '';
  if(state.filterFocus==='schools')return schoolPanelHtml();
  if(state.filterFocus==='subjects')return subjectPanelHtml();
  if(state.filterFocus==='more')return morePanelHtml();
  return regionPanelHtml();
};

const homeHtml=()=>{
  const p=store()?.profile?.get?.();
  const favorites=favoriteKeys().size;
  const alerts=store()?.alerts?.get?.()||{enabled:false};
  const active=state.indexed.filter(r=>r.active);
  const soon=active.filter(r=>{const d=dayDiff(r.j.applyEnd);return d!==null&&d>=0&&d<=3}).length;
  const today=active.filter(r=>isToday(r.j.registered)).length;
  const latest=[...active].sort((a,b)=>b.registered-a.registered).slice(0,HOME_LIMIT);
  return `<section class="home-radar">
    <div class="radar-top"><div><h2><span class="radar-heading-icon">${icon('radar')}</span>내 채용 레이더</h2><p>내 조건에 맞는 새로운 일자리를 찾아드려요!</p></div><div class="radar-mascot"><img src="assets/mascot.png?v=20260920b" width="70" height="70" alt="수도권에듀잡 마스코트" loading="lazy"><span>좋은 기회가<br>기다리고 있어요!</span></div></div>
    <div class="metric-grid">
      <button class="metric" data-home="new"><span class="metric-icon">${icon('document')}</span><b>${p?snapshotNewCount(p):0}</b><strong>새 공고</strong><small>지난 방문 이후</small></button>
      <button class="metric" data-home="saved"><span class="metric-icon">${icon('heart')}</span><b>${favorites}</b><strong>관심 공고</strong><small>저장한 공고</small></button>
      <button class="metric" data-home="radar"><span class="metric-icon">${icon('bookmark')}</span><b>${p?1:0}</b><strong>저장 조건</strong><small>내 검색 조건</small></button>
      <button class="metric" data-home="alert"><span class="metric-icon">${icon('bell')}</span><b>${alerts.enabled?'✓':'-'}</b><strong>알림 ${alerts.enabled?'켜짐':'꺼짐'}</strong><small>새 공고 알림</small></button>
    </div>
    <div class="radar-actions">
      <button type="button" data-radar-action="save">현재 조건 저장</button><button type="button" data-radar-action="load">내 조건 불러오기</button><button type="button" data-radar-action="new">새 공고만</button><button type="button" data-radar-action="saved">관심공고</button>
    </div>
  </section>
  <div class="section-title"><span>${icon('database')}</span><h2>채용 현황</h2><span class="spacer"></span><button class="link-btn" data-go="search">전체보기 ›</button></div>
  <div class="status-grid">
    <div class="status-card"><span class="status-icon">${icon('users')}</span><b>${active.length.toLocaleString()}</b><span>모집 중</span></div>
    <div class="status-card"><span class="status-icon">${icon('calendar')}</span><b>${soon.toLocaleString()}</b><span>3일 내 마감</span></div>
    <div class="status-card"><span class="status-icon">${icon('document')}</span><b>${today.toLocaleString()}</b><span>오늘 등록</span></div>
    <div class="status-card"><span class="status-icon">${icon('database')}</span><b>${Number(state.payload?.totalSourceCount||0).toLocaleString()}</b><span>수집 출처</span></div>
  </div>
  <div class="filter-row"><strong>빠른 검색</strong><button type="button" class="reset-btn" id="homeReset">전체 초기화</button><button type="button" class="open-filter" data-go="search">조건 찾기</button></div>
  <div class="section-title"><span>${icon('document')}</span><h2>최신 채용 공고</h2><span class="spacer"></span><button class="link-btn" data-go="search">전체보기 ›</button></div>
  ${jobsListHtml(latest,HOME_LIMIT)}`;
};

const searchHtml=()=>{
  const rows=filteredRows();
  return `<div class="search-filter-row">
    <button type="button" class="grow ${state.filterOpen&&state.filterFocus==='regions'?'active':''}" data-filter-focus="regions">${esc(selectedSummary(state.regions,'지역'))}⌄</button>
    <button type="button" class="grow ${state.filterOpen&&state.filterFocus==='schools'?'active':''}" data-filter-focus="schools">${esc(selectedSummary(state.schools,'학교급'))}⌄</button>
    <button type="button" class="grow ${state.filterOpen&&state.filterFocus==='subjects'?'active':''}" data-filter-focus="subjects">${esc(selectedSummary(state.subjects,'과목'))}⌄</button>
    <button type="button" class="filter-main ${state.filterOpen&&state.filterFocus==='more'?'active':''}" data-filter-focus="more">${icon('filter')}<span>${esc(quickCountLabel())}</span></button>
  </div>
  ${quickFilterPanelHtml()}
  <div class="results-bar"><span>검색 결과 <strong>${rows.length.toLocaleString()}</strong>건</span><select id="sortSelect" class="results-sort" aria-label="정렬"><option value="newest" ${state.sort==='newest'?'selected':''}>최신순</option><option value="deadline" ${state.sort==='deadline'?'selected':''}>마감임박순</option><option value="relevance" ${state.sort==='relevance'?'selected':''}>관련도순</option></select></div>
  ${jobsListHtml(rows,state.visible)}`;
};

const profileSummary=(p)=>{
  const items=[];
  if(arr(p?.provinces).length)items.push(arr(p.provinces).join('·'));
  if(arr(p?.regions).length)items.push(arr(p.regions).slice(0,3).join('·')+(arr(p.regions).length>3?` +${arr(p.regions).length-3}`:''));
  if(arr(p?.schools).length)items.push(arr(p.schools).join('·'));
  if(arr(p?.subjects).length)items.push(arr(p.subjects).slice(0,2).join('·'));
  if(p?.q)items.push(`“${p.q}”`);
  return items.join(' · ')||'저장된 상세 조건';
};

const radarHtml=()=>{
  const p=store()?.profile?.get?.(),a=store()?.alerts?.get?.()||{enabled:false};
  const matches=p?profileMatches(p):[];
  if(state.radarTab==='matches'&&p)writeSnapshot(p);
  return `<section class="radar-page">
    <div class="hero-row"><div class="hero-copy"><div class="hero-title-row"><button type="button" class="back-btn" data-go="home" aria-label="홈으로">←</button><h1>내 채용 레이더</h1></div><p>내가 원하는 조건에 맞는 공고를 자동으로 찾아드려요.</p></div><img src="assets/mascot.png?v=20260920b" width="76" height="64" alt="수도권에듀잡 마스코트" loading="lazy"></div>
    <div class="segment-tabs"><button type="button" data-radar-tab="conditions" class="${state.radarTab==='conditions'?'active':''}">내 조건</button><button type="button" data-radar-tab="matches" class="${state.radarTab==='matches'?'active':''}">맞춤 공고</button></div>
    ${state.radarTab==='conditions'?
      `<div class="condition-card"><div class="condition-head"><strong>저장된 검색 조건 (${p?1:0})</strong><button type="button" data-go="search">＋ 새 조건 추가</button></div>
      ${p?`<div class="saved-condition"><div><strong>${esc(p.q||'내 채용 조건')}</strong><p>${esc(profileSummary(p))}</p><em>새 공고 ${snapshotNewCount(p).toLocaleString()}건</em></div><details class="condition-menu"><summary aria-label="저장 조건 메뉴">⋯</summary><div class="condition-menu-pop"><button type="button" id="conditionEdit">수정</button><button type="button" class="danger" id="conditionDelete">삭제</button></div></details></div>`:
      '<div class="empty-state"><strong>저장된 조건이 없습니다.</strong><p>공고검색에서 원하는 조건을 선택한 뒤 저장해 주세요.</p></div>'}</div>`
      :jobsListHtml(matches,state.visible,{emptyText:'저장 조건에 맞는 모집 중 공고가 없습니다.'})
    }
    <div class="alert-card"><div class="alert-copy">${icon('bell')}<div><strong>알림 설정</strong><p>새로운 공고가 등록되면 저장한 조건 기준으로 알려드립니다.</p></div></div><button type="button" class="switch ${a.enabled?'on':''}" id="alertToggle" aria-label="알림 ${a.enabled?'켜짐':'꺼짐'}"></button></div>
    <div class="tip-card"><img src="assets/mascot.png?v=20260920b" width="72" height="66" alt="수도권에듀잡 마스코트" loading="lazy"><div><strong>내 조건에 딱 맞는<br>좋은 기회를 찾아드릴게요!</strong><p>✓ 새로운 공고 자동 확인<br>✓ 조건별 맞춤 알림<br>✓ 관심 공고와 쉽게 비교</p></div></div>
  </section>`;
};

const savedHtml=()=>{
  const fav=favoriteKeys();
  const savedRows=state.indexed.filter(r=>fav.has(r.key)&&r.active).sort((a,b)=>b.registered-a.registered);
  const recentMap=new Map(state.indexed.map(r=>[r.key,r]));
  const recent=recentRows().map(x=>recentMap.get(x.key)).filter(Boolean);
  const rows=state.savedTab==='saved'?savedRows:recent;
  return `<section class="saved-page"><div class="segment-tabs"><button type="button" data-saved-tab="saved" class="${state.savedTab==='saved'?'active':''}">저장한 공고 (${savedRows.length})</button><button type="button" data-saved-tab="recent" class="${state.savedTab==='recent'?'active':''}">최근 본 공고</button></div>
  ${rows.length?jobsListHtml(rows,state.visible,{forceFavorite:state.savedTab==='saved'}):`<div class="empty-state saved-tip"><img src="assets/mascot.png?v=20260920b" width="76" height="68" alt="수도권에듀잡 마스코트" loading="lazy"><strong>${state.savedTab==='saved'?'관심 있는 공고를 저장하고 놓치지 마세요!':'최근 본 공고가 없습니다.'}</strong><p>${state.savedTab==='saved'?'✓ 중요한 공고 따로 관리<br>✓ 마감 임박 공고 다시 확인<br>✓ 내 채용 레이더와 함께 활용':'공고를 열어보면 최근 본 공고에 최대 50건까지 기록됩니다.'}</p><button type="button" class="empty-cta" data-go="search">공고 검색하러 가기</button></div>`}</section>`;
};

const meHtml=()=>{
  const fav=favoriteKeys().size,p=store()?.profile?.get?.(),recent=recentRows().length,a=store()?.alerts?.get?.()||{enabled:false};
  const row=(ic,label,action,status='',disabled=false)=>`<button type="button" data-me="${action}" ${disabled?'disabled':''}>${icon(ic)}<span>${esc(label)}</span><em class="${status?'status':''}">${status?esc(status):'›'}</em></button>`;
  return `<div class="me-profile"><div class="avatar">${icon('user')}</div><div><strong>선생님</strong><p>안녕하세요!</p></div><span style="margin-left:auto;color:#2b7cf3">${icon('settings')}</span></div>
  <div class="me-stats"><div><span>저장한 공고</span><b>${fav}</b></div><div><span>저장한 조건</span><b>${p?1:0}</b></div><div><span>최근 본 공고</span><b>${recent}</b></div></div>
  <div class="menu-list menu-list-single">
    ${row('user','내 정보 관리','profile','준비 중',true)}
    ${row('bell','알림 설정','alerts',a.enabled?'켜짐':'꺼짐')}
    ${row('bookmark','저장한 조건','radar')}
    ${row('heart','관심공고','saved')}
    ${row('history','최근 본 공고','recent')}
    ${row('document','이용 가이드','guide','준비 중',true)}
    ${row('document','문의하기','contact','준비 중',true)}
    ${row('document','서비스 소개','about','준비 중',true)}
  </div>
  <button type="button" class="device-reset" id="deviceReset">내 기기 데이터 초기화</button>`;
};

const errorHtml=()=>`<div class="empty-state"><strong>채용 데이터 파일을 불러오지 못했습니다.</strong><p>잠시 후 다시 접속해 주세요. 기존 수집 데이터는 변경하지 않습니다.</p></div>`;

function render(){
  const screen=$('#screen');if(!screen)return;
  const searchTop=$('#searchTop');
  if(searchTop)searchTop.hidden=!['home','search'].includes(state.route);
  $$('#bottomNav [data-route]').forEach(a=>a.classList.toggle('active',a.dataset.route===state.route));
  $$('#surfaceSegment [data-surface]').forEach(b=>b.classList.toggle('active',b.dataset.surface===state.surface));
  const input=$('#searchInput');if(input&&input.value!==state.q)input.value=state.q;
  $('#searchClear')?.classList.toggle('show',Boolean(state.q));

  if(state.loading){screen.innerHTML=skeleton();bindCommon();return}
  if(state.error){screen.innerHTML=errorHtml();bindCommon();return}

  state.visible=Math.max(PAGE_SIZE,state.visible);
  if(state.route==='home')screen.innerHTML=homeHtml();
  else if(state.route==='search')screen.innerHTML=searchHtml();
  else if(state.route==='radar')screen.innerHTML=radarHtml();
  else if(state.route==='saved')screen.innerHTML=savedHtml();
  else screen.innerHTML=meHtml();

  bindScreen();
  bindCommon();
}

function resetFilters({surface=true}={}){
  state.provinces.clear();state.regions.clear();state.schools.clear();state.subjects.clear();state.quickFlags.clear();
  state.q='';state.sort='newest';state.visible=PAGE_SIZE;state.filterOpen=false;state.filterFocus='';
  state.regionQuery='';state.regionExpanded=false;state.subjectQuery='';state.subjectExpanded=false;
  if(surface)state.surface='';
  render();
}
function applyProfileToState(p){
  if(!p)return;
  state.provinces=new Set(arr(p.provinces));
  state.regions=new Set(arr(p.regions));
  state.schools=new Set(arr(p.schools));
  state.subjects=new Set(arr(p.subjects));
  state.quickFlags=new Set(arr(p.quickFlags));
  state.q=String(p.q||'');
  state.visible=PAGE_SIZE;
}
function setRoute(route){
  if(!ROUTES.has(route))route='home';
  state.route=route;state.visible=PAGE_SIZE;state.filterOpen=false;
  if(location.hash!==`#/${route}`)location.hash=`#/${route}`;
  else render();
  window.scrollTo({top:0,behavior:'instant'});
}
function routeFromHash(){
  const route=(location.hash.match(/^#\/(home|search|radar|saved|me)/)||[])[1]||'home';
  state.route=route;state.visible=PAGE_SIZE;state.filterOpen=false;render();
}

function bindCommon(){
  $$('[data-go]').forEach(b=>b.onclick=()=>setRoute(b.dataset.go));
}
function bindScreen(){
  const screen=$('#screen');
  if(!screen)return;

  $('#moreJobs',screen)?.addEventListener('click',()=>{state.visible+=PAGE_SIZE;render()});
  $('#homeReset',screen)?.addEventListener('click',()=>resetFilters());
  $('[data-filter-focus]',screen).forEach(b=>b.addEventListener('click',()=>{
    const focus=b.dataset.filterFocus;
    if(state.filterOpen&&state.filterFocus===focus){state.filterOpen=false;state.filterFocus=''}
    else{state.filterOpen=true;state.filterFocus=focus}
    state.visible=PAGE_SIZE;render();
  }));
  $('#filterClose',screen)?.addEventListener('click',()=>{state.filterOpen=false;state.filterFocus='';render()});
  $('#filterReset',screen)?.addEventListener('click',()=>{
    state.provinces.clear();state.regions.clear();state.schools.clear();state.subjects.clear();state.quickFlags.clear();
    state.regionQuery='';state.regionExpanded=false;state.subjectQuery='';state.subjectExpanded=false;state.visible=PAGE_SIZE;render();
  });
  $('#filterApply',screen)?.addEventListener('click',()=>{state.filterOpen=false;state.filterFocus='';state.visible=PAGE_SIZE;render()});
  $('#sortSelect',screen)?.addEventListener('change',e=>{state.sort=e.target.value;state.visible=PAGE_SIZE;render()});
  $('[data-quick-filter]',screen).forEach(btn=>btn.addEventListener('click',()=>{
    const name=btn.dataset.quickFilter,value=btn.dataset.value;
    const set=state[name];if(!(set instanceof Set))return;
    if(name==='provinces'){
      const wasSelected=set.has(value);
      set.clear();
      if(!wasSelected)set.add(value);
      state.regions.clear();
      state.regionQuery='';state.regionExpanded=false;
    }else{
      set.has(value)?set.delete(value):set.add(value);
    }
    state.visible=PAGE_SIZE;render();
  }));
  $('#regionMore',screen)?.addEventListener('click',()=>{state.regionExpanded=!state.regionExpanded;render()});
  $('#subjectMore',screen)?.addEventListener('click',()=>{state.subjectExpanded=!state.subjectExpanded;render()});
  $('#regionFilterSearch',screen)?.addEventListener('input',e=>{state.regionQuery=e.target.value;state.regionExpanded=true;render();setTimeout(()=>$('#regionFilterSearch')?.focus(),0)});
  $('#subjectFilterSearch',screen)?.addEventListener('input',e=>{state.subjectQuery=e.target.value;state.subjectExpanded=true;render();setTimeout(()=>$('#subjectFilterSearch')?.focus(),0)});

  $$('[data-home]',screen).forEach(b=>b.addEventListener('click',()=>{
    const x=b.dataset.home;
    if(x==='saved')setRoute('saved');
    else if(x==='radar'||x==='new')setRoute('radar');
    else if(x==='alert')setRoute('radar');
  }));
  $$('[data-radar-action]',screen).forEach(b=>b.addEventListener('click',()=>{
    const x=b.dataset.radarAction;
    if(x==='save'){
      const p=currentProfile();
      if(!hasProfileConditions(p)){toast('검색어나 필터 조건을 먼저 선택해 주세요.');return}
      store()?.profile?.set?.(p);writeSnapshot(p);toast('현재 검색 조건을 저장했습니다.');render();
    }else if(x==='load'){
      const p=store()?.profile?.get?.();if(!p){toast('저장된 조건이 없습니다.');return}
      applyProfileToState(p);setRoute('search');
    }else if(x==='new'){
      const p=store()?.profile?.get?.();if(!p){toast('먼저 검색 조건을 저장해 주세요.');return}
      applyProfileToState(p);setRoute('search');
    }else if(x==='saved')setRoute('saved');
  }));

  $$('[data-radar-tab]',screen).forEach(b=>b.addEventListener('click',()=>{state.radarTab=b.dataset.radarTab;state.visible=PAGE_SIZE;render()}));
  $('#conditionEdit',screen)?.addEventListener('click',()=>{const p=store()?.profile?.get?.();if(p)applyProfileToState(p);setRoute('search')});
  $('#conditionDelete',screen)?.addEventListener('click',()=>{if(!confirm('저장한 검색 조건을 삭제할까요?'))return;store()?.profile?.remove?.();store()?.snapshot?.remove?.();toast('저장 조건을 삭제했습니다.');render()});
  $('#alertToggle',screen)?.addEventListener('click',()=>{
    const legacy=$('#jobRadarAlerts');
    if(legacy){legacy.click();setTimeout(render,600)}else toast('이 브라우저에서는 알림 설정을 사용할 수 없습니다.');
  });

  $$('[data-saved-tab]',screen).forEach(b=>b.addEventListener('click',()=>{state.savedTab=b.dataset.savedTab;state.visible=PAGE_SIZE;render()}));
  $$('[data-me]',screen).forEach(b=>b.addEventListener('click',()=>{
    const x=b.dataset.me;
    if(x==='alerts')setRoute('radar');
    else if(x==='radar')setRoute('radar');
    else if(x==='saved'){state.savedTab='saved';setRoute('saved')}
    else if(x==='recent'){state.savedTab='recent';setRoute('saved')}
  }));
  $('#deviceReset',screen)?.addEventListener('click',()=>{
    if(!confirm('이 기기에 저장된 관심공고, 검색조건, 최근 본 공고와 알림 설정을 초기화할까요?'))return;
    store()?.resetLocal?.();toast('이 기기의 저장 데이터를 초기화했습니다.');render();
  });

  $$('.favorite-btn',screen).forEach(btn=>btn.addEventListener('click',e=>{
    e.stopPropagation();
    const r=state.indexed.find(x=>x.key===btn.dataset.favorite);if(!r)return;
    const on=toggleFavorite(r.j);btn.classList.toggle('on',on);btn.setAttribute('aria-pressed',String(on));render();
  }));
  $$('.job-card',screen).forEach(card=>{
    const open=()=>{
      const r=state.indexed.find(x=>x.key===card.dataset.jobKey);if(!r)return;
      const href=window.postingLink(r.j);
      if(!href){toast('원문 링크를 확인 중인 공고입니다.');return}
      recordRecent(r.j);
      window.open(href,'_blank','noopener');
    };
    card.addEventListener('click',e=>{if(e.target.closest('.favorite-btn'))return;open()});
    card.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&!e.target.closest('.favorite-btn')){e.preventDefault();open()}});
  });
}

function installStaticEvents(){
  $('#searchForm')?.addEventListener('submit',e=>{
    e.preventDefault();state.q=$('#searchInput')?.value||'';state.visible=PAGE_SIZE;setRoute('search');
  });
  let timer=0;
  $('#searchInput')?.addEventListener('input',e=>{
    state.q=e.target.value;$('#searchClear')?.classList.toggle('show',Boolean(state.q));
    clearTimeout(timer);timer=setTimeout(()=>{if(state.route==='search'){state.visible=PAGE_SIZE;render()}},180);
  });
  $('#searchClear')?.addEventListener('click',()=>{state.q='';const q=$('#searchInput');if(q)q.value='';state.visible=PAGE_SIZE;render();q?.focus()});
  $$('#surfaceSegment [data-surface]').forEach(b=>b.addEventListener('click',()=>{state.surface=b.dataset.surface;state.visible=PAGE_SIZE;render()}));
  $('#headerMenuBtn')?.addEventListener('click',()=>setRoute('me'));
  $('#headerAlertBtn')?.addEventListener('click',()=>setRoute('radar'));
  const compactHeader=()=>$('#appHeader')?.classList.toggle('compact',window.scrollY>36);
  window.addEventListener('scroll',compactHeader,{passive:true});compactHeader();
  window.addEventListener('hashchange',routeFromHash);
  window.addEventListener('edujob:user-state-changed',()=>render());
}

function installIcons(){
  $('[data-icon="home"]')?.insertAdjacentHTML('beforeend',icon('home'));
  $('[data-icon="search"]')?.insertAdjacentHTML('beforeend',icon('search'));
  $('[data-icon="radar"]')?.insertAdjacentHTML('beforeend',icon('radar'));
  $('[data-icon="heart"]')?.insertAdjacentHTML('beforeend',icon('heart'));
  $('[data-icon="user"]')?.insertAdjacentHTML('beforeend',icon('user'));
  const si=$('.search-icon');if(si)si.innerHTML=icon('search');
  const ab=$('#headerAlertBtn');if(ab)ab.innerHTML=icon('bell');
  const mb=$('#headerMenuBtn');if(mb)mb.innerHTML=icon('menu');
}

async function loadData(){
  state.loading=true;render();
  try{
    const res=await fetch('unified_jobs.json',{cache:'no-cache'});
    if(!res.ok)throw new Error(`HTTP ${res.status}`);
    const payload=await res.json();
    if(!payload||!Array.isArray(payload.jobs))throw new Error('invalid unified_jobs.json');
    state.payload=payload;state.jobs=payload.jobs;state.indexed=buildIndex(payload.jobs);
    state.error='';
  }catch(e){
    console.error(e);state.error='load-failed';
  }finally{
    state.loading=false;render();
  }
}

installIcons();
installStaticEvents();
if(!location.hash)history.replaceState(null,'','#/home');
routeFromHash();
loadData();
})();
