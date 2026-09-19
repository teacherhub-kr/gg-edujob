import {createClient} from 'npm:@supabase/supabase-js@2.116.0';
import {fetchCurrentJobs,matchingKeys,profileComparable,sha256,stampedProfile,MATCH_CONTRACT_VERSION,type Profile} from '../_shared/alerts.ts';

const PUBLIC_ORIGIN='https://teacherhub-kr.github.io';

const json=(body:unknown,status=200,origin=PUBLIC_ORIGIN)=>new Response(JSON.stringify(body),{
  status,
  headers:{
    'content-type':'application/json',
    'access-control-allow-origin':origin,
    'access-control-allow-headers':'content-type',
    'access-control-allow-methods':'POST,OPTIONS',
    'vary':'origin'
  }
});

const adminClient=()=>{
  const url=Deno.env.get('SUPABASE_URL')||'';
  const modern=JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS')||'{}');
  const key=modern.default||Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
  if(!url||!key)return null;
  return createClient(url,key,{auth:{persistSession:false}});
};

export default {
  fetch: async (req:Request)=>{
    const origin=req.headers.get('origin')||'';
    if(origin!==PUBLIC_ORIGIN)return json({error:'origin'},403);
    if(req.method==='OPTIONS')return json({ok:true});
    if(req.method!=='POST')return json({error:'method'},405);

    const db=adminClient();
    if(!db)return json({error:'server-config'},503);

    let body:any;
    try{body=await req.json()}catch{return json({error:'json'},400)}
    const action=String(body?.action||'');
    const clientToken=String(body?.clientToken||'');
    if(clientToken.length<32||clientToken.length>256)return json({error:'token'},400);
    const tokenHash=await sha256(clientToken);

    if(action==='unsubscribe'){
      const endpoint=String(body?.endpoint||'');
      if(!endpoint.startsWith('https://'))return json({error:'endpoint'},400);
      const endpointHash=await sha256(endpoint);
      const {error}=await db.from('edujob_push_subscriptions')
        .delete().eq('endpoint_hash',endpointHash).eq('client_token_hash',tokenHash);
      if(error)return json({error:'db'},500);
      return json({ok:true});
    }

    if(action!=='subscribe')return json({error:'action'},400);
    const sub=body?.subscription;
    const endpoint=String(sub?.endpoint||'');
    const p256dh=String(sub?.keys?.p256dh||'');
    const auth=String(sub?.keys?.auth||'');
    const profile=profileComparable((body?.profile||{}) as Profile) as Profile;
    const hasConditions=['provinces','regions','schools','types','categories','subjects']
      .some(k=>Array.isArray((profile as any)[k])&&(profile as any)[k].length)
      ||Boolean(String(profile.q||'').trim());
    if(!hasConditions)return json({error:'profile-required'},400);
    if(!endpoint.startsWith('https://')||endpoint.length>4096||p256dh.length<20||auth.length<8){
      return json({error:'subscription'},400);
    }
    if(JSON.stringify(profile).length>12000)return json({error:'profile-too-large'},400);

    const endpointHash=await sha256(endpoint);
    const {data:existing,error:lookupError}=await db.from('edujob_push_subscriptions')
      .select('client_token_hash,profile,seen_ids').eq('endpoint_hash',endpointHash).maybeSingle();
    if(lookupError)return json({error:'db'},500);
    if(existing&&existing.client_token_hash!==tokenHash)return json({error:'subscription-owned'},409);

    let seenIds=Array.isArray(existing?.seen_ids)?existing.seen_ids:[];
    const existingProfile=(existing?.profile||{}) as Profile;
    const profileChanged=JSON.stringify(profileComparable(existingProfile))!==JSON.stringify(profileComparable(profile));
    const contractChanged=Number(existingProfile?._matchContractVersion||0)!==MATCH_CONTRACT_VERSION;
    if(!existing||profileChanged||contractChanged){
      try{
        const jobs=await fetchCurrentJobs();
        seenIds=matchingKeys(jobs,profile).slice(0,3000);
      }catch{
        return json({error:'baseline-unavailable'},503);
      }
    }

    const row={
      endpoint_hash:endpointHash,
      endpoint,
      p256dh,
      auth,
      client_token_hash:tokenHash,
      profile:stampedProfile(profile),
      seen_ids:seenIds,
      enabled:true,
      updated_at:new Date().toISOString()
    };
    const {error}=await db.from('edujob_push_subscriptions').upsert(row,{onConflict:'endpoint_hash'});
    if(error)return json({error:'db'},500);
    return json({ok:true,baselineCount:seenIds.length});
  }
};
