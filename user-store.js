(()=>{
  if(window.EduJobUserStore)return;

  const KEYS={
    profile:'edujob.jobRadar.profile.v1',
    snapshot:'edujob.jobRadar.snapshot.v1',
    favorites:'edujob.jobRadar.favorites.v1'
  };

  const parse=(raw,fallback=null)=>{try{return raw?JSON.parse(raw):fallback}catch(e){return fallback}};
  const local={
    get:(key,fallback=null)=>parse(localStorage.getItem(key),fallback),
    set:(key,value)=>localStorage.setItem(key,JSON.stringify(value)),
    remove:key=>localStorage.removeItem(key)
  };

  let accountAdapter=null;

  const api={
    version:1,
    storageMode:()=>accountAdapter?'hybrid':'local',
    profile:{
      get:()=>local.get(KEYS.profile),
      set:value=>{local.set(KEYS.profile,value);api.syncAccountSoon()},
      remove:()=>{local.remove(KEYS.profile);api.syncAccountSoon()}
    },
    snapshot:{
      get:()=>local.get(KEYS.snapshot),
      set:value=>{local.set(KEYS.snapshot,value);api.syncAccountSoon()},
      remove:()=>{local.remove(KEYS.snapshot);api.syncAccountSoon()}
    },
    favorites:{
      get:()=>local.get(KEYS.favorites,[]),
      set:value=>{local.set(KEYS.favorites,Array.isArray(value)?value:[]);api.syncAccountSoon()}
    },
    exportState:()=>({
      version:1,
      profile:local.get(KEYS.profile),
      snapshot:local.get(KEYS.snapshot),
      favorites:local.get(KEYS.favorites,[])
    }),
    importState:(state,{overwrite=true}={})=>{
      if(!state||typeof state!=='object')return;
      const current=api.exportState();
      if(overwrite||!current.profile){if(state.profile)local.set(KEYS.profile,state.profile)}
      if(overwrite||!current.snapshot){if(state.snapshot)local.set(KEYS.snapshot,state.snapshot)}
      if(overwrite||!current.favorites?.length){if(Array.isArray(state.favorites))local.set(KEYS.favorites,state.favorites)}
    },
    setAccountAdapter:adapter=>{
      if(adapter!==null&&(!adapter||typeof adapter.pull!=='function'||typeof adapter.push!=='function')){
        throw new Error('account adapter must provide pull() and push(state)');
      }
      accountAdapter=adapter;
      return api;
    },
    hydrateAccount:async()=>{
      if(!accountAdapter)return null;
      const remote=await accountAdapter.pull();
      if(remote)api.importState(remote,{overwrite:true});
      return remote;
    },
    syncAccount:async()=>{
      if(!accountAdapter)return null;
      const state=api.exportState();
      await accountAdapter.push(state);
      return state;
    },
    syncAccountSoon:()=>{
      if(!accountAdapter)return;
      Promise.resolve().then(()=>api.syncAccount()).catch(()=>{});
    }
  };

  window.EduJobUserStore=api;
})();