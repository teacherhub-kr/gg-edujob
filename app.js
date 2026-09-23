(()=>{
'use strict';

const $=(s,p=document)=>p.querySelector(s);
const $$=(s,p=document)=>[...p.querySelectorAll(s)];
const store=()=>window.EduJobUserStore;
const PAGE_SIZE=80;
const HOME_LIMIT=10;
const SUBJECT_LIMIT=24;
const ROUTES=new Set(['home','search','radar','saved','me']);
const APP_URL='https://teacherhub-kr.github.io/gg-edujob/';
const INSTALL_DISMISS_KEY='edujob.installPrompt.dismissed.v1';
const pushCapable=()=>('serviceWorker'in navigator)&&('PushManager'in window)&&('Notification'in window);
const isIOSDevice=()=>/iphone|ipad|ipod/i.test(navigator.userAgent||'')||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const isAndroidDevice=()=>/android/i.test(navigator.userAgent||'');
const isStandaloneApp=()=>window.matchMedia?.('(display-mode: standalone)').matches===true||navigator.standalone===true;
const pushReady=()=>pushCapable()&&(!isIOSDevice()||isStandaloneApp());
const chromeIntentUrl=()=>`intent://teacherhub-kr.github.io/gg-edujob/#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${encodeURIComponent(APP_URL)};end`;
let deferredInstallPrompt=null;
const installDismissed=()=>{try{return localStorage.getItem(INSTALL_DISMISS_KEY)==='1'}catch(e){return false}};
const dismissInstallPrompt=()=>{try{localStorage.setItem(INSTALL_DISMISS_KEY,'1')}catch(e){}};
const shouldShowInstallCard=()=>!isStandaloneApp()&&!installDismissed();
const copyAppUrl=async()=>{
  try{
    if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(APP_URL);return true}
  }catch(e){}
  try{
    const t=document.createElement('textarea');t.value=APP_URL;t.setAttribute('readonly','');t.style.position='fixed';t.style.opacity='0';
    document.body.appendChild(t);t.select();const ok=document.execCommand('copy');t.remove();return ok;
  }catch(e){return false}
};

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
  types:new Set(),
  sources:new Set(),
  categories:new Set(),
  subjects:new Set(),
  sort:'newest',
  visible:PAGE_SIZE,
  filterOpen:false,
  filterFocus:'',
  radarTab:'conditions',
  radarMode:'all',
  radarNewKeys:null,
  savedTab:'saved',
  loading:true,
  error:''
};

const GYEONGGI_REGIONS=['수원시','성남시','용인시','고양시','화성시','안산시','평택시','파주시','김포시','남양주시','부천시','안양시','시흥시','광명시','광주시','군포시','이천시','오산시','안성시','의왕시','하남시','여주시','양평군','과천시','의정부시','양주시','구리시','포천시','동두천시','가평군','연천군'];
const SEOUL_REGIONS=['강남구','강동구','강북구','강서구','관악구','광진구','구로구','금천구','노원구','도봉구','동대문구','동작구','마포구','서대문구','서초구','성동구','성북구','송파구','양천구','영등포구','용산구','은평구','종로구','중구','중랑구'];
const INCHEON_REGIONS=['중구','동구','미추홀구','연수구','남동구','부평구','계양구','서구','강화군','옹진군'];
const SCHOOL_VALUES=['유치원','초등학교','중학교','고등학교','특수학교','교육행정기관','기타'];
const TYPE_VALUES=['기간제교원','시간강사/강사','교육공무직/기간제근로자','정규채용','자원봉사','기타'];
const SOURCE_VALUES=['공식','민간'];
const CATEGORY_VALUES=['방과후·늘봄','음악·예체능','문화예술','학원강사','강사·교사','기타 민간구인'];
const SUBJECT_VALUES=['국어','영어','수학','과학','사회·역사','음악','미술','체육','특수','보건','상담','사서','영양','정보·컴퓨터','유아'];
const SUBJECT_RULES={
  '국어':/(^|\s)(국어|독서|논술)(\s|$)/,
  '영어':/(^|\s)(영어|영어회화)(\s|$)/,
  '수학':/(^|\s)(수학|수리)(\s|$)/,
  '과학':/(^|\s)(과학|물리|화학|생명과학|생물|지구과학|통합과학)(\s|$)/,
  '사회·역사':/(^|\s)(사회|역사|한국사|지리|윤리|도덕|통합사회)(\s|$)/,
  '음악':/(^|\s)(음악|합창|오케스트라|관현악|밴드)(\s|$)/,
  '미술':/(^|\s)(미술|디자인)(\s|$)/,
  '체육':/(^|\s)(체육|스포츠|운동)(\s|$)/,
  '특수':/(^|\s)(특수|특수교육)(\s|$)/,
  '보건':/(^|\s)(보건|간호)(\s|$)/,
  '상담':/(^|\s)(상담|전문상담|위클래스|wee)(\s|$)/,
  '사서':/(^|\s)(사서|도서관)(\s|$)/,
  '영양':/(^|\s)(영양|영양교사)(\s|$)/,
  '정보·컴퓨터':/(^|\s)(정보|컴퓨터|코딩|소프트웨어|ai|인공지능)(\s|$)/,
  '유아':/(^|\s)(유아|유치원|유치)(\s|$)/,
};
const regionKey=(v)=>String(v||'').replace(/^(경기도|서울특별시|인천광역시|경기|서울|인천)\s*/,'').trim();
const regionsMatch=(selected,actual)=>[...selected].some(s=>regionKey(s)===regionKey(actual));
const subjectHay=(j)=>` ${norm([j.subject,j.title,j.schoolLevel,j.type].filter(Boolean).join(' '))} `;
const matchesSubject=(j,label)=>SUBJECT_RULES[label]?.test(subjectHay(j))===true;
const sourceKinds=(j)=>new Set([j?.feedKind==='private'?'민간':'공식',...(arr(j?.alsoSeenOn).length?['민간']:[])]);
const categorySet=(j)=>new Set(arr(j?.categories));

