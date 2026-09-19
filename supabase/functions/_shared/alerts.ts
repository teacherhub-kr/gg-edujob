export type Job=Record<string,unknown>;
export type Profile={
  provinces?:string[];
  regions?:string[];
  schools?:string[];
  types?:string[];
  categories?:string[];
  subjects?:string[];
  q?:string;
};

const arr=(v:unknown):string[]=>Array.isArray(v)?v.map(String).filter(Boolean):[];
const norm=(v:unknown)=>String(v??'').toLowerCase().normalize('NFKC')
  .replace(/[\u200b-\u200d\ufeff]/g,'')
  .replace(/[^0-9a-z가-힣]+/gi,' ')
  .replace(/\s+/g,' ').trim();

export const jobKey=(j:Job)=>String(
  j.sourceIdentity||j.id||j.verifiedUrl||j.detailUrl||j.url||
  [j.source,j.school,j.title,j.registered].filter(Boolean).join('|')
);

const schoolLevel=(j:Job)=>{
  const raw=String(j.schoolLevel||'');
  const allowed=['유치원','초등학교','중학교','고등학교','특수학교','교육행정기관','기타'];
  if(raw==='교육지원청')return '교육행정기관';
  if(allowed.includes(raw))return raw;
  const text=String(j.school||'')+' '+String(j.title||'');
  if(/특수학교/.test(text))return '특수학교';
  if(/유치원|병설유/.test(text))return '유치원';
  if(/초등학교/.test(text))return '초등학교';
  if(/중학교/.test(text))return '중학교';
  if(/고등학교/.test(text))return '고등학교';
  if(/교육지원청|교육청/.test(text))return '교육행정기관';
  return '기타';
};

const jobType=(j:Job)=>{
  const raw=String(j.type||'');
  const allowed=['기간제교원','시간강사/강사','교육공무직/기간제근로자','정규채용','자원봉사','기타'];
  if(raw==='교육공무직')return '교육공무직/기간제근로자';
  if(allowed.includes(raw))return raw;
  const text=raw+' '+String(j.title||'')+' '+String(j.subject||'');
  if(/자원봉사|봉사자/.test(text))return '자원봉사';
  if(/정규/.test(text))return '정규채용';
  if(/교육공무직|기간제근로|조리실무|돌봄전담/.test(text))return '교육공무직/기간제근로자';
  if(/시간강사|강사|시간제/.test(text))return '시간강사/강사';
  if(/기간제|교원|교사/.test(text))return '기간제교원';
  return '기타';
};

const province=(j:Job)=>String(j.province||'')||(/구$/.test(String(j.region||''))?'서울':'경기');
const jobProvinces=(j:Job)=>{const xs=arr(j.provinces);return xs.length?[...new Set(xs)]:[province(j)]};
const jobRegions=(j:Job)=>[...new Set([String(j.region||''),...arr(j.regions)].filter(Boolean))];

const subjectRules:Record<string,RegExp>={
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
  '유아':/(^|\s)(유아|유치원|유치)(\s|$)/
};

const searchHay=(j:Job)=>String(j.searchText||'')||norm([
  j.school,j.title,j.subject,j.region,...arr(j.regions),j.type,j.source,j.schoolLevel,j.province
].join(' '));

const isExpired=(value:unknown)=>{
  const m=String(value||'').match(/(\d{4})[\/.\-](\d{1,2})[\/.\-](\d{1,2})/);
  if(!m)return false;
  const end=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]),23,59,59);
  return end.getTime()<Date.now();
};

export const matchesProfile=(j:Job,p:Profile)=>{
  if(isExpired(j.applyEnd))return false;
  const provinces=arr(p.provinces),regions=arr(p.regions),schools=arr(p.schools),types=arr(p.types);
  const categories=arr(p.categories),subjects=arr(p.subjects);
  if(provinces.length&&!jobProvinces(j).some(x=>provinces.includes(x)))return false;
  if(regions.length&&!jobRegions(j).some(x=>regions.includes(x)))return false;
  if(schools.length&&!schools.includes(schoolLevel(j)))return false;
  if(types.length&&!types.includes(jobType(j)))return false;
  if(categories.length){
    const jc=new Set(arr(j.categories));
    if(!categories.some(x=>jc.has(x)))return false;
  }
  if(subjects.length){
    const hay=' '+norm([j.subject,j.title,j.schoolLevel,j.type].filter(Boolean).join(' '))+' ';
    if(!subjects.some(x=>subjectRules[x]?.test(hay)))return false;
  }
  const q=norm(p.q||'');
  if(q){
    const hay=searchHay(j);
    if(!q.split(' ').filter(Boolean).every(token=>hay.includes(token)))return false;
  }
  return true;
};

export const matchingKeys=(jobs:Job[],profile:Profile)=>jobs.filter(j=>matchesProfile(j,profile)).map(jobKey).filter(Boolean);

export async function fetchCurrentJobs(){
  const url=Deno.env.get('EDUJOB_JOBS_URL')||
    'https://raw.githubusercontent.com/teacherhub-kr/gg-edujob/main/unified_jobs.json';
  const res=await fetch(url,{headers:{'cache-control':'no-cache'}});
  if(!res.ok)throw new Error('jobs fetch '+res.status);
  const data=await res.json();
  const jobs=Array.isArray(data)?data:data?.jobs;
  if(!Array.isArray(jobs))throw new Error('jobs payload missing array');
  return jobs as Job[];
}

export async function sha256(value:string){
  const bytes=new TextEncoder().encode(value);
  const digest=await crypto.subtle.digest('SHA-256',bytes);
  return Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,'0')).join('');
}
