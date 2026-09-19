(()=>{
  if(window.__edujobAlertClientLoaded)return;
  window.__edujobAlertClientLoaded=true;

  const config=window.EDUJOB_ALERT_CONFIG||{};
  const store=window.EduJobUserStore;
  if(!store||!config.enabled||!config.endpoint||!config.vapidPublicKey)return;

  const supported=()=>('serviceWorker'in navigator)&&('PushManager'in window)&&('Notification'in window);
  const isIOS=()=>/iphone|ipad|ipod/i.test(navigator.userAgent||'');
  const isStandalone=()=>window.matchMedia?.('(display-mode: standalone)').matches===true||navigator.standalone===true;
  const b64url=bytes=>btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  const appKey=value=>{
    const pad='='.repeat((4-value.length%4)%4);
    const raw=atob((value+pad).replace(/-/g,'+').replace(/_/g,'/'));
    return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)));
  };
  const makeToken=()=>b64url(crypto.getRandomValues(new Uint8Array(32)));
  const state=()=>store.alerts?.get?.()||{};
  const save=value=>store.alerts?.set?.(value);

  async function post(body){
    const res=await fetch(config.endpoint,{
      method:'POST',
      headers:{'content-type':'application/json'},
      body:JSON.stringify(body),
      cache:'no-store'
    });
    if(!res.ok)throw new Error('alert endpoint '+res.status);
    return res.json().catch(()=>({ok:true}));
  }

  async function registration(){
    return navigator.serviceWorker.register('./sw.js',{scope:'./'});
  }

  async function currentSubscription(){
    const reg=await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  async function subscribe(){
    if(!supported())throw new Error('unsupported');
    const profile=store.profile.get();
    const hasConditions=profile&&(['provinces','regions','schools','types','categories','subjects'].some(k=>Array.isArray(profile[k])&&profile[k].length)||String(profile.q||'').trim());
    if(!hasConditions)throw new Error('profile-required');
    if(isIOS()&&!isStandalone())throw new Error('ios-home-screen-required');
    const permission=await Notification.requestPermission();
    if(permission!=='granted')throw new Error('permission-denied');

    const reg=await registration();
    let sub=await reg.pushManager.getSubscription();
    if(!sub){
      sub=await reg.pushManager.subscribe({
        userVisibleOnly:true,
        applicationServerKey:appKey(config.vapidPublicKey)
      });
    }
    const prev=state();
    const clientToken=prev.clientToken||makeToken();
    await post({
      action:'subscribe',
      subscription:sub.toJSON(),
      profile,
      clientToken
    });
    save({enabled:true,clientToken,endpoint:sub.endpoint,updatedAt:new Date().toISOString()});
    return sub;
  }

  async function unsubscribe(){
    const prev=state();
    const sub=await currentSubscription().catch(()=>null);
    const endpoint=sub?.endpoint||prev.endpoint||'';
    if(endpoint&&prev.clientToken){
      await post({action:'unsubscribe',endpoint,clientToken:prev.clientToken}).catch(()=>{});
    }
    if(sub)await sub.unsubscribe().catch(()=>{});
    save({enabled:false,clientToken:prev.clientToken||'',endpoint:'',updatedAt:new Date().toISOString()});
  }

  async function sync(){
    const prev=state();
    if(!prev.enabled||!prev.clientToken||!supported())return;
    const sub=await currentSubscription().catch(()=>null);
    if(!sub)return;
    await post({
      action:'subscribe',
      subscription:sub.toJSON(),
      profile:store.profile.get(),
      clientToken:prev.clientToken
    });
  }

  window.EduJobAlerts=Object.freeze({
    supported,
    state,
    subscribe,
    unsubscribe,
    sync
  });

  function setStatus(message){
    const copy=document.getElementById('jobRadarCopy');
    if(copy&&message)copy.textContent=message;
  }

  function installButton(attempt=0){
    const actions=document.querySelector('.job-radar-actions');
    if(!actions){
      if(attempt<20)setTimeout(()=>installButton(attempt+1),120);
      return;
    }
    if(document.getElementById('jobRadarAlerts'))return;

    const btn=document.createElement('button');
    btn.type='button';
    btn.className='job-radar-btn';
    btn.id='jobRadarAlerts';
    const refresh=()=>{
      const on=Boolean(state().enabled);
      btn.textContent=on?'🔔 알림 켜짐':'🔔 새 공고 알림';
      btn.classList.toggle('primary',on);
      btn.setAttribute('aria-pressed',String(on));
    };
    refresh();

    btn.addEventListener('click',async()=>{
      btn.disabled=true;
      try{
        if(state().enabled){
          await unsubscribe();
          setStatus('새 공고 알림을 껐습니다. 저장한 조건과 관심공고는 그대로 유지됩니다.');
        }else{
          await subscribe();
          setStatus('새 공고 알림을 켰습니다. 앞으로 내 조건에 맞는 새 공고만 알려드립니다.');
        }
      }catch(e){
        if(String(e.message)==='profile-required')setStatus('먼저 원하는 지역·학교급·직종·과목 조건을 저장한 뒤 새 공고 알림을 켜 주세요.');
        else if(String(e.message)==='ios-home-screen-required')setStatus('iPhone·iPad에서는 수도권에듀잡을 홈 화면에 추가한 뒤 알림을 켤 수 있습니다.');
        else if(String(e.message)==='permission-denied')setStatus('브라우저에서 알림 권한이 허용되지 않았습니다.');
        else if(String(e.message)==='unsupported')setStatus('현재 브라우저에서는 웹 푸시 알림을 지원하지 않습니다.');
        else setStatus('알림 설정 중 오류가 발생했습니다. 기존 검색과 레이더 기능에는 영향이 없습니다.');
      }finally{
        btn.disabled=false;refresh();
      }
    });
    actions.appendChild(btn);
  }

  window.addEventListener('edujob:user-state-changed',event=>{
    if(event.detail?.kind==='profile')sync().catch(()=>{});
  });
  window.addEventListener('pageshow',()=>sync().catch(()=>{}));
  registration().catch(()=>{});
  installButton();
})();