const installCardHtml=()=>{
  if(!shouldShowInstallCard())return '';
  if(isIOSDevice()){
    return `<section class="install-card install-card-ios" aria-label="에듀잡 홈 화면 추가 안내">
      <button type="button" class="install-dismiss" data-install-dismiss aria-label="설치 안내 닫기">×</button>
      <div class="install-card-head">
        <img src="edujob-icon.svg" width="52" height="52" alt="" aria-hidden="true">
        <div><strong>에듀잡을 홈 화면에 추가하세요</strong><p>앱처럼 바로 열고, 새 공고 알림도 받을 수 있습니다.</p></div>
      </div>
      <div class="ios-install-steps">
        <span><b>1</b>브라우저의 <strong>공유</strong> 메뉴 열기</span>
        <span><b>2</b><strong>홈 화면에 추가</strong> 선택</span>
        <span><b>3</b>홈 화면의 <strong>에듀잡</strong>으로 실행</span>
      </div>
      <small>iPhone·iPad 알림은 홈 화면에 추가한 에듀잡 앱에서 켤 수 있습니다.</small>
    </section>`;
  }
  const canPrompt=Boolean(deferredInstallPrompt);
  return `<section class="install-card install-card-android" aria-label="에듀잡 앱 설치 안내">
    <button type="button" class="install-dismiss" data-install-dismiss aria-label="설치 안내 닫기">×</button>
    <div class="install-card-head">
      <img src="edujob-icon.svg" width="52" height="52" alt="" aria-hidden="true">
      <div><strong>에듀잡을 앱처럼 사용하세요</strong><p>홈 화면에서 바로 열고 새 공고를 더 빠르게 확인할 수 있습니다.</p></div>
    </div>
    ${canPrompt
      ?'<button type="button" class="install-primary-btn" id="appInstallBtn">에듀잡 앱 설치</button>'
      :'<div class="install-manual-note">브라우저 메뉴에서 <strong>앱 설치</strong> 또는 <strong>홈 화면에 추가</strong>를 선택하세요.</div>'}
  </section>`;
};

