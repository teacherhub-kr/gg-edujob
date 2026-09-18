import {createClient} from 'npm:@supabase/supabase-js@2.116.0';
import webpush from 'npm:web-push@3.6.7';
import {fetchCurrentJobs,jobKey,matchesProfile,type Job,type Profile} from '../_shared/alerts.ts';

const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,
  headers:{'content-type':'application/json'}
});

const safeEqual=(a:string,b:string)=>{
  if(a.length!==b.length)return false;
  let out=0;
  for(let i=0;i<a.length;i++)out|=a.charCodeAt(i)^b.charCodeAt(i);
  return out===0;
};

const adminClient=()=>{
  const url=Deno.env.get('SUPABASE_URL')||'';
  const modern=JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS')||'{}');
  const key=modern.default||Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
  if(!url||!key)return null;
  return createClient(url,key,{auth:{persistSession:false}});
};

export default {
  fetch: async (req:Request)=>{
    if(req.method!=='POST')return response({error:'method'},405);
    const db=adminClient();
    if(!db)return response({error:'server-config'},503);

    const {data:config,error:configError}=await db.from('edujob_alert_config')
      .select('vapid_public_key,vapid_private_key,vapid_subject,dispatch_secret,public_url')
      .eq('id',1).maybeSingle();
    if(configError||!config)return response({error:'server-config'},503);

    const supplied=req.headers.get('x-edujob-alert-secret')||'';
    if(!safeEqual(String(config.dispatch_secret||''),supplied))return response({error:'unauthorized'},401);

    webpush.setVapidDetails(
      String(config.vapid_subject),
      String(config.vapid_public_key),
      String(config.vapid_private_key)
    );

    const jobs=await fetchCurrentJobs();
    const {data:rows,error}=await db.from('edujob_push_subscriptions')
      .select('id,endpoint,p256dh,auth,profile,seen_ids').eq('enabled',true).limit(1000);
    if(error)return response({error:'db'},500);

    let sent=0,disabled=0,unchanged=0,failed=0;
    for(const row of rows||[]){
      const profile=(row.profile||{}) as Profile;
      const matching=(jobs as Job[]).filter(j=>matchesProfile(j,profile));
      const currentIds=matching.map(jobKey).filter(Boolean).slice(0,3000);
      const seen=new Set(Array.isArray(row.seen_ids)?row.seen_ids:[]);
      const fresh=matching.filter(j=>!seen.has(jobKey(j)));
      if(!fresh.length){unchanged++;continue}

      const first=fresh[0];
      const title=fresh.length===1?'내 조건에 맞는 새 공고 1건':`내 조건에 맞는 새 공고 ${fresh.length}건`;
      const school=String(first.school||'기관명 확인');
      const jobTitle=String(first.title||'채용 공고');
      const body=fresh.length===1?`${school} · ${jobTitle}`:`${school} · ${jobTitle} 외 ${fresh.length-1}건`;

      try{
        await webpush.sendNotification(
          {endpoint:String(row.endpoint),keys:{p256dh:String(row.p256dh),auth:String(row.auth)}},
          JSON.stringify({title,body,tag:'edujob-new-jobs',url:String(config.public_url)}),
          {TTL:3600}
        );
        await db.from('edujob_push_subscriptions').update({
          seen_ids:currentIds,
          last_notified_at:new Date().toISOString(),
          updated_at:new Date().toISOString()
        }).eq('id',row.id);
        sent++;
      }catch(e){
        const status=Number((e as any)?.statusCode||0);
        if(status===404||status===410){
          await db.from('edujob_push_subscriptions').update({
            enabled:false,
            updated_at:new Date().toISOString()
          }).eq('id',row.id);
          disabled++;
        }else failed++;
      }
    }
    return response({ok:true,sent,disabled,unchanged,failed,total:(rows||[]).length});
  }
};
