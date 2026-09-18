import { createClient } from "npm:@supabase/supabase-js@2.116.0";
import webpush from "npm:web-push@3.6.7";

type Json = Record<string, unknown>;
type Profile = {
  provinces: string[];
  regions: string[];
  schools: string[];
  types: string[];
  categories: string[];
  subjects: string[];
  q: string;
};

const ALLOWED_ORIGINS=(Deno.env.get("EDUJOB_ALLOWED_ORIGINS")||"https://teacherhub-kr.github.io")
  .split(",").map(x=>x.trim()).filter(Boolean);
const JOBS_URL=Deno.env.get("EDUJOB_JOBS_URL")||"https://raw.githubusercontent.com/teacherhub-kr/gg-edujob/main/unified_jobs.json";
const SITE_URL=Deno.env.get("EDUJOB_SITE_URL")||"https://teacherhub-kr.github.io/gg-edujob/";
const DISPATCH_KEY=Deno.env.get("EDUJOB_ALERT_DISPATCH_KEY")||"";
const VAPID_PUBLIC_KEY=Deno.env.get("EDUJOB_VAPID_PUBLIC_KEY")||"";
const VAPID_PRIVATE_KEY=Deno.env.get("EDUJOB_VAPID_PRIVATE_KEY")||"";
const VAPID_SUBJECT=Deno.env.get("EDUJOB_VAPID_SUBJECT")||"mailto:admin@example.com";

const secretKeys=JSON.parse(Deno.env.get("SUPABASE_SECRET_KEYS")||"{}");
const adminKey=secretKeys.default||Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
const supabase=createClient(Deno.env.get("SUPABASE_URL")||"",adminKey,{auth:{persistSession:false}});

const SUBJECT_RULES:Record<string,RegExp>={
  "국어":/(^|\s)(국어|한국어)(\s|$)/,
  "영어":/(^|\s)(영어|english)(\s|$)/,
  "수학":/(^|\s)(수학|math)(\s|$)/,
  "사회":/(^|\s)(사회|일반사회)(\s|$)/,
  "역사":/(^|\s)(역사|한국사)(\s|$)/,
  "과학":/(^|\s)(과학|물리|화학|생명과학|지구과학)(\s|$)/,
  "음악":/(^|\s)(음악|합창|오케스트라|관현악|밴드)(\s|$)/,
  "미술":/(^|\s)(미술|디자인)(\s|$)/,
  "체육":/(^|\s)(체육|스포츠|운동)(\s|$)/,
  "특수":/(^|\s)(특수|특수교육)(\s|$)/,
  "보건":/(^|\s)(보건|간호)(\s|$)/,
  "상담":/(^|\s)(상담|전문상담|위클래스|wee)(\s|$)/,
  "사서":/(^|\s)(사서|도서관)(\s|$)/,
  "영양":/(^|\s)(영양|영양교사)(\s|$)/,
  "정보·컴퓨터":/(^|\s)(정보|컴퓨터|코딩|소프트웨어|ai|인공지능)(\s|$)/,
  "유아":/(^|\s)(유아|유치원|유치)(\s|$)/
};

const norm=(v:unknown)=>String(v||"").toLowerCase().normalize("NFKC")
  .replace(/[\u200b-\u200d\ufeff]/g,"").replace(/[^0-9a-z가-힣]+/gi," ")
  .replace(/\s+/g," ").trim();
const arr=(v:unknown)=>Array.isArray(v)?v.map(String).filter(Boolean):[];
const jobKey=(j:Json)=>String(j.sourceIdentity||j.id||j.verifiedUrl||j.detailUrl||j.url||
  [j.source,j.school,j.title,j.registered].filter(Boolean).join("|"));