window.addEventListener('beforeinstallprompt',event=>{
  event.preventDefault();
  deferredInstallPrompt=event;
  if(!state.loading&&state.route==='home')render();
});
window.addEventListener('appinstalled',()=>{
  deferredInstallPrompt=null;
  dismissInstallPrompt();
  toast('에듀잡이 홈 화면에 설치되었습니다.');
  if(!state.loading)render();
});

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
const schoolLevel=(j)=>{
  const raw=String(j?.schoolLevel||'').trim();
  if(raw==='교육지원청')return '교육행정기관';
  if(SCHOOL_VALUES.includes(raw))return raw;
  const t=`${j?.school||''} ${j?.title||''}`;
  if(/특수학교/.test(t))return '특수학교';
  if(/유치원|병설유/.test(t))return '유치원';
  if(/초등학교/.test(t))return '초등학교';
  if(/중학교/.test(t))return '중학교';
  if(/고등학교/.test(t))return '고등학교';
  if(/교육지원청|교육청/.test(t))return '교육행정기관';
  return '기타';
};
const jobType=(j)=>{
  const raw=String(j?.type||'').trim();
  if(raw==='교육공무직')return '교육공무직/기간제근로자';
  if(TYPE_VALUES.includes(raw))return raw;
  const t=`${raw} ${j?.title||''} ${j?.subject||''}`;
  if(/자원봉사|봉사자/.test(t))return '자원봉사';
  if(/정규/.test(t))return '정규채용';
  if(/교육공무직|기간제근로|조리실무|돌봄전담/.test(t))return '교육공무직/기간제근로자';
  if(/시간강사|강사|시간제/.test(t))return '시간강사/강사';
  if(/기간제|교원|교사/.test(t))return '기간제교원';
  return '기타';
};
const regionsOf=(j)=>arr(j?.regions).length?arr(j.regions):[j?.region].filter(Boolean);
const today0=()=>{const n=new Date();return new Date(n.getFullYear(),n.getMonth(),n.getDate())};
const parseDate=(v)=>{
  if(!v)return null;
  const m=String(v).match(/(\d{4})[.\/-](\d{1,2})[.\/-](\d{1,2})/);
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
  type:jobType(j),
  sources:sourceKinds(j),
  categories:categorySet(j),
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
  if(state.regions.size&&!r.regions.some(x=>regionsMatch(state.regions,x)))return false;
  if(state.schools.size&&!state.schools.has(r.school))return false;
  if(state.types.size&&!state.types.has(r.type))return false;
  if(state.sources.size&&![...state.sources].some(x=>r.sources.has(x)))return false;
  if(state.categories.size&&![...state.categories].some(x=>r.categories.has(x)))return false;
  if(state.subjects.size&&![...state.subjects].some(x=>matchesSubject(r.j,x)))return false;
  if(state.q&&!r.search.includes(norm(state.q)))return false;
  return true;
};
const deadlineSortKey=(r)=>{
  const j=r.j,dd=dayDiff(j.applyEnd),rd=parseDate(j.registered);
  const r0=rd?new Date(rd.getFullYear(),rd.getMonth(),rd.getDate()):null;
  const age=r0?Math.floor((today0()-r0)/86400000):null;
  const official=(j.feedKind||'official')==='official';
  let bucket=4,primary=0;
  if(dd!==null&&dd>=0&&dd<=3){bucket=0;primary=dd}
  else if(dd!==null&&dd>=4&&dd<=7){bucket=1;primary=dd}
  else if(dd===null&&official&&age!==null&&age>=0&&age<=7){bucket=2}
  else if(dd!==null){bucket=3;primary=dd}
  return [bucket,primary,-(rd?rd.getTime():0),r.key];
};
const compareDeadline=(a,b)=>{
  const x=deadlineSortKey(a),y=deadlineSortKey(b);
  return x[0]-y[0]||x[1]-y[1]||x[2]-y[2]||String(x[3]).localeCompare(String(y[3]));
};
const filteredRows=()=>{
  const out=state.indexed.filter(matchesFilters);
  out.sort((a,b)=>{
    if(state.sort==='deadline')return compareDeadline(a,b);
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
  types:[...state.types],
  sources:[...state.sources],
  categories:[...state.categories],
  subjects:[...state.subjects],
  q:String(state.q||'').trim(),
  savedAt:new Date().toISOString()
});
const hasProfileConditions=(p)=>['provinces','regions','schools','types','sources','categories','subjects'].some(k=>arr(p?.[k]).length)||Boolean(String(p?.q||'').trim());
const profileSignature=(p)=>JSON.stringify({
  provinces:[...arr(p?.provinces)].sort(),
  regions:[...arr(p?.regions)].sort(),
  schools:[...arr(p?.schools)].sort(),
  types:[...arr(p?.types)].sort(),
  sources:[...arr(p?.sources)].sort(),
  categories:[...arr(p?.categories)].sort(),
  subjects:[...arr(p?.subjects)].sort(),
  q:norm(p?.q||'')
});
const matchesProfile=(r,p)=>{
  const ps=arr(p?.provinces),rs=arr(p?.regions),ss=arr(p?.schools),ts=arr(p?.types),src=arr(p?.sources),cats=arr(p?.categories),subs=arr(p?.subjects),q=norm(p?.q||'');
  if(!r.active)return false;
  if(ps.length&&!ps.includes(r.province))return false;
  if(rs.length&&!r.regions.some(x=>rs.some(s=>regionKey(s)===regionKey(x))))return false;
  if(ss.length&&!ss.includes(r.school))return false;
  if(ts.length&&!ts.includes(r.type))return false;
  if(src.length&&!src.some(x=>r.sources.has(x)))return false;
  if(cats.length&&!cats.some(x=>r.categories.has(x)))return false;
  if(subs.length&&!subs.some(x=>matchesSubject(r.j,x)))return false;
  if(q&&!r.search.includes(q))return false;
  return true;
};
const profileMatches=(p)=>state.indexed.filter(r=>matchesProfile(r,p));

const newProfileRows=(p)=>{
  if(!p)return [];
  const current=profileMatches(p);
  const snap=store()?.snapshot?.get?.();
  if(!snap||!Array.isArray(snap.keys))return current;
  const old=new Set(snap.keys);
  return current.filter(r=>!old.has(r.key));
};
const snapshotNewCount=(p)=>newProfileRows(p).length;
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

const optionCounts=(getter)=>{
  const m=new Map();
  state.indexed.filter(r=>r.active).forEach(r=>{
    const vals=arr(getter(r));
    vals.forEach(v=>{if(v)m.set(v,(m.get(v)||0)+1)});
  });
  return m;
};
const provinceOptions=()=>['경기','서울','인천'].map(v=>[v,optionCounts(r=>[r.province]).get(v)||0]);
const canonicalOptions=(values,getter)=>{const m=optionCounts(getter);return values.map(v=>[v,m.get(v)||0])};
const regionCounts=()=>{
  const m=new Map();
  state.indexed.filter(r=>r.active).forEach(r=>r.regions.forEach(v=>{const k=regionKey(v);if(k)m.set(k,(m.get(k)||0)+1)}));
  return m;
};
const regionOptions=(values)=>{const m=regionCounts();return values.map(v=>[v,m.get(v)||0])};
const schoolOptions=()=>canonicalOptions(SCHOOL_VALUES,r=>[r.school]);
const typeOptions=()=>canonicalOptions(TYPE_VALUES,r=>[r.type]);
const sourceOptions=()=>SOURCE_VALUES.map(v=>[v,state.indexed.filter(r=>r.active&&r.sources.has(v)).length]);
const categoryOptions=()=>CATEGORY_VALUES.map(v=>[v,state.indexed.filter(r=>r.active&&r.categories.has(v)).length]);
const subjectOptions=()=>SUBJECT_VALUES.map(v=>[v,state.indexed.filter(r=>r.active&&matchesSubject(r.j,v)).length]);
const chipsHtml=(name,options,set,cls='')=>`<div class="check-grid ${cls}">${options.map(([v,n])=>`<label class="check-chip ${set.has(v)?'checked':''}"><input type="checkbox" data-filter="${name}" value="${esc(v)}" ${set.has(v)?'checked':''}><span>${esc(v)} <small>${n.toLocaleString()}</small></span></label>`).join('')}</div>`;
const regionGroupHtml=(title,key,values)=>{
  const selected=values.filter(v=>state.regions.has(v)).length;
  return `<details class="region-group" ${selected?'open':''}>
    <summary><b>${title}</b><span>${selected?`${selected}개 선택`:`${values.length}개 지역`}</span><i>⌄</i></summary>
    <div class="region-group-body"><button type="button" class="region-all" data-region-all="${key}">${title} 전체 선택</button>${chipsHtml('regions',regionOptions(values),state.regions,'region-checks')}</div>
  </details>`;
};
const selectedSummaryHtml=()=>{
  const parts=[];
  if(state.provinces.size)parts.push(`시·도 ${[...state.provinces].join(', ')}`);
  if(state.regions.size)parts.push(`지역 ${state.regions.size}곳`);
  if(state.schools.size)parts.push(`학교급 ${[...state.schools].join(', ')}`);
  if(state.types.size)parts.push(`직종 ${[...state.types].join(', ')}`);
  if(state.sources.size)parts.push(`공고 ${[...state.sources].join('·')}`);
  if(state.categories.size)parts.push(`분야 ${[...state.categories].join('·')}`);
  if(state.subjects.size)parts.push(`과목·담당 ${[...state.subjects].join('·')}`);
  return parts.length?`<div class="selected-box show"><b>선택된 조건</b><p>${parts.map(esc).join(' · ')}</p></div>`:'<div class="selected-box"></div>';
};
const sectionChoiceLabel=(set,empty='선택 안 함')=>{
  if(!(set instanceof Set)||!set.size)return empty;
  const vals=[...set];
  if(vals.length===1)return vals[0];
  return `${vals[0]} 외 ${vals.length-1}`;
};
const filterSectionHtml=(key,title,set,body,{defaultOpen=false,note='중복 선택 가능'}={})=>{
  const open=defaultOpen||state.filterFocus===key||Boolean(set?.size);
  return `<details class="filter-section" data-group="${key}" ${open?'open':''}>
    <summary><span class="filter-section-title">${esc(title)}</span><span class="filter-section-choice">${esc(sectionChoiceLabel(set))}</span><span class="filter-chevron">⌄</span></summary>
    <div class="filter-section-body"><div class="filter-section-note">${esc(note)}</div>${body}</div>
  </details>`;
};
const filterDrawerHtml=()=>`<div id="filterDrawer" class="filter-drawer ${state.filterOpen?'open':''}">
  <div class="filter-drawer-head"><strong>필터</strong><button type="button" class="filter-reset-top" id="filterReset">전체 초기화</button><button type="button" class="filter-close" id="filterClose">닫기</button></div>
  ${filterSectionHtml('provinces','시·도',state.provinces,chipsHtml('provinces',provinceOptions(),state.provinces,'two-col'),{defaultOpen:true})}
  ${filterSectionHtml('regions','지역',state.regions,`${regionGroupHtml('경기','gyeonggi',GYEONGGI_REGIONS)}${regionGroupHtml('서울','seoul',SEOUL_REGIONS)}${regionGroupHtml('인천','incheon',INCHEON_REGIONS)}`,{defaultOpen:true,note:'여러 지역 동시 선택'})}
  ${filterSectionHtml('schools','학교급',state.schools,chipsHtml('schools',schoolOptions(),state.schools,'two-col'))}
  ${filterSectionHtml('types','직종',state.types,chipsHtml('types',typeOptions(),state.types,'one-col'))}
  ${filterSectionHtml('sources','공고 구분',state.sources,chipsHtml('sources',sourceOptions(),state.sources,'two-col'))}
  ${filterSectionHtml('categories','구인 분야',state.categories,chipsHtml('categories',categoryOptions(),state.categories,'one-col'))}
  ${filterSectionHtml('subjects','과목·담당',state.subjects,chipsHtml('subjects',subjectOptions(),state.subjects,'one-col'))}
  ${selectedSummaryHtml()}
  <div class="filter-footer"><button type="button" id="filterApply">${filteredRows().length.toLocaleString()}건 공고 보기</button></div>
</div>`;

const homeHtml=()=>{
  const p=store()?.profile?.get?.();
  const favorites=favoriteKeys().size;
  const alerts=store()?.alerts?.get?.()||{enabled:false};
  const active=state.indexed.filter(r=>r.active);
  const latest=[...active].sort((a,b)=>b.registered-a.registered);
  const matches=p?[...profileMatches(p)].sort((a,b)=>b.registered-a.registered):[];
  const newRows=p?[...newProfileRows(p)].sort((a,b)=>b.registered-a.registered):[];
  return `${installCardHtml()}<section class="home-radar calm personalized">
    <div class="radar-top"><div><h2><span class="radar-heading-icon">${icon('radar')}</span>내 채용 레이더</h2><p>${p?'한 번 저장한 조건을 기준으로 필요한 공고만 먼저 보여드립니다.':'원하는 조건을 한 번 저장하면 다음부터 홈이 내 채용 화면으로 바뀝니다.'}</p></div><div class="radar-mascot"><img src="assets/mascot.png?v=20260920b" width="70" height="70" alt="수도권에듀잡 마스코트" loading="lazy"><span>좋은 기회가<br>기다리고 있어요!</span></div></div>
    ${p?`<div class="home-saved-profile"><div><span>내 조건</span><strong>${esc(profileSummary(p))}</strong></div><button type="button" data-home-profile="edit">수정</button></div>`:''}
    <div class="metric-grid calm">
      <button class="metric" data-home="new"><span class="metric-icon">${icon('document')}</span><b>${p?newRows.length:0}</b><strong>새 공고</strong><small>지난 확인 이후</small></button>
      <button class="metric" data-home="saved"><span class="metric-icon">${icon('heart')}</span><b>${favorites}</b><strong>관심공고</strong><small>저장한 공고</small></button>
      <button class="metric" data-home="alert"><span class="metric-icon">${icon('bell')}</span><b>${alerts.enabled?'ON':'OFF'}</b><strong>알림</strong><small>${p?'내 조건 기준':'조건 저장 필요'}</small></button>
    </div>
    ${p?
      '<div class="radar-actions calm"><button type="button" data-home-profile="matches">맞춤공고 전체보기</button><button type="button" data-home-profile="edit">조건 수정</button></div>':
      '<div class="radar-actions calm"><button type="button" data-go="search">내 조건 만들기</button><button type="button" data-go="radar">채용 레이더 보기</button></div>'}
  </section>
  ${p?
    `<div class="section-title home-primary-title"><span>${icon('document')}</span><h2>내 조건에 맞는 새 공고</h2><span class="spacer"></span><button class="link-btn" data-home-new>${newRows.length.toLocaleString()}건 전체보기 ›</button></div>
      ${newRows.length?
        jobsListHtml(newRows,5):
        `<div class="home-no-new"><strong>새로 들어온 맞춤 공고가 없습니다.</strong><p>현재 조건에 맞는 모집 중 공고는 ${matches.length.toLocaleString()}건입니다.</p><button type="button" data-home-profile="matches">기존 맞춤공고 보기</button></div>`}
      <button type="button" class="latest-secondary-link" data-home-latest>전체 최신공고 보기 ›</button>`:
    `<div class="first-use-card"><strong>먼저 원하는 채용 조건을 저장해 보세요.</strong><p>지역·학교급·직종·과목을 한 번 선택하면 다음 방문부터 맞춤공고와 새 공고를 홈에서 바로 확인할 수 있습니다.</p><button type="button" data-go="search">내 조건 만들기</button></div>
      <div class="section-title home-secondary-title"><span>${icon('document')}</span><h2>최근 공고 미리보기</h2><span class="spacer"></span><button class="link-btn" data-home-latest>전체보기 ›</button></div>
      ${jobsListHtml(latest,3)}`}
  `;
};

const searchHtml=()=>{
  const rows=filteredRows();
  return `<div class="search-filter-row">
    <button type="button" class="filter-main" id="searchFilterOpen">${icon('filter')}<span>필터</span></button>
    <button type="button" class="grow" data-filter-focus="regions">지역${selectedCount(state.regions)?` ${selectedCount(state.regions)}`:''}⌄</button>
    <button type="button" class="grow" data-filter-focus="schools">학교급${selectedCount(state.schools)?` ${selectedCount(state.schools)}`:''}⌄</button>
    <button type="button" class="grow" data-filter-focus="subjects">과목${selectedCount(state.subjects)?` ${selectedCount(state.subjects)}`:''}⌄</button>
  </div>
  ${filterDrawerHtml()}
  <div class="results-bar"><span>검색 결과 <strong>${rows.length.toLocaleString()}</strong>건</span><select id="sortSelect" class="results-sort" aria-label="정렬"><option value="newest" ${state.sort==='newest'?'selected':''}>최신순</option><option value="deadline" ${state.sort==='deadline'?'selected':''}>마감임박순</option><option value="relevance" ${state.sort==='relevance'?'selected':''}>관련도순</option></select></div>
  ${jobsListHtml(rows,state.visible)}`;
};

const profileSummary=(p)=>{
  const items=[];
  if(arr(p?.provinces).length)items.push(arr(p.provinces).join('·'));
  if(arr(p?.regions).length)items.push(arr(p.regions).slice(0,3).join('·')+(arr(p.regions).length>3?` +${arr(p.regions).length-3}`:''));
  if(arr(p?.schools).length)items.push(arr(p.schools).join('·'));
  if(arr(p?.types).length)items.push(arr(p.types).slice(0,2).join('·'));
  if(arr(p?.sources).length)items.push(arr(p.sources).join('·'));
  if(arr(p?.categories).length)items.push(arr(p.categories).slice(0,2).join('·'));
  if(arr(p?.subjects).length)items.push(arr(p.subjects).slice(0,2).join('·'));
  if(p?.q)items.push(`“${p.q}”`);
  return items.join(' · ')||'저장된 상세 조건';
};

const radarHtml=()=>{
  const p=store()?.profile?.get?.(),a=store()?.alerts?.get?.()||{enabled:false};
  const pushOk=pushReady();
  const iosNeedsInstall=isIOSDevice()&&!isStandaloneApp();
  const matches=p?profileMatches(p):[];
  const newMatches=state.radarMode==='new'&&state.radarNewKeys instanceof Set
    ?matches.filter(r=>state.radarNewKeys.has(r.key))
    :[];
  const rows=state.radarMode==='new'?newMatches:matches;
  return `<section class="radar-page">
    <div class="hero-row"><div class="hero-copy"><div class="hero-title-row"><button type="button" class="back-btn" data-go="home" aria-label="홈으로">←</button><h1>내 채용 레이더</h1></div><p>내가 원하는 조건에 맞는 공고를 자동으로 찾아드려요.</p></div><img src="assets/mascot.png?v=20260920b" width="76" height="64" alt="수도권에듀잡 마스코트" loading="lazy"></div>
    <div class="segment-tabs"><button type="button" data-radar-tab="conditions" class="${state.radarTab==='conditions'?'active':''}">내 조건</button><button type="button" data-radar-tab="matches" class="${state.radarTab==='matches'?'active':''}">맞춤 공고</button></div>
    ${state.radarTab==='conditions'?
      `<div class="condition-card"><div class="condition-head"><strong>내 검색 조건</strong>${p?'':'<button type="button" data-go="search">조건 만들기</button>'}</div>
      ${p?`<div class="saved-condition"><div><strong>${esc(p.q||'내 채용 조건')}</strong><p>${esc(profileSummary(p))}</p><em>새 공고 ${snapshotNewCount(p).toLocaleString()}건</em></div><details class="condition-menu"><summary aria-label="저장 조건 메뉴">⋯</summary><div class="condition-menu-pop"><button type="button" id="conditionEdit">수정</button><button type="button" class="danger" id="conditionDelete">삭제</button></div></details></div>`:
      '<div class="empty-state"><strong>저장된 조건이 없습니다.</strong><p>공고검색에서 원하는 조건을 선택한 뒤 저장해 주세요.</p></div>'}</div>`
      :`${state.radarMode==='new'?'<div class="radar-result-head"><strong>지난 확인 이후 새 공고 '+rows.length.toLocaleString()+'건</strong><button type="button" data-radar-all>전체 맞춤공고</button></div>':''}${jobsListHtml(rows,state.visible,{emptyText:state.radarMode==='new'?'지난 확인 이후 새로 들어온 맞춤 공고가 없습니다.':'저장 조건에 맞는 모집 중 공고가 없습니다.'})}`
    }
    <div class="alert-card"><div class="alert-copy">${icon('bell')}<div><strong>알림 설정</strong><p>${pushOk?'새로운 공고가 등록되면 저장한 조건 기준으로 알려드립니다.':iosNeedsInstall?'iPhone·iPad는 홈 화면에 추가한 에듀잡 앱에서 알림을 사용할 수 있습니다.':'현재 브라우저에서는 웹 푸시를 사용할 수 없습니다.'}</p></div></div><button type="button" class="switch ${a.enabled?'on':''}" id="alertToggle" aria-label="알림 ${a.enabled?'켜짐':'꺼짐'}"></button></div>
    ${pushOk?'':iosNeedsInstall
      ?`<div class="push-browser-guide ios-push-guide"><strong>먼저 홈 화면에 에듀잡을 추가하세요.</strong><p>브라우저의 공유 메뉴 → 홈 화면에 추가 → 홈 화면의 에듀잡 실행 → 알림 켜기 순서입니다.</p></div>`
      :`<div class="push-browser-guide"><strong>Chrome에서 열어 알림을 켜주세요.</strong><p>네이버·카카오 등 앱 안 브라우저에서는 알림 기능이 제한될 수 있습니다.</p><div class="push-browser-actions"><button type="button" class="chrome-open-btn" data-open-chrome>Chrome에서 열기</button><button type="button" class="url-copy-btn" data-copy-app-url>주소 복사</button></div></div>`}
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
  const row=(ic,label,action,status='')=>`<button type="button" data-me="${action}">${icon(ic)}<span>${esc(label)}</span><em class="${status?'status':''}">${status?esc(status):'›'}</em></button>`;
  return `<div class="me-profile"><div class="avatar">${icon('user')}</div><div><strong>선생님</strong><p>안녕하세요!</p></div><span style="margin-left:auto;color:#2b7cf3">${icon('settings')}</span></div>
  <div class="me-stats"><div><span>저장한 공고</span><b>${fav}</b></div><div><span>저장한 조건</span><b>${p?1:0}</b></div><div><span>최근 본 공고</span><b>${recent}</b></div></div>
  <div class="menu-list menu-list-single">
    ${row('bell','알림 설정','alerts',a.enabled?'켜짐':'꺼짐')}
    ${row('bookmark','저장한 조건','radar')}
    ${row('heart','관심공고','saved')}
    ${row('history','최근 본 공고','recent')}
  </div>
  <button type="button" class="device-reset" id="deviceReset">내 기기 데이터 초기화</button>`;
};

const errorHtml=()=>`<div class="empty-state"><strong>채용 데이터 파일을 불러오지 못했습니다.</strong><p>잠시 후 다시 접속해 주세요. 기존 수집 데이터는 변경하지 않습니다.</p></div>`;

function render(){
  const screen=$('#screen');if(!screen)return;
  const searchTop=$('#searchTop');
  if(searchTop)searchTop.hidden=!['home','search'].includes(state.route);
  const surfaceSegment=$('#surfaceSegment');
  if(surfaceSegment)surfaceSegment.hidden=state.route!=='search';
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
  state.provinces.clear();state.regions.clear();state.schools.clear();state.types.clear();state.sources.clear();state.categories.clear();state.subjects.clear();
  state.q='';state.sort='newest';state.visible=PAGE_SIZE;state.filterOpen=false;state.filterFocus='';
  if(surface)state.surface='';
  render();
}
function applyProfileToState(p){
  if(!p)return;
  state.provinces=new Set(arr(p.provinces));
  state.regions=new Set(arr(p.regions));
  state.schools=new Set(arr(p.schools));
  state.types=new Set(arr(p.types));
  state.sources=new Set(arr(p.sources));
  state.categories=new Set(arr(p.categories));
  state.subjects=new Set(arr(p.subjects));
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
  $('#homeFilterOpen',screen)?.addEventListener('click',()=>{state.filterOpen=!state.filterOpen;render()});
  $('#searchFilterOpen',screen)?.addEventListener('click',()=>{state.filterOpen=!state.filterOpen;render()});
  $$('[data-filter-focus]',screen).forEach(b=>b.addEventListener('click',()=>{state.filterOpen=true;state.filterFocus=b.dataset.filterFocus;render();setTimeout(()=>screen.querySelector(`[data-group="${state.filterFocus}"]`)?.scrollIntoView({behavior:'smooth',block:'center'}),10)}));
  $('#filterReset',screen)?.addEventListener('click',()=>resetFilters({surface:false}));
  $('#filterClose',screen)?.addEventListener('click',()=>{state.filterOpen=false;state.filterFocus='';state.visible=PAGE_SIZE;render()});
  $('#filterApply',screen)?.addEventListener('click',()=>{
    const next=currentProfile();
    if(hasProfileConditions(next)){
      const prev=store()?.profile?.get?.();
      const changed=profileSignature(prev)!==profileSignature(next);
      store()?.profile?.set?.(next);
      if(changed)writeSnapshot(next);
      toast(changed?'내 조건으로 저장했습니다.':'저장한 조건으로 공고를 보여드립니다.');
    }
    state.filterOpen=false;state.filterFocus='';state.visible=PAGE_SIZE;render();
  });
  $('#sortSelect',screen)?.addEventListener('change',e=>{state.sort=e.target.value;state.visible=PAGE_SIZE;render()});
  $$('[data-filter]',screen).forEach(input=>input.addEventListener('change',e=>{
    const set=state[e.target.dataset.filter];if(!(set instanceof Set))return;
    e.target.checked?set.add(e.target.value):set.delete(e.target.value);
    e.target.closest('.check-chip')?.classList.toggle('checked',e.target.checked);
    state.visible=PAGE_SIZE;
    const box=$('.selected-box',screen);if(box)box.outerHTML=selectedSummaryHtml();
    const section=e.target.closest('.filter-section');
    const choice=section?.querySelector('.filter-section-choice');
    if(choice)choice.textContent=sectionChoiceLabel(set);
    const apply=$('#filterApply',screen);if(apply)apply.textContent=`${filteredRows().length.toLocaleString()}건 공고 보기`;
  }));
  $$('[data-region-all]',screen).forEach(btn=>btn.addEventListener('click',()=>{
    const groups={gyeonggi:GYEONGGI_REGIONS,seoul:SEOUL_REGIONS,incheon:INCHEON_REGIONS};
    const vals=groups[btn.dataset.regionAll]||[];
    const all=vals.every(v=>state.regions.has(v));
    vals.forEach(v=>all?state.regions.delete(v):state.regions.add(v));
    state.visible=PAGE_SIZE;render();
  }));

  const openNewRadar=()=>{
    const p=store()?.profile?.get?.();
    if(!p){toast('먼저 검색 조건을 저장해 주세요.');setRoute('search');return}
    const rows=newProfileRows(p);
    state.radarNewKeys=new Set(rows.map(r=>r.key));
    state.radarMode='new';
    state.radarTab='matches';
    writeSnapshot(p);
    setRoute('radar');
  };
  $$('[data-install-dismiss]',screen).forEach(btn=>btn.addEventListener('click',()=>{
    dismissInstallPrompt();
    render();
  }));
  $('#appInstallBtn',screen)?.addEventListener('click',async()=>{
    const prompt=deferredInstallPrompt;
    if(!prompt){
      toast('브라우저 메뉴에서 앱 설치 또는 홈 화면에 추가를 선택해 주세요.');
      return;
    }
    try{
      await prompt.prompt();
      const choice=await prompt.userChoice;
      deferredInstallPrompt=null;
      if(choice?.outcome==='accepted'){
        dismissInstallPrompt();
        toast('에듀잡 설치를 시작했습니다.');
      }else{
        toast('설치를 취소했습니다. 나중에 다시 설치할 수 있습니다.');
      }
    }catch(e){
      toast('설치 창을 열지 못했습니다. 브라우저 메뉴에서 홈 화면에 추가해 주세요.');
    }
    render();
  });

  $$('[data-home]',screen).forEach(b=>b.addEventListener('click',()=>{
    const x=b.dataset.home;
    if(x==='saved')setRoute('saved');
    else if(x==='new')openNewRadar();
    else if(x==='radar'||x==='alert')setRoute('radar');
  }));
  $$('[data-home-new]',screen).forEach(b=>b.addEventListener('click',openNewRadar));
  $$('[data-home-profile]',screen).forEach(b=>b.addEventListener('click',()=>{
    const x=b.dataset.homeProfile,p=store()?.profile?.get?.();
    if(x==='edit'){
      if(p)applyProfileToState(p);
      setRoute('search');
    }else if(x==='matches'){
      state.radarMode='all';state.radarNewKeys=null;state.radarTab='matches';
      if(p)writeSnapshot(p);
      setRoute('radar');
    }
  }));
  $$('[data-home-latest]',screen).forEach(b=>b.addEventListener('click',()=>{
    state.provinces.clear();state.regions.clear();state.schools.clear();state.types.clear();state.sources.clear();state.categories.clear();state.subjects.clear();
    state.q='';state.surface='';state.sort='newest';state.visible=PAGE_SIZE;
    setRoute('search');
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

  $$('[data-radar-tab]',screen).forEach(b=>b.addEventListener('click',()=>{
    state.radarTab=b.dataset.radarTab;state.visible=PAGE_SIZE;
    if(state.radarTab==='matches'){
      state.radarMode='all';state.radarNewKeys=null;
      const p=store()?.profile?.get?.();if(p)writeSnapshot(p);
    }
    render();
  }));
  $$('[data-radar-all]',screen).forEach(b=>b.addEventListener('click',()=>{
    state.radarMode='all';state.radarNewKeys=null;state.radarTab='matches';state.visible=PAGE_SIZE;
    const p=store()?.profile?.get?.();if(p)writeSnapshot(p);
    render();
  }));
  $('#conditionEdit',screen)?.addEventListener('click',()=>{const p=store()?.profile?.get?.();if(p)applyProfileToState(p);setRoute('search')});
  $('#conditionDelete',screen)?.addEventListener('click',()=>{if(!confirm('저장한 검색 조건을 삭제할까요?'))return;store()?.profile?.remove?.();store()?.snapshot?.remove?.();toast('저장 조건을 삭제했습니다.');render()});
  $$('[data-open-chrome]',screen).forEach(btn=>btn.addEventListener('click',()=>{
    if(isIOSDevice()){
      toast('iPhone에서는 홈 화면에 추가한 에듀잡 앱에서 알림을 켜주세요.');
      return;
    }
    location.href=chromeIntentUrl();
  }));
  $$('[data-copy-app-url]',screen).forEach(btn=>btn.addEventListener('click',async()=>{
    const ok=await copyAppUrl();
    toast(ok?'수도권에듀잡 주소를 복사했습니다.':'주소 복사에 실패했습니다. 주소창의 주소를 직접 복사해 주세요.');
  }));

  $('#alertToggle',screen)?.addEventListener('click',async()=>{
    const btn=$('#alertToggle',screen);
    if(btn)btn.disabled=true;
    try{
      const client=window.EduJobAlerts;
      if(!client)throw new Error('client-unavailable');
      const on=await client.reconcile();
      if(on){
        await client.unsubscribe();
        toast('새 공고 알림을 껐습니다.');
      }else{
        await client.subscribe();
        toast('내 조건 새 공고 알림을 켰습니다.');
      }
    }catch(e){
      const code=String(e?.message||e);
      if(code==='profile-required')toast('먼저 검색 조건을 저장해 주세요.');
      else if(code==='ios-home-screen-required')toast('iPhone·iPad는 홈 화면에 추가한 뒤 알림을 켤 수 있습니다.');
      else if(code==='permission-denied')toast('브라우저 알림 권한을 허용해 주세요.');
      else if(code==='unsupported')toast(isIOSDevice()?'iPhone·iPad는 홈 화면에 추가한 에듀잡 앱에서 알림을 켜주세요.':'현재 브라우저에서는 알림을 사용할 수 없습니다. Chrome에서 열어주세요.');
      else toast('알림 설정을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }finally{
      if(btn)btn.disabled=false;
      render();
    }
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
    const on=toggleFavorite(r.j);
    toast(on?'관심공고에 저장했어요.':'관심공고에서 해제했어요.');
    render();
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

if('serviceWorker'in navigator){
  navigator.serviceWorker.register('./sw.js',{scope:'./'}).catch(()=>{});
}
installIcons();
installStaticEvents();
if(!location.hash)history.replaceState(null,'','#/home');
routeFromHash();
loadData();
})();
