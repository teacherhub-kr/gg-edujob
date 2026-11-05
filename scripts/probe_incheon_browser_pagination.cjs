/* Diagnostic only: click the official ICE page-2 link in a real browser. */
'use strict';
const {chromium}=require('@playwright/test');

async function readOfficialIds(page){
 for(let attempt=1;attempt<=3;attempt+=1){
  try{
   await page.waitForLoadState('domcontentloaded',{timeout:10000});
   const rows=page.locator('a.nttInfoBtn[data-id]');
   await rows.first().waitFor({state:'attached',timeout:10000});
   return await rows.evaluateAll(nodes=>nodes.map(x=>x.getAttribute('data-id')).filter(Boolean));
  }catch(error){
   const navigationRace=/execution context was destroyed|navigation/i.test(error.message);
   if(!navigationRace||attempt===3)throw error;
   console.warn('BROWSER_NAVIGATION_RACE_RETRY',JSON.stringify({attempt}));
   await page.waitForTimeout(500);
  }
 }
 throw Error('Official IDs unavailable after bounded navigation retries');
}

(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({locale:'ko-KR',timezoneId:'Asia/Seoul'});
  const url='https://www.ice.go.kr/ice/na/ntt/selectNttList.do?bbsId=1981&mi=10997';
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:35000});
  const first=await readOfficialIds(page);
  console.log('BROWSER_PAGE1',JSON.stringify({count:first.length,firstTwoIds:first.slice(0,2),urlHost:new URL(page.url()).hostname}));
  if(first.length<5)throw Error('Official first page not parseable (fail-closed)');
  const control=page.locator('a[onclick="goPaging(2)"]').first();
  if(await control.count()!==1)throw Error('Official goPaging(2) link missing');
  await Promise.all([
   page.waitForNavigation({waitUntil:'domcontentloaded',timeout:20000}),
   control.click({timeout:20000})
  ]);
  const second=await readOfficialIds(page);
  const repeated=first.length===second.length&&first.every((v,i)=>v===second[i]);
  console.log('BROWSER_PAGE2',JSON.stringify({count:second.length,firstTwoIds:second.slice(0,2),
   identicalToFirst:repeated,hasNewIds:second.some(id=>!first.includes(id)),
   urlHost:new URL(page.url()).hostname}));
  if(second.length<5||repeated||!second.some(id=>!first.includes(id)))
   throw Error('Official browser page-2 not independently distinct (fail-closed)');
 }finally{await browser.close();}
})().catch(error=>{console.error('BROWSER_PAGINATION_DIAGNOSTIC_FAILED',error.message);process.exitCode=1});