const jobProvinces=(j:Json)=>{
  const xs=arr(j.provinces);return xs.length?xs:[String(j.province||"")].filter(Boolean);
};
const jobRegions=(j:Json)=>[String(j.region||""),...arr(j.regions)].filter(Boolean);
const active=(j:Json)=>{
  const raw=String(j.applyEnd||"");if(!raw)return true;
  const m=raw.match(/(\d{4})[\/.\-](\d{1,2})[\/.\-](\d{1,2})/);if(!m)return true;
  const end=new Date(Number(m[1]),Number(m[2])-1,Number(m[3]),23,59,59);
  return end.getTime()>=Date.now()-86400000;
};
const profile=(raw:unknown):Profile=>{
  const p=(raw&&typeof raw==="object"?raw:{}) as Json;
  const limit=(v:unknown)=>arr(v).slice(0,50).map(x=>x.slice(0,80));
  return {
    provinces:limit(p.provinces),regions:limit(p.regions),schools:limit(p.schools),
    types:limit(p.types),categories:limit(p.categories),subjects:limit(p.subjects),
    q:String(p.q||"").trim().slice(0,120)
  };
};
const hasConditions=(p:Profile)=>[
  p.provinces,p.regions,p.schools,p.types,p.categories,p.subjects
].some(x=>x.length>0)||Boolean(p.q);
const matches=(j:Json,p:Profile)=>{
  if(!active(j))return false;
  if(p.provinces.length&&!jobProvinces(j).some(x=>p.provinces.includes(x)))return false;
  if(p.regions.length&&!jobRegions(j).some(x=>p.regions.includes(x)))return false;
  if(p.schools.length&&!p.schools.includes(String(j.schoolLevel||"")))return false;
  if(p.types.length&&!p.types.includes(String(j.type||"")))return false;
  const cats=arr(j.categories);
  if(p.categories.length&&!p.categories.some(x=>cats.includes(x)))return false;
  if(p.subjects.length){
    const hay=" "+norm([j.subject,j.title,j.schoolLevel,j.type].filter(Boolean).join(" "))+" ";
    if(!p.subjects.some(x=>SUBJECT_RULES[x]?.test(hay)===true))return false;
  }
  if(p.q){
    const hay=String(j.searchText||norm([j.school,j.title,j.subject,j.region,j.type,j.source,j.schoolLevel,j.province].join(" ")));
    const tokens=norm(p.q).split(" ").filter(Boolean);
    if(!tokens.every(t=>hay.includes(t)))return false;
  }
  return true;
};
const hash=async(value:string)=>{
  const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes)).map(x=>x.toString(16).padStart(2,"0")).join("");
};
const fetchJobs=async()=>{
  const r=await fetch(JOBS_URL,{headers:{"cache-control":"no-cache"}});
  if(!r.ok)throw new Error("jobs fetch "+r.status);
  const data=await r.json();
  return (Array.isArray(data)?data:data.jobs||[]) as Json[];
};
const cors=(origin:string)=>({
  "access-control-allow-origin":origin,
  "access-control-allow-methods":"POST, OPTIONS",
  "access-control-allow-headers":"content-type,x-edujob-alert-key",
  "vary":"origin"
});
const response=(body:unknown,status=200,headers:HeadersInit={})=>new Response(JSON.stringify(body),{
  status,headers:{"content-type":"application/json",...headers}
});
const safeEqual=(a:string,b:string)=>{
  if(a.length!==b.length)return false;let out=0;for(let i=0;i<a.length;i++)out|=a.charCodeAt(i)^b.charCodeAt(i);return out===0;
};

