#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright

TARGETS=[
 {"key":"nambu","name":"인천남부교육지원청","home":"https://nambu.ice.go.kr/Main.do"},
 {"key":"seobu","name":"인천서부교육지원청","home":"https://seobu.ice.go.kr/"},
]
SIGNAL=re.compile(r"구인|채용|recruit|job|bbs|board|content|data|list",re.I)
EXACT_LABELS=("구인정보","구인","채용정보","채용공고")

def clean(s):
 return re.sub(r"\s+"," ",str(s or "")).strip()

def main():
 out={"mode":"read-only-browser-diagnostic-v2","targets":[]}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True)
  for t in TARGETS:
   ctx=browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",viewport={"width":1440,"height":1100})
   page=ctx.new_page()
   net=[]
   def record(resp):
    u=str(resp.url or "")
    if SIGNAL.search(u):
     net.append({"url":u,"status":resp.status,"contentType":resp.headers.get("content-type","")})
   page.on("response",record)
   item={"key":t["key"],"name":t["name"],"home":t["home"],"ok":False,"errors":[]}
   try:
    r=page.goto(t["home"],wait_until="domcontentloaded",timeout=60000)
    page.wait_for_timeout(1200)
    item["homeStatus"]=r.status if r else 0
    item["loadedUrl"]=page.url
    candidates=[]
    for a in page.locator("a").all():
     try:
      txt=clean(a.inner_text(timeout=400))
      href=clean(a.get_attribute("href"))
      onclick=clean(a.get_attribute("onclick"))
      if txt in EXACT_LABELS or (txt and re.fullmatch(r".{0,4}(?:구인정보|채용정보|채용공고).{0,4}",txt)):
       candidates.append({
        "text":txt[:160],
        "href":href[:600],
        "absoluteHref":(urljoin(page.url,href) if href and not href.lower().startswith(("javascript:","#")) else href)[:600],
        "onclick":onclick[:600],
       })
     except Exception:
      pass
    item["exactRecruitmentLinks"]=candidates

    clicked=False
    click_meta=None
    # Click only an exact recruitment navigation candidate, never a broad regex match.
    for label in EXACT_LABELS:
     loc=page.get_by_text(label,exact=True)
     for i in range(min(loc.count(),10)):
      node=loc.nth(i)
      try:
       if not node.is_visible():
        continue
       click_meta={"text":label}
       # Capture nearest link attributes before navigation.
       link=node.locator("xpath=ancestor-or-self::a[1]")
       if link.count():
        click_meta["href"]=clean(link.get_attribute("href"))
        click_meta["onclick"]=clean(link.get_attribute("onclick"))
       node.click(timeout=3500)
       page.wait_for_timeout(1800)
       clicked=True
       break
      except Exception as exc:
       item["errors"].append(f"click-{label}:{type(exc).__name__}:{str(exc)[:160]}")
     if clicked:
      break

    item["clicked"]=clicked
    item["clickMeta"]=click_meta
    item["afterUrl"]=page.url
    item["bodySample"]=clean(page.locator("body").inner_text(timeout=3000))[:7000]
    anchors=[]
    for a in page.locator("a").all():
     try:
      txt=clean(a.inner_text(timeout=400))
      href=clean(a.get_attribute("href"))
      onclick=clean(a.get_attribute("onclick"))
      if txt and (SIGNAL.search(txt) or SIGNAL.search(href) or SIGNAL.search(onclick)):
       absolute=urljoin(page.url,href) if href and not href.lower().startswith(("javascript:","#")) else href
       anchors.append({"text":txt[:180],"href":absolute[:700],"onclick":onclick[:700]})
     except Exception:
      pass
    item["anchorsAfter"]=anchors[:220]
    item["networkSignals"]=list({x["url"]:x for x in net}.values())[-220:]
    if t["key"]=="seobu":
     try:
      direct_url="https://seobu.ice.go.kr/bseobu/list.aspx?board_code=4674"
      direct=page.goto(direct_url,wait_until="domcontentloaded",timeout=60000)
      page.wait_for_timeout(1000)
      item["seobuDirectStatus"]=direct.status if direct else 0
      item["seobuDirectUrl"]=page.url
      pager=[]
      for a in page.locator("a").all():
       try:
        txt=clean(a.inner_text(timeout=300))
        href=clean(a.get_attribute("href"))
        if txt and (txt.isdigit() or re.search(r"다음|이전|next|prev|>|<",txt,re.I) or "__doPostBack" in href):
         pager.append({"text":txt[:80],"href":href[:700]})
       except Exception:
        pass
      item["seobuPagerAnchors"]=pager[:120]
      rows=[]
      for a in page.locator('a[href*="read.aspx?board_code=4674"]').all():
       try:
        rows.append({"text":clean(a.inner_text(timeout=300))[:300],"href":clean(a.get_attribute("href"))[:700]})
       except Exception:
        pass
      item["seobuRowLinks"]=rows[:40]
     except Exception as exc:
      item["errors"].append(f"seobu-direct:{type(exc).__name__}:{str(exc)[:500]}")
     try:
      req=Request("https://seobu.ice.go.kr/bseobu/list.aspx?board_code=4674",headers={"User-Agent":"Mozilla/5.0"})
      with urlopen(req,timeout=30) as resp:
       body=resp.read()
       item["seobuSystemCaProbe"]={"status":getattr(resp,"status",0),"finalUrl":resp.geturl(),"length":len(body),"sample":body[:240].decode("utf-8",errors="replace")}
     except Exception as exc:
      item["seobuSystemCaProbe"]={"error":f"{type(exc).__name__}: {str(exc)[:500]}"}
    if t["key"]=="nambu":
     try:
      cfg_url="https://nambu.ice.go.kr/cms/json/config/getBoardConfigDataByBoardCode.act?boardcode=0gVhzY"
      cfg=page.request.get(cfg_url,timeout=30000)
      item["nambuConfigStatus"]=cfg.status
      item["nambuConfigBody"]=cfg.text()[:12000]
      list_url="https://nambu.ice.go.kr/cms/json/board/getFrontBoardList.do?boardconfigidx=39&startnum=0&limitnum=30&searchdatestart=&searchdatelast=&searchtype=&searchtxt=&searchtype1=&searchtype2="
      listing=page.request.get(list_url,timeout=30000)
      item["nambuListStatus"]=listing.status
      raw_listing=listing.text()
      item["nambuListBody"]=raw_listing[:3000]
      try:
       parsed=json.loads(raw_listing)
       rows=parsed.get("resultData") or []
       item["nambuListSummary"]={
        "count":len(rows),
        "keys":sorted({k for row in rows[:5] if isinstance(row,dict) for k in row.keys()}),
        "rows":[{
          k:(clean(v)[:500] if not isinstance(v,(dict,list)) else v)
          for k,v in row.items()
          if k.lower() not in {"boardcontent","content","boardreply","boardattachfile"}
        } for row in rows[:5] if isinstance(row,dict)]
       }
      except Exception as exc:
       item["nambuListParseError"]=f"{type(exc).__name__}: {str(exc)[:300]}"
     except Exception as exc:
      item["errors"].append(f"nambu-config:{type(exc).__name__}:{str(exc)[:180]}")
    item["ok"]=bool(r and r.status<500)
   except Exception as e:
    item["errors"].append(f"{type(e).__name__}: {e}")
   finally:
    page.remove_listener("response",record)
    ctx.close()
   out["targets"].append(item)
  browser.close()
 Path("incheon_support_browser_diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False))
 for item in out.get("targets",[]):
  if item.get("key")=="nambu" and item.get("nambuListSummary"):
   print("NAMBU_SUMMARY "+json.dumps(item["nambuListSummary"],ensure_ascii=False))
  if item.get("key")=="seobu" and item.get("seobuSystemCaProbe"):
   print("SEOBU_SYSTEM_CA "+json.dumps(item["seobuSystemCaProbe"],ensure_ascii=False))
 return 0

if __name__=="__main__":
 raise SystemExit(main())
