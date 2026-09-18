import {createClient} from 'npm:@supabase/supabase-js@2.116.0';
import {fetchCurrentJobs,matchingKeys,sha256,type Profile} from '../_shared/alerts.ts';

const json=(body:unknown,status=200,origin='*')=>new Response(JSON.stringify(body),{
  status,
  headers:{
    'content-type':'application/json',
    'access-control-allow-origin':origin,
    'access-control-allow-headers':'content-type',
    'access-control-allow-methods':'POST,OPTIONS'
  }
});

export default {
  fetch: async (req:Request)=>{
    const configuredOrigin=Deno.env.get('EDUJOB_PUBLIC_ORIGIN')||'*';
    const origin=req.headers.get('origin')||'';
    if(configuredOrigin!=='*'&&origin&&origin!==configuredOrigin)return json({error:'origin'},403,configuredOrigin);
    if(req.method==='OPTIONS')return json({ok:true},200,configuredOrigin);
    if(req.method!=='POST')return json({error:'method'},405,configuredOrigin);

    const url=Deno.env.get('SUPABASE_URL');
    const key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if(!url||!key)return json({error:'server-config'},503,configuredOrigin);
    const db=createClient(url,key,{auth:{persistSession:false}});

    let body:any;
    try{body=await req.json()}catch{return json({error:'json'},400,configuredOrigin)}
    const action=String(body?.action||'');
    const clientToken=String(body?.clientToken||'');
    if(clientToken.length<32||clientToken.length>256)return json({error:'token'},400,configuredOrigin);
    const tokenHash=await sha256(clientToken);

    if(action==='unsubscribe'){
      const endpoint=String(body?.endpoint||'');
      if(!endpoint.startsWith('https://'))return json({error:'endpoint'},400,configuredOrigin);
      const endpointHash=await sha256(endpoint);
      const {error}=await db.from('edujob_push_subscriptions')
        .delete().eq('endpoint_hash',endpointHash).eq('client_token_hash',tokenHash);
      if(error)return json({error:'db'},500,configuredOrigin);
      return json({ok:true},200,configuredOrigin);
    }

    if(action!=='subscribe')return json({error:'action'},400,configuredOrigin);
    const sub=body?.subscription;
    const endpoint=String(sub?.endpoint||'');
    const p256dh=String(sub?.keys?.p256dh||'');
    const auth=String(sub?.keys?.auth||'');
    const profile=(body?.profile||{}) as Profile;
    const hasConditions=['provinces','regions','schools','types','categories','subjects']
      .some(k=>Array.isArray((profile as any)[k])&&(profile as any)[k].length)
      ||Boolean(String(profile.q||'').trim());
    if(!hasConditions)return json({error:'profile-required'},400,configuredOrigin);
    if(!endpoint.startsWith('https://')||endpoint.length>4096||p256dh.length<20||auth.length<8){
      return json({error:'subscription'},400,configuredOrigin);
    }
    if(JSON.stringify(profile).length>12000)return json({error:'profile-too-large'},400,configuredOrigin);

    const endpointHash=await sha256(endpoint);
    const {data:existing,error:lookupError}=await db.from('edujob_push_subscriptions')
      .select('client_token_hash,profile,seen_ids').eq('endpoint_hash',endpointHash).maybeSingle();
    if(lookupError)return json({error:'db'},500,configuredOrigin);
    if(existing&&existing.client_token_hash!==tokenHash)return json({error:'subscription-owned'},409,configuredOrigin);

    let seenIds=Array.isArray(existing?.seen_ids)?existing.seen_ids:[];
    const profileChanged=JSON.stringify(existing?.profile||{})!==JSON.stringify(profile||{});
    if(!existing||profileChanged){
      try{
        const jobs=await fetchCurrentJobs();
        seenIds=matchingKeys(jobs,profile).slice(0,3000);
      }catch{
        return json({error:'baseline-unavailable'},503,configuredOrigin);
      }
    }

    const row={
      endpoint_hash:endpointHash,
      endpoint,
      p256dh,
      auth,
      client_token_hash:tokenHash,
      profile,
      seen_ids:seenIds,
      enabled:true,
      updated_at:new Date().toISOString()
    };
    const {error}=await db.from('edujob_push_subscriptions').upsert(row,{onConflict:'endpoint_hash'});
    if(error)return json({error:'db'},500,configuredOrigin);
    return json({ok:true,baselineCount:seenIds.length},200,configuredOrigin);
  }
};
