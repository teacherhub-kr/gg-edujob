import {createClient} from 'npm:@supabase/supabase-js@2.116.0';
import {sendPushNotification} from 'npm:@mmmike/web-push@1.0.1/send';
import {fetchCurrentJobs,jobKey,matchesProfile,type Job,type Profile} from '../_shared/alerts.ts';

const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,
  headers:{'content-type':'application/json'}
});

export default {
  fetch: async (req:Request)=>{
    if(req.method!=='POST')return response({error:'method'},405);
    const secret=Deno.env.get('EDUJOB_ALERT_DISPATCH_SECRET')||'';
    const supplied=req.headers.get('x-edujob-alert-secret')||'';
    if(!secret||supplied!==secret)return response({error:'unauthorized'},401);

    const url=Deno.env.get('SUPABASE_URL');
    const serviceRole=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    const publicKey=Deno.env.get('VAPID_PUBLIC_KEY');
    const privateKey=Deno.env.get('VAPID_PRIVATE_KEY');
    const subject=Deno.env.get('VAPID_SUBJECT');
    const publicUrl=Deno.env.get('EDUJOB_PUBLIC_URL')||'./';
    if(!url||!serviceRole||!publicKey||!privateKey||!subject)return response({error:'server-config'},503);

    const jobs=await fetchCurrentJobs();
    const db=createClient(url,serviceRole,{auth:{persistSession:false}});
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
        await sendPushNotification(
          {endpoint:String(row.endpoint),keys:{p256dh:String(row.p256dh),auth:String(row.auth)}},
          {title,body,tag:'edujob-new-jobs',data:{url:publicUrl}},
          {publicKey,privateKey,subject}
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