async function subscribe(body:Json,origin:string){
  const sub=(body.subscription&&typeof body.subscription==="object"?body.subscription:{}) as Json;
  const endpoint=String(sub.endpoint||"");
  const keys=(sub.keys&&typeof sub.keys==="object"?sub.keys:{}) as Json;
  const p=profile(body.profile);
  const clientToken=String(body.clientToken||"");
  if(!hasConditions(p))return response({error:"profile_required"},400,cors(origin));
  if(!/^https:\/\//.test(endpoint)||endpoint.length>2048)return response({error:"invalid_endpoint"},400,cors(origin));
  if(clientToken.length<32||clientToken.length>128)return response({error:"invalid_client_token"},400,cors(origin));
  if(!String(keys.p256dh||"")||!String(keys.auth||""))return response({error:"invalid_subscription"},400,cors(origin));

  const jobs=await fetchJobs();
  const seen=jobs.filter(j=>matches(j,p)).map(jobKey).filter(Boolean).slice(0,3000);
  const endpointHash=await hash(endpoint);
  const tokenHash=await hash(clientToken);
  const {error}=await supabase.from("push_subscriptions").upsert({
    endpoint_hash:endpointHash,endpoint,
    p256dh:String(keys.p256dh),auth:String(keys.auth),
    client_token_hash:tokenHash,profile:p,seen_job_keys:seen,
    active:true,updated_at:new Date().toISOString()
  },{onConflict:"endpoint_hash"});
  if(error)throw error;
  return response({ok:true,baselineCount:seen.length},200,cors(origin));
}

async function unsubscribe(body:Json,origin:string){
  const endpoint=String(body.endpoint||"");
  const clientToken=String(body.clientToken||"");
  if(!endpoint||!clientToken)return response({error:"invalid_request"},400,cors(origin));
  const endpointHash=await hash(endpoint),tokenHash=await hash(clientToken);
  const {error}=await supabase.from("push_subscriptions")
    .update({active:false,updated_at:new Date().toISOString()})
    .eq("endpoint_hash",endpointHash).eq("client_token_hash",tokenHash);
  if(error)throw error;
  return response({ok:true},200,cors(origin));
}

async function dispatch(req:Request){
  const key=req.headers.get("x-edujob-alert-key")||"";
  if(!DISPATCH_KEY||!safeEqual(key,DISPATCH_KEY))return response({error:"unauthorized"},401);
  if(!VAPID_PUBLIC_KEY||!VAPID_PRIVATE_KEY)return response({error:"vapid_not_configured"},503);
  webpush.setVapidDetails(VAPID_SUBJECT,VAPID_PUBLIC_KEY,VAPID_PRIVATE_KEY);

  const jobs=await fetchJobs();
  const {data,error}=await supabase.from("push_subscriptions").select("*").eq("active",true).limit(500);
  if(error)throw error;

  let sent=0,deactivated=0,checked=0;
  for(const row of data||[]){
    checked++;
    const p=profile(row.profile);
    const matchesNow=jobs.filter(j=>matches(j,p));
    const keysNow=matchesNow.map(jobKey).filter(Boolean).slice(0,3000);
    const old=new Set(arr(row.seen_job_keys));
    const fresh=matchesNow.filter(j=>!old.has(jobKey(j))).slice(0,10);
    if(fresh.length){
      const first=fresh[0];
      const payload=JSON.stringify({
        title:fresh.length===1?"내 조건에 맞는 새 공고 1건":`내 조건에 맞는 새 공고 ${fresh.length}건`,
        body:fresh.length===1?String(first.title||"새 교육 채용공고가 등록되었습니다."):
          `${String(first.title||"새 공고")} 외 ${fresh.length-1}건`,
        url:SITE_URL+"?radar=new",
        tag:"edujob-new-jobs"
      });
      try{
        await webpush.sendNotification({
          endpoint:row.endpoint,
          keys:{p256dh:row.p256dh,auth:row.auth}
        },payload,{TTL:3600});
        sent++;
      }catch(e){
        const code=Number((e as {statusCode?:number})?.statusCode||0);
        if(code===404||code===410){
          await supabase.from("push_subscriptions").update({active:false,updated_at:new Date().toISOString()})
            .eq("endpoint_hash",row.endpoint_hash);
          deactivated++;
          continue;
        }
      }
    }
    await supabase.from("push_subscriptions").update({
      seen_job_keys:keysNow,last_dispatched_at:new Date().toISOString(),updated_at:new Date().toISOString()
    }).eq("endpoint_hash",row.endpoint_hash);
  }
  return response({ok:true,checked,sent,deactivated});
}

export default {
  fetch:async(req:Request)=>{
    try{
      if(req.method==="OPTIONS"){
        const origin=req.headers.get("origin")||"";
        if(!ALLOWED_ORIGINS.includes(origin))return new Response(null,{status:403});
        return new Response(null,{status:204,headers:cors(origin)});
      }
      if(req.method!=="POST")return response({error:"method_not_allowed"},405);
      const origin=req.headers.get("origin")||"";
      const body=await req.json().catch(()=>({})) as Json;
      if(body.action==="dispatch")return dispatch(req);
      if(!ALLOWED_ORIGINS.includes(origin))return response({error:"origin_not_allowed"},403);
      if(body.action==="subscribe")return subscribe(body,origin);
      if(body.action==="unsubscribe")return unsubscribe(body,origin);
      return response({error:"unknown_action"},400,cors(origin));
    }catch(e){
      console.error(e);
      return response({error:"internal_error"},500);
    }
  }
};
