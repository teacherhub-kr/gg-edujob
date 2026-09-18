self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));

self.addEventListener('push',event=>{
  let payload={};
  try{payload=event.data?event.data.json():{}}catch(e){payload={body:event.data?.text?.()||''}}
  const title=payload.title||'수도권에듀잡';
  const options={
    body:payload.body||'내 조건에 맞는 새 교육 채용공고가 등록되었습니다.',
    icon:'./edujob-icon.svg',
    badge:'./edujob-icon.svg',
    tag:payload.tag||'edujob-new-jobs',
    data:{url:payload.url||'./'},
    renotify:false
  };
  event.waitUntil(self.registration.showNotification(title,options));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const raw=event.notification?.data?.url||'./';
  event.waitUntil((async()=>{
    const target=new URL(raw,self.registration.scope).href;
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows){
      if(client.url===target&&'focus' in client)return client.focus();
    }
    return self.clients.openWindow?self.clients.openWindow(target):undefined;
  })());
});
