(()=>{
  if(window.EduJobUserStore)return;

  const KEYS={
    profile:'edujob.jobRadar.profile.v1',
    snapshot:'edujob.jobRadar.snapshot.v1',
    favorites:'edujob.jobRadar.favorites.v1',
    alerts:'edujob.alerts.v1',
    recent:'edujob.recentJobs.v1',
    installPrompt:'edujob.installPrompt.dismissed.v1'
  };

  const parse=(raw,fallback=null)=>{try{return raw?JSON.parse(raw):fallback}catch(e){return fallback}};
  const memory=new Map();
  const local={
    get:(key,fallback=null)=>{
      try{
        const raw=localStorage.getItem(key);
        if(raw!==null)return parse(raw,fallback);
      }catch(e){}
      return memory.has(key)?memory.get(key):fallback;
    },
    set:(key,value)=>{
      memory.set(key,value);
      try{localStorage.setItem(key,JSON.stringify(value))}catch(e){}
    },
    remove:key=>{
      memory.delete(key);
      try{localStorage.removeItem(key)}catch(e){}
    }
  };

  let accountAdapter=null;
  const emit=kind=>{try{window.dispatchEvent(new CustomEvent('edujob:user-state-changed',{detail:{kind}}))}catch(e){}};

  const api={
    version:1,
    storageMode:()=>accountAdapter?'hybrid':'local',
    profile:{
      get:()=>local.get(KEYS.profile),
      set:value=>{local.set(KEYS.profile,value);emit('profile');api.syncAccountSoon()},
      remove:()=>{local.remove(KEYS.profile);emit('profile');api.syncAccountSoon()}
    },
    snapshot:{
      get:()=>local.get(KEYS.snapshot),
      set:value=>{local.set(KEYS.snapshot,value);api.syncAccountSoon()},
      remove:()=>{local.remove(KEYS.snapshot);api.syncAccountSoon()}
    },
    favorites:{
      get:()=>local.get(KEYS.favorites,[]),
      set:value=>{local.set(KEYS.favorites,Array.isArray(value)?value:[]);emit('favorites');api.syncAccountSoon()}
    },
    alerts:{
      get:()=>local.get(KEYS.alerts,{enabled:false}),
      set:value=>{local.set(KEYS.alerts,value&&typeof value==='object'?value:{enabled:false});emit('alerts');api.syncAccountSoon()}
    },
    recent:{
      get:()=>local.get(KEYS.recent,[]),
      set:value=>{local.set(KEYS.recent,Array.isArray(value)?value.slice(0,50):[]);emit('recent');api.syncAccountSoon()},
      clear:()=>{local.remove(KEYS.recent);emit('recent');api.syncAccountSoon()}
    },
    installPrompt:{
      dismissed:()=>Boolean(local.get(KEYS.installPrompt,false)),
      dismiss:()=>local.set(KEYS.installPrompt,true),
      reset:()=>local.remove(KEYS.installPrompt)
    },
    exportState:()=>({
      version:1,
      profile:local.get(KEYS.profile),
      snapshot:local.get(KEYS.snapshot),
      favorites:local.get(KEYS.favorites,[]),
      alerts:local.get(KEYS.alerts,{enabled:false}),
      recent:local.get(KEYS.recent,[])
    }),
    importState:(state,{overwrite=true}={})=>{
      if(!state||typeof state!=='object')return;
      const current=api.exportState();
      if(overwrite||!current.profile){if(state.profile)local.set(KEYS.profile,state.profile)}
      if(overwrite||!current.snapshot){if(state.snapshot)local.set(KEYS.snapshot,state.snapshot)}
      if(overwrite||!current.favorites?.length){if(Array.isArray(state.favorites))local.set(KEYS.favorites,state.favorites)}
      if(overwrite||!current.alerts?.enabled){if(state.alerts&&typeof state.alerts==='object')local.set(KEYS.alerts,state.alerts)}
      if(overwrite||!current.recent?.length){if(Array.isArray(state.recent))local.set(KEYS.recent,state.recent.slice(0,50))}
    },
    resetLocal:()=>{
      Object.values(KEYS).forEach(local.remove);
      emit('reset');
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
    migrateLocalToAccount:async()=>{
      if(!accountAdapter)return null;
      const localState=api.exportState();
      await accountAdapter.push(localState);
      return localState;
    },
    syncAccountSoon:()=>{
      if(!accountAdapter)return;
      Promise.resolve().then(()=>api.syncAccount()).catch(()=>{});
    }
  };

  window.EduJobUserStore=api;
})();